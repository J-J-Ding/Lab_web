from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer,StrictString,StrictBoolean
from apps.members.serializers import StrictInteger
from .serializers import VersionInput,DecisionInput


class ApplicationInput(StrictSerializer):
    application_kind=serializers.ChoiceField(choices=['STUDENT','TEACHER'])
    target_profile=serializers.UUIDField(required=False,allow_null=True,default=None)
    proof_asset=serializers.UUIDField(required=False,allow_null=True,default=None)
    statement=StrictString(max_length=2000)


class MemberSubmitInput(VersionInput):
    public_visible=StrictBoolean(default=False)
    contact_visible=StrictBoolean(default=False)
    education_visible=StrictBoolean(default=False)
    alumni_visible=StrictBoolean(default=False)


class RestrictInput(StrictSerializer):
    scopes=serializers.ListField(child=serializers.ChoiceField(choices=['public','contact','education','alumni']),min_length=1,max_length=4)


class CatalogInput(StrictSerializer):
    display_name=StrictString(max_length=150)
    member_kind=serializers.ChoiceField(choices=['STUDENT','TEACHER'],default='STUDENT')


class BindInput(StrictSerializer):
    user_id=StrictInteger(min_value=1)


def application_data(application):
    return {'id':str(application.pk),'application_kind':application.application_kind,
            'target_profile':str(application.target_profile_id) if application.target_profile_id else None,
            'proof_asset':str(application.proof_asset_id) if application.proof_asset_id else None,
            'statement':application.statement,'state':application.state,'lock_version':application.lock_version,
            'review_note':application.review_note,'created_at':application.created_at}


class ApplicationDecisionInput(DecisionInput):
    use_applicant_fields=StrictBoolean(default=False)
