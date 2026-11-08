"""Strict workbook schema for deterministic research content import."""
import io,json,sys,zipfile,datetime,re
from defusedxml.ElementTree import fromstring
from openpyxl import Workbook,load_workbook
from openpyxl.styles import Font,PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

COMMON=['序号','标题','摘要','正文','关联成员用户名','成员顺序','关联项目编号','展示范围']
SHEETS={
 '论文':('PAPER',[('doi','DOI'),('venue','期刊或会议'),('publication_date','发表日期'),('category','论文分类'),('volume','卷'),('issue','期'),('pages','页码'),('open_url','公开链接')]),
 '专利':('PATENT',[('patent_number','专利号'),('application_date','申请日期'),('grant_date','授权日期'),('status','专利状态'),('abstract','专利摘要')]),
 '科研项目':('PROJECT',[('project_number','项目编号'),('funder','资助方'),('level','项目级别'),('start_date','开始日期'),('end_date','结束日期'),('status','项目状态')]),
 '竞赛荣誉':('AWARD',[('event_name','赛事名称'),('award_name','奖项'),('award_date','获奖日期'),('category','成果分类'),('level','奖励级别')]),
 '著作':('PUBLICATION',[('isbn','ISBN'),('publisher','出版社'),('publication_date','出版日期'),('edition','版次')])}
KINDS={v[0]:v[1] for v in SHEETS.values()}
ENUMS={'成果分类':{'学科竞赛':'COMPETITION','荣誉奖励':'HONOR'},'项目状态':{'进行中':'ACTIVE','已结项':'COMPLETED','已取消':'CANCELLED'},'专利状态':{'申请中':'APPLIED','已授权':'GRANTED','已失效':'EXPIRED'}}


def template():
 b=Workbook();b.remove(b.active)
 for title,(_,fields) in SHEETS.items():
  s=b.create_sheet(title);s.append(COMMON+[label for _,label in fields]);s.freeze_panes='C2'
  for cell in s[1]:cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='205F9D');s.column_dimensions[cell.column_letter].width=23
  s.column_dimensions['B'].width=40;s.column_dimensions['D'].width=45
  for row in s.iter_rows(min_row=2,max_row=201,min_col=2,max_col=len(COMMON)+len(fields)):
   for cell in row:cell.number_format='@'
  for col,label in enumerate(COMMON+[label for _,label in fields],1):
   choices=['团队可见','公开网站'] if label=='展示范围' else list(ENUMS.get(label,{}))
   if choices:
    dv=DataValidation(type='list',formula1='"'+','.join(choices)+'"');dv.showErrorMessage=True;s.add_data_validation(dv);dv.add(f'{s.cell(1,col).column_letter}2:{s.cell(1,col).column_letter}201')
 info=b.create_sheet('填写说明')
 for line in ['按类型在对应表填写；标题必填，各类型详细字段可逐步补充。合计最多200条，文件2 MiB。','展示范围留空默认团队可见；公开网站必须在最终确认中核对。','关联成员填写有效Teacher/Student登录用户名，英文逗号分隔；成员顺序可填同一组用户名的排列。禁止按姓名猜测。','关联项目填项目编号，英文逗号分隔；支持本批科研项目表中的项目编号，不能循环关联自身。','日期填写YYYY-MM-DD或Excel日期；DOI、专利号、ISBN、用户名按文本填写。','项目状态：进行中/已结项/已取消；专利状态：申请中/已授权/已失效；成果分类：学科竞赛/荣誉奖励。','正文按纯文本导入，不自动导入内嵌图片；创建后可在图文编辑器补充图片。','序号仅作核对；此说明表不是待创建数据，数据表没有实际示例行。']:
  info.append([line])
 info.column_dimensions['A'].width=110;o=io.BytesIO();b.save(o);return o.getvalue()


