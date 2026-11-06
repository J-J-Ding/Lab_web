"""Editable, macro-free blue/white academic DOCX, built using native OOXML."""
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from xml.etree import ElementTree as ET
from django.conf import settings
from django.utils import timezone
from PIL import Image
import re

NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing','a':'http://schemas.openxmlformats.org/drawingml/2006/main','pic':'http://schemas.openxmlformats.org/drawingml/2006/picture'}
for prefix,uri in NS.items():ET.register_namespace(prefix,uri)
BLUE='173F6B'
WIDTH=9866

def q(name):
    prefix,local=name.split(':');return '{'+NS[prefix]+'}'+local

def w(parent,name,**attrs):return ET.SubElement(parent,q('w:'+name),{q('w:'+key):str(value) for key,value in attrs.items()})

def paragraph(parent,text='',style='CVBody',keep=None):
    p=w(parent,'p');props=w(p,'pPr');w(props,'pStyle',val=style)
    if keep is not None:w(props,'keepNext',val='1' if keep else '0')
    if text:
        run=w(p,'r')
        for i,line in enumerate(str(text).split('\n')):
            if i:w(run,'br')
            for j,part in enumerate(line.split('\t')):
                if j:w(run,'tab')
                t=w(run,'t');t.set('{http://www.w3.org/XML/1998/namespace}space','preserve');t.text=part
    return p

def joined(*values):return '  |  '.join(str(v).strip() for v in values if v and str(v).strip())

def period(value):
    value=re.sub(r'(\d{4})-(\d{2})-\d{2}',r'\1.\2',str(value or ''))
    return value.strip(' —-')

def photo(profile):
    revision=(profile.published_revision or profile.draft_revision) if profile else None
    asset=revision.avatar_asset if revision and revision.avatar_asset_id else None
    if not asset or asset.purpose!='avatar' or asset.scan_status!='CLEAN' or asset.deletion_requested_at or (asset.expires_at and asset.expires_at<=timezone.now()):return None
    root=Path(settings.PRIVATE_MEDIA_ROOT).resolve();path=root/asset.storage_key
    if path.is_symlink() or path.resolve().parent!=root or not path.is_file() or path.stat().st_size>5*1024*1024:return None
    try:
        with Image.open(path) as im:
            if im.width*im.height>10_000_000:return None
            im.thumbnail((600,800));out=BytesIO();im.convert('RGBA').save(out,format='PNG')
            scale=min(1.0/im.width,1.3/im.height)
            return out.getvalue(),int(im.width*scale*914400),int(im.height*scale*914400)
    except (OSError,ValueError,Image.DecompressionBombError):return None

def picture(parent,cx,cy):
    p=paragraph(parent);w(p.find(q('w:pPr')),'jc',val='right');run=w(p,'r');drawing=w(run,'drawing')
    inline=ET.SubElement(drawing,q('wp:inline'),{'distT':'0','distB':'0','distL':'0','distR':'0'})
    ET.SubElement(inline,q('wp:extent'),{'cx':str(cx),'cy':str(cy)})
    ET.SubElement(inline,q('wp:docPr'),{'id':'1','name':'个人照片','descr':'个人照片'})
    graphic=ET.SubElement(inline,q('a:graphic'));data=ET.SubElement(graphic,q('a:graphicData'),{'uri':NS['pic']});pic=ET.SubElement(data,q('pic:pic'))
    nv=ET.SubElement(pic,q('pic:nvPicPr'));ET.SubElement(nv,q('pic:cNvPr'),{'id':'0','name':'avatar.png'});ET.SubElement(nv,q('pic:cNvPicPr'))
    fill=ET.SubElement(pic,q('pic:blipFill'));ET.SubElement(fill,q('a:blip'),{q('r:embed'):'rIdPhoto'});stretch=ET.SubElement(fill,q('a:stretch'));ET.SubElement(stretch,q('a:fillRect'))
    shape=ET.SubElement(pic,q('pic:spPr'));xf=ET.SubElement(shape,q('a:xfrm'));ET.SubElement(xf,q('a:off'),{'x':'0','y':'0'});ET.SubElement(xf,q('a:ext'),{'cx':str(cx),'cy':str(cy)})
    geom=ET.SubElement(shape,q('a:prstGeom'),{'prst':'rect'});ET.SubElement(geom,q('a:avLst'))

