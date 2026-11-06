from django.db import migrations

def forwards(apps,schema_editor):
    Asset=apps.get_model('assets','AssetFile')
    # V5 supported only avatar images and private PDF proofs.
    Asset.objects.filter(mime_type__in=['image/png','image/jpeg','image/webp']).update(purpose='avatar')
    Profile=apps.get_model('members','MemberProfile')
    from django.utils import timezone
    from django.db.models import Q
    current=Profile.objects.filter(public_visible=True,merged_into__isnull=True,published_revision__state='PUBLISHED',published_revision__public_member_status__in=['ACTIVE','ALUMNI']).values_list('published_revision__avatar_asset_id',flat=True)
    Asset.objects.filter(pk__in=current,purpose='avatar',scan_status='CLEAN').filter(Q(expires_at__isnull=True)|Q(expires_at__gt=timezone.now())).update(visibility='PUBLIC')

class Migration(migrations.Migration):
    dependencies=[('assets','0002_assetfile_deletion_requested_at_assetfile_purpose'),('members','0005_profile_baseline_guard')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
