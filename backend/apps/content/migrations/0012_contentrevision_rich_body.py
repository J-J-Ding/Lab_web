from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies=[('content','0011_v12_patent_guards')]
    operations=[migrations.AddField(model_name='contentrevision',name='rich_body',field=models.JSONField(blank=True,null=True))]