def styles():
    root=ET.Element(q('w:styles'));defaults=w(root,'docDefaults');rp=w(w(defaults,'rPrDefault'),'rPr');w(rp,'rFonts',ascii='Calibri',hAnsi='Calibri',eastAsia='Microsoft YaHei');w(rp,'sz',val=21);w(rp,'color',val='263445')
    pp=w(w(defaults,'pPrDefault'),'pPr');w(pp,'spacing',after=50,line=264,lineRule='auto');w(pp,'widowControl')
    for sid,size,color,bold in [('CVBody',21,'263445',False),('CVName',50,BLUE,True),('CVMeta',20,'52647A',False),('CVSection',24,BLUE,True),('CVEntryTitle',22,'203950',True),('CVFooter',17,'8794A5',False)]:
        st=w(root,'style',type='paragraph',styleId=sid);w(st,'name',val=sid);pr=w(st,'pPr');rpr=w(st,'rPr');w(rpr,'sz',val=size);w(rpr,'color',val=color)
        if bold:w(rpr,'b')
        if sid in ('CVSection','CVEntryTitle'):w(pr,'keepNext');w(pr,'widowControl')
        if sid=='CVName':w(pr,'spacing',after=115,line=300,lineRule='auto')
        if sid=='CVMeta':w(pr,'spacing',after=45)
        if sid=='CVSection':
            w(pr,'spacing',before=170,after=85);border=w(pr,'pBdr');w(border,'bottom',val='single',sz=7,space=4,color=BLUE)
        if sid=='CVEntryTitle':
            w(pr,'spacing',before=60,after=45);tabs=w(pr,'tabs');w(tabs,'tab',val='right',pos=WIDTH-50)
        if sid=='CVFooter':w(pr,'jc',val='center')
    return root

def serialize(root):return ET.tostring(root,encoding='utf-8',xml_declaration=True)

