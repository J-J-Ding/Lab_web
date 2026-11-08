from django.db import transaction, connection, IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from apps.accounts.serializers import StrictSerializer, StrictString, StrictBoolean
from apps.accounts.services import locked_users
from apps.accounts.models import User
from apps.members.serializers import StrictInteger
from apps.members.models import MemberProfile, Resume, MemberResearchArea
from apps.members import direct as profiles
from apps.workflow.api import BusinessAPIView
from apps.workflow.serializers import revision_data
from apps.workflow.models import ContentEditGrant
from apps.workflow.audit import record
from . import direct_services as services
from .models import ContentItem
from .public_selectors import content_queryset, member_queryset, published_items_base
from .public_serializers import content_data, member_data
from .public_views import PublicView, PublicPagination, paged


class SaveInput(StrictSerializer):
    kind=serializers.ChoiceField(choices=list(services.DETAIL_MODELS),required=False)
    title=StrictString(max_length=500,required=False)
    summary=StrictString(max_length=10000,allow_blank=True,required=False)
    detail=serializers.DictField(required=False)
    rich_body=serializers.JSONField(required=False,allow_null=True)
    lock_version=StrictInteger(min_value=0,required=False)
    authors=serializers.ListField(child=StrictInteger(min_value=1),max_length=100,required=False)
    authors_ordered=StrictBoolean(default=False)
    cover_asset=serializers.UUIDField(allow_null=True,required=False)
    assets=serializers.ListField(child=serializers.UUIDField(),max_length=60,required=False)
    project_links=serializers.ListField(child=serializers.UUIDField(),max_length=30,required=False)
    visibility_scope=serializers.ChoiceField(choices=['PUBLIC','TEAM'],required=False)
    featured=StrictBoolean(required=False)


def validated(cls,request):
    s=cls(data=request.data);s.is_valid(raise_exception=True);return s.validated_data


def item_data(item,actor):
    r=item.published_revision or (item.working_revision if services.editable(actor,item) else None)
    rev=revision_data(r)
    if rev is not None:
        from .public_serializers import cover_for_revision
        cover=cover_for_revision(r)
        rev['asset_details']=[{'id':str(link.asset_id),'name':link.asset.original_filename,'mime_type':link.asset.mime_type,'purpose':link.purpose,'download_url':f'/api/assets/{link.asset_id}/download/'} for link in r.assets.select_related('asset').order_by('position')]
    else:cover=None
    authors=[]
    if r:
        for c in r.contributions.select_related('contributor__member_profile__user','contributor__member_profile__published_revision','contributor__member_profile__draft_revision').all():
            profile=c.contributor.member_profile
            if profile and profile.user_id and profile.user.is_active and profile.user.role in ('TEACHER','STUDENT'):
                authors.append({'user_id':profile.user_id,'display_name':services.name_for(profile),'position':c.position})
    return {'id':str(item.pk),'kind':item.kind,'created_by':item.created_by_id,'lock_version':item.lock_version,'visibility_scope':item.visibility_scope,'featured':item.featured,'cover_asset':str(cover.pk) if cover else None,'visible':item.visibility_gate,'deleted':bool(item.deleted_at),'archived':bool(item.archived_at),'can_edit':services.editable(actor,item),'revision':rev,'authors':authors,'legacy_working_revision':revision_data(item.working_revision) if services.editable(actor,item) else None}


class TeamView(BusinessAPIView):
    def initial(self,request,*args,**kwargs):
        super().initial(request,*args,**kwargs)
        if not services.team(request.user):raise PermissionDenied('Teacher or Student access required.')


class Items(TeamView):
    def get(self,request):
        scope=request.query_params.get('scope','normal')
        if scope not in ('normal','deleted'):raise ValidationError({'scope':'Unknown scope.'})
        qs=services.readable(request.user,deleted=scope=='deleted').order_by('-updated_at','id')
        kind=request.query_params.get('kind')
        if kind:
            if kind not in services.DETAIL_MODELS:raise ValidationError({'kind':'Unknown content kind.'})
            qs=qs.filter(kind=kind)
        if request.query_params.get('mine')=='1':qs=qs.filter(created_by=request.user)
        query=request.query_params.get('q','').strip()
        if len(query)>100:raise ValidationError('Search too long.')
        if query:qs=qs.filter(Q(published_revision__title__icontains=query)|Q(working_revision__title__icontains=query))
        return paged(request,qs,lambda item:item_data(item,request.user))
    def post(self,request):
        data=validated(SaveInput,request)
        if not {'kind','title'}<=set(data):raise ValidationError('Kind and title required.')
        return Response(item_data(services.save(request,data),request.user),status=201)


