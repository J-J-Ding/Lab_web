import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.workflow.models import RevisionState
from ..types import ContentKind


class ContentItem(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    kind=models.CharField(max_length=12,choices=ContentKind)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name='+')
    last_edited_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name='+')
    published_revision=models.OneToOneField('ContentRevision',null=True,blank=True,on_delete=models.PROTECT,related_name='+')
    working_revision=models.OneToOneField('ContentRevision',null=True,blank=True,on_delete=models.SET_NULL,related_name='+')
    visibility_scope=models.CharField(max_length=7,choices=[('PUBLIC','PUBLIC'),('TEAM','TEAM')],default='PUBLIC')
    featured=models.BooleanField(default=False)
    visibility_gate=models.BooleanField(default=True)
    public_sort_date=models.DateField(null=True,editable=False)
    archived_at=models.DateTimeField(null=True,blank=True)
    deleted_at=models.DateTimeField(null=True,blank=True,db_index=True)
    deleted_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="+")
    lock_version=models.PositiveBigIntegerField(default=0)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=Q(kind__in=ContentKind.values),name='content_kind_valid')]
        indexes=[models.Index(fields=['kind','created_at']),models.Index(fields=['kind','-public_sort_date','id'],name='content_public_kind_date_idx'),models.Index(fields=['-public_sort_date','id'],name='content_public_date_idx')]


class ContentRevision(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    item=models.ForeignKey(ContentItem,on_delete=models.CASCADE,related_name='revisions')
    number=models.PositiveIntegerField()
    state=models.CharField(max_length=12,choices=RevisionState,default=RevisionState.DRAFT)
    base_published_revision=models.ForeignKey('self',null=True,blank=True,on_delete=models.PROTECT)
    title=models.CharField(max_length=500)
    summary=models.TextField(blank=True,max_length=10000)
    edited_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL)
    submitted_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['item','number'],name='content_revision_number_unique'),models.UniqueConstraint(fields=['item'],condition=Q(state__in=['DRAFT','SUBMITTED','APPROVED']),name='content_one_working_revision'),models.CheckConstraint(condition=Q(number__gt=0),name='content_revision_positive'),models.CheckConstraint(condition=Q(state__in=RevisionState.values),name='content_revision_state_valid')]


class ContentIdentifier(models.Model):
    item=models.ForeignKey(ContentItem,on_delete=models.PROTECT,related_name='identifiers')
    scheme=models.CharField(max_length=12,choices=[('DOI','DOI'),('PROJECT','PROJECT'),('ISBN','ISBN'),('PAGE','PAGE')])
    value=models.CharField(max_length=255)
    is_current=models.BooleanField(default=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['scheme','value'],name='content_identifier_unique'),models.UniqueConstraint(fields=['item','scheme'],condition=Q(is_current=True),name='content_one_current_identifier'),models.CheckConstraint(condition=Q(scheme__in=['DOI','PROJECT','ISBN','PAGE']),name='identifier_scheme_valid'),models.CheckConstraint(condition=~Q(value=''),name='identifier_not_empty')]