def render(profile,values,blocks,sections,blank_mode=False):
    document=ET.Element(q('w:document'));body=w(document,'body');image=photo(profile);has_photo=bool(image) or blank_mode
    blocks={name:[row for row in rows if any((period(value) if key in ('起止时间','日期') else str(value or '').strip()) for key,value in row.items())] for name,rows in blocks.items()}
    rev=(profile.published_revision or profile.draft_revision) if profile else None
    private=getattr(profile,'private_data',None) if profile else None;cv=private.cv_data if private else {}
    header=w(body,'tbl');props=w(header,'tblPr');w(props,'tblW',w=WIDTH,type='dxa');w(props,'tblLayout',type='fixed');margins=w(props,'tblCellMar')
    for side in ('top','left','bottom','right'):w(margins,side,w=0,type='dxa')
    grid=w(header,'tblGrid');w(grid,'gridCol',w=WIDTH-1600 if has_photo else WIDTH)
    if has_photo:w(grid,'gridCol',w=1600)
    row=w(header,'tr');w(w(row,'trPr'),'cantSplit');left=w(row,'tc');lp=w(left,'tcPr');w(lp,'tcW',w=WIDTH-1600 if has_photo else WIDTH,type='dxa')
    paragraph(left,values.get('姓名') or '个人简历','CVName')
    identity=joined(getattr(rev,'highest_education',''),str(rev.enrollment_year)+'级' if rev and rev.enrollment_year else '',cv.get('gender'))
    if identity:paragraph(left,identity,'CVMeta')
    contact=joined(values.get('联系电话'),values.get('联系邮箱'))
    if contact:paragraph(left,contact,'CVMeta')
    if values.get('政治面貌'):paragraph(left,'政治面貌：'+values['政治面貌'],'CVMeta')
    if values.get('研究方向') and len(values['研究方向'])<=180:paragraph(left,'研究方向：'+values['研究方向'],'CVMeta')
    if has_photo:
        right=w(row,'tc');rp=w(right,'tcPr');w(rp,'tcW',w=1600,type='dxa');w(rp,'vAlign',val='center')
        if image:picture(right,image[1],image[2])
        else:
            w(rp,'shd',fill='F1F5FA');hint=paragraph(right,'个人照片','CVMeta');w(hint.find(q('w:pPr')),'jc',val='center')
    def section(title):paragraph(body,title,'CVSection')
    def entry(title,date='',subtitle='',lines=()):
        lines=[str(line).strip() for line in lines if line and str(line).strip()]
        if title or period(date):paragraph(body,(title or '')+('\t'+period(date) if period(date) else ''),'CVEntryTitle',keep=bool(subtitle or lines))
        if subtitle:paragraph(body,subtitle,'CVMeta')
        for line in lines:paragraph(body,line)
    if len(values.get('研究方向',''))>180:section('研究方向');paragraph(body,values['研究方向'])
    selected=set(sections)
    education=blocks.get('教育经历',[]) if '教育经历' in selected else []
    if education:
        section('教育背景')
        for row in education:entry(row.get('学校'),row.get('起止时间'),row.get('专业及学位'))
    projects=blocks.get('项目经历',[]) if '项目经历' in selected else []
    if projects:
        section('科研项目')
        for row in projects:
            role=row.get('本人角色','')
            for code,label in [('PARTICIPANT','项目成员'),('LEAD','项目负责人'),('ADVISOR','指导教师'),('WINNER','参赛成员')]:role=role.replace(code,label)
            entry(row.get('项目名称'),row.get('起止时间'),role,[('项目简介：'+row['项目概要']) if row.get('项目概要') else '',('本人工作：'+row['本人职责与成果']) if row.get('本人职责与成果') else ''])
    papers=blocks.get('论文',[]) if '论文' in selected else []
    patents=blocks.get('专利',[]) if '专利' in selected else []
    if papers or patents:
        section('论文与专利')
        for i,row in enumerate(papers,1):entry('['+str(i)+'] '+row.get('论文题目',''),'',row.get('作者署名'),[joined(row.get('期刊或会议'),row.get('年份'),row.get('DOI或链接'))])
        for row in patents:entry(row.get('专利名称'),'',row.get('发明人'),[joined(row.get('专利号'),row.get('状态及日期'))])
    competitions=blocks.get('学科竞赛',[]) if '学科竞赛' in selected else []
    if competitions:
        section('学科竞赛')
        for row in competitions:entry(row.get('赛事或作品名称'),row.get('日期'),row.get('奖项与级别'),[row.get('赛事概要'),('本人工作：'+row['本人职责']) if row.get('本人职责') else ''])
    for name in ('实习经历','实践经历'):
        rows=blocks.get(name,[]) if name in selected else []
        if rows:
            section(name)
            for row in rows:entry(row.get('单位及部门') or row.get('组织与职务'),row.get('起止时间'),row.get('岗位'),[row.get('项目内容') or row.get('工作内容及成效')])
    honors=blocks.get('荣誉奖项',[]) if '荣誉奖项' in selected else []
    if honors:
        section('荣誉奖项')
        for row in honors:entry(row.get('荣誉名称'),row.get('年份'))
    if values.get('技能简介'):section('专业技能');paragraph(body,values['技能简介'])
    sect=w(body,'sectPr');w(sect,'footerReference',type='default').set(q('r:id'),'rIdFooter');w(sect,'pgSz',w=11906,h=16838);w(sect,'pgMar',top=900,bottom=900,left=1020,right=1020,header=360,footer=420,gutter=0)
    footer=ET.Element(q('w:ftr'));p=paragraph(footer,'','CVFooter');field=w(p,'fldSimple',instr='PAGE');w(w(field,'r'),'t').text='1'
    relns='http://schemas.openxmlformats.org/package/2006/relationships';rels=ET.Element('Relationships',{'xmlns':relns})
    for rid,typ,target in [('rIdStyles','styles','styles.xml'),('rIdFooter','footer','footer1.xml')]+([('rIdPhoto','image','media/avatar.png')] if image else []):ET.SubElement(rels,'Relationship',{'Id':rid,'Type':NS['r']+'/'+typ,'Target':target})
    package=ET.Element('Relationships',{'xmlns':relns});ET.SubElement(package,'Relationship',{'Id':'rIdDocument','Type':NS['r']+'/officeDocument','Target':'word/document.xml'})
    ct='http://schemas.openxmlformats.org/package/2006/content-types';types=ET.Element('Types',{'xmlns':ct})
    for ext,typ in [('rels','application/vnd.openxmlformats-package.relationships+xml'),('xml','application/xml')]+([('png','image/png')] if image else []):ET.SubElement(types,'Default',{'Extension':ext,'ContentType':typ})
    for name,kind in [('document','document.main'),('styles','styles'),('footer1','footer')]:ET.SubElement(types,'Override',{'PartName':'/word/'+name+'.xml','ContentType':'application/vnd.openxmlformats-officedocument.wordprocessingml.'+kind+'+xml'})
    out=BytesIO()
    with ZipFile(out,'w',ZIP_DEFLATED) as z:
        for name,root in [('word/document.xml',document),('word/styles.xml',styles()),('word/footer1.xml',footer),('word/_rels/document.xml.rels',rels),('_rels/.rels',package),('[Content_Types].xml',types)]:z.writestr(name,serialize(root))
        if image:z.writestr('word/media/avatar.png',image[0])
    return out.getvalue()


def blank():
    return render(None,{'姓名':'姓名','联系电话':'联系电话','联系邮箱':'联系邮箱','研究方向':'研究方向'}, {'教育经历':[{'学校':'学校名称','专业及学位':'专业 · 学历 · 学位','起止时间':'起止年月'}],'项目经历':[{'项目名称':'项目名称','本人角色':'本人角色','项目概要':'研究目标与主要工作','本人职责与成果':'本人承担的工作与取得的成果'}],'论文':[{'论文题目':'论文题目','作者署名':'作者署名','期刊或会议':'期刊 / 会议','年份':'年份'}],'荣誉奖项':[{'荣誉名称':'荣誉名称','年份':'年份'}]},['教育经历','项目经历','论文','荣誉奖项'],blank_mode=True)
