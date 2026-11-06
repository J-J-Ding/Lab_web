from apps.workflow.api import BusinessAPIView as AccountAPIView
from django.db.models import Q,F
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from apps.accounts.views import UserPagination,validated
from apps.accounts.permissions import is_manager,IsManager,can_manage
from apps.accounts.models import User
from apps.members.models import MemberProfile,MemberRevision,MembershipApplication
from apps.members.serializers import draft_data
from apps.members import services as member_core
from apps.content.models import ContentItem,ContentRevision,Contributor,RevisionContribution
from .permissions import visible_items,can_edit,selectable_contributors,can_submit,can_self_review
from .serializers import (ContentCreateInput,ContentUpdateInput,NewRevisionInput,VersionInput,DecisionInput,ReasonInput,ConfirmationInput,GrantInput,CorrectionInput,ContributorInput,item_data,revision_data)
from .member_serializers import ApplicationInput,ApplicationDecisionInput,MemberSubmitInput,RestrictInput,CatalogInput,BindInput,application_data
from . import content_services as content,member_services as members
from .models import ReviewDecision,RevisionSubmission,CorrectionRequest


def page(request,query,serializer):
    paginator=UserPagination();rows=paginator.paginate_queryset(query,request)
    return paginator.get_paginated_response([serializer(row) for row in rows])


def filters(request,allowed):
    if set(request.query_params)-set(allowed)-{'page','page_size'}:raise ValidationError({'detail':'Unsupported filter.'})



class ItemsView(AccountAPIView):
    http_method_names=['get','post']
    def get(self,request):
        filters(request,{'kind','state','scope'})
        qs=visible_items(request.user).select_related('working_revision','published_revision')
        kind=request.query_params.get('kind');state=request.query_params.get('state');scope=request.query_params.get('scope')
        if kind:
            from apps.content.types import ContentKind
            if kind not in ContentKind.values:raise ValidationError({'kind':'Invalid content kind.'})
            qs=qs.filter(kind=kind)
        if state:
            if state not in ('DRAFT','SUBMITTED','PUBLISHED','REJECTED','WITHDRAWN'):raise ValidationError({'state':'Invalid state.'})
            qs=qs.filter(Q(working_revision__state=state)|Q(published_revision__state=state))
        if scope not in (None,'mine','shared'):raise ValidationError({'scope':'Invalid scope.'})
        if scope=='mine':qs=qs.filter(created_by=request.user)
        if scope=='shared':qs=qs.exclude(created_by=request.user)
        return page(request,qs,item_data)
    def post(self,request):return Response(item_data(content.create(request,validated(ContentCreateInput,request))),status=201)


class ItemView(AccountAPIView):
    http_method_names=['get']
    def get(self,request,pk):
        item=get_object_or_404(visible_items(request.user),pk=pk)
        data=item_data(item);data['can_edit']=can_edit(request.user,item) and can_submit(request.user)
        r=item.working_revision
        data['can_review']=bool(is_manager(request.user) and r and r.state=='SUBMITTED' and not item.archived_at and r.base_published_revision_id==item.published_revision_id and (can_self_review(request.user) or (not r.edit_events.filter(editor_snapshot=request.user.pk).exists() and r.submission.submitter_snapshot!=request.user.pk)))
        data['grants']=[{'user_id':g.user_id,'can_edit':g.can_edit,'revoked':g.revoked_at is not None} for g in item.edit_grants.all()] if is_manager(request.user) or item.created_by_id==request.user.pk else []
        return Response(data)


class NewRevisionView(AccountAPIView):
    http_method_names=['post']
    def post(self,request,pk):return Response(item_data(content.clone(request,pk,validated(NewRevisionInput,request))),status=201)


class RevisionView(AccountAPIView):
    http_method_names=['patch']
    def patch(self,request,pk):return Response(item_data(content.edit(request,pk,validated(ContentUpdateInput,request))))


class RevisionActionView(AccountAPIView):
    http_method_names=['post']
    action='submit'
    def post(self,request,pk):
        data=validated(VersionInput,request)
        return Response(item_data(getattr(content,self.action)(request,pk,data['lock_version'])))


