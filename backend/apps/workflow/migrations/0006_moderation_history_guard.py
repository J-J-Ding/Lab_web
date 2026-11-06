from django.db import migrations


class Migration(migrations.Migration):
    dependencies=[('workflow','0005_contentmoderationevent')]
    operations=[migrations.RunSQL('CREATE TRIGGER append_only_contentmoderationevent BEFORE UPDATE OR DELETE ON workflow_contentmoderationevent FOR EACH ROW EXECUTE FUNCTION lab_workflow_append_only();','DROP TRIGGER append_only_contentmoderationevent ON workflow_contentmoderationevent;')]
