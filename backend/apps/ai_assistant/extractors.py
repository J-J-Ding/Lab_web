"""Deterministic bounded parsing. Child process receives bytes, not server credentials."""
from io import BytesIO
import json,re,sys,subprocess,os
from pathlib import Path

class ExtractionError(Exception):
    def __init__(self,code):self.code=code;super().__init__(code)

def redact(text):
    text=re.sub(r'(?i)(?:sk-[A-Za-z0-9_-]{12,}|(?:api[_ -]?key|password|密码|密钥)\s*[:=：]\s*\S+)','[敏感凭据已移除]',text)
    text=re.sub(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b','[邮箱已移除]',text)
    text=re.sub(r'(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)','[电话已移除]',text)
    text=re.sub(r'(?<![\w])\d{15,19}[Xx]?(?![\w])','[证件或账号已移除]',text)
    text=re.sub(r'(?i)(?:电话|手机|phone|tel)\s*[:：]\s*[+()\d -]{7,30}','[电话已移除]',text)
    text=re.sub(r'(?<!\d)(?:\d[ -]?){13,19}(?!\d)',lambda m:'[证件或账号已移除]' if 13<=sum(c.isdigit() for c in m[0])<=19 else m[0],text)
    return text

def extract_bytes(raw,kind):
    if len(raw)>20*1024*1024:raise ExtractionError('file_too_large')
    try:
        from apps.assets.inspect_file import clean
        cleaned=clean('docx' if kind=='docx' else 'proof',raw)
        if kind=='pdf':
            from pypdf import PdfReader
            reader=PdfReader(BytesIO(cleaned),strict=True)
            pages=[{'page':i,'text':p.extract_text() or ''} for i,p in enumerate(reader.pages,1)]
        elif kind=='docx':
            from zipfile import ZipFile
            import xml.etree.ElementTree as ET
            with ZipFile(BytesIO(cleaned)) as z:
                root=ET.fromstring(z.read('word/document.xml').decode('utf-8-sig'))
                paragraphs=[''.join(e.itertext()) for e in root.iter() if e.tag.rsplit('}',1)[-1]=='p']
                pages=[{'page':1,'text':'\n'.join(paragraphs)}]
        else:raise ExtractionError('unsupported_document')
        if sum(len(p['text']) for p in pages)>100000:raise ExtractionError('text_too_large')
        if not any(p['text'].strip() for p in pages):raise ExtractionError('ocr_required' if kind=='pdf' else 'empty_document')
        return pages
    except ExtractionError:raise
    except Exception:raise ExtractionError('invalid_document') from None

def extract_asset(asset):
    from django.conf import settings
    root=Path(settings.PRIVATE_MEDIA_ROOT).resolve();source=root/asset.storage_key
    if source.is_symlink():raise ExtractionError('source_unavailable')
    path=source.resolve()
    if path.parent!=root or not path.is_file():raise ExtractionError('source_unavailable')
    try:
        with path.open('rb') as f:raw=f.read(20*1024*1024+1)
        result=subprocess.run([sys.executable,'-m','apps.ai_assistant.extractors','docx' if asset.mime_type.endswith('document') else 'pdf'],input=raw,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=12,env={'PATH':os.defpath,'PYTHONPATH':str(settings.BASE_DIR),'PYTHONDONTWRITEBYTECODE':'1'})
        data=json.loads(result.stdout)
        if result.returncode or 'error' in data:raise ExtractionError(data.get('error','invalid_document'))
        return [{'page':p['page'],'text':redact(p['text'])} for p in data['pages']]
    except ExtractionError:raise
    except Exception:raise ExtractionError('parser_timeout_or_failure') from None

def main():
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(256*1024*1024,256*1024*1024));resource.setrlimit(resource.RLIMIT_CPU,(8,8))
    try:print(json.dumps({'pages':extract_bytes(sys.stdin.buffer.read(20*1024*1024+1),sys.argv[1])},ensure_ascii=False))
    except ExtractionError as exc:print(json.dumps({'error':exc.code}));sys.exit(2)
    except Exception:print(json.dumps({'error':'parser_failure'}));sys.exit(2)
if __name__=='__main__':main()