class DecisionView(AccountAPIView):
    permission_classes=[IsManager]
    http_method_names=['post']
    def post(self,request,pk):return Response(item_data(content.decide(request,pk,validated(DecisionInput,request))))


class ModerateView(AccountAPIView):
    permission_classes=[IsManager]
    http_method_names=['post']
    action='archive'
    def post(self,request,pk):return Response(item_data(content.moderate(request,pk,self.action,validated(ReasonInput,request))))


class GrantView(AccountAPIView):
    http_method_names=['post']
    def post(self,request,pk):return Response(item_data(content.grant(request,pk,validated(GrantInput,request))))


class ConfirmView(AccountAPIView):
    http_method_names=['post']
    proxy=False
    def post(self,request,pk):return Response(content.confirm(request,pk,validated(ConfirmationInput,request),proxy=self.proxy))


class CorrectionsView(AccountAPIView):
    http_method_names=['post']
    def post(self,request,pk):
        data=validated(CorrectionInput,request);result=content.correction(request,pk,data['reason'])
        return Response({'id':str(result.pk),'state':result.state},status=201)


class HistoryView(AccountAPIView):
    http_method_names=['get']
    def get(self,request,pk):
        item=get_object_or_404(visible_items(request.user),pk=pk)
        return page(request,item.revisions.order_by('-number'),lambda r:{**revision_data(r),'decision':({'decision':r.decision.decision,'reason':r.decision.reason,'reviewer':r.decision.reviewer_snapshot} if hasattr(r,'decision') else None)})


class ConfirmationsView(AccountAPIView):
    http_method_names=['get']
    def get(self,request):
        qs=RevisionContribution.objects.filter(contributor__member_profile__user=request.user,revision__state__in=['DRAFT','SUBMITTED'],revision__item__working_revision=F('revision_id')).select_related('revision__item').order_by('pk')
        return page(request,qs,lambda c:{'id':str(c.pk),'item_id':str(c.revision.item_id),'title':c.revision.title,'name':c.approved_display_name,'role':c.contribution_role,'position':c.position,'state':c.revision.state})


class ContributorsView(AccountAPIView):
    http_method_names=['get','post']
    def get(self,request):
        filters(request,{'q'})
        q=request.query_params.get('q','')
        if len(q)>100:raise ValidationError({'q':'Query too long.'})
        qs=selectable_contributors(request.user) if can_submit(request.user) else Contributor.objects.none()
        if q:qs=qs.filter(safe_name__icontains=q)
        return page(request,qs.order_by('safe_name','id'),lambda c:{'id':str(c.pk),'display_name':c.safe_name,'external_affiliation':c.safe_affiliation})
    def post(self,request):
        from django.db import transaction
        from .permissions import actor_for
        from .audit import record
        with transaction.atomic():
            actor=actor_for(request,editor=True)
            c=Contributor.objects.create(created_by=actor,**validated(ContributorInput,request))
            record(actor,c,'content.external_contributor.create',('display_name',))
            return Response({'id':str(c.pk),'display_name':c.display_name,'external_affiliation':c.external_affiliation},status=201)


class TasksView(AccountAPIView):
    permission_classes=[IsManager]
    http_method_names=['get']
    def get(self,request):
        filters(request,{'kind','state'})
        qs=ContentRevision.objects.filter(state='SUBMITTED').select_related('item').order_by('submitted_at','pk')
        if request.query_params.get('state') not in (None,'SUBMITTED'):raise ValidationError({'state':'Only SUBMITTED tasks are accepted.'})
        kind=request.query_params.get('kind')
        if kind:
            from apps.content.types import ContentKind
            if kind not in ContentKind.values:raise ValidationError({'kind':'Invalid content kind.'})
            qs=qs.filter(item__kind=kind)
        def data(r):
            submission=RevisionSubmission.objects.filter(content_revision=r).first()
            self_authored=(submission and submission.submitter_snapshot==request.user.pk) or r.edit_events.filter(editor_snapshot=request.user.pk).exists()
            return {'id':str(r.pk),'item_id':str(r.item_id),'kind':r.item.kind,'title':r.title,'lock_version':r.item.lock_version,'can_review':(can_self_review(request.user) or not bool(self_authored)) and r.item.archived_at is None and r.base_published_revision_id==r.item.published_revision_id,'state':r.state}
        return page(request,qs,data)


