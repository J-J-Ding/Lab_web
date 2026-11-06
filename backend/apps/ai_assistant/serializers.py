from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer,StrictString,StrictBoolean
from apps.members.serializers import StrictInteger
from apps.workflow.serializers import ContributionInput,VersionInput
from .schemas import TARGET_TYPES

class ImportInput(StrictSerializer):
    asset=serializers.UUIDField()
    target_type=serializers.ChoiceField(choices=TARGET_TYPES)
    consent_version=serializers.ChoiceField(choices=['local-v1'])
class SummaryInput(StrictSerializer):
    target_type=serializers.ChoiceField(choices=TARGET_TYPES)
    verified_fields=serializers.DictField()
    consent_version=serializers.ChoiceField(choices=['deepseek-text-v1'])
class ConsentInput(VersionInput):
    consent_version=serializers.ChoiceField(choices=['deepseek-text-v1'])
    text_digest=StrictString(min_length=64,max_length=64)
    selected_text=StrictString(max_length=100000)
class CandidateInput(VersionInput):
    candidate=serializers.DictField()
class MatchInput(ContributionInput):
    index=StrictInteger(min_value=0,max_value=99)
class ApplyInput(VersionInput):
    record_index=StrictInteger(min_value=0,max_value=9)
    confirmed_fields=serializers.ListField(child=StrictString(max_length=100),min_length=1,max_length=40)
    confirm=StrictBoolean()
    target_id=serializers.UUIDField(required=False)
    target_lock_version=StrictInteger(min_value=0,required=False)
    contributor_matches=MatchInput(many=True,max_length=100,required=False,default=list)
    def validate_confirm(self,v):
        if v is not True:raise serializers.ValidationError('请显式确认所选字段。')
        return v
