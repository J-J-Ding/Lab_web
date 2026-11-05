from rest_framework.exceptions import ValidationError
from apps.accounts.views import AccountAPIView,UserPagination
from apps.members.selectors import own_profile
from .selectors import published_for_member
from .serializers import public_content
from .types import ContentKind


class ParticipationsView(AccountAPIView):
    http_method_names=['get']
    def get(self,request):
        if set(request.query_params)-{'kind','page','page_size'}:
            raise ValidationError({'detail':'Unsupported filter.'})
        kind=request.query_params.get('kind')
        if kind is not None and kind not in ContentKind.values:
            raise ValidationError({'kind':'Unsupported content kind.'})
        items=published_for_member(own_profile(request.user))
        if kind:
            items=items.filter(kind=kind)
        paginator=UserPagination()
        page=paginator.paginate_queryset(items,request)
        return paginator.get_paginated_response([public_content(item) for item in page])