class Item(TeamView):
    def get(self,request,pk):return Response(item_data(get_object_or_404(services.readable(request.user)|services.readable(request.user,deleted=True),pk=pk),request.user))
    def patch(self,request,pk):
        data=validated(SaveInput,request)
        if 'kind' in data:raise ValidationError({'kind':'Content type is immutable.'})
        if 'lock_version' not in data:raise ValidationError({'lock_version':'Reload before saving.'})
        return Response(item_data(services.save(request,data,pk),request.user))


class Directory(TeamView):
    def get(self,request):
        qs=services.directory();q=request.query_params.get('q','').strip()
        if len(q)>100:raise ValidationError('Search too long.')
        if q:qs=qs.filter(Q(published_revision__display_name__icontains=q)|Q(draft_revision__display_name__icontains=q))
        return paged(request,qs,lambda p:{'user_id':p.user_id,'username':p.user.username,'profile_id':str(p.pk),'display_name':services.name_for(p),'identity':'Teacher' if p.user.role=='TEACHER' else 'Student','selectable':bool(services.name_for(p)),'avatar_url':services.avatar_for(p)})


class Profile(BusinessAPIView):
    def get(self,request,pk=None):
        with transaction.atomic():
            actor,profile=profiles.get_profile(request,pk)
            return Response(profiles.profile_data(profile,actor))
    def patch(self,request,pk=None):
        profile=profiles.save_profile(request,validated(profiles.RootProfileInput if request.user.is_superuser else profiles.ProfileInput,request),pk)
        return Response(profiles.profile_data(profile,request.user))


class ProfileHistory(BusinessAPIView):
    def get(self,request,pk=None):
        actor,profile=profiles.get_profile(request,pk)
        return paged(request,profile.revisions.order_by('-number'),lambda r:{'id':str(r.pk),'number':r.number,'display_name':r.display_name,'created_at':r.created_at,'state':r.state})
    def post(self,request,pk=None):
        data=validated(RestoreInput,request)
        profile=profiles.save_profile(request,{'lock_version':data['lock_version']},pk,data['source_revision'])
        return Response(profiles.profile_data(profile,request.user))


class Resumes(BusinessAPIView):
    def initial(self,request,*args,**kwargs):
        super().initial(request,*args,**kwargs)
        if kwargs.get("owner_id") and request.method=="GET" and request.user.is_superuser:return

    def get(self,request,pk=None,owner_id=None):
        if owner_id and not request.user.is_superuser:raise PermissionDenied()
        owner=get_object_or_404(User,pk=owner_id) if owner_id else request.user
        qs=Resume.objects.filter(owner=owner,deleted_at__isnull=True).order_by('-updated_at','pk')
        if pk:return Response(profiles.resume_data(get_object_or_404(qs,pk=pk)))
        if request.user.is_superuser and owner_id:
            with transaction.atomic():
                from apps.accounts.services import audit
                audit('resume.access',actor=request.user,target=owner,request=request)
        return paged(request,qs,profiles.resume_data)
    def post(self,request,pk=None,owner_id=None):
        owner=get_object_or_404(User,pk=owner_id) if owner_id else None
        return Response(profiles.resume_data(profiles.save_resume(request,validated(profiles.ResumeInput,request),owner=owner)),status=201)
    def patch(self,request,pk,owner_id=None):
        return Response(profiles.resume_data(profiles.save_resume(request,validated(profiles.ResumeInput,request),pk)))


class RestoreInput(StrictSerializer):
    lock_version=StrictInteger(min_value=0)
    source_revision=serializers.UUIDField()


class History(TeamView):
    def get(self,request,pk):
        item=get_object_or_404(services.readable(request.user),pk=pk)
        if not services.editable(request.user,item):raise PermissionDenied()
        return paged(request,item.revisions.order_by('-number'),lambda r:{'id':str(r.pk),'number':r.number,'title':r.title,'created_at':r.created_at,'state':r.state,'revision':revision_data(r)})
    def post(self,request,pk):
        data=validated(RestoreInput,request)
        return Response(item_data(services.save(request,{'lock_version':data['lock_version']},pk,data['source_revision']),request.user))


