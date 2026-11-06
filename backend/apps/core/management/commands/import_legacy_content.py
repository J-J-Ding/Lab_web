import hashlib,json,os,uuid
from pathlib import Path
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from apps.accounts.models import User
from apps.accounts.permissions import is_manager
from apps.content.models import ImportBatch,ImportRecord
from apps.content.legacy import validate_row,import_row,canonical_path

class Command(BaseCommand):
    help='Validate reviewed source manifest; --apply creates drafts only, never users/publication.'
    def add_arguments(self,p):
        p.add_argument('--manifest',required=True);p.add_argument('--source-root',required=True);p.add_argument('--report',required=True)
        mode=p.add_mutually_exclusive_group(required=True);mode.add_argument('--dry-run',action='store_true');mode.add_argument('--apply',action='store_true')
        p.add_argument('--batch-id');p.add_argument('--actor',type=int)
    def handle(self,*args,**o):
        try:
            raw=Path(o['manifest']).read_bytes()
            if len(raw)>5*1024*1024:raise ValueError('Manifest too large')
            data=json.loads(raw);root=Path(o['source_root']).resolve(strict=True)
            if set(data)!={'version','records'} or data['version']!=1 or len(data['records'])>10000:raise ValueError('Invalid manifest')
            sources=[r['source'] for r in data['records']]
            if len(sources)!=len(set(sources)):raise ValueError('Duplicate source records')
            aliases=[]
            for row in data['records']:
                for path in row.get('legacy_paths',[]):
                    try:aliases.append(canonical_path(path))
                    except (ValueError,UnicodeError):pass  # Per-row validation writes its private error report.
            if len(aliases)!=len(set(aliases)):raise ValueError('Legacy URL collision across manifest records')
            actor=User.objects.filter(pk=o['actor'],is_active=True).first() if o['apply'] else None
            digest=hashlib.sha256(raw).hexdigest();batch=None
            if o['apply']:
                if not actor or not is_manager(actor) or not o['batch_id']:raise ValueError('Apply requires a current management actor and reviewed batch UUID')
                batch,created=ImportBatch.objects.get_or_create(pk=uuid.UUID(o['batch_id']),defaults={'actor':actor,'manifest_sha256':digest})
                if batch.manifest_sha256!=digest:raise ValueError('Batch manifest changed; review a new batch')
        except Exception as exc:raise CommandError('Manifest/setup invalid: '+str(exc)) from None
        report={'batch_id':str(batch.pk) if batch else None,'dry_run':o['dry_run'],'records':[]}
        for row in data['records']:
            entry={'source':row.get('source'),'sha256':row.get('sha256'),'kind':row.get('kind')}
            try:
                validate_row(row,root)
                if batch:
                    result,changed=import_row(actor,batch,row,root)
                    entry.update(status='APPLIED',created=changed,target=str(result.item_id or result.member_id))
                else:entry.update(status='VALID',created=False)
            except Exception as exc:
                entry.update(status='ERROR',error=type(exc).__name__+': '+str(exc)[:1500])
                if batch:
                    ImportRecord.objects.update_or_create(batch=batch,source_path=row.get('source','')[:1000],defaults={'source_sha256':row.get('sha256','')[:64],'payload_sha256':'','kind':row.get('kind','')[:12],'status':'ERROR','error':entry['error']})
            report['records'].append(entry)
        target=Path(o['report']);target.parent.mkdir(parents=True,exist_ok=True)
        # Report contains private migration details; no symlink overwrite.
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as f:json.dump(report,f,ensure_ascii=False,indent=2)
        os.chmod(target,0o600)
        errors=sum(r['status']=='ERROR' for r in report['records'])
        self.stdout.write(f'Records={len(report["records"])} errors={errors}; report saved privately. No publication performed.')

        if errors:raise CommandError(f'{errors} records failed; inspect private report before retrying.')
