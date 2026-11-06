from django.core.management.base import BaseCommand,CommandError
from apps.content.models import ImportBatch,LegacyURLMap

class Command(BaseCommand):
    def add_arguments(self,p):p.add_argument('--batch-id',required=True)
    def handle(self,*args,**o):
        batch=ImportBatch.objects.get(pk=o['batch_id']);fail=[]
        for r in batch.records.select_related('item','member'):
            if r.status!='APPLIED' or not (r.item_id or r.member_id):fail.append(str(r.pk));continue
            maps=LegacyURLMap.objects.filter(item_id=r.item_id,member_id=r.member_id)
            if not maps.exists():fail.append(str(r.pk))
        if fail:raise CommandError(f'Import verification failed: {len(fail)} records')
        self.stdout.write(f'PASS: {batch.records.count()} records, targets and aliases consistent. Publication requires independent V5 review.')
