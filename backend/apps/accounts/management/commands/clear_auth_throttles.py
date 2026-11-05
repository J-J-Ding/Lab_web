from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import LoginThrottleBucket


class Command(BaseCommand):
    help = 'Delete expired authentication throttle buckets; retains active counters.'

    def handle(self, *args, **options):
        with transaction.atomic():
            ids = list(LoginThrottleBucket.objects.select_for_update(skip_locked=True).filter(expires_at__lte=timezone.now()).values_list('pk', flat=True))
            count, _ = LoginThrottleBucket.objects.filter(pk__in=ids).delete()
        self.stdout.write(f'Deleted {count} expired authentication buckets.')
