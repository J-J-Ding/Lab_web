from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from apps.assets.models import AssetFile


class Command(BaseCommand):
    help='Report expired private files; --apply removes bytes while retaining audit metadata.'
    def add_arguments(self,parser):parser.add_argument('--apply',action='store_true')
    def handle(self,*args,**options):
        root=Path(settings.PRIVATE_MEDIA_ROOT).resolve();count=0
        for pk in AssetFile.objects.filter(visibility='PRIVATE',expires_at__lte=timezone.now(),scan_status='CLEAN').values_list('pk',flat=True).iterator():
            with transaction.atomic():
                asset=AssetFile.objects.select_for_update().get(pk=pk)
                # Never collect an avatar still referenced by a live/pending member version.
                if asset.resume_set.exists() or asset.ai_import_jobs.exists() or asset.memberrevision_set.exists() or asset.revisionasset_set.exists() or asset.memberrevisionasset_set.exists() or asset.membershipapplication_set.exists():continue
                target=(root/asset.storage_key).resolve()
                if target.parent!=root:continue
                count+=1
                if options['apply']:
                    target.unlink(missing_ok=True)
                    asset.scan_status='REJECTED';asset.save(update_fields=['scan_status'])
        self.stdout.write(f'Expired private files: {count}; mode={"apply" if options["apply"] else "dry-run"}.')
