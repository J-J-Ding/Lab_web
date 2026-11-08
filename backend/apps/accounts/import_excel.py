"""Bounded XLSX parsing; also executable in a resource-limited subprocess."""
import io,json,re,sys,zipfile
from defusedxml.ElementTree import fromstring
from openpyxl import Workbook,load_workbook
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.worksheet.datavalidation import DataValidation

class ImportFileError(ValueError):
    pass


HEADERS=['序号','用户名','初始密码','账号身份','是否启用','姓名']


def template():
    book=Workbook();sheet=book.active;sheet.title='账号导入';sheet.append(HEADERS)
    for cell in sheet[1]:cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='205F9D');cell.alignment=Alignment(horizontal='center')
    sheet.freeze_panes='A2';sheet.auto_filter.ref='A1:F501'
    for col,width in zip('ABCDEF',[10,26,26,18,18,22]):sheet.column_dimensions[col].width=width
    for row in sheet.iter_rows(min_row=2,max_row=501,min_col=2,max_col=6):
        for cell in row:cell.number_format='@'
    for col,formula in [('D','"Teacher,student,custom"'),('E','"正常,已注销"')]:
        rule=DataValidation(type='list',formula1=formula);rule.errorTitle='请选择规定值';rule.error='请使用下拉选项';rule.showErrorMessage=True;sheet.add_data_validation(rule);rule.add(f'{col}2:{col}501')
    info=book.create_sheet('填写说明')
    for line in ['仅在账号导入表填写数据；最多500人、文件2 MiB。','用户名、初始密码按文本填写；密码留空使用系统默认初始密码。','身份Teacher/student/custom；状态正常/已注销；姓名可留空。','已有用户名（含已注销账号）不可复用；整批校验通过后才创建。','说明示例（不要复制为真实账号）：1 | example_student | 留空 | student | 正常 | 示例姓名','请妥善保管包含初始密码的原始Excel，不要上传到公开目录。']:
        info.append([line])
    info.column_dimensions['A'].width=100
    output=io.BytesIO();book.save(output);return output.getvalue()


def parse(raw):
    if not raw or len(raw)>2*1024*1024:raise ImportFileError('文件须大于0且不超过2 MiB。')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries=archive.infolist()
        if len(entries)>200 or len({e.filename for e in entries})!=len(entries) or sum(e.file_size for e in entries)>20*1024*1024:raise ImportFileError('Excel压缩内容超过限制。')
        for entry in entries:
            name=entry.filename
            if entry.flag_bits&1 or entry.file_size>10*1024*1024 or entry.file_size>max(1,entry.compress_size)*500 or '..' in name.split('/') or name.startswith('/'):raise ImportFileError('Excel文件结构不支持。')
            if any(v in name.lower() for v in ('vbaproject','externallinks/','embeddings/','activex/')):raise ImportFileError('不支持宏、外部链接或嵌入文件。')
            if name.endswith(('.xml','.rels')):
                root=fromstring(archive.read(entry))
                if any(node.attrib.get('TargetMode')=='External' for node in root.iter()):raise ImportFileError('不支持外部链接。')
                if name.startswith('xl/worksheets/'):
                    for node in root.iter():
                        tag=node.tag.rsplit('}',1)[-1]
                        if tag in ('mergeCell','f'):raise ImportFileError('不支持公式或合并单元格。')
                        if tag=='row' and int(node.attrib.get('r','0'))>10000:raise ImportFileError('工作表行号超过限制。')
                        if tag=='c' and name=='xl/worksheets/sheet1.xml' and re.sub('[0-9]','',node.attrib.get('r','')) not in list('ABCDEF'):
                            if list(node):raise ImportFileError('数据表仅允许6列。')
    book=load_workbook(io.BytesIO(raw),read_only=True,data_only=False,keep_links=False)
    try:
        if book.sheetnames not in (['账号导入'],['账号导入','填写说明']):raise ImportFileError('工作表须为账号导入，可附填写说明表；请使用系统模板。')
        sheet=book['账号导入'];sheet.reset_dimensions()
        rows=sheet.iter_rows(max_col=7,max_row=10000);first=next(rows)
        if [c.value for c in first[:6]]!=HEADERS or first[6].value is not None:raise ImportFileError('表头须依次为：'+ '、'.join(HEADERS))
        result=[]
        for index,row in enumerate(rows,2):
            values=[cell.value for cell in row]
            if all(v is None or v=='' for v in values):continue
            if values[6] is not None:raise ImportFileError('数据表仅允许6列。')
            if len(result)>=500:raise ImportFileError('每批最多500个非空数据行。')
            errors=[];item={'row':index}
            for key,cell in zip(['serial','username','password','role','status','name'],row[:6]):
                val=cell.value
                if cell.data_type=='f':raise ImportFileError('不支持公式。')
                if key=='serial':item[key]='' if val is None else str(val)[:50];continue
                if val is not None and not isinstance(val,str):errors.append('用户名、密码、身份、状态及姓名须按文本填写。');val=''
                item[key]=val or ''
            if any(len(item[k])>n for k,n in [('username',150),('password',128),('name',150),('role',30),('status',20)]):errors.append('字段长度超过限制。')
            item['errors']=errors;result.append(item)
        if not result:raise ImportFileError('没有待创建的账号。')
        return result
    finally:book.close()


if __name__=='__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024));resource.setrlimit(resource.RLIMIT_CPU,(8,8))
    try:print(json.dumps({'rows':parse(sys.stdin.buffer.read(2*1024*1024+1))},ensure_ascii=False))
    except Exception as exc:
        message=str(exc) if isinstance(exc,ImportFileError) else 'Excel解析失败，请重新下载模板填写。'
        print(json.dumps({'error':message[:200]},ensure_ascii=False));sys.exit(1)
