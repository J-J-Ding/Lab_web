from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer,StrictString,StrictBoolean
from apps.members.serializers import StrictInteger
from apps.content.types import ContentKind
from apps.content.models import DETAIL_MODELS
from .models import ContributionConfirmation


class VersionInput(StrictSerializer):
    lock_version=StrictInteger(min_value=0)


class DecisionInput(VersionInput):
    decision=serializers.ChoiceField(choices=['APPROVE','REJECT'])
    reason=StrictString(max_length=2000)


class ContributionInput(StrictSerializer):
    contributor=serializers.UUIDField()
    contribution_role=serializers.ChoiceField(choices=['AUTHOR','EDITOR','LEAD','PARTICIPANT','ORGANIZER','WINNER','ADVISOR'])
    position=StrictInteger(min_value=1,max_value=100)
    is_corresponding=StrictBoolean(default=False)


class ContentCreateInput(StrictSerializer):
    kind=serializers.ChoiceField(choices=ContentKind)
    title=StrictString(max_length=500)
    summary=StrictString(max_length=10000,allow_blank=True,default='')
    detail=serializers.DictField(default=dict)
    contributions=ContributionInput(many=True,max_length=100,default=list)


class ContentUpdateInput(VersionInput):
    title=StrictString(max_length=500,required=False)
    summary=StrictString(max_length=10000,allow_blank=True,required=False)
    detail=serializers.DictField(required=False)
    contributions=ContributionInput(many=True,max_length=100,required=False)
    assets=serializers.ListField(child=serializers.UUIDField(),max_length=30,required=False)
    project_links=serializers.ListField(child=serializers.UUIDField(),max_length=30,required=False)


class NewRevisionInput(VersionInput):
    source_revision=serializers.UUIDField(required=False)


class ReasonInput(VersionInput):
    reason=StrictString(max_length=2000)


class ConfirmationInput(StrictSerializer):
    decision=serializers.ChoiceField(choices=['CONFIRMED','DISPUTED'])
    reason=StrictString(max_length=2000,allow_blank=True,default='')


class GrantInput(VersionInput):
    user_id=StrictInteger(min_value=1)
    can_edit=StrictBoolean(default=True)
    revoke=StrictBoolean(default=False)


class CorrectionInput(StrictSerializer):
    reason=StrictString(max_length=2000)


class ContributorInput(StrictSerializer):
    display_name=StrictString(max_length=150)
    external_affiliation=StrictString(max_length=300,allow_blank=True,default='')


def confirmation_info(contribution):
    last=contribution.confirmations.order_by('-created_at','-pk').first()
    return {'confirmation_status':last.decision if last else 'UNCONFIRMED','confirmation_note':last.reason if last else '', 'proxy_confirmed':last.is_proxy if last else False}


def revision_data(revision):
    if revision is None:return None
    detail=getattr(revision,DETAIL_MODELS[revision.item.kind]._meta.get_field('revision').remote_field.related_name)
    data={f.name:getattr(detail,f.name) for f in detail._meta.fields if f.name!='revision'}
    return {'id':str(revision.pk),'number':revision.number,'state':revision.state,'title':revision.title,
            'summary':revision.summary,'base_published_revision':str(revision.base_published_revision_id) if revision.base_published_revision_id else None,
            'detail':data,'assets':[str(x.asset_id) for x in revision.assets.all()],'project_links':[str(x) for x in revision.project_links.values_list('target_project_id',flat=True)],
            'contributions':[{'id':str(c.pk),'contributor':str(c.contributor_id),'name':c.approved_display_name,'affiliation':c.approved_affiliation,'contribution_role':c.contribution_role,'position':c.position,'is_corresponding':c.is_corresponding,**confirmation_info(c)} for c in revision.contributions.all()]}


def item_data(item):
    return {'id':str(item.pk),'kind':item.kind,'created_by':item.created_by_id,'lock_version':item.lock_version,
            'archived':item.archived_at is not None,'visible':item.visibility_gate,
            'working_revision':revision_data(item.working_revision),
            'published_revision':revision_data(item.published_revision)}
