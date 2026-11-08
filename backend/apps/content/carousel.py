"""Root-only carousel writes; public access depends on active configuration."""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied,ValidationError
from rest_framework.response import Response
from apps.accounts.serializers import StrictSerializer,StrictString,StrictBoolean
from apps.accounts.services import locked_users
from apps.members.serializers import StrictInteger
from apps.members.services import VersionConflict
from apps.workflow.api import BusinessAPIView
from apps.workflow.audit import record
from apps.assets.models import AssetFile
from .models import CarouselSettings,CarouselSlide
from .public_views import paged


def active_slides():
    return CarouselSlide.objects.filter(enabled=True,deleted_at__isnull=True,asset__scan_status='CLEAN',asset__deletion_requested_at__isnull=True).filter(Q(asset__expires_at__isnull=True)|Q(asset__expires_at__gt=timezone.now())).select_related('asset')


def public_slides():
    config=CarouselSettings.objects.filter(pk=1).first()
    if not config or config.mode=='AUTO':return None
    from .public_serializers import asset_data
    return [{'id':str(s.pk),'title':s.title,'subtitle':s.subtitle,'image':asset_data(s.asset)} for s in active_slides()]


def public_asset(asset):
    return CarouselSettings.objects.filter(pk=1,mode='MANUAL').exists() and active_slides().filter(asset=asset).exists()


def data(slide):
    return {'id':str(slide.pk),'asset':str(slide.asset_id),'image_url':f'/api/assets/{slide.asset_id}/download/','title':slide.title,'subtitle':slide.subtitle,'position':slide.position,'enabled':slide.enabled}


class Input(StrictSerializer):
    lock_version=StrictInteger(min_value=0)
    mode=serializers.ChoiceField(choices=['AUTO','MANUAL'],required=False)
    asset=serializers.UUIDField(required=False)
    title=StrictString(max_length=200,allow_blank=True,required=False)
    subtitle=StrictString(max_length=500,allow_blank=True,required=False)
    position=StrictInteger(min_value=1,max_value=10000,required=False)
    enabled=StrictBoolean(required=False)
    delete=StrictBoolean(default=False)


class Carousel(BusinessAPIView):
    def initial(self,request,*args,**kwargs):
        super().initial(request,*args,**kwargs)
        if not request.user.is_active or not request.user.is_superuser:raise PermissionDenied()

    def get(self,request):
        config=CarouselSettings.objects.filter(pk=1).first()
        if request.query_params.get('page_size','5')!='5':raise ValidationError('轮播列表每页固定5项。')
        response=paged(request,CarouselSlide.objects.filter(deleted_at__isnull=True).select_related('asset'),data)
        response.data.update({'mode':config.mode if config else 'AUTO','lock_version':config.lock_version if config else 0})
        return response

    @transaction.atomic
    def post(self,request,pk=None):
        actor,_=locked_users(request)
        if not actor.is_superuser:raise PermissionDenied()
        serializer=Input(data=request.data);serializer.is_valid(raise_exception=True);values=serializer.validated_data
        CarouselSettings.objects.get_or_create(pk=1)
        config=CarouselSettings.objects.select_for_update().get(pk=1)
        if config.lock_version!=values['lock_version']:raise VersionConflict()
        if 'mode' in values:
            if pk or set(values)-{'lock_version','mode','delete'} or values['delete']:raise ValidationError('模式修改不得包含轮播项字段。')
            config.mode=values['mode'];target=config
        else:
            slide=get_object_or_404(CarouselSlide.objects.select_for_update(),pk=pk,deleted_at__isnull=True) if pk else None
            if values['delete']:
                if not slide:raise ValidationError('请选择轮播项。')
                slide.deleted_at=timezone.now();slide.save();target=slide
            else:
                aid=values.get('asset',slide.asset_id if slide else None)
                asset=get_object_or_404(AssetFile.objects.select_for_update(),pk=aid,scan_status='CLEAN',purpose='image',deletion_requested_at__isnull=True)
                if (asset.owner_id!=actor.pk and (not slide or slide.asset_id!=asset.pk)) or (asset.expires_at and asset.expires_at<=timezone.now()):raise ValidationError({'asset':'图片不可用，请重新上传。'})
                asset.expires_at=None;asset.save(update_fields=['expires_at'])
                if not slide:slide=CarouselSlide(asset=asset)
                slide.asset=asset
                for key in ('title','subtitle','position','enabled'):
                    if key in values:setattr(slide,key,values[key])
                slide.save();target=slide
        config.lock_version+=1;config.save()
        record(actor,target,'carousel.deleted' if values['delete'] else 'carousel.saved',tuple(values))
        return Response({'lock_version':config.lock_version,'mode':config.mode,'slide':data(target) if isinstance(target,CarouselSlide) else None})
