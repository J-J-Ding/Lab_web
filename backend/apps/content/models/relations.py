from django.db import models
from .base import ContentRevision,ContentItem


class ContentProjectLink(models.Model):
    source_revision=models.ForeignKey(ContentRevision,on_delete=models.CASCADE,related_name='project_links')
    target_project=models.ForeignKey(ContentItem,on_delete=models.PROTECT,related_name='output_links')
    relation_type=models.CharField(max_length=16,default='OUTPUT',choices=[('OUTPUT','OUTPUT')])
    class Meta:
        constraints=[models.UniqueConstraint(fields=['source_revision','target_project'],name='content_project_link_unique'),models.CheckConstraint(condition=models.Q(relation_type='OUTPUT'),name='content_project_relation_valid')]


class RevisionAsset(models.Model):
    revision=models.ForeignKey(ContentRevision,on_delete=models.CASCADE,related_name='assets')
    asset=models.ForeignKey('assets.AssetFile',on_delete=models.PROTECT)
    purpose=models.CharField(max_length=32)
    position=models.PositiveIntegerField(default=1)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['revision','asset','purpose'],name='content_asset_unique'),models.CheckConstraint(condition=models.Q(position__gt=0),name='content_asset_position_positive')]