class ApplicationsView(AccountAPIView):
    http_method_names=['get','post']
    def get(self,request):return page(request,MembershipApplication.objects.filter(applicant=request.user).order_by('-created_at','pk'),application_data)
    def post(self,request):return Response(application_data(members.apply(request,validated(ApplicationInput,request))),status=201)


class ApplicationWithdrawView(AccountAPIView):
    http_method_names=['post']
    def post(self,request,pk):return Response(application_data(members.withdraw_application(request,pk,validated(VersionInput,request)['lock_version'])))


class ApplicationTasksView(AccountAPIView):
    permission_classes=[IsManager]
    http_method_names=['get']
    def get(self,request):
        qs=MembershipApplication.objects.filter(state='SUBMITTED').select_related('applicant').order_by('created_at','pk')
        if not request.user.is_superuser:qs=qs.filter(Q(applicant=request.user)|Q(applicant__is_superuser=False,applicant__role__in=['CUSTOMER','STUDENT','TEACHER']))
        def details(a):
            own=MemberProfile.objects.filter(user=a.applicant).first()
            target=a.target_profile
            comparison={'applicant_draft':draft_data(own,own.draft_revision) if own else None,'target_draft':draft_data(target,target.draft_revision or target.published_revision) if target else None}
            return {**application_data(a),'applicant_id':a.applicant_id,'applicant_username':a.applicant.username,'can_review':can_self_review(request.user) or a.applicant_id!=request.user.pk,'claim_comparison':comparison}
        return page(request,qs,details)


class ApplicationDecisionView(AccountAPIView):
    permission_classes=[IsManager]
    http_method_names=['post']
    def post(self,request,pk):return Response(application_data(members.decide_application(request,pk,validated(ApplicationDecisionInput,request))))


class ProfileSubmitView(AccountAPIView):
    http_method_names=['post']
    def post(self,request):
        profile=members.submit_profile(request,validated(MemberSubmitInput,request))
        return Response(draft_data(profile,profile.draft_revision))


class ProfileWithdrawView(AccountAPIView):
    http_method_names=['post']
    def post(self,request):
        profile=members.withdraw_profile(request,validated(VersionInput,request)['lock_version'])
        return Response({'lock_version':profile.lock_version})


class ProfileTasksView(AccountAPIView):
    permission_classes=[IsManager]
    http_method_names=['get']
    def get(self,request):
        qs=MemberRevision.objects.filter(state='SUBMITTED').select_related('profile').order_by('created_at','pk')
        if not request.user.is_superuser:qs=qs.filter(Q(profile__user=request.user)|Q(profile__user__is_superuser=False,profile__user__role__in=['CUSTOMER','STUDENT','TEACHER']))
        def details(r):
            consent=r.publication_consent
            authored=r.edit_events.filter(editor_snapshot=request.user.pk).exists() or r.submission.submitter_snapshot==request.user.pk
            reason='self_authored' if authored and not can_self_review(request.user) else 'consent_changed' if consent.privacy_version!=r.profile.privacy_version else 'baseline_changed' if r.base_published_revision_id!=r.profile.published_revision_id else ''
            return {**draft_data(r.profile,r),'can_review':not bool(reason),'review_block_reason':reason,
                    'public_consent':{f:getattr(consent,f) for f in ('public_visible','contact_visible','education_visible','alumni_visible')},
                    'avatar_download_url':f'/api/assets/{r.avatar_asset_id}/download/' if r.avatar_asset_id else None}
        return page(request,qs,details)


class ProfileDecisionView(AccountAPIView):
    permission_classes=[IsManager]
    http_method_names=['post']
    def post(self,request,pk):
        profile=members.decide_profile(request,pk,validated(DecisionInput,request))
        return Response({'profile_id':str(profile.pk),'lock_version':profile.lock_version,'public_visible':profile.public_visible})


class PrivacyView(AccountAPIView):
    http_method_names=['post']
    def post(self,request):
        profile=members.restrict_privacy(request,validated(RestrictInput,request)['scopes'])
        return Response({'lock_version':profile.lock_version,'privacy_version':profile.privacy_version})


