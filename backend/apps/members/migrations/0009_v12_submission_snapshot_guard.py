from django.db import migrations

SQL="""
CREATE FUNCTION lab_resume_submission_frozen() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Submission history cannot be deleted' USING ERRCODE='23514'; END IF;
 IF (to_jsonb(NEW)-ARRAY['state','withdrawn_at']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','withdrawn_at']) THEN
  RAISE EXCEPTION 'Submitted profile and resume snapshots are immutable' USING ERRCODE='23514'; END IF;
 IF OLD.state='WITHDRAWN' AND NEW IS DISTINCT FROM OLD THEN RAISE EXCEPTION 'Withdrawn submission is final' USING ERRCODE='23514'; END IF;
 IF NEW.state='WITHDRAWN' AND NEW.withdrawn_at IS NULL THEN RAISE EXCEPTION 'Withdrawal requires timestamp' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER resume_submission_frozen BEFORE UPDATE OR DELETE ON members_resumesubmission FOR EACH ROW EXECUTE FUNCTION lab_resume_submission_frozen();
"""

class Migration(migrations.Migration):
    dependencies=[('members','0008_v12_private_cv')]
    operations=[migrations.RunSQL(SQL,'DROP TRIGGER resume_submission_frozen ON members_resumesubmission; DROP FUNCTION lab_resume_submission_frozen();')]
