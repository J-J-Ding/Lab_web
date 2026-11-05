from rest_framework.response import Response
from apps.accounts.views import AccountAPIView,validated
from apps.accounts.serializers import StrictSerializer
from apps.content.selectors import published_for_member
from .selectors import own_profile
from .serializers import DraftInput,draft_data
from . import services


class OwnDraftView(AccountAPIView):
    http_method_names=['get','post','patch']
    def get(self,request):
        profile=own_profile(request.user)
        return Response({'draft':draft_data(profile,profile.draft_revision) if profile else None})
    def post(self,request):
        validated(StrictSerializer,request)
        profile,revision,created=services.initialize_draft(request.user)
        return Response(draft_data(profile,revision),status=201 if created else 200)
    def patch(self,request):
        profile,revision=services.update_draft(request.user,validated(DraftInput,request))
        return Response(draft_data(profile,revision))


class OwnOverviewView(AccountAPIView):
    http_method_names=['get']
    def get(self,request):
        profile=own_profile(request.user)
        return Response({'profile_id':str(profile.pk) if profile else None,
                         'membership_status':profile.membership_status if profile else None,
                         'draft_state':profile.draft_revision.state if profile and profile.draft_revision else None,
                         'has_published_profile':bool(profile and profile.published_revision_id),
                         'published_content_count':published_for_member(profile).count()})