class MemberCatalogView(AccountAPIView):
    permission_classes=[IsManager]
    http_method_names=['get','post']
    def get(self,request):
        qs=MemberProfile.objects.filter(merged_into__isnull=True).select_related('user','draft_revision','published_revision').order_by('created_at','pk')
        if not request.user.is_superuser:qs=qs.filter(Q(user__isnull=True)|Q(user__is_superuser=False,user__role__in=['CUSTOMER','STUDENT','TEACHER']))
        return page(request,qs,lambda p:{'id':str(p.pk),'user_id':p.user_id,'membership_status':p.membership_status,'draft':draft_data(p,p.draft_revision)})
    def post(self,request):
        from django.db import transaction
        with transaction.atomic():
            from .permissions import actor_for
            actor=actor_for(request,manager=True)
            data=validated(CatalogInput,request);p=member_core.create_unbound_profile(actor)
            r=member_core.clone_revision(p,request.user);r.display_name=data['display_name'];r.member_kind=data['member_kind'];r.save()
            from .models import RevisionEditEvent
            RevisionEditEvent.objects.get_or_create(member_revision=r,editor_snapshot=request.user.pk,defaults={'editor':request.user})
            return Response({'id':str(p.pk),'draft':draft_data(p,r)},status=201)


class MemberBindView(AccountAPIView):
    permission_classes=[IsManager]
    http_method_names=['post']
    def post(self,request,pk):
        from django.db import transaction
        with transaction.atomic():
            from .permissions import actor_for
            data=validated(BindInput,request)
            from apps.accounts.services import locked_users
            actor,_=locked_users(request,data['user_id'])
            if not is_manager(actor):
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied()
            p=member_core.bind_profile(actor,pk,data['user_id'])
            return Response({'id':str(p.pk),'user_id':p.user_id})


class CorrectionTasksView(AccountAPIView):
    permission_classes=[IsManager]
    http_method_names=['get']
    def get(self,request):
        return page(request,CorrectionRequest.objects.filter(state='OPEN').select_related('item').order_by('created_at','pk'),lambda c:{'id':str(c.pk),'item_id':str(c.item_id),'reason':c.reason,'state':c.state,'created_at':c.created_at})


class CorrectionResolveView(AccountAPIView):
    permission_classes=[IsManager]
    http_method_names=['post']
    def post(self,request,pk):
        result=content.resolve_correction(request,pk,validated(CorrectionInput,request)['reason'])
        return Response({'id':str(result.pk),'state':result.state,'reply':result.reply})


class CapabilitiesView(AccountAPIView):
    http_method_names=['get']
    def get(self,request):return Response({'can_submit':can_submit(request.user),'can_manage':is_manager(request.user),'account_id':request.user.pk})


class ProjectChoicesView(AccountAPIView):
    http_method_names=['get']
    def get(self,request):
        filters(request,{'q'})
        if not can_submit(request.user):return page(request,ContentItem.objects.none(),lambda x:{})
        visible=visible_items(request.user).values('pk')
        qs=ContentItem.objects.filter(kind='PROJECT').filter(Q(pk__in=visible)|Q(published_revision__state='PUBLISHED',visibility_gate=True)).select_related('working_revision','published_revision')
        q=request.query_params.get('q','')
        if len(q)>100:raise ValidationError({'q':'Query too long.'})
        # Search only the title that this actor may see; unpublished project titles
        # never participate in public-only matching.
        from django.db.models import Case,When,CharField
        qs=qs.annotate(safe_title=Case(When(pk__in=visible,working_revision__isnull=False,then=F('working_revision__title')),default=F('published_revision__title'),output_field=CharField()))
        if q:qs=qs.filter(safe_title__icontains=q)
        return page(request,qs.order_by('safe_title','pk'),lambda i:{'id':str(i.pk),'title':i.safe_title or '未命名项目'})


class ModerationHistoryView(AccountAPIView):
    http_method_names=['get']
    def get(self,request,pk):
        item=get_object_or_404(visible_items(request.user),pk=pk)
        return page(request,item.moderation_events.order_by('-created_at','-pk'),lambda e:{'id':e.pk,'action':e.action,'reason':e.reason,'actor':e.actor_snapshot,'created_at':e.created_at})