def parse(raw):
 if not raw or len(raw)>2*1024*1024:raise ValueError('文件不超过2 MiB。')
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  entries=z.infolist()
  if len(entries)>300 or len({e.filename for e in entries})!=len(entries) or sum(e.file_size for e in entries)>24*1024*1024:raise ValueError('工作簿结构超限。')
  for e in entries:
   if '..' in e.filename.split('/') or e.filename.startswith('/') or e.file_size>8*1024*1024 or e.file_size>max(1,e.compress_size)*500 or e.flag_bits&1 or any(x in e.filename.lower() for x in ['vbaproject','externallinks','embeddings/','activex/']):raise ValueError('不支持宏、外部链接或超限压缩内容。')
   if e.filename.endswith(('.xml','.rels')):
    root=fromstring(z.read(e))
    for n in root.iter():
     if n.attrib.get('TargetMode')=='External' or n.tag.rsplit('}',1)[-1] in ('f','mergeCell'):raise ValueError('不支持公式、外部链接或合并单元格。')
     if n.tag.rsplit('}',1)[-1]=='row' and int(n.attrib.get('r','0'))>10000:raise ValueError('工作表行数超限。')
 b=load_workbook(io.BytesIO(raw),read_only=True,data_only=False,keep_links=False)
 try:
  if any(name not in [*SHEETS,'填写说明'] for name in b.sheetnames):raise ValueError('存在未知数据表，请使用规范模板。')
  result=[]
  for title,s in [(name,b[name]) for name in b.sheetnames if name in SHEETS]:
   kind,fields=SHEETS[title];headers=COMMON+[label for _,label in fields]
   from openpyxl.utils.cell import coordinate_from_string,column_index_from_string
   with zipfile.ZipFile(io.BytesIO(raw)) as archive:
    root=fromstring(archive.read(s._worksheet_path))
    for cell in root.iter():
     if cell.tag.rsplit('}',1)[-1]=='c' and list(cell):
      column,_=coordinate_from_string(cell.attrib['r'])
      if column_index_from_string(column)>len(headers):raise ValueError('数据表存在额外非空列。')
   s.reset_dimensions();it=s.iter_rows(max_col=len(headers)+1,max_row=10000);first=next(it)
   if [c.value for c in first[:len(headers)]]!=headers or first[-1].value is not None:raise ValueError(title+'表头不正确。')
   for line,row in enumerate(it,2):
    values=[c.value for c in row]
    if all(v in (None,'') for v in values):continue
    if len(result)>=200:raise ValueError('合计最多200条记录。')
    if values[-1] is not None:raise ValueError(title+'存在额外非空列。')
    def text(value):
     if value is None:return ''
     if isinstance(value,(datetime.datetime,datetime.date)):return value.strftime('%Y-%m-%d')
     if not isinstance(value,(str,int,float)):raise ValueError('字段类型不支持。')
     return str(value).strip()
    for index in [4,5,6]+[i+8 for i,(key,_) in enumerate(fields) if key in ('doi','isbn','project_number','patent_number')]:
     if values[index] is not None and not isinstance(values[index],str):raise ValueError('用户名和标识符必须按文本填写。')
    vals=list(map(text,values));d={key:ENUMS.get(label,{}).get(vals[i+8],vals[i+8]) for i,(key,label) in enumerate(fields) if vals[i+8]}
    scope={'':'TEAM','团队可见':'TEAM','公开网站':'PUBLIC','TEAM':'TEAM','PUBLIC':'PUBLIC'}.get(vals[7],vals[7])
    result.append({'id':str(len(result)+1),'kind':kind,'title':vals[1],'summary':vals[2],'body':vals[3],'authors':re.split('[,，]',vals[4]) if vals[4] else [],'author_order':re.split('[,，]',vals[5]) if vals[5] else [],'project_numbers':re.split('[,，]',vals[6]) if vals[6] else [],'visibility_scope':scope,'detail':d,'evidence':[],'warnings':[],'source_label':title+' 第'+str(line)+'行','reviewed':False,'selected':False})
  if not result:raise ValueError('没有待导入记录。')
  return result
 finally:b.close()


if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,)*2);resource.setrlimit(resource.RLIMIT_CPU,(8,8))
 try:print(json.dumps({'records':parse(sys.stdin.buffer.read(2*1024*1024+1))},ensure_ascii=False))
 except Exception:print(json.dumps({'error':'解析失败：请检查模板表头、公式、外部链接、合并单元格或200条/2 MiB限制。'},ensure_ascii=False));sys.exit(1)
