import time
from django.core.management.base import BaseCommand
from apps.ai_assistant.tasks import run_once

class Command(BaseCommand):
    help='Claim bounded PostgreSQL AI jobs; no inbound ports.'
    def add_arguments(self,p):p.add_argument('--once',action='store_true');p.add_argument('--idle-seconds',type=int,default=2)
    def handle(self,*args,**o):
        last_cleanup=0
        while True:
            from pathlib import Path
            Path('/tmp/lab-ai-worker-heartbeat').touch()
            worked=run_once()
            if o['once']:self.stdout.write('Processed one job.' if worked else 'No runnable job.');return
            if time.monotonic()-last_cleanup>60:
                from apps.ai_assistant.retention import cleanup
                cleanup(apply=True);last_cleanup=time.monotonic()
            if not worked:time.sleep(min(max(o['idle_seconds'],1),30))
