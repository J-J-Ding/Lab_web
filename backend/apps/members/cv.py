"""Fill the reviewed, server-owned OOXML template; no uploaded templates or remote assets."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import re
from zipfile import ZipFile,ZIP_DEFLATED
from xml.etree import ElementTree as ET
from django.db import transaction
from django.http import HttpResponse
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied,ValidationError
from rest_framework.response import Response
from apps.accounts.serializers import StrictSerializer,StrictBoolean
from apps.workflow.api import BusinessAPIView
from apps.workflow.audit import record
from apps.content.models import DETAIL_MODELS
from apps.content.direct_services import readable
from .direct import get_profile,profile_data

VERSION='v12.1'
TEMPLATE=Path(__file__).parent/'templates/cv-v12.docx'
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
ET.register_namespace('w',W[1:-1])
SECTIONS=['教育经历','实习经历','项目经历','论文','专利','学科竞赛','实践经历','荣誉奖项']


def own(request):
    if request.user.role not in ('TEACHER','STUDENT') or request.user.is_superuser:raise PermissionDenied('Team CV generation is available to Teacher and Student.')
    actor,profile=get_profile(request)
    items=readable(actor).filter(deleted_at__isnull=True,archived_at__isnull=True,visibility_gate=True,published_revision__state='PUBLISHED',published_revision__contributions__contributor__member_profile=profile,kind__in=['PAPER','PROJECT','AWARD','PATENT','PUBLICATION']).select_related('published_revision').distinct()
    return actor,profile,items


def achievement(item,profile):
    r=item.published_revision;detail=getattr(r,DETAIL_MODELS[item.kind]._meta.get_field('revision').remote_field.related_name)
    links=list(r.contributions.filter(contributor__member_profile=profile).order_by('position','id'));link=links[0]
    return {'id':str(item.pk),'title':r.title,'kind':item.kind,'visibility_scope':item.visibility_scope,'position':link.position,'role':' / '.join(dict.fromkeys(l.contribution_role for l in links)),'category':getattr(detail,'category','')}


class CVData(BusinessAPIView):
    @transaction.atomic
    def get(self,request):
        actor,profile,items=own(request)
        return Response({'template_version':VERSION,'profile':profile_data(profile,actor),'achievements':[achievement(i,profile) for i in items.order_by('-public_sort_date','id')],'missing_fields':[] if profile.published_revision and profile.published_revision.display_name else ['姓名']})


class CVInput(StrictSerializer):
    item_ids=serializers.ListField(child=serializers.UUIDField(),max_length=100,required=False)
    sections=serializers.ListField(child=serializers.ChoiceField(choices=SECTIONS),max_length=8,required=False)
    include_team=StrictBoolean(default=False)
    template_version=serializers.ChoiceField(choices=[VERSION],default=VERSION)


def text(p):return ''.join(t.text or '' for t in p.iter(W+'t'))


def fill(p,values):
    original=text(p)
    value=re.sub(r'\{\{([^{}]+)\}\}',lambda m:str(values.get(m[1],'')),original)
    ts=list(p.iter(W+'t'))
    if ts:
        ts[0].text=value
        for t in ts[1:]:t.text=''
    return p


def generate(profile,items,sections):
    r=profile.published_revision or profile.draft_revision
    private=getattr(profile,'private_data',None);cv=private.cv_data if private else {}
    values={'姓名':r.display_name if r else '', '联系电话':private.phone if private else '', '联系邮箱':private.internal_contact if private else '', '政治面貌':cv.get('political_status',''),'技能简介':cv.get('skills',''),'研究方向':'、'.join(l.area.name for l in r.research_links.select_related('area')) if r else ''}
    blocks={key:[] for key in SECTIONS}
    if r:
        for e in r.education.all():blocks['教育经历'].append({'起止时间':f'{e.start_date or ""} — {e.end_date or ""}','学校':e.school,'专业及学位':' '.join(filter(None,[e.education_level,e.major,e.degree])),'成绩课程及补充说明':cv.get('education_note','')})
    for key,source in [('实习经历','internships'),('实践经历','practice')]:
        for e in cv.get(source,[]):blocks[key].append({'起止时间':e.get('period') or ' — '.join(filter(None,[e.get('start_date'),e.get('end_date')])),'单位及部门':e.get('organization',''),'岗位':e.get('role',''),'项目内容':e.get('description',''),'组织与职务':' '.join([e.get('organization',''),e.get('role','')]),'工作内容及成效':e.get('description','')})
    for item in items:
        rev=item.published_revision;d=getattr(rev,DETAIL_MODELS[item.kind]._meta.get_field('revision').remote_field.related_name)
        links=list(rev.contributions.filter(contributor__member_profile=profile).order_by('position','id'));link=links[0];roles=' / '.join(dict.fromkeys(l.contribution_role for l in links))
        names='、'.join(c.approved_display_name for c in rev.contributions.order_by('position','id'))
        duty=cv.get('responsibilities',{}).get(str(item.pk),'')
        if item.kind=='PAPER':blocks['论文'].append({'作者署名':names,'论文题目':rev.title,'期刊或会议':d.venue,'年份':d.publication_date.year if d.publication_date else '', 'DOI或链接':d.doi or d.open_url})
        elif item.kind=='PATENT':blocks['专利'].append({'发明人':names,'专利名称':rev.title,'专利号':d.patent_number,'状态及日期':f'{d.get_status_display()} {d.grant_date or d.application_date or ""}'})
        elif item.kind=='PROJECT':blocks['项目经历'].append({'起止时间':f'{d.start_date or ""} — {d.end_date or ""}','项目名称':rev.title,'本人角色':roles,'项目概要':rev.summary,'本人职责与成果':duty})
        elif item.kind=='AWARD':
            if d.category=='HONOR':blocks['荣誉奖项'].append({'荣誉名称':rev.title,'年份':d.award_date.year if d.award_date else ''})
            else:blocks['学科竞赛'].append({'日期':d.award_date or '', '赛事或作品名称':d.event_name or rev.title,'本人角色':roles,'赛事概要':rev.summary,'本人职责':duty,'奖项与级别':' '.join([d.award_name,d.level])})
        elif item.kind=='PUBLICATION':blocks['论文'].append({'作者署名':names,'论文题目':rev.title,'期刊或会议':d.publisher,'年份':d.publication_date.year if d.publication_date else '', 'DOI或链接':d.isbn})
    src=ZipFile(TEMPLATE);root=ET.fromstring(src.read('word/document.xml'));body=root.find(W+'body');children=list(body)
    output=[];i=0
    while i<len(children):
        p=children[i];value=text(p)
        if value.startswith('{{#'):
            name=value[3:-2];j=i+1
            while j<len(children) and text(children[j])!='{{/'+name+'}}':j+=1
            for row in blocks.get(name,[]) if name in sections else []:
                for original in children[i+1:j]:
                    result=fill(deepcopy(original),row)
                    # Omit empty optional lines and their label.
                    fields=re.findall(r'\{\{([^{}]+)\}\}',text(original))
                    if fields and not any(row.get(f) for f in fields):continue
                    output.append(result)
            i=j+1;continue
        headings={'教育背景':['教育经历'],'实习经历':['实习经历'],'项目经历':['项目经历'],'论文与专利':['论文','专利'],'学科竞赛':['学科竞赛'],'实践经历':['实践经历'],'荣誉奖项':['荣誉奖项']}
        if value in headings and not any(blocks[k] and k in sections for k in headings[value]):i+=1;continue
        fields=re.findall(r'\{\{([^{}]+)\}\}',value)
        if not fields or any(values.get(f) for f in fields):output.append(fill(deepcopy(p),values))
        i+=1
    body[:]=output
    buf=BytesIO()
    with ZipFile(buf,'w',ZIP_DEFLATED) as target:
        for entry in src.infolist():
            if entry.filename=='word/document.xml':target.writestr(entry,ET.tostring(root,encoding='utf-8',xml_declaration=True))
            else:target.writestr(entry,src.read(entry.filename))
    return buf.getvalue()


class GenerateCV(BusinessAPIView):
    @transaction.atomic
    def post(self,request):
        actor,profile,qs=own(request)
        s=CVInput(data=request.data);s.is_valid(raise_exception=True);options=s.validated_data
        ids=options.get('item_ids')
        items=list(qs.filter(visibility_scope='PUBLIC').order_by('-public_sort_date','id')) if ids is None else list(qs.filter(pk__in=ids))
        if ids is not None:
            if len(ids)!=len(set(ids)) or len(items)!=len(ids):raise ValidationError({'item_ids':'Select your current available contributions only.'})
            ordered={i.pk:i for i in items};items=[ordered[pk] for pk in ids]
        if any(i.visibility_scope=='TEAM' for i in items) and not options['include_team']:raise ValidationError({'include_team':'Explicitly confirm including selected internal achievements.'})
        content=generate(profile,items,options.get('sections',SECTIONS))
        record(actor,profile,'member.cv.generated',('template:'+VERSION,'items:'+str(len(items))))
        response=HttpResponse(content,content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document');response['Content-Disposition']='attachment; filename="personal-cv.docx"';response['Cache-Control']='no-store';return response


class BlankCV(BusinessAPIView):
    def get(self,request):
        if request.user.role not in ('TEACHER','STUDENT') or request.user.is_superuser:raise PermissionDenied()
        response=HttpResponse(TEMPLATE.read_bytes(),content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document');response['Content-Disposition']='attachment; filename="cv-template.docx"';response['Cache-Control']='no-store';return response
