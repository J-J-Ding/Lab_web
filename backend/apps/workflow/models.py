import uuid
from django.conf import settings
from django.db import models


class RevisionState(models.TextChoices):
    DRAFT='DRAFT'
    SUBMITTED='SUBMITTED'
    APPROVED='APPROVED'
    PUBLISHED='PUBLISHED'
    REJECTED='REJECTED'
    WITHDRAWN='WITHDRAWN'


class BusinessAuditLog(models.Model):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    actor_snapshot=models.PositiveBigIntegerField(null=True)
    target_id=models.UUIDField(db_index=True)
    revision_id=models.UUIDField(null=True)
    action=models.CharField(max_length=64)
    outcome=models.CharField(max_length=16, default='success')
    changed_fields=models.JSONField(default=list)
    request_id=models.UUIDField(default=uuid.uuid4)
    created_at=models.DateTimeField(auto_now_add=True, db_index=True)


class ContentEditGrant(models.Model):
    item=models.ForeignKey('content.ContentItem',on_delete=models.PROTECT,related_name='edit_grants')
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    granted_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name='+')
    can_edit=models.BooleanField(default=True)
    revoked_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['item','user'],name='workflow_grant_user_unique')]


class RevisionEditEvent(models.Model):
    content_revision=models.ForeignKey('content.ContentRevision',null=True,on_delete=models.PROTECT,related_name='edit_events')
    member_revision=models.ForeignKey('members.MemberRevision',null=True,on_delete=models.PROTECT,related_name='edit_events')
    editor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL)
    editor_snapshot=models.PositiveBigIntegerField()
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=(models.Q(content_revision__isnull=False,member_revision__isnull=True)|models.Q(content_revision__isnull=True,member_revision__isnull=False)),name='workflow_edit_one_revision'),models.UniqueConstraint(fields=['content_revision','editor_snapshot'],name='workflow_content_editor_unique'),models.UniqueConstraint(fields=['member_revision','editor_snapshot'],name='workflow_member_editor_unique')]


class RevisionSubmission(models.Model):
    content_revision=models.OneToOneField('content.ContentRevision',null=True,on_delete=models.PROTECT,related_name='submission')
    member_revision=models.OneToOneField('members.MemberRevision',null=True,on_delete=models.PROTECT,related_name='submission')
    submitted_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL)
    submitter_snapshot=models.PositiveBigIntegerField()
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=(models.Q(content_revision__isnull=False,member_revision__isnull=True)|models.Q(content_revision__isnull=True,member_revision__isnull=False)),name='workflow_submit_one_revision')]


class ReviewDecision(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    content_revision=models.OneToOneField('content.ContentRevision',null=True,on_delete=models.PROTECT,related_name='decision')
    member_revision=models.OneToOneField('members.MemberRevision',null=True,on_delete=models.PROTECT,related_name='decision')
    application=models.OneToOneField('members.MembershipApplication',null=True,on_delete=models.PROTECT,related_name='decision')
    reviewer=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL)
    reviewer_snapshot=models.PositiveBigIntegerField()
    decision=models.CharField(max_length=8,choices=[('APPROVE','APPROVE'),('REJECT','REJECT')])
    reason=models.CharField(max_length=2000)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=(models.Q(content_revision__isnull=False,member_revision__isnull=True,application__isnull=True)|models.Q(content_revision__isnull=True,member_revision__isnull=False,application__isnull=True)|models.Q(content_revision__isnull=True,member_revision__isnull=True,application__isnull=False)),name='workflow_decision_one_target'),models.CheckConstraint(condition=models.Q(decision__in=['APPROVE','REJECT']),name='workflow_decision_valid')]


class ContributionConfirmation(models.Model):
    contribution=models.ForeignKey('content.RevisionContribution',on_delete=models.PROTECT,related_name='confirmations')
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL)
    actor_snapshot=models.PositiveBigIntegerField()
    decision=models.CharField(max_length=12,choices=[('CONFIRMED','CONFIRMED'),('DISPUTED','DISPUTED')])
    is_proxy=models.BooleanField(default=False)
    reason=models.CharField(max_length=2000,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['created_at','id']
        constraints=[models.CheckConstraint(condition=models.Q(decision__in=['CONFIRMED','DISPUTED']),name='workflow_confirmation_valid'),models.CheckConstraint(condition=models.Q(is_proxy=False)|~models.Q(reason=''),name='workflow_proxy_reason_required')]


class CorrectionRequest(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    item=models.ForeignKey('content.ContentItem',on_delete=models.PROTECT,related_name='corrections')
    requester=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL)
    reason=models.CharField(max_length=2000)
    state=models.CharField(max_length=8,choices=[('OPEN','OPEN'),('RESOLVED','RESOLVED')],default='OPEN')
    reply=models.CharField(max_length=2000,blank=True)
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(state__in=['OPEN','RESOLVED']),name='workflow_correction_valid')]


class MemberPublicationConsent(models.Model):
    revision=models.OneToOneField('members.MemberRevision',on_delete=models.PROTECT,related_name='publication_consent')
    privacy_version=models.PositiveBigIntegerField()
    public_visible=models.BooleanField(default=False)
    contact_visible=models.BooleanField(default=False)
    education_visible=models.BooleanField(default=False)
    alumni_visible=models.BooleanField(default=False)
    created_at=models.DateTimeField(auto_now_add=True)


class ContentModerationEvent(models.Model):
    item=models.ForeignKey('content.ContentItem',on_delete=models.PROTECT,related_name='moderation_events')
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL)
    actor_snapshot=models.PositiveBigIntegerField()
    action=models.CharField(max_length=12,choices=[('ARCHIVE','ARCHIVE'),('UNARCHIVE','UNARCHIVE'),('UNPUBLISH','UNPUBLISH')])
    reason=models.CharField(max_length=2000)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(action__in=['ARCHIVE','UNARCHIVE','UNPUBLISH']),name='workflow_moderation_action_valid'),models.CheckConstraint(condition=~models.Q(reason=''),name='workflow_moderation_reason_required')]
