import time
from pathlib import Path
from django.core.management.base import BaseCommand
from apps.accounts.batch_imports import process_one


class Command(BaseCommand):
    help='Process confirmed account imports without putting password hashing in HTTP requests.'
    def add_arguments(self,parser):parser.add_argument('--once',action='store_true')
    def handle(self,*args,**options):
        while True:
            Path('/tmp/account-import-heartbeat').touch()
            processed=process_one()
            Path('/tmp/account-import-heartbeat').touch()
            if options['once']:return
            if not processed:time.sleep(2)
