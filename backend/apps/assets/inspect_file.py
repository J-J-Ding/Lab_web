"""Bounded child process: parse/clean bytes, never execute document actions."""
from io import BytesIO
import resource
import sys
import warnings


def clean(kind,raw):
    if kind=='avatar':
        from PIL import Image
        Image.MAX_IMAGE_PIXELS=10_000_000
        warnings.simplefilter('error',Image.DecompressionBombWarning)
        with Image.open(BytesIO(raw),formats=['PNG','JPEG','WEBP']) as image:
            if image.width*image.height>10_000_000 or getattr(image,'n_frames',1)!=1:raise ValueError()
            image.load()
            out=BytesIO();image.convert('RGBA').save(out,format='PNG')
            return out.getvalue()
    if kind=='docx':return clean_docx(raw)
    from pypdf import PdfReader,PdfWriter
    reader=PdfReader(BytesIO(raw),strict=True)
    if reader.is_encrypted or len(reader.pages)>100 or len(reader.pages)<1:raise ValueError()
    forbidden={'/JS','/JavaScript','/OpenAction','/AA','/Launch','/EmbeddedFiles','/RichMedia','/AcroForm','/XFA','/Annots','/SubmitForm'}
    seen=set();count=0
    from pypdf.generic import IndirectObject,DictionaryObject,ArrayObject
    def inspect(value,depth=0):
        nonlocal count
        count+=1
        if count>10000 or depth>50:raise ValueError()
        if isinstance(value,IndirectObject):
            key=(value.idnum,value.generation)
            if key in seen:return
            seen.add(key);value=value.get_object()
        if isinstance(value,DictionaryObject):
            if any(str(key) in forbidden for key in value):raise ValueError()
            for child in value.values():inspect(child,depth+1)
        elif isinstance(value,ArrayObject):
            for child in value:inspect(child,depth+1)
    inspect(reader.trailer['/Root'])
    writer=PdfWriter()
    for page in reader.pages:writer.add_page(page)
    out=BytesIO();writer.write(out)
    return out.getvalue()


def clean_docx(raw):
    from zipfile import ZipFile,ZIP_DEFLATED
    from pathlib import PurePosixPath
    import xml.etree.ElementTree as ET
    out=BytesIO()
    with ZipFile(BytesIO(raw)) as z:
        files=z.infolist()
        if len(files)>2000 or len({f.filename for f in files})!=len(files):raise ValueError()
        if sum(f.file_size for f in files)>50*1024*1024:raise ValueError()
        names={f.filename for f in files}
        if not {'[Content_Types].xml','word/document.xml'}<=names:raise ValueError()
        with ZipFile(out,'w',compression=ZIP_DEFLATED) as cleaned:
            for f in files:
                name=f.filename;path=PurePosixPath(name)
                if path.is_absolute() or any(part.strip() in ('.','..','') for part in name.split('/') if not (f.is_dir() and part=='')) or '\\' in name or ':' in name:raise ValueError()
                lower=name.lower()
                if any(x in lower for x in ('vbaproject','activex','embeddings','customui')) or f.flag_bits&1:raise ValueError()
                if f.file_size>20*1024*1024 or f.file_size>max(1,f.compress_size)*100:raise ValueError()
                data=z.read(f)
                if name.endswith(('.xml','.rels')):
                    text=data.decode('utf-8-sig')
                    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():raise ValueError()
                    root=ET.fromstring(text)
                    for e in root.iter():
                        if e.attrib.get('TargetMode','').lower()=='external' or any('macroenabled' in v.lower() or 'oleobject' in v.lower() for v in e.attrib.values()):raise ValueError()
                        if 'Target' in e.attrib:
                            target=e.attrib['Target']
                            if ':' in target or '\\' in target:raise ValueError()
                    if name=='[Content_Types].xml' and b'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml' not in data:raise ValueError()
                elif not f.is_dir():
                    # Non-XML payloads limited to validated raster images, never embedded binaries.
                    if not name.startswith('word/media/') or not lower.endswith(('.png','.jpg','.jpeg','.webp')):raise ValueError()
                    validated=clean('avatar',data)
                    if lower.endswith('.png'):data=validated
                    else:
                        from PIL import Image
                        output=BytesIO()
                        with Image.open(BytesIO(validated)) as image:image.convert('RGB').save(output,format='WEBP' if lower.endswith('.webp') else 'JPEG')
                        data=output.getvalue()
                cleaned.writestr(name,data)
    return out.getvalue()


def main():
    resource.setrlimit(resource.RLIMIT_AS,(256*1024*1024,256*1024*1024))
    resource.setrlimit(resource.RLIMIT_CPU,(5,5))
    try:
        data=sys.stdin.buffer.read(20*1024*1024+1)
        if len(data)>20*1024*1024:raise ValueError()
        output=clean(sys.argv[1],data)
        if len(output)>20*1024*1024:raise ValueError()
        sys.stdout.buffer.write(output)
    except Exception:
        sys.exit(2)


if __name__=='__main__':main()
