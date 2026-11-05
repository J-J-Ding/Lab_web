from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer
from .models import DETAIL_MODELS


class StrictDetailSerializer(StrictSerializer, serializers.ModelSerializer):
    pass


def validate_detail(kind, data):
    model=DETAIL_MODELS[kind]
    allowed=[f.name for f in model._meta.fields if f.name!='revision']
    meta=type('Meta',(),{'model':model,'fields':allowed})
    cls=type('DetailInput',(StrictDetailSerializer,),{'Meta':meta})
    s=cls(data=data)
    s.is_valid(raise_exception=True)
    return s.validated_data


def public_content(item):
    """Explicit safe projection; never includes internal project funding or drafts."""
    rev=item.published_revision
    return {'id':str(item.pk),'kind':item.kind,'revision':str(rev.pk),
            'title':rev.title,'summary':rev.summary,
            'contributors':[{'name':c.approved_display_name,'affiliation':c.approved_affiliation,
                              'role':c.contribution_role,'position':c.position,'is_corresponding':c.is_corresponding}
                            for c in rev.contributions.all()]}
