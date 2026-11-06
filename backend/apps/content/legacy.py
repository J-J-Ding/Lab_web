"""Explicit reviewed manifest -> drafts. Never creates users, matches names, or publishes."""
import hashlib,json,re
from pathlib import Path,PurePosixPath
from urllib.parse import unquote
from django.db import transaction
from django.db.models import Max
from django.core.exceptions import ValidationError as ModelValidationError
from rest_framework.exceptions import ValidationError
from apps.accounts.permissions import is_manager
from apps.members.models import MemberRevision
from apps.members.services import create_unbound_profile
from apps.workflow.audit import record
from apps.workflow.models import RevisionEditEvent
from .models import ImportBatch,ImportRecord,LegacyURLMap,ContentRevision,DETAIL_MODELS
from .services import create_content,locked_editor
from .serializers import validate_detail


def canonical_path(value):
    if not isinstance(value,str) or len(value)>1000:raise ValueError('Invalid legacy path')
    decoded=unquote(value,errors='strict')
    if any(ord(c)<32 or ord(c)==127 for c in decoded) or '%' in decoded or '\\' in decoded or '?' in decoded or '#' in decoded or '\x00' in decoded or not decoded.startswith('/data/') or '//' in decoded:raise ValueError('Invalid legacy path')
    if any(p in ('.','..','') for p in decoded[1:].split('/')):raise ValueError('Invalid legacy path')
    if not decoded.endswith('/index.html'):raise ValueError('Only legacy HTML entries may be mapped')
    return decoded


def source_file(root,value,digest):
    if not isinstance(value,str) or PurePosixPath(value).is_absolute() or any(p.strip() in ('..','.','') for p in value.split('/')) or '\\' in value:raise ValueError('Invalid source path')
    path=root/value
    if any(p.is_symlink() for p in [path,*path.parents] if p!=root.parent):raise ValueError('Symlink source rejected')
    path=path.resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size>20*1024*1024:raise ValueError('Missing or oversized source')
    if not re.fullmatch('[0-9a-f]{64}',digest or '') or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Source hash mismatch')
    return path


def validate_row(row,root):
    if set(row)-{'source','sha256','kind','payload','legacy_paths','public_authorized','assets'}:raise ValueError('Unknown manifest field')
    source_file(root,row['source'],row['sha256'])
    if row.get('public_authorized') is not True:raise ValueError('Explicit public authorization required')
    paths=[canonical_path(p) for p in row.get('legacy_paths',[])]
    if not paths or len(paths)!=len(set(paths)):raise ValueError('Missing or duplicate legacy paths')
    payload=row['payload']
    if row['kind']=='MEMBER':
        allowed={'display_name','slug','member_kind','bio','public_member_status','alumni','education','research_areas'}
        if set(payload)-allowed or not payload.get('display_name') or not payload.get('slug'):raise ValueError('Invalid member candidate')
        candidate=MemberRevision(number=1,**{k:v for k,v in payload.items() if k not in ('alumni','education','research_areas')});candidate.clean_fields(exclude=['profile','base_published_revision','edited_by','avatar_asset'])
        from apps.members.serializers import DraftInput
        children=DraftInput(data={'lock_version':0,**{k:v for k,v in payload.items() if k in ('alumni','education','research_areas')}});children.is_valid(raise_exception=True)
    else:
        if row['kind'] not in DETAIL_MODELS or set(payload)-{'title','summary','detail'}:raise ValueError('Invalid content payload')
        if not isinstance(payload.get('title'),str) or not 1<=len(payload['title'].strip())<=500:raise ValueError('Invalid title')
        validate_detail(row['kind'],payload.get('detail',{}))
    for asset in row.get('assets',[]):
        if set(asset)!={'source','sha256','purpose','mime_type'} or asset['purpose'] not in ('avatar','image','attachment'):raise ValueError('Invalid asset descriptor')
        source_file(root,asset['source'],asset['sha256'])
    return paths


