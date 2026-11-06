"""Single anonymous visibility boundary; never reads a working revision."""
from django.db.models import DateField,Prefetch
from django.db.models.functions import Cast,Coalesce
from apps.members.models import MemberProfile
from .models import ContentItem,ContentProjectLink


def content_queryset():
    fields=['paper','project','award','activity','news','blog','publication','lab_page']
    return ContentItem.objects.filter(visibility_gate=True,published_revision__state='PUBLISHED').select_related(
        'published_revision',*['published_revision__'+f for f in fields]).prefetch_related(
        'published_revision__contributions__contributor__member_profile__published_revision',
        'published_revision__assets__asset',
        Prefetch('published_revision__project_links',queryset=ContentProjectLink.objects.filter(
            target_project__visibility_gate=True,target_project__published_revision__state='PUBLISHED').select_related('target_project__published_revision'))
    ).annotate(public_date=Coalesce('published_revision__paper__publication_date','published_revision__project__start_date',
        'published_revision__award__award_date',Cast('published_revision__activity__starts_at',DateField()),
        'published_revision__news__event_date','published_revision__blog__event_date','published_revision__publication__publication_date',
        Cast('published_revision__created_at',DateField()),output_field=DateField())).order_by('-public_date','id')


def member_queryset():
    return MemberProfile.objects.filter(merged_into__isnull=True,public_visible=True,
        published_revision__state='PUBLISHED',published_revision__public_member_status__in=['ACTIVE','ALUMNI']).select_related(
        'published_revision__avatar_asset','published_revision__alumni').prefetch_related(
        'published_revision__education','published_revision__research_links__area').order_by('published_revision__display_name','id')
