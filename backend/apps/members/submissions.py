"""Private, immutable application snapshots with per-recipient notifications."""
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.http import FileResponse
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from apps.accounts.models import User
from apps.accounts.serializers import StrictSerializer, StrictBoolean
from apps.accounts.services import locked_users
from apps.workflow.api import BusinessAPIView
from apps.workflow.audit import record
from apps.assets.services import permitted_asset
from .models import Resume,ResumeSubmission,SubmissionNotification
from .direct import get_profile,profile_data,resume_data


def customer(actor):
    if not actor.is_active or actor.is_superuser or actor.role!='CUSTOMER':raise PermissionDenied('Only Customer may submit resumes.')


def receiver(actor):
    if not actor.is_active or not (actor.is_superuser or actor.role in ('TEACHER','ADMIN')):raise PermissionDenied()


def snapshot(profile,actor):
    data=profile_data(profile,actor)
    allowed=('display_name','highest_education','bio','phone','internal_contact','education','research_areas','public_member_status','cv_private','public_contact_email')
    result={key:data[key] for key in allowed if key in data}
    if 'cv_private' in result:result['cv_private']={k:v for k,v in result['cv_private'].items() if k!='responsibilities'}
    if data.get('public_member_status')=='ALUMNI':result['alumni']=data.get('alumni')
    return json.loads(json.dumps(result,cls=DjangoJSONEncoder))


def data(row,detail=True):
    result={'id':str(row.pk),'state':row.state,'created_at':row.created_at,'withdrawn_at':row.withdrawn_at,'title':row.resume_snapshot.get('title','简历'),'display_name':row.profile_snapshot.get('display_name','访客')}
    if detail:result.update(profile=row.profile_snapshot,resume=row.resume_snapshot,download_url=f'/api/members/resume-inbox/{row.pk}/download/')
    return result


class SubmitInput(StrictSerializer):
    resume_id=serializers.UUIDField()
    consent=StrictBoolean()


class Submissions(BusinessAPIView):
    def get(self,request):
        customer(request.user)
        from apps.content.public_views import paged
        return paged(request,ResumeSubmission.objects.filter(owner=request.user,resume__deleted_at__isnull=True).order_by('-created_at'),lambda row:data(row))

    @transaction.atomic
    def post(self,request):
        actor,_=locked_users(request);customer(actor)
        s=SubmitInput(data=request.data);s.is_valid(raise_exception=True)
        if not s.validated_data['consent']:raise ValidationError({'consent':'Confirm sharing this application with teachers.'})
        resume=get_object_or_404(Resume.objects.select_for_update(),pk=s.validated_data['resume_id'],owner=actor,deleted_at__isnull=True)
        existing=ResumeSubmission.objects.filter(owner=actor,resume=resume,state='SUBMITTED').first()
        if existing:return Response(data(existing),status=200)
        if not resume.asset_id:raise ValidationError({'resume_id':'Upload and save a resume file first.'})
        # Reuse ownership, scan, expiry and filesystem checks; no public URL is created.
        asset,path=permitted_asset(actor,resume.asset_id)
        if asset.purpose!='resume' or asset.visibility!='PRIVATE' or asset.deletion_requested_at:raise ValidationError('Resume file unavailable.')
        _,profile=get_profile(request)
        saved=snapshot(profile,actor)
        if not saved.get('display_name','').strip():raise ValidationError({'display_name':'Save your name in your profile before submitting.'})
        row=ResumeSubmission.objects.create(owner=actor,resume=resume,asset=asset,resume_version=resume.lock_version,profile_snapshot=saved,resume_snapshot={k:v for k,v in resume_data(resume).items() if k in ('title','introduction')})
        recipients=User.objects.filter(is_active=True).filter(Q(is_superuser=True)|Q(role__in=['TEACHER','ADMIN']))
        SubmissionNotification.objects.bulk_create([SubmissionNotification(recipient=u,submission=row) for u in recipients])
        asset.expires_at=None;asset.save(update_fields=['expires_at'])
        record(actor,row,'resume.submitted',('profile_snapshot','resume_snapshot','asset'))
        return Response(data(row),status=201)


class Withdraw(BusinessAPIView):
    @transaction.atomic
    def post(self,request,pk):
        actor,_=locked_users(request);customer(actor)
        s=StrictSerializer(data=request.data);s.is_valid(raise_exception=True)
        row=get_object_or_404(ResumeSubmission.objects.select_for_update(),pk=pk,owner=actor)
        if row.state!='WITHDRAWN':
            row.state='WITHDRAWN';row.withdrawn_at=timezone.now();row.save(update_fields=['state','withdrawn_at'])
            record(actor,row,'resume.withdrawn',('state',))
        return Response(data(row))


class Inbox(BusinessAPIView):
    def get(self,request,pk=None):
        receiver(request.user)
        if request.path.startswith('/api/admin/') and not request.user.is_superuser:raise PermissionDenied()
        rows=ResumeSubmission.objects.filter(resume__deleted_at__isnull=True)
        if not request.user.is_superuser:rows=rows.filter(state='SUBMITTED')
        if pk:
            row=get_object_or_404(rows,pk=pk)
            with transaction.atomic():record(request.user,row,'resume.submission.view',())
            return Response(data(row))
        from apps.content.public_views import paged
        return paged(request,rows.order_by('-created_at'),lambda row:data(row,False))


class SubmissionDownload(BusinessAPIView):
    inline=False
    @transaction.atomic
    def get(self,request,pk):
        actor,_=locked_users(request);receiver(actor)
        rows=ResumeSubmission.objects.select_for_update(of=('self',)).filter(resume__deleted_at__isnull=True)
        if not actor.is_superuser:rows=rows.filter(state='SUBMITTED')
        row=get_object_or_404(rows,pk=pk)
        # Authorization belongs to the submission, never the general asset download route.
        asset,path=permitted_asset(row.owner,row.asset_id)
        record(actor,row,'resume.submission.download',())
        response=FileResponse(path.open('rb'),as_attachment=not (self.inline and asset.mime_type=='application/pdf'),filename='resume.docx' if asset.mime_type.endswith('document') else 'resume.pdf',content_type=asset.mime_type)
        response['Cache-Control']='no-store';response['X-Content-Type-Options']='nosniff';response['Content-Security-Policy']="default-src 'none'; sandbox"
        return response


class Notifications(BusinessAPIView):
    def get(self,request):
        receiver(request.user)
        from apps.content.public_views import paged
        rows=SubmissionNotification.objects.filter(recipient=request.user,submission__resume__deleted_at__isnull=True).select_related('submission').order_by('-created_at')
        response=paged(request,rows,lambda n:{'id':str(n.pk),'read_at':n.read_at,'created_at':n.created_at,'withdrawn':n.submission.state=='WITHDRAWN','display_name':n.submission.profile_snapshot.get('display_name','访客') if n.submission.state=='SUBMITTED' or request.user.is_superuser else '', 'url':f'/submission.html?id={n.submission_id}&notice={n.pk}' if n.submission.state=='SUBMITTED' or request.user.is_superuser else None})
        response.data['unread_count']=rows.filter(read_at__isnull=True).count()
        return response


class ReadNotification(BusinessAPIView):
    @transaction.atomic
    def post(self,request,pk):
        actor,_=locked_users(request);receiver(actor)
        row=get_object_or_404(SubmissionNotification.objects.select_for_update(),pk=pk,recipient=actor)
        if not row.read_at:row.read_at=timezone.now();row.save(update_fields=['read_at'])
        return Response({'id':str(row.pk),'read_at':row.read_at})


class SubmissionPreview(SubmissionDownload):
    inline=True
