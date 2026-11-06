import re
from django.db import DatabaseError,InterfaceError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from .public_selectors import content_queryset,member_queryset
from .public_serializers import content_data,member_data
from .types import ContentKind


class PublicView(APIView):
    authentication_classes=[]
    permission_classes=[AllowAny]
    http_method_names=['get','head','options']
    def handle_exception(self,exc):
        if isinstance(exc,(DatabaseError,InterfaceError)):return Response({'code':'temporarily_unavailable','detail':'Public service temporarily unavailable.'},status=503)
        return super().handle_exception(exc)
    def finalize_response(self,request,response,*args,**kwargs):
        response=super().finalize_response(request,response,*args,**kwargs)
        # No shared/browser cache: revocation always rechecks the current gate.
        response['Cache-Control']='no-store';response['X-Content-Type-Options']='nosniff'
        return response


class PublicPagination(PageNumberPagination):
    page_size=20;page_size_query_param='page_size';max_page_size=100


def params(request,allowed):
    p=request.query_params
    if set(p)-set(allowed)-{'page','page_size'}:raise ValidationError('Unknown query parameter.')
    for key in p:
        if len(p[key])>(1000 if key=='path' else 100):raise ValidationError({key:'Parameter too long.'})
        if len(p.getlist(key))!=1:raise ValidationError('Duplicate query parameter.')
    if 'q' in p and not 1<=len(p['q'].strip())<=100:raise ValidationError({'q':'Use 1–100 characters.'})
    for key in ('page','page_size'):
        if key in p and (not re.fullmatch(r'[0-9]+',p[key]) or not 1<=int(p[key])<=1000000):raise ValidationError({key:'Positive integer required.'})
    if 'year' in p and (not re.fullmatch(r'[0-9]+',p['year']) or not 1900<=int(p['year'])<=2200):raise ValidationError({'year':'Invalid year.'})
    if 'kind' in p and p['kind'] not in ContentKind.values:raise ValidationError({'kind':'Invalid content kind.'})
    if 'category' in p and len(p['category'])>100:raise ValidationError({'category':'Too long.'})
    return p


def content_filter(qs,p):
    if 'kind' in p:qs=qs.filter(kind=p['kind'])
    if 'year' in p:qs=qs.filter(public_date__year=int(p['year']))
    if 'category' in p:
        term=p['category'];qs=qs.filter(Q(published_revision__paper__category=term)|Q(published_revision__award__category=term)|Q(published_revision__news__category=term)|Q(published_revision__blog__category=term))
    if 'q' in p:
        term=p['q'].strip();qs=qs.filter(Q(published_revision__title__icontains=term)|Q(published_revision__summary__icontains=term)|Q(published_revision__news__body__icontains=term)|Q(published_revision__blog__body__icontains=term)|Q(published_revision__activity__body__icontains=term)|Q(published_revision__lab_page__body__icontains=term))
    return qs


def paged(request,qs,serialize):
    pager=PublicPagination();rows=pager.paginate_queryset(qs,request)
    return pager.get_paginated_response([serialize(r) for r in rows])


def profile_for(slug):return get_object_or_404(member_queryset(),slugs__slug=slug)


class ContentList(PublicView):
    def get(self,request):return paged(request,content_filter(content_queryset(),params(request,{'kind','year','category','q'})),content_data)
class ContentDetail(PublicView):
    def get(self,request,pk):
        params(request,set());return Response(content_data(get_object_or_404(content_queryset(),pk=pk)))
class MemberList(PublicView):
    def get(self,request):
        p=params(request,{'member_kind','direction','status','year','q'});qs=member_queryset()
        if 'member_kind' in p:
            if p['member_kind'] not in ('STUDENT','TEACHER'):raise ValidationError('Invalid member kind.')
            qs=qs.filter(published_revision__member_kind=p['member_kind'])
        if 'status' in p:
            if p['status'] not in ('ACTIVE','ALUMNI'):raise ValidationError('Invalid status.')
            qs=qs.filter(published_revision__public_member_status=p['status'])
        if 'direction' in p:qs=qs.filter(published_revision__research_links__area__name=p['direction']).distinct()
        if 'q' in p:qs=qs.filter(Q(published_revision__display_name__icontains=p['q']))
        if 'year' in p:qs=qs.filter(published_revision__enrollment_year=int(p['year']))
        return paged(request,qs,member_data)
class MemberDetail(PublicView):
    def get(self,request,slug):
        params(request,set());return Response(member_data(profile_for(slug)))
class Achievements(PublicView):
    def get(self,request,slug):
        p=profile_for(slug);qs=content_queryset().filter(published_revision__contributions__contributor__member_profile=p).distinct()
        return paged(request,content_filter(qs,params(request,{'kind','year'})),content_data)
class Outputs(PublicView):
    def get(self,request,pk):
        project=get_object_or_404(content_queryset(),pk=pk,kind='PROJECT')
        qs=content_queryset().filter(published_revision__project_links__target_project=project).distinct()
        return paged(request,content_filter(qs,params(request,{'kind','year'})),content_data)
class Graduates(PublicView):
    def get(self,request):
        p=params(request,{'year','degree','q'});qs=member_queryset().filter(published_revision__public_member_status='ALUMNI')
        if 'year' in p:qs=qs.filter(published_revision__enrollment_year=int(p['year']))
        if 'q' in p:qs=qs.filter(Q(published_revision__display_name__icontains=p['q']))
        if 'degree' in p:qs=qs.filter(published_revision__education__education_level=p['degree']).distinct()
        return paged(request,qs,member_data)
class FixedPage(PublicView):
    def get(self,request,key):
        params(request,set())
        if key not in ('home','about','contact'):
            from rest_framework.exceptions import NotFound
            raise NotFound()
        return Response(content_data(get_object_or_404(content_queryset(),kind='LAB_PAGE',published_revision__lab_page__page_key=key)))

class LegacyResolve(PublicView):
    def get(self,request):
        from .legacy import canonical_path
        from .models import LegacyURLMap
        from rest_framework.exceptions import NotFound
        params(request,{'path'})
        try:path=canonical_path(request.query_params.get('path',''))
        except (ValueError,UnicodeError):raise NotFound() from None
        link=get_object_or_404(LegacyURLMap,path=path)
        if link.item_id:
            item=get_object_or_404(content_queryset(),pk=link.item_id)
            return Response({'type':'content','id':str(item.pk),'url':f'/content.html?id={item.pk}'})
        member=get_object_or_404(member_queryset(),pk=link.member_id)
        from urllib.parse import quote
        return Response({'type':'member','slug':member.published_revision.slug,'url':'/member.html?slug='+quote(member.published_revision.slug,safe='')})
