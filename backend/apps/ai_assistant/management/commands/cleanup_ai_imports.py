from django.core.management.base import BaseCommand
from apps.ai_assistant.retention import cleanup
class Command(BaseCommand):
    help='Preview AI source/candidate retention. --apply performs bounded cleanup; business drafts remain.'
    def add_arguments(self,p):p.add_argument('--apply',action='store_true')
    def handle(self,*args,**o):self.stdout.write(str(cleanup(apply=o['apply']))+'; mode='+('apply' if o['apply'] else 'dry-run'))
