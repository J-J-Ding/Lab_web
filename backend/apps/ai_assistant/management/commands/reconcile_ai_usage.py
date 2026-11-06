from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from apps.ai_assistant.models import AIImportJob
from apps.ai_assistant.quota import settle
class Command(BaseCommand):
    help='Server-only reconciliation after checking provider usage; never retries a billed request.'
    def add_arguments(self,p):
        p.add_argument('--actor',required=True,type=int);p.add_argument('--job',required=True);p.add_argument('--input-tokens',required=True,type=int);p.add_argument('--output-tokens',required=True,type=int);p.add_argument('--reason',required=True)
    def handle(self,*args,**o):
        if min(o['input_tokens'],o['output_tokens'])<0 or not 1<=len(o['reason'])<=500:raise CommandError('Invalid reconciliation values')
        with transaction.atomic():
            from apps.accounts.models import User
            actor=User.objects.select_for_update().filter(pk=o['actor'],is_active=True,is_superuser=True).first()
            if not actor:raise CommandError('An active ROOT actor is required')
            job=AIImportJob.objects.select_for_update().get(pk=o['job'])
            if job.usage.state!='UNKNOWN':raise CommandError('Only UNKNOWN usage may be reconciled')
            settle(job,o['input_tokens'],o['output_tokens'])
            from apps.workflow.audit import record
            import hashlib
            ledger=job.usage;ledger.refresh_from_db();ledger.reconciliation_reason_digest=hashlib.sha256(o['reason'].encode()).hexdigest();ledger.save(update_fields=['reconciliation_reason_digest'])
            record(actor,job,'ai.usage.reconciled',('input_tokens','output_tokens','reconciliation_reason_digest'))
        self.stdout.write('Reconciled. No provider request sent.')
