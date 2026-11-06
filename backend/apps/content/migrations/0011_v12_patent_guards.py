from importlib import import_module
from django.db import migrations

base=import_module('apps.content.migrations.0002_graph_guards').SQL
old_graph=base[:base.index('CREATE FUNCTION lab_content_kind_immutable')]
new_graph=old_graph.replace('CREATE FUNCTION','CREATE OR REPLACE FUNCTION',1).replace('(SELECT count(*) FROM content_paperdetail', '(SELECT count(*) FROM content_patentdetail WHERE revision_id=r.id)+(SELECT count(*) FROM content_paperdetail',1).replace(" WHEN 'PAPER' THEN", " WHEN 'PATENT' THEN SELECT count(*) INTO correct FROM content_patentdetail WHERE revision_id=r.id;\n WHEN 'PAPER' THEN",1).replace(" (obj.kind='PAPER'", " (obj.kind='PATENT' AND c.contribution_role='INVENTOR') OR\n (obj.kind='PAPER'",1)
sort=import_module('apps.content.migrations.0006_public_sort_trigger').SQL
sort=sort[:sort.index('CREATE TRIGGER')].replace('CREATE FUNCTION','CREATE OR REPLACE FUNCTION',1)
new_sort=sort.replace("  WHEN 'PAPER' THEN", "  WHEN 'PATENT' THEN SELECT COALESCE(grant_date,application_date) INTO d FROM content_patentdetail WHERE revision_id=NEW.published_revision_id;\n  WHEN 'PAPER' THEN",1)
extra="""
CREATE CONSTRAINT TRIGGER graph_content_patentdetail AFTER INSERT OR UPDATE OR DELETE ON content_patentdetail DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lab_content_event('revision_id');
CREATE TRIGGER frozen_content_patentdetail BEFORE INSERT OR UPDATE OR DELETE ON content_patentdetail FOR EACH ROW EXECUTE FUNCTION lab_frozen_child('content_contentrevision','revision_id');
"""

class Migration(migrations.Migration):
    dependencies=[('content','0010_v12_deleted_patent_contact')]
    operations=[migrations.RunSQL(new_graph+new_sort+extra, "DROP TRIGGER graph_content_patentdetail ON content_patentdetail; DROP TRIGGER frozen_content_patentdetail ON content_patentdetail;"+old_graph.replace('CREATE FUNCTION','CREATE OR REPLACE FUNCTION',1)+sort)]
