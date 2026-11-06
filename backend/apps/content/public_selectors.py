"""Single anonymous visibility boundary; never reads a working revision."""
from django.db.models import Prefetch,F,Q
from apps.members.models import MemberProfile
from .models import ContentItem,ContentProjectLink


def published_items_base():
    return ContentItem.objects.filter(visibility_gate=True,visibility_scope='PUBLIC',archived_at__isnull=True,published_revision__state='PUBLISHED')

def content_queryset():
    fields=['paper','project','award','activity','news','blog','publication','lab_page']
    return published_items_base().select_related(
        'published_revision',*['published_revision__'+f for f in fields]).prefetch_related(
        'published_revision__contributions__contributor__member_profile__published_revision',
        'published_revision__contributions__contributor__member_profile__user',
        'published_revision__assets__asset',
        Prefetch('published_revision__project_links',queryset=ContentProjectLink.objects.filter(
            target_project__visibility_gate=True,target_project__visibility_scope='PUBLIC',target_project__archived_at__isnull=True,target_project__published_revision__state='PUBLISHED').select_related('target_project__published_revision'))
    ).annotate(public_date=F('public_sort_date')).order_by('-public_date','id')


def member_queryset():
    return MemberProfile.objects.filter(Q(user__isnull=True)|Q(user__is_active=True,user__role__in=['TEACHER','STUDENT']),merged_into__isnull=True,public_visible=True,
        published_revision__state='PUBLISHED',published_revision__public_member_status__in=['ACTIVE','ALUMNI']).select_related(
        'published_revision__avatar_asset','published_revision__alumni').prefetch_related(
        'published_revision__education','published_revision__research_links__area').order_by('published_revision__display_name','id')
