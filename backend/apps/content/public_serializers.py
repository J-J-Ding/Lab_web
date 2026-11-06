from django.utils import timezone
from .models import DETAIL_MODELS


def asset_data(asset):
    if asset.scan_status!='CLEAN' or asset.visibility!='PUBLIC' or (asset.expires_at and asset.expires_at<=timezone.now()):return None
    return {'id':str(asset.pk),'mime_type':asset.mime_type,'size':asset.size,'url':f'/api/public/assets/{asset.pk}/'}


def member_data(profile):
    r=profile.published_revision
    result={'id':str(profile.pk),'slug':r.slug,'display_name':r.display_name,'bio':r.bio,
        'member_kind':r.member_kind,'public_member_status':r.public_member_status,
        'research_areas':[l.area.name for l in r.research_links.all()]}
    if profile.contact_visible and r.public_contact_enabled:result['public_contact_email']=r.public_contact_email
    if profile.education_visible:
        result['education']=[{f:getattr(e,f) for f in ('school','major','degree','start_date','end_date')} for e in r.education.all() if e.is_public]
    alumni=getattr(r,'alumni',None)
    if profile.alumni_visible and alumni and alumni.is_public:
        result['alumni']={f:getattr(alumni,f) for f in ('graduation_year','degree','destination_type','organization')}
    result['avatar']=asset_data(r.avatar_asset) if r.avatar_asset_id else None
    return result


def content_data(item):
    r=item.published_revision
    detail=getattr(r,DETAIL_MODELS[item.kind]._meta.get_field('revision').remote_field.related_name)
    # Explicit exclusion from the typed model; account/private tables are never traversed.
    data={f.name:getattr(detail,f.name) for f in detail._meta.fields if f.name not in ('revision','funding_amount')}
    # URL content is rendered only after a browser-side protocol check.
    people=[]
    for c in r.contributions.all():
        p=c.contributor.member_profile
        public=p and p.public_visible and p.merged_into_id is None and p.published_revision_id and p.published_revision.state=='PUBLISHED' and p.published_revision.public_member_status in ('ACTIVE','ALUMNI')
        people.append({'name':c.approved_display_name,'affiliation':c.approved_affiliation,'position':c.position,
            'role':c.contribution_role,'is_corresponding':c.is_corresponding,'member_slug':p.published_revision.slug if public else None})
    return {'id':str(item.pk),'kind':item.kind,'revision':str(r.pk),'title':r.title,'summary':r.summary,
        'date':item.public_date,'detail':data,'contributions':people,
        'projects':[{'id':str(l.target_project_id),'title':l.target_project.published_revision.title} for l in r.project_links.all()],
        'assets':[d for link in r.assets.all() if (d:=asset_data(link.asset))]}