class GrantInput(StrictSerializer):
    lock_version=StrictInteger(min_value=0)
    user_id=StrictInteger(min_value=1)
    revoke=StrictBoolean(default=False)
    can_edit=StrictBoolean(default=True)


class Grant(TeamView):
    def post(self,request,pk):
        data=validated(GrantInput,request)
        with transaction.atomic():
            actor,target=locked_users(request,data['user_id'])
            if not services.is_manager(actor):raise PermissionDenied()
            item=get_object_or_404(ContentItem.objects.select_for_update(),pk=pk)
            if item.lock_version!=data['lock_version']:raise profiles.VersionConflict()
            if not target or not target.is_active or target.role not in ('TEACHER','STUDENT'):raise ValidationError('Select an active team account.')
            ContentEditGrant.objects.update_or_create(item=item,user=target,defaults={'granted_by':actor,'can_edit':data['can_edit'],'revoked_at':timezone.now() if data['revoke'] else None})
            item.lock_version+=1;item.save(update_fields=['lock_version']);record(actor,item,'content.grant',('edit_grants',))
        return Response(item_data(item,actor))


class Capabilities(BusinessAPIView):
    def get(self,request):
        from apps.accounts.serializers import UserSerializer
        data=UserSerializer(request.user).data
        return Response({**data['capabilities'],'can_submit':False,'can_review':False,'rich_content':True,'identity':data['identity']})


class Gone(BusinessAPIView):
    def get(self,request,*args,**kwargs):return Response({'code':'workflow_retired','detail':'审批流程已取消，请使用资料或内容编辑页直接保存。'},status=410)
    post=get
    patch=get
    delete=get


class Home(PublicView):
    def get(self,request):
        nested=connection.in_atomic_block
        with transaction.atomic():
            if not nested:
                with connection.cursor() as cursor:cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            qs=published_items_base();people=member_queryset()
            def cards(kind,category=None):
                selected=content_queryset().filter(kind=kind)
                if category:selected=selected.filter(**{f'published_revision__{kind.lower()}__category':category})
                return [{k:v for k,v in content_data(i).items() if k in ('id','kind','title','summary','date','assets','cover')} for i in selected.order_by('-featured','-public_sort_date','id')[:4]]
            slides=[]
            for row in content_queryset().filter(kind__in=['ACTIVITY','NEWS']).order_by('-featured','-public_sort_date','id')[:12]:
                public=content_data(row)
                if public['cover']:
                    slides.append({'id':public['id'],'title':public['title'],'image':public['cover'],'url':'/content.html?id='+public['id']})
                if len(slides)>=5:break
            from .carousel import public_slides
            managed=public_slides()
            if managed is not None:slides=managed
            result={'slides':slides,'schema_version':'v10.1','as_of':timezone.now(),'stats':{'members':people.count(),'papers':qs.filter(kind='PAPER').count(),'projects':qs.filter(kind='PROJECT').count(),'competitions':qs.filter(kind='AWARD',published_revision__award__category='COMPETITION').count()},'research_areas':list(MemberResearchArea.objects.filter(revision_id__in=people.values('published_revision_id')).values_list('area__name',flat=True).distinct()[:8]),'news':cards('NEWS'),'papers':cards('PAPER'),'projects':cards('PROJECT'),'competitions':cards('AWARD','COMPETITION'),'members':[member_data(p) for p in people[:5]],'resources':cards('BLOG','RESOURCE')}
            return Response(result)


class DeleteInput(StrictSerializer):
    lock_version=StrictInteger(min_value=0)


class Delete(TeamView):
    deleted=True
    def post(self,request,pk):
        data=validated(DeleteInput,request)
        return Response(item_data(services.set_deleted(request,pk,data['lock_version'],self.deleted),request.user))


class Undelete(Delete):
    deleted=False


class ResumeDeleteInput(StrictSerializer):
    lock_version=StrictInteger(min_value=0)


class ResumeDelete(BusinessAPIView):
    http_method_names=['post']
    def post(self,request,pk):
        from apps.members.resume_deletion import delete_resume
        data=validated(ResumeDeleteInput,request)
        return Response(delete_resume(request,pk,data['lock_version']))
