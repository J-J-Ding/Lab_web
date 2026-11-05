from .models import MemberProfile


def own_profile(user):
    return MemberProfile.objects.filter(user=user,merged_into__isnull=True).select_related('draft_revision','published_revision').first()
