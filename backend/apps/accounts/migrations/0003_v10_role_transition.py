from django.db import migrations
from django.db.models import F

def transition(apps, schema_editor):
    User=apps.get_model('accounts','User'); Audit=apps.get_model('accounts','AuthAuditLog')
    for user in User.objects.filter(role='ADMIN').iterator():
        Audit.objects.create(target_id=user.pk,target_snapshot=user.pk,action='user.role.v10',changed_fields=['role'],changes={'role':{'before':'ADMIN','after':'TEACHER'}})
    User.objects.filter(role='ADMIN').update(role='TEACHER')
    User.objects.all().update(session_version=F('session_version')+1)

class Migration(migrations.Migration):
    dependencies=[('accounts','0002_user_session_version_authauditlog_and_more')]
    operations=[migrations.RunPython(transition,migrations.RunPython.noop)]