@transaction.atomic
def _import_row(actor,batch,row,root,new_files):
    batch=ImportBatch.objects.select_for_update().get(pk=batch.pk)
    actor=locked_editor(actor)
    if not is_manager(actor):raise ValueError('A management actor is required')
    paths=validate_row(row,root)
    digest=hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    existing=ImportRecord.objects.select_for_update().filter(batch=batch,source_path=row['source']).first()
    if existing and existing.status=='APPLIED':return existing,False
    mapped=list(LegacyURLMap.objects.select_for_update().filter(path__in=paths))
    targets={(m.item_id,m.member_id) for m in mapped}
    if len(targets)>1:raise ValueError('Legacy aliases point to conflicting targets')
    for link in mapped:
        if not ImportRecord.objects.filter(source_path=row['source'],item_id=link.item_id,member_id=link.member_id,status='APPLIED').exists():raise ValueError('Legacy alias belongs to a different source identity')
    previous=ImportRecord.objects.filter(source_path=row['source'],source_sha256=row['sha256'],payload_sha256=digest,status='APPLIED').first()
    item=previous.item if previous else None;profile=previous.member if previous else None
    changed=previous is None
    if changed:
        if row['kind']=='MEMBER':
            profile=mapped[0].member if mapped else create_unbound_profile(actor)
            if not profile or profile.user_id or profile.published_revision_id:raise ValueError('Member update needs explicit owner workflow')
            profile=type(profile).objects.select_for_update().get(pk=profile.pk)
            if profile.draft_revision_id:
                if profile.draft_revision.state!='DRAFT':raise ValueError('Member review in progress')
                MemberRevision.objects.filter(pk=profile.draft_revision_id).update(state='WITHDRAWN')
            number=(profile.revisions.aggregate(n=Max('number'))['n'] or 0)+1
            rev=MemberRevision.objects.create(profile=profile,number=number,edited_by=actor,**{k:v for k,v in row['payload'].items() if k not in ('alumni','education','research_areas')})
            from apps.members.serializers import DraftInput
            from apps.members.models import EducationEntry,AlumniDestination,ResearchArea,MemberResearchArea
            children=DraftInput(data={'lock_version':0,**{k:v for k,v in row['payload'].items() if k in ('alumni','education','research_areas')}});children.is_valid(raise_exception=True)
            for entry in children.validated_data.get('education',[]):EducationEntry.objects.create(revision=rev,**entry)
            if children.validated_data.get('alumni'):AlumniDestination.objects.create(revision=rev,**children.validated_data['alumni'])
            for pos,name in enumerate(children.validated_data.get('research_areas',[]),1):
                area,_=ResearchArea.objects.get_or_create(name=name);MemberResearchArea.objects.create(revision=rev,area=area,position=pos)
            profile.draft_revision=rev;profile.lock_version+=1;profile.save()
            RevisionEditEvent.objects.get_or_create(member_revision=rev,editor_snapshot=actor.pk,defaults={'editor':actor})
        else:
            item=mapped[0].item if mapped else None
            if item:
                item=type(item).objects.select_for_update().get(pk=item.pk)
                if item.kind!=row['kind']:raise ValueError('Existing content kind conflict')
                old=item.working_revision
                if old:
                    if old.state!='DRAFT':raise ValueError('Content review in progress')
                    ContentRevision.objects.filter(pk=old.pk).update(state='WITHDRAWN')
                values=validate_detail(item.kind,row['payload'].get('detail',{}))
                from apps.workflow.content_services import reserve_identifier
                reserve_identifier(item,values)
                number=(item.revisions.aggregate(n=Max('number'))['n'] or 0)+1
                rev=ContentRevision.objects.create(item=item,number=number,edited_by=actor,base_published_revision=item.published_revision,title=row['payload']['title'],summary=row['payload'].get('summary',''))
                DETAIL_MODELS[item.kind].objects.create(revision=rev,**values)
                item.working_revision=rev;item.last_edited_by=actor;item.lock_version+=1;item.save()
                RevisionEditEvent.objects.get_or_create(content_revision=rev,editor_snapshot=actor.pk,defaults={'editor':actor})
            else:
                payload=row['payload'];item=create_content(actor,row['kind'],payload['title'],payload.get('detail',{}),payload.get('summary',''));rev=item.working_revision
        if row.get('assets'):
            from types import SimpleNamespace
            from django.core.files.uploadedfile import SimpleUploadedFile
            from django.contrib.auth import HASH_SESSION_KEY
            from apps.accounts.services import SESSION_VERSION_KEY
            from apps.assets.services import upload
            from .models import RevisionAsset
            request=SimpleNamespace(user=actor,session={SESSION_VERSION_KEY:actor.session_version,HASH_SESSION_KEY:actor.get_session_auth_hash()})
            for index,descriptor in enumerate(row['assets'],1):
                source=source_file(root,descriptor['source'],descriptor['sha256'])
                if (profile and descriptor['purpose']!='avatar') or (item and descriptor['purpose']=='avatar'):raise ValueError('Asset purpose mismatch')
                asset=upload(request,SimpleUploadedFile(source.name,source.read_bytes(),content_type=descriptor['mime_type']),descriptor['purpose'])
                new_files.append(asset.storage_key)
                if profile:rev.avatar_asset=asset;rev.save(update_fields=['avatar_asset'])
                else:RevisionAsset.objects.create(revision=rev,asset=asset,purpose=descriptor['purpose'],position=index)
        record(actor,profile or item,'legacy.import.draft',('source_sha256',),rev)
    result,_=ImportRecord.objects.update_or_create(batch=batch,source_path=row['source'],defaults={'source_sha256':row['sha256'],'payload_sha256':digest,'kind':row['kind'],'status':'APPLIED','error':'','item':item,'member':profile})
    for path in paths:
        LegacyURLMap.objects.update_or_create(path=path,defaults={'item':item,'member':profile,'batch':batch,'source_sha256':row['sha256']})
    return result,changed


def import_row(actor,batch,row,root):
    from django.conf import settings
    new_files=[]
    try:return _import_row(actor,batch,row,root,new_files)
    except BaseException:
        media=Path(settings.PRIVATE_MEDIA_ROOT).resolve()
        for key in new_files:
            target=(media/key).resolve()
            if target.parent==media:target.unlink(missing_ok=True)
        raise
