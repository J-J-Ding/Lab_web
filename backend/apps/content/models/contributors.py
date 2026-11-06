import uuid
from django.db import models
from django.conf import settings
from django.db.models import Q
from .base import ContentRevision


class Contributor(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="+")
    display_name=models.CharField(max_length=150)
    member_profile=models.OneToOneField('members.MemberProfile',null=True,blank=True,on_delete=models.PROTECT,related_name='contributor')
    external_affiliation=models.CharField(max_length=300,blank=True)


class RevisionContribution(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    revision=models.ForeignKey(ContentRevision,on_delete=models.CASCADE,related_name='contributions')
    contributor=models.ForeignKey(Contributor,on_delete=models.PROTECT,related_name='contributions')
    contribution_role=models.CharField(max_length=16)
    position=models.PositiveIntegerField()
    is_corresponding=models.BooleanField(default=False)
    confirmation_status=models.CharField(max_length=12,default='UNCONFIRMED')
    approved_display_name=models.CharField(max_length=150)
    approved_affiliation=models.CharField(max_length=300,blank=True)
    class Meta:
        ordering=['position','id']
        constraints=[models.UniqueConstraint(fields=['revision','contributor','contribution_role'],name='revision_contributor_role_unique'),models.UniqueConstraint(fields=['revision','position'],condition=Q(contribution_role='AUTHOR'),name='revision_author_position_unique'),models.CheckConstraint(condition=Q(position__gt=0),name='contribution_position_positive'),models.CheckConstraint(condition=Q(confirmation_status__in=['UNCONFIRMED','CONFIRMED','DISPUTED']),name='contribution_confirmation_valid'),models.CheckConstraint(condition=Q(is_corresponding=False)|Q(contribution_role='AUTHOR'),name='corresponding_author_only')]
