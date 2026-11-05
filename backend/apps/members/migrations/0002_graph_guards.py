from django.db import migrations

SQL = r"""
CREATE FUNCTION lab_member_graph(p uuid) RETURNS void LANGUAGE plpgsql AS $$
DECLARE obj members_memberprofile%ROWTYPE;
BEGIN
 SELECT * INTO obj FROM members_memberprofile WHERE id=p FOR UPDATE;
 IF NOT FOUND THEN RETURN; END IF;
 IF obj.published_revision_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM members_memberrevision WHERE id=obj.published_revision_id AND profile_id=p AND state='PUBLISHED') THEN RAISE EXCEPTION 'Invalid published member pointer' USING ERRCODE='23514'; END IF;
 IF obj.draft_revision_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM members_memberrevision WHERE id=obj.draft_revision_id AND profile_id=p AND state IN ('DRAFT','SUBMITTED','APPROVED')) THEN RAISE EXCEPTION 'Invalid member draft pointer' USING ERRCODE='23514'; END IF;
 IF obj.public_visible AND NOT EXISTS(SELECT 1 FROM members_memberrevision r JOIN members_memberslug s ON s.profile_id=p AND s.slug=r.slug WHERE r.id=obj.published_revision_id AND r.profile_id=p AND r.state='PUBLISHED' AND r.slug<>'') THEN RAISE EXCEPTION 'Public member slug must be reserved' USING ERRCODE='23514'; END IF;
 IF obj.merged_into_id IS NOT NULL AND obj.user_id IS NOT NULL THEN RAISE EXCEPTION 'Merged profile cannot retain account binding' USING ERRCODE='23514'; END IF;
END; $$;
CREATE FUNCTION lab_member_event() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_TABLE_NAME='members_memberprofile' THEN
  IF TG_OP<>'INSERT' THEN PERFORM lab_member_graph(OLD.id); END IF;
  IF TG_OP<>'DELETE' THEN PERFORM lab_member_graph(NEW.id); END IF;
 ELSE
  IF TG_OP<>'INSERT' THEN PERFORM lab_member_graph(OLD.profile_id); END IF;
  IF TG_OP<>'DELETE' THEN PERFORM lab_member_graph(NEW.profile_id); END IF;
 END IF;
 RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER graph_member_profile AFTER INSERT OR UPDATE OR DELETE ON members_memberprofile DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lab_member_event();
CREATE CONSTRAINT TRIGGER graph_member_revision AFTER INSERT OR UPDATE OR DELETE ON members_memberrevision DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lab_member_event();
CREATE CONSTRAINT TRIGGER graph_member_slug AFTER INSERT OR UPDATE OR DELETE ON members_memberslug DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lab_member_event();
CREATE FUNCTION lab_research_term_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.name IS DISTINCT FROM OLD.name THEN RAISE EXCEPTION 'Create a new canonical research term instead of renaming' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER research_term_immutable BEFORE UPDATE ON members_researcharea FOR EACH ROW EXECUTE FUNCTION lab_research_term_immutable();
CREATE TRIGGER frozen_member_revision BEFORE UPDATE OR DELETE ON members_memberrevision FOR EACH ROW EXECUTE FUNCTION lab_frozen_revision();
CREATE TRIGGER frozen_members_educationentry BEFORE INSERT OR UPDATE OR DELETE ON members_educationentry FOR EACH ROW EXECUTE FUNCTION lab_frozen_child('members_memberrevision','revision_id');
CREATE TRIGGER frozen_members_memberresearcharea BEFORE INSERT OR UPDATE OR DELETE ON members_memberresearcharea FOR EACH ROW EXECUTE FUNCTION lab_frozen_child('members_memberrevision','revision_id');
CREATE TRIGGER frozen_members_alumnidestination BEFORE INSERT OR UPDATE OR DELETE ON members_alumnidestination FOR EACH ROW EXECUTE FUNCTION lab_frozen_child('members_memberrevision','revision_id');
CREATE TRIGGER frozen_members_memberrevisionasset BEFORE INSERT OR UPDATE OR DELETE ON members_memberrevisionasset FOR EACH ROW EXECUTE FUNCTION lab_frozen_child('members_memberrevision','revision_id');
"""

class Migration(migrations.Migration):
    dependencies = [("members", "0001_initial"), ("content", "0002_graph_guards")]
    operations = [migrations.RunSQL(SQL, 'DROP FUNCTION lab_research_term_immutable() CASCADE; DROP TRIGGER frozen_member_revision ON members_memberrevision;\nDROP TRIGGER frozen_members_educationentry ON members_educationentry;\nDROP TRIGGER frozen_members_memberresearcharea ON members_memberresearcharea;\nDROP TRIGGER frozen_members_alumnidestination ON members_alumnidestination;\nDROP TRIGGER frozen_members_memberrevisionasset ON members_memberrevisionasset;\nDROP FUNCTION lab_member_event() CASCADE; DROP FUNCTION lab_member_graph(uuid) CASCADE;')]
