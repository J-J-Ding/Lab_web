from django.db import migrations

SQL = r"""
CREATE FUNCTION lab_content_graph(p uuid) RETURNS void LANGUAGE plpgsql AS $$
DECLARE obj content_contentitem%ROWTYPE; r record; total integer; correct integer;
BEGIN
 SELECT * INTO obj FROM content_contentitem WHERE id=p FOR UPDATE;
 IF NOT FOUND THEN RETURN; END IF;
 IF obj.published_revision_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM content_contentrevision WHERE id=obj.published_revision_id AND item_id=p AND state='PUBLISHED') THEN
  RAISE EXCEPTION 'Invalid published content pointer' USING ERRCODE='23514'; END IF;
 IF obj.working_revision_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM content_contentrevision WHERE id=obj.working_revision_id AND item_id=p AND state IN ('DRAFT','SUBMITTED','APPROVED')) THEN
  RAISE EXCEPTION 'Invalid working content pointer' USING ERRCODE='23514'; END IF;
 FOR r IN SELECT * FROM content_contentrevision WHERE item_id=p LOOP
 SELECT (SELECT count(*) FROM content_paperdetail WHERE revision_id=r.id)+(SELECT count(*) FROM content_projectdetail WHERE revision_id=r.id)+(SELECT count(*) FROM content_awarddetail WHERE revision_id=r.id)+(SELECT count(*) FROM content_activitydetail WHERE revision_id=r.id)+(SELECT count(*) FROM content_newsdetail WHERE revision_id=r.id)+(SELECT count(*) FROM content_blogdetail WHERE revision_id=r.id)+(SELECT count(*) FROM content_publicationdetail WHERE revision_id=r.id)+(SELECT count(*) FROM content_labpagedetail WHERE revision_id=r.id) INTO total;
 CASE obj.kind
 WHEN 'PAPER' THEN SELECT count(*) INTO correct FROM content_paperdetail WHERE revision_id=r.id;
 WHEN 'PROJECT' THEN SELECT count(*) INTO correct FROM content_projectdetail WHERE revision_id=r.id;
 WHEN 'AWARD' THEN SELECT count(*) INTO correct FROM content_awarddetail WHERE revision_id=r.id;
 WHEN 'ACTIVITY' THEN SELECT count(*) INTO correct FROM content_activitydetail WHERE revision_id=r.id;
 WHEN 'NEWS' THEN SELECT count(*) INTO correct FROM content_newsdetail WHERE revision_id=r.id;
 WHEN 'BLOG' THEN SELECT count(*) INTO correct FROM content_blogdetail WHERE revision_id=r.id;
 WHEN 'PUBLICATION' THEN SELECT count(*) INTO correct FROM content_publicationdetail WHERE revision_id=r.id;
 WHEN 'LAB_PAGE' THEN SELECT count(*) INTO correct FROM content_labpagedetail WHERE revision_id=r.id;
 ELSE correct:=0; END CASE;
 IF total<>1 OR correct<>1 THEN RAISE EXCEPTION 'Content revision must have exactly one matching detail' USING ERRCODE='23514'; END IF;
 IF r.base_published_revision_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM content_contentrevision WHERE id=r.base_published_revision_id AND item_id=p AND state='PUBLISHED') THEN RAISE EXCEPTION 'Invalid base revision' USING ERRCODE='23514'; END IF;
 IF EXISTS(SELECT 1 FROM content_revisioncontribution c WHERE c.revision_id=r.id AND NOT (
 (obj.kind='PAPER' AND c.contribution_role='AUTHOR') OR
 (obj.kind='PROJECT' AND c.contribution_role IN ('LEAD','PARTICIPANT')) OR
 (obj.kind='AWARD' AND c.contribution_role IN ('WINNER','ADVISOR')) OR
 (obj.kind='ACTIVITY' AND c.contribution_role IN ('ORGANIZER','PARTICIPANT')) OR
 (obj.kind IN ('NEWS','BLOG') AND c.contribution_role='AUTHOR') OR
 (obj.kind='PUBLICATION' AND c.contribution_role IN ('AUTHOR','EDITOR')))) THEN
 RAISE EXCEPTION 'Invalid contribution role' USING ERRCODE='23514'; END IF;
 IF EXISTS(SELECT 1 FROM content_contentprojectlink l JOIN content_contentitem target ON target.id=l.target_project_id WHERE l.source_revision_id=r.id AND (target.kind<>'PROJECT' OR target.id=p)) THEN RAISE EXCEPTION 'Invalid target project' USING ERRCODE='23514'; END IF;
 END LOOP;
 IF EXISTS(SELECT 1 FROM content_paperdetail d JOIN content_contentrevision v ON v.id=d.revision_id WHERE v.item_id=p AND d.doi<>'' AND NOT EXISTS(SELECT 1 FROM content_contentidentifier i WHERE i.item_id=p AND i.scheme='DOI' AND i.value=d.doi)) OR
 EXISTS(SELECT 1 FROM content_projectdetail d JOIN content_contentrevision v ON v.id=d.revision_id WHERE v.item_id=p AND d.project_number<>'' AND NOT EXISTS(SELECT 1 FROM content_contentidentifier i WHERE i.item_id=p AND i.scheme='PROJECT' AND i.value=d.project_number)) OR
 EXISTS(SELECT 1 FROM content_publicationdetail d JOIN content_contentrevision v ON v.id=d.revision_id WHERE v.item_id=p AND d.isbn<>'' AND NOT EXISTS(SELECT 1 FROM content_contentidentifier i WHERE i.item_id=p AND i.scheme='ISBN' AND i.value=d.isbn)) OR
 EXISTS(SELECT 1 FROM content_labpagedetail d JOIN content_contentrevision v ON v.id=d.revision_id WHERE v.item_id=p AND NOT EXISTS(SELECT 1 FROM content_contentidentifier i WHERE i.item_id=p AND i.scheme='PAGE' AND i.value=d.page_key)) THEN
 RAISE EXCEPTION 'Detail identifier requires a canonical reservation' USING ERRCODE='23514'; END IF;
 IF EXISTS(SELECT 1 FROM content_contentidentifier i WHERE i.item_id=p AND NOT (
 (obj.kind='PAPER' AND i.scheme='DOI') OR (obj.kind='PROJECT' AND i.scheme='PROJECT') OR
 (obj.kind='PUBLICATION' AND i.scheme='ISBN') OR (obj.kind='LAB_PAGE' AND i.scheme='PAGE'))) THEN RAISE EXCEPTION 'Identifier kind mismatch' USING ERRCODE='23514'; END IF;
END; $$;
CREATE FUNCTION lab_content_kind_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.kind IS DISTINCT FROM OLD.kind THEN RAISE EXCEPTION 'Stable content kind cannot change' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER immutable_content_kind BEFORE UPDATE ON content_contentitem FOR EACH ROW EXECUTE FUNCTION lab_content_kind_immutable();
CREATE FUNCTION lab_content_event() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE old_item uuid; new_item uuid;
BEGIN
 IF TG_TABLE_NAME='content_contentitem' THEN
  IF TG_OP<>'INSERT' THEN old_item:=OLD.id; END IF;
  IF TG_OP<>'DELETE' THEN new_item:=NEW.id; END IF;
 ELSIF TG_TABLE_NAME IN ('content_contentrevision','content_contentidentifier') THEN
  IF TG_OP<>'INSERT' THEN old_item:=OLD.item_id; END IF;
  IF TG_OP<>'DELETE' THEN new_item:=NEW.item_id; END IF;
 ELSE
  IF TG_OP<>'INSERT' THEN SELECT item_id INTO old_item FROM content_contentrevision WHERE id=(to_jsonb(OLD)->>TG_ARGV[0])::uuid; END IF;
  IF TG_OP<>'DELETE' THEN SELECT item_id INTO new_item FROM content_contentrevision WHERE id=(to_jsonb(NEW)->>TG_ARGV[0])::uuid; END IF;
 END IF;
 IF old_item IS NOT NULL THEN PERFORM lab_content_graph(old_item); END IF;
 IF new_item IS NOT NULL AND new_item IS DISTINCT FROM old_item THEN PERFORM lab_content_graph(new_item); END IF;
 RETURN NULL;
END; $$;
CREATE FUNCTION lab_frozen_revision() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.state<>'DRAFT' THEN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Submitted snapshots cannot be deleted' USING ERRCODE='23514'; END IF;
  IF (to_jsonb(NEW)-'state')=(to_jsonb(OLD)-'state') AND (
   (OLD.state='SUBMITTED' AND NEW.state IN ('APPROVED','PUBLISHED','REJECTED','WITHDRAWN')) OR
   (OLD.state='APPROVED' AND NEW.state='PUBLISHED')) THEN RETURN NEW; END IF;
  IF NEW.edited_by_id IS NULL AND (to_jsonb(NEW)-'edited_by_id')=(to_jsonb(OLD)-'edited_by_id') THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'Submitted snapshots are immutable' USING ERRCODE='23514';
 END IF;
 RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END; $$;
CREATE FUNCTION lab_frozen_child() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE rid uuid; rev_state text;
BEGIN
 IF TG_OP<>'INSERT' THEN
  rid:=(to_jsonb(OLD)->>TG_ARGV[1])::uuid;
  EXECUTE format('SELECT state FROM %I WHERE id=$1 FOR SHARE',TG_ARGV[0]) INTO rev_state USING rid;
  IF rev_state<>'DRAFT' THEN RAISE EXCEPTION 'Submitted snapshot children are immutable' USING ERRCODE='23514'; END IF;
 END IF;
 IF TG_OP<>'DELETE' THEN
  rid:=(to_jsonb(NEW)->>TG_ARGV[1])::uuid;
  EXECUTE format('SELECT state FROM %I WHERE id=$1 FOR SHARE',TG_ARGV[0]) INTO rev_state USING rid;
  IF rev_state<>'DRAFT' THEN RAISE EXCEPTION 'Submitted snapshot children are immutable' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END; $$;
CREATE FUNCTION lab_canonical_identifier(scheme text, value text) RETURNS boolean LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE i integer; score integer:=0; digit integer;
BEGIN
 IF scheme='DOI' THEN RETURN value=lower(value) AND value !~ '\s' AND value ~ '^10\.[0-9]{4,9}/[^[:space:]]+$'; END IF;
 IF scheme='PROJECT' THEN RETURN value<>'' AND value=upper(value) AND value !~ '\s'; END IF;
 IF scheme='PAGE' THEN RETURN value IN ('home','about'); END IF;
 IF scheme='ISBN' THEN
  IF value ~ '^[0-9]{13}$' THEN
   FOR i IN 1..13 LOOP score:=score+substr(value,i,1)::integer*CASE WHEN i%2=1 THEN 1 ELSE 3 END; END LOOP;
   RETURN score%10=0;
  ELSIF value ~ '^[0-9]{9}[0-9X]$' THEN
   FOR i IN 1..10 LOOP digit:=CASE WHEN substr(value,i,1)='X' THEN 10 ELSE substr(value,i,1)::integer END; score:=score+(11-i)*digit; END LOOP;
   RETURN score%11=0;
  END IF;
 END IF;
 RETURN FALSE;
END; $$;
CREATE FUNCTION lab_identifier_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT lab_canonical_identifier(NEW.scheme,NEW.value) THEN RAISE EXCEPTION 'Identifier must be canonical and valid' USING ERRCODE='23514'; END IF;
 IF TG_OP='UPDATE' AND (NEW.item_id IS DISTINCT FROM OLD.item_id OR NEW.scheme IS DISTINCT FROM OLD.scheme OR NEW.value IS DISTINCT FROM OLD.value) THEN RAISE EXCEPTION 'Identifier reservations cannot be reassigned' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER canonical_identifier BEFORE INSERT OR UPDATE ON content_contentidentifier FOR EACH ROW EXECUTE FUNCTION lab_identifier_guard();
CREATE CONSTRAINT TRIGGER graph_content_contentitem AFTER INSERT OR UPDATE OR DELETE ON content_contentitem DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lab_content_event('');
CREATE CONSTRAINT TRIGGER graph_content_contentrevision AFTER INSERT OR UPDATE OR DELETE ON content_contentrevision DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lab_content_event('');
CREATE CONSTRAINT TRIGGER graph_content_contentidentifier AFTER INSERT OR UPDATE OR DELETE ON content_contentidentifier DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lab_content_event('');
CREATE CONSTRAINT TRIGGER graph_content_paperdetail AFTER INSERT OR UPDATE OR DELETE ON content_paperdetail DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lab_content_event('revision_id');
CREATE CONSTRAINT TRIGGER graph_content_projectdetail AFTER INSERT OR UPDATE OR DELETE ON content_projectdetail DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lab_content_event('revision_id');
CREATE CONSTRAINT TRIGGER graph_content_awarddetail AFTER INSERT OR UPDATE OR DELETE ON content_awarddetail DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lab_content_event('revision_id');
CREATE CONSTRAINT TRIGGER graph_content_activitydetail AFTER INSERT OR UPDATE OR DELETE ON content_activitydetail DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lab_content_event('revision_id');
CREATE CONSTRAINT TRIGGER graph_content_newsdetail AFTER INSERT OR UPDATE OR DELETE ON content_newsdetail DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lab_content_event('revision_id');
CREATE CONSTRAINT TRIGGER graph_content_blogdetail AFTER INSERT OR UPDATE OR DELETE ON content_blogdetail DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lab_content_event('revision_id');
CREATE CONSTRAINT TRIGGER graph_content_publicationdetail AFTER INSERT OR UPDATE OR DELETE ON content_publicationdetail DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lab_content_event('revision_id');
CREATE CONSTRAINT TRIGGER graph_content_labpagedetail AFTER INSERT OR UPDATE OR DELETE ON content_labpagedetail DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lab_content_event('revision_id');
CREATE CONSTRAINT TRIGGER graph_content_revisioncontribution AFTER INSERT OR UPDATE OR DELETE ON content_revisioncontribution DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lab_content_event('revision_id');
CREATE CONSTRAINT TRIGGER graph_content_contentprojectlink AFTER INSERT OR UPDATE OR DELETE ON content_contentprojectlink DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lab_content_event('source_revision_id');
CREATE CONSTRAINT TRIGGER graph_content_revisionasset AFTER INSERT OR UPDATE OR DELETE ON content_revisionasset DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lab_content_event('revision_id');
CREATE TRIGGER frozen_content_paperdetail BEFORE INSERT OR UPDATE OR DELETE ON content_paperdetail FOR EACH ROW EXECUTE FUNCTION lab_frozen_child('content_contentrevision','revision_id');
CREATE TRIGGER frozen_content_projectdetail BEFORE INSERT OR UPDATE OR DELETE ON content_projectdetail FOR EACH ROW EXECUTE FUNCTION lab_frozen_child('content_contentrevision','revision_id');
CREATE TRIGGER frozen_content_awarddetail BEFORE INSERT OR UPDATE OR DELETE ON content_awarddetail FOR EACH ROW EXECUTE FUNCTION lab_frozen_child('content_contentrevision','revision_id');
CREATE TRIGGER frozen_content_activitydetail BEFORE INSERT OR UPDATE OR DELETE ON content_activitydetail FOR EACH ROW EXECUTE FUNCTION lab_frozen_child('content_contentrevision','revision_id');
CREATE TRIGGER frozen_content_newsdetail BEFORE INSERT OR UPDATE OR DELETE ON content_newsdetail FOR EACH ROW EXECUTE FUNCTION lab_frozen_child('content_contentrevision','revision_id');
CREATE TRIGGER frozen_content_blogdetail BEFORE INSERT OR UPDATE OR DELETE ON content_blogdetail FOR EACH ROW EXECUTE FUNCTION lab_frozen_child('content_contentrevision','revision_id');
CREATE TRIGGER frozen_content_publicationdetail BEFORE INSERT OR UPDATE OR DELETE ON content_publicationdetail FOR EACH ROW EXECUTE FUNCTION lab_frozen_child('content_contentrevision','revision_id');
CREATE TRIGGER frozen_content_labpagedetail BEFORE INSERT OR UPDATE OR DELETE ON content_labpagedetail FOR EACH ROW EXECUTE FUNCTION lab_frozen_child('content_contentrevision','revision_id');
CREATE TRIGGER frozen_content_revisioncontribution BEFORE INSERT OR UPDATE OR DELETE ON content_revisioncontribution FOR EACH ROW EXECUTE FUNCTION lab_frozen_child('content_contentrevision','revision_id');
CREATE TRIGGER frozen_content_contentprojectlink BEFORE INSERT OR UPDATE OR DELETE ON content_contentprojectlink FOR EACH ROW EXECUTE FUNCTION lab_frozen_child('content_contentrevision','source_revision_id');
CREATE TRIGGER frozen_content_revisionasset BEFORE INSERT OR UPDATE OR DELETE ON content_revisionasset FOR EACH ROW EXECUTE FUNCTION lab_frozen_child('content_contentrevision','revision_id');
CREATE TRIGGER frozen_content_revision BEFORE UPDATE OR DELETE ON content_contentrevision FOR EACH ROW EXECUTE FUNCTION lab_frozen_revision();
"""

class Migration(migrations.Migration):
    dependencies = [("content", "0001_initial")]
    operations = [migrations.RunSQL(SQL, 'DROP FUNCTION lab_content_kind_immutable() CASCADE; DROP FUNCTION lab_identifier_guard() CASCADE; DROP FUNCTION lab_canonical_identifier(text,text) CASCADE; DROP FUNCTION lab_content_event() CASCADE; DROP FUNCTION lab_content_graph(uuid) CASCADE; DROP FUNCTION lab_frozen_child() CASCADE; DROP FUNCTION lab_frozen_revision() CASCADE;')]
