"""Versioned local form options; region validation never calls external services."""
import json
from pathlib import Path
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from apps.accounts.serializers import StrictSerializer,StrictString
from apps.content.public_views import PublicView
from rest_framework.response import Response

GENDERS=['男','女']
EDUCATION=['小学','初中','高中','中专','专科','本科','硕士研究生','博士研究生','其他']
DEGREES=['无学位','学士','硕士','博士','其他']
POLITICAL=['中共党员','中共预备党员','共青团员','民革党员','民盟盟员','民建会员','民进会员','农工党党员','致公党党员','九三学社社员','台盟盟员','无党派人士','群众']
COUNTRIES={'US':'美国','GB':'英国','CA':'加拿大','AU':'澳大利亚','SG':'新加坡','JP':'日本','KR':'韩国','DE':'德国','FR':'法国','OTHER':'其他国家或地区'}
REGIONS=json.loads((Path(__file__).parent/'data/regions.json').read_text())

class RegionInput(StrictSerializer):
    names=serializers.ListField(read_only=True)
    version=serializers.CharField(read_only=True)
    province=StrictString(max_length=16,allow_blank=True,default='')
    city=StrictString(max_length=16,allow_blank=True,default='')
    district=StrictString(max_length=16,allow_blank=True,default='')
    country=serializers.ChoiceField(choices=['',*COUNTRIES],default='')
    note=StrictString(max_length=100,allow_blank=True,default='')
    def validate(self,attrs):
        province=attrs['province']
        if not province:
            if any(attrs[k] for k in ('city','district','country','note')):raise ValidationError('请先选择籍贯省份或境外。')
            return attrs
        if province=='OVERSEAS':
            if not attrs['country'] or attrs['city'] or attrs['district']:raise ValidationError('请选择国家或地区，境外不填国内城市。')
            return {**attrs,'names':[COUNTRIES[attrs['country']],attrs['note']],'version':REGIONS['version']}
        rows=REGIONS['provinces'];names=[]
        if attrs['country']:raise ValidationError('国内地区不填写境外国家。')
        for field in ('province','city','district'):
            code=attrs[field]
            if not code:
                if field=='city' and attrs['district']:raise ValidationError('请先选择城市。')
                break
            row=next((r for r in rows if r['code']==code),None)
            if not row:raise ValidationError('地区代码与上级地区不匹配。')
            names.append(row['name']);rows=row.get('children',[])
        return {**attrs,'names':names,'version':REGIONS['version']}

class Options(PublicView):
    def get(self,request):return Response({'gender':GENDERS,'education_level':EDUCATION,'degree':DEGREES,'political_status':POLITICAL,'regions':REGIONS,'countries':COUNTRIES})
