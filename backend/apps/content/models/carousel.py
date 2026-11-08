import uuid
from django.db import models


class CarouselSettings(models.Model):
    id=models.PositiveSmallIntegerField(primary_key=True,default=1,editable=False)
    mode=models.CharField(max_length=6,choices=[('AUTO','AUTO'),('MANUAL','MANUAL')],default='AUTO')
    lock_version=models.PositiveBigIntegerField(default=0)
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(id=1),name='carousel_single_settings'),models.CheckConstraint(condition=models.Q(mode__in=['AUTO','MANUAL']),name='carousel_mode_valid')]


class CarouselSlide(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    asset=models.ForeignKey('assets.AssetFile',on_delete=models.PROTECT,related_name='carousel_slides')
    title=models.CharField(max_length=200,blank=True)
    subtitle=models.CharField(max_length=500,blank=True)
    position=models.PositiveIntegerField(default=1)
    enabled=models.BooleanField(default=True)
    deleted_at=models.DateTimeField(null=True,blank=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        ordering=['position','id']
        constraints=[models.CheckConstraint(condition=models.Q(position__gt=0),name='carousel_position_positive')]
