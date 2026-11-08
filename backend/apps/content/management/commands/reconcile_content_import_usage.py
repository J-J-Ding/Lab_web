import hashlib
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from apps.content.models import ContentImportCall
from apps.content.batch_ai import settle
from apps.accounts.services import audit


class Command(BaseCommand):
 help='Reconcile UNKNOWN mixed-document billing from a verified provider bill. Never resends requests.'
 def add_arguments(self,p):
  p.add_argument('--call',type=int,required=True);p.add_argument('--input-tokens',type=int,default=0);p.add_argument('--output-tokens',type=int,default=0);p.add_argument('--not-billed',action='store_true');p.add_argument('--reason',required=True)
 def handle(self,*args,**o):
  if not o['reason'].strip() or not 0<=o['input_tokens']<=24000 or not 0<=o['output_tokens']<=4000 or (o['not_billed'] and (o['input_tokens'] or o['output_tokens'])):raise CommandError('Invalid verified usage or reason.')
  with transaction.atomic():
   c=ContentImportCall.objects.select_for_update().get(pk=o['call'])
   if c.state!='UNKNOWN':raise CommandError('Only UNKNOWN calls can be reconciled.')
   settle(c.pk,o['input_tokens'],o['output_tokens'],release=o['not_billed'],reconcile=True)
   audit('content_import.reconciled',changes={'call':c.pk,'reason_digest':hashlib.sha256(o['reason'].encode()).hexdigest()})
  self.stdout.write('Verified usage reconciled; no model request sent.')
