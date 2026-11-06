"""Read-only stable-URL cover inventory; does not upload, bind or publish anything."""
import json
from pathlib import Path
from urllib.parse import unquote
from django.core.management.base import BaseCommand,CommandError
from apps.content.models import LegacyURLMap
from apps.content.public_serializers import cover_for_revision

class Command(BaseCommand):
    help='Read-only inventory of legacy cover files using existing URL-to-item mappings.'
    def add_arguments(self,parser):
        parser.add_argument('--root',required=True)
        parser.add_argument('--output',required=True)
    def handle(self,*args,**options):
        root=Path(options['root']).resolve();output=Path(options['output']).resolve()
        if not root.is_dir() or output.exists():raise CommandError('Use an existing legacy root and a new private output file.')
        rows=[];seen=set()
        for link in LegacyURLMap.objects.filter(item__isnull=False).select_related('item__published_revision'):
            relative=Path(unquote(link.path).lstrip('/'))
            if '..' in relative.parts:continue
            directory=(root/relative).parent.resolve()
            if not directory.is_relative_to(root) or not directory.is_dir():continue
            for file in directory.iterdir():
                if file.is_symlink() or not file.is_file() or not file.stem.startswith('封面') or file.suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):continue
                key=(str(link.item_id),str(file))
                if key in seen:continue
                seen.add(key);cover=cover_for_revision(link.item.published_revision)
                rows.append({'item_id':str(link.item_id),'legacy_path':link.path,'candidate':str(file.relative_to(root)),'has_current_cover':bool(cover),'action':'keep_existing' if cover else 'manual_upload_and_confirm_required'})
        output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        import os
        descriptor=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,'w') as handle:json.dump(rows,handle,ensure_ascii=False,indent=2)
        self.stdout.write(f'Read-only inventory: {len(rows)} candidates; no files uploaded, records edited or content published.')
