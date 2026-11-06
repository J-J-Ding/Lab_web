"""Server-owned schemas. Provider JSON is untrusted data, never a permission grant."""
import json
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework.exceptions import ValidationError
from apps.content.models import DETAIL_MODELS
from apps.content.serializers import validate_detail
from apps.members.serializers import DraftInput

TARGET_TYPES=['MEMBER',*DETAIL_MODELS]
MEMBER_FIELDS={'display_name','bio','education','research_areas','alumni'}

def normalize_fields(fields,target):
    if not isinstance(fields,dict) or not fields:raise ValidationError({'fields':'Nonempty field object required.'})
    if target=='MEMBER':
        if set(fields)-MEMBER_FIELDS:raise ValidationError({'fields':'Unknown or forbidden member field.'})
        serializer=DraftInput(data={'lock_version':0,**fields});serializer.is_valid(raise_exception=True)
        values={k:v for k,v in serializer.validated_data.items() if k!='lock_version'}
    else:
        if target not in DETAIL_MODELS or set(fields)-{'title','summary','detail','authors'}:raise ValidationError({'fields':'Unknown or forbidden content field.'})
        values=dict(fields)
        for key,limit in [('title',500),('summary',10000)]:
            if key in fields and (not isinstance(fields[key],str) or len(fields[key])>limit or (key=='title' and not fields[key].strip())):raise ValidationError({key:'Invalid text field.'})
        if 'detail' in fields:values['detail']=dict(validate_detail(target,fields['detail']))
        if 'authors' in fields:
            if not isinstance(fields['authors'],list) or len(fields['authors'])>100:raise ValidationError({'authors':'At most 100 authors.'})
            for author in fields['authors']:
                if not isinstance(author,dict) or set(author)-{'name','affiliation'} or not isinstance(author.get('name'),str) or not 1<=len(author['name'].strip())<=150 or not isinstance(author.get('affiliation',''),str) or len(author.get('affiliation',''))>300:raise ValidationError({'authors':'Names and affiliation only; explicit matching is required.'})
    return json.loads(json.dumps(values,cls=DjangoJSONEncoder))

def paths(fields):
    return [f'detail.{key}' for key in fields.get('detail',{})]+[key for key in fields if key!='detail']

def validate_candidate(data,target,pages,selected_text,human=False,summary=False):
    if not isinstance(data,dict) or set(data)-{'schema_version','target_type','records','warnings'} or data.get('schema_version')!=1 or data.get('target_type')!=target:raise ValidationError('Invalid candidate envelope.')
    records=data.get('records');warnings=data.get('warnings',[])
    if not isinstance(records,list) or not 1<=len(records)<=10 or not isinstance(warnings,list) or len(warnings)>20:raise ValidationError('Use 1–10 candidate records.')
    page_text={p['page']:p['text'] for p in pages}
    normalized=[]
    for record in records:
        if not isinstance(record,dict) or set(record)-{'fields','evidence','uncertain_fields','warnings'}:raise ValidationError('Invalid record fields.')
        fields=normalize_fields(record.get('fields'),target)
        if summary and set(fields)-({'bio'} if target=='MEMBER' else {'summary'}):raise ValidationError('Summary may only suggest bio or summary.')
        available=paths(fields);evidence=record.get('evidence',[]);uncertain=record.get('uncertain_fields',[]);notes=record.get('warnings',[])
        if not isinstance(evidence,list) or len(evidence)>200 or not isinstance(uncertain,list) or set(uncertain)-set(available) or not isinstance(notes,list) or len(notes)>20:raise ValidationError('Invalid evidence or uncertainty list.')
        for item in evidence:
            if not isinstance(item,dict) or set(item)!={'field','page','excerpt'} or item['field'] not in available or isinstance(item['page'],bool) or item['page'] not in page_text or not isinstance(item['excerpt'],str) or not 1<=len(item['excerpt'])<=2000 or item['excerpt'] not in page_text[item['page']] or item['excerpt'] not in selected_text:raise ValidationError('Evidence must quote the selected redacted source page.')
        for field in available:
            value=fields['detail'].get(field.split('.',1)[1]) if field.startswith('detail.') else fields[field]
            if value in ('',None,[],{}):continue
            anchors=[e['excerpt'] for e in evidence if e['field']==field]
            if not anchors and not human:raise ValidationError({'evidence':'Every populated field needs a source reference.'})
            if not anchors or field in ('summary','bio') or (isinstance(value,str) and not any(value in a for a in anchors)):
                uncertain=list(dict.fromkeys([*uncertain,field]))
        for note in [*warnings,*notes]:
            if not isinstance(note,str) or len(note)>500:raise ValidationError('Invalid warning text.')
        normalized.append({'fields':fields,'evidence':evidence,'uncertain_fields':uncertain,'warnings':notes})
    return {'schema_version':1,'target_type':target,'records':normalized,'warnings':warnings}

def prompt_schema(target,summary=False):
    allowed=['bio'] if summary and target=='MEMBER' else ['summary'] if summary else sorted(MEMBER_FIELDS) if target=='MEMBER' else ['title','summary','authors','detail']
    detail=[] if target=='MEMBER' else [f.name for f in DETAIL_MODELS[target]._meta.fields if f.name!='revision']
    return {'schema_version':1,'target_type':target,'records':[{'fields':{key:'use appropriate type; omit unknown values' for key in allowed},'evidence':[{'field':'exact populated field path, e.g. title or detail.venue','page':1,'excerpt':'EXACT quote from selected source'}],'uncertain_fields':[],'warnings':[]}],'warnings':[],'allowed_detail_fields':detail,'member_education_fields':['school','major','degree','start_date','end_date','is_public','position'],'member_alumni_fields':['graduation_year','degree','destination_type','organization','is_public'],'author_fields':['name','affiliation']}
