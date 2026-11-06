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


def main():
    resource.setrlimit(resource.RLIMIT_AS,(256*1024*1024,256*1024*1024))
    resource.setrlimit(resource.RLIMIT_CPU,(5,5))
    try:
        data=sys.stdin.buffer.read(10*1024*1024+1)
        if len(data)>10*1024*1024:raise ValueError()
        output=clean(sys.argv[1],data)
        if len(output)>10*1024*1024:raise ValueError()
        sys.stdout.buffer.write(output)
    except Exception:
        sys.exit(2)


if __name__=='__main__':main()
