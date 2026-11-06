from django.db import migrations

SQL=r"""

CREATE OR REPLACE FUNCTION lab_member_graph(p uuid) RETURNS void LANGUAGE plpgsql AS $$
DECLARE obj members_memberprofile%ROWTYPE;
BEGIN
 SELECT * INTO obj FROM members_memberprofile WHERE id=p FOR UPDATE;
 IF NOT FOUND THEN RETURN; END IF;
 IF obj.published_revision_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM members_memberrevision WHERE id=obj.published_revision_id AND profile_id=p AND state='PUBLISHED') THEN RAISE EXCEPTION 'Invalid published member pointer' USING ERRCODE='23514'; END IF;
 IF obj.draft_revision_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM members_memberrevision WHERE id=obj.draft_revision_id AND profile_id=p AND state IN ('DRAFT','SUBMITTED','APPROVED')) THEN RAISE EXCEPTION 'Invalid member draft pointer' USING ERRCODE='23514'; END IF;
 IF obj.public_visible AND NOT EXISTS(SELECT 1 FROM members_memberrevision r JOIN members_memberslug s ON s.profile_id=p AND s.slug=r.slug WHERE r.id=obj.published_revision_id AND r.profile_id=p AND r.state='PUBLISHED' AND r.slug<>'') THEN RAISE EXCEPTION 'Public member slug must be reserved' USING ERRCODE='23514'; END IF;
 IF EXISTS(SELECT 1 FROM members_memberrevision r JOIN members_memberrevision b ON b.id=r.base_published_revision_id WHERE r.profile_id=p AND (b.profile_id<>p OR b.state<>'PUBLISHED')) THEN RAISE EXCEPTION 'Invalid member base revision' USING ERRCODE='23514'; END IF;
 IF obj.merged_into_id IS NOT NULL AND obj.user_id IS NOT NULL THEN RAISE EXCEPTION 'Merged profile cannot retain account binding' USING ERRCODE='23514'; END IF;
END; $$;
"""
REVERSE=r"""

CREATE OR REPLACE FUNCTION lab_member_graph(p uuid) RETURNS void LANGUAGE plpgsql AS $$
DECLARE obj members_memberprofile%ROWTYPE;
BEGIN
 SELECT * INTO obj FROM members_memberprofile WHERE id=p FOR UPDATE;
 IF NOT FOUND THEN RETURN; END IF;
 IF obj.published_revision_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM members_memberrevision WHERE id=obj.published_revision_id AND profile_id=p AND state='PUBLISHED') THEN RAISE EXCEPTION 'Invalid published member pointer' USING ERRCODE='23514'; END IF;
 IF obj.draft_revision_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM members_memberrevision WHERE id=obj.draft_revision_id AND profile_id=p AND state IN ('DRAFT','SUBMITTED','APPROVED')) THEN RAISE EXCEPTION 'Invalid member draft pointer' USING ERRCODE='23514'; END IF;
 IF obj.public_visible AND NOT EXISTS(SELECT 1 FROM members_memberrevision r JOIN members_memberslug s ON s.profile_id=p AND s.slug=r.slug WHERE r.id=obj.published_revision_id AND r.profile_id=p AND r.state='PUBLISHED' AND r.slug<>'') THEN RAISE EXCEPTION 'Public member slug must be reserved' USING ERRCODE='23514'; END IF;
 IF obj.merged_into_id IS NOT NULL AND obj.user_id IS NOT NULL THEN RAISE EXCEPTION 'Merged profile cannot retain account binding' USING ERRCODE='23514'; END IF;
END; $$;
"""

def backfill_drafts(apps,schema_editor):
    Revision=apps.get_model('members','MemberRevision')
    for revision in Revision.objects.filter(state='DRAFT',base_published_revision__isnull=True,profile__published_revision__isnull=False).select_related('profile').iterator():
        revision.base_published_revision_id=revision.profile.published_revision_id
        revision.save(update_fields=['base_published_revision'])


class Migration(migrations.Migration):
    dependencies=[("members","0004_memberrevision_base_published_revision")]
    operations=[migrations.RunSQL(SQL,REVERSE),migrations.RunPython(backfill_drafts,migrations.RunPython.noop)]
