import time
from pathlib import Path
from django.core.management.base import BaseCommand
from apps.content.batch_tasks import run_once


class Command(BaseCommand):
 def add_arguments(self,p):p.add_argument('--once',action='store_true')
 def handle(self,*args,**options):
  last=0
  while True:
   Path('/tmp/content-import-heartbeat').touch();worked=run_once();Path('/tmp/content-import-heartbeat').touch()
   if options['once']:return
   if time.monotonic()-last>60:
    from django.core.management import call_command
    call_command('cleanup_private_assets',apply=True);last=time.monotonic()
   if not worked:time.sleep(2)
