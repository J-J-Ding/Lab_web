from django.utils import timezone
from rest_framework import serializers
from apps.accounts.serializers import StrictSerializer,StrictString,StrictBoolean
from .models import MemberRevision,EducationEntry,AlumniDestination


class StrictInteger(serializers.IntegerField):
    def to_internal_value(self,data):
        if not isinstance(data,int) or isinstance(data,bool):
            self.fail('invalid')
        return super().to_internal_value(data)


class EducationInput(StrictSerializer):
    education_level=serializers.ChoiceField(choices=["","小学","初中","高中","中专","专科","本科","硕士研究生","博士研究生","其他"],required=False)
    school=StrictString(max_length=200,allow_blank=True,required=False,default="")
    major=StrictString(max_length=200,required=False,allow_blank=True,default='')
    degree=StrictString(max_length=100,required=False,allow_blank=True,default='')
    start_date=serializers.DateField(required=False,allow_null=True,default=None)
    end_date=serializers.DateField(required=False,allow_null=True,default=None)
    is_public=StrictBoolean(required=False,default=False)
    position=StrictInteger(min_value=1,max_value=100)
    def validate(self,attrs):
        if attrs['start_date'] and attrs['end_date'] and attrs['start_date']>attrs['end_date']:
            raise serializers.ValidationError('End date must follow start date.')
        return attrs


class AlumniInput(StrictSerializer):
    graduation_year=StrictInteger(min_value=1900)
    degree=StrictString(max_length=100,required=False,allow_blank=True,default='')
    destination_type=serializers.ChoiceField(choices=['WORK','STUDY','OTHER'])
    organization=StrictString(max_length=200,required=False,allow_blank=True,default='')
    is_public=StrictBoolean(required=False,default=False)
    def validate_graduation_year(self,value):
        if value>timezone.localdate().year+10:
            raise serializers.ValidationError('Graduation year is too far in the future.')
        return value


class DraftInput(StrictSerializer):
    lock_version=StrictInteger(min_value=0)
    display_name=StrictString(max_length=150,allow_blank=True,required=False)
    slug=serializers.SlugField(max_length=160,allow_unicode=True,allow_blank=True,required=False)
    bio=StrictString(max_length=10000,allow_blank=True,required=False)
    public_contact_email=serializers.EmailField(max_length=254,allow_blank=True,required=False)
    public_contact_enabled=StrictBoolean(required=False)
    avatar_asset=serializers.UUIDField(allow_null=True,required=False)
    education=EducationInput(many=True,required=False,max_length=30)
    research_areas=serializers.ListField(child=StrictString(max_length=100),max_length=30,required=False)
    alumni=AlumniInput(allow_null=True,required=False)
    def validate_education(self,value):
        positions=[v['position'] for v in value]
        if len(positions)!=len(set(positions)):
            raise serializers.ValidationError('Education positions must be unique.')
        return value
    def validate_research_areas(self,value):
        if len({v.casefold() for v in value})!=len(value):
            raise serializers.ValidationError('Research areas must be unique.')
        return value


def draft_data(profile,revision):
    if revision is None:
        return None
    result={f:getattr(revision,f) for f in ('number','display_name','slug','bio','enrollment_year','member_kind','public_member_status','public_contact_email','public_contact_enabled','state')}
    result.update(id=str(revision.pk),lock_version=profile.lock_version,avatar_asset=str(revision.avatar_asset_id) if revision.avatar_asset_id else None)
    result['education']=list(revision.education.values('school','education_level','major','degree','start_date','end_date','is_public','position'))
    result['research_areas']=[link.area.name for link in revision.research_links.select_related('area')]
    alumni=AlumniDestination.objects.filter(revision=revision).values('graduation_year','degree','destination_type','organization','is_public').first()
    result['alumni']=alumni
    consent=getattr(revision,'publication_consent',None)
    result['publication_consent']=({f:getattr(consent,f) for f in ('public_visible','contact_visible','education_visible','alumni_visible')} if consent else None)
    result['consent_current']=not consent or consent.privacy_version==profile.privacy_version
    return result


def public_member(profile):
    """Use the same fixed projection as every public member entry point."""
    from apps.content.public_selectors import member_queryset
    from apps.content.public_serializers import member_data
    if not member_queryset().filter(pk=profile.pk).exists():return None
    return member_data(profile)
