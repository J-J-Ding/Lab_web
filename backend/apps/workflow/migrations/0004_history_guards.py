from django.db import migrations


def backfill(apps,schema_editor):
    Event=apps.get_model('workflow','RevisionEditEvent')
    Audit=apps.get_model('workflow','BusinessAuditLog')
    User=apps.get_model('accounts','User')
    for app,model,key,parent in [('content','ContentRevision','content_revision','item'),('members','MemberRevision','member_revision','profile')]:
        Revision=apps.get_model(app,model)
        for revision in Revision.objects.select_related(parent).iterator():
            editors=set(Audit.objects.filter(revision_id=revision.pk,action__in=['content.draft.create','content.draft.update','content.draft.clone','content.contributor.add','member.draft.create','member.draft.update']).exclude(actor_snapshot=None).values_list('actor_snapshot',flat=True))
            if revision.edited_by_id:editors.add(revision.edited_by_id)
            if revision.number==1:
                creator=getattr(revision,parent).created_by_id
                if creator:editors.add(creator)
            for pk in editors:
                Event.objects.get_or_create(**{key:revision,'editor_snapshot':pk},defaults={'editor_id':pk if User.objects.filter(pk=pk).exists() else None})


SQL=r'''
CREATE FUNCTION lab_workflow_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE before_row jsonb; after_row jsonb; column_name text;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Workflow history is append-only' USING ERRCODE='23514'; END IF;
 before_row:=to_jsonb(OLD); after_row:=to_jsonb(NEW);
 FOREACH column_name IN ARRAY ARRAY['actor_id','editor_id','reviewer_id','submitted_by_id'] LOOP
  IF before_row ? column_name AND after_row->column_name='null'::jsonb THEN
   before_row:=before_row-column_name; after_row:=after_row-column_name;
  END IF;
 END LOOP;
 IF before_row<>after_row THEN RAISE EXCEPTION 'Workflow history is immutable' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $$;
'''
for table in ['businessauditlog','revisioneditevent','revisionsubmission','reviewdecision','contributionconfirmation','memberpublicationconsent']:
    SQL+=f'CREATE TRIGGER append_only_{table} BEFORE UPDATE OR DELETE ON workflow_{table} FOR EACH ROW EXECUTE FUNCTION lab_workflow_append_only();\n'


class Migration(migrations.Migration):
    dependencies=[('workflow','0003_revisioneditevent_workflow_content_editor_unique_and_more'),('members','0004_memberrevision_base_published_revision')]
    operations=[migrations.RunPython(backfill,migrations.RunPython.noop),migrations.RunSQL(SQL,'DROP FUNCTION lab_workflow_append_only() CASCADE;')]
