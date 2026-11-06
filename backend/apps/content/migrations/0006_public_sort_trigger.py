from django.db import migrations
SQL="""
CREATE FUNCTION lab_public_sort_date() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE d date; fallback_date date;
BEGIN
 IF NEW.published_revision_id IS NULL THEN NEW.public_sort_date=NULL; RETURN NEW; END IF;
 SELECT (created_at AT TIME ZONE 'Asia/Shanghai')::date INTO fallback_date FROM content_contentrevision WHERE id=NEW.published_revision_id;
 CASE NEW.kind
  WHEN 'PAPER' THEN SELECT publication_date INTO d FROM content_paperdetail WHERE revision_id=NEW.published_revision_id;
  WHEN 'PROJECT' THEN SELECT start_date INTO d FROM content_projectdetail WHERE revision_id=NEW.published_revision_id;
  WHEN 'AWARD' THEN SELECT award_date INTO d FROM content_awarddetail WHERE revision_id=NEW.published_revision_id;
  WHEN 'ACTIVITY' THEN SELECT (starts_at AT TIME ZONE 'Asia/Shanghai')::date INTO d FROM content_activitydetail WHERE revision_id=NEW.published_revision_id;
  WHEN 'NEWS' THEN SELECT event_date INTO d FROM content_newsdetail WHERE revision_id=NEW.published_revision_id;
  WHEN 'BLOG' THEN SELECT event_date INTO d FROM content_blogdetail WHERE revision_id=NEW.published_revision_id;
  WHEN 'PUBLICATION' THEN SELECT publication_date INTO d FROM content_publicationdetail WHERE revision_id=NEW.published_revision_id;
  ELSE d=NULL;
 END CASE;
 NEW.public_sort_date=COALESCE(d,fallback_date);
 RETURN NEW;
END; $$;
CREATE TRIGGER content_sort_date_derive BEFORE INSERT OR UPDATE OF published_revision_id,public_sort_date ON content_contentitem FOR EACH ROW EXECUTE FUNCTION lab_public_sort_date();
UPDATE content_contentitem SET published_revision_id=published_revision_id;
"""
class Migration(migrations.Migration):
    dependencies=[('content','0005_contentitem_public_sort_date_and_more')]
    operations=[migrations.RunSQL(SQL,'DROP TRIGGER IF EXISTS content_sort_date_derive ON content_contentitem; DROP FUNCTION IF EXISTS lab_public_sort_date();')]
