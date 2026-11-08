from django.core.management.base import BaseCommand
from apps.accounts.batch_imports import cleanup


class Command(BaseCommand):
    help='Purge expired encrypted account import payloads.'
    def handle(self,*args,**options):cleanup();self.stdout.write('Expired import payload cleanup complete.')
