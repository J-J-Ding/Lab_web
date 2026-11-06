from .models import ContentItem


def published_content():
    return ContentItem.objects.filter(visibility_gate=True,visibility_scope='PUBLIC',archived_at__isnull=True,published_revision__state='PUBLISHED').select_related('published_revision').prefetch_related('published_revision__contributions').order_by('-created_at','id')


def published_for_member(profile):
    if profile is None:
        return published_content().none()
    return published_content().filter(published_revision__contributions__contributor__member_profile=profile).distinct()
