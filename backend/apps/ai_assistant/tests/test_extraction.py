from io import BytesIO
from zipfile import ZipFile,ZIP_DEFLATED
from django.test import SimpleTestCase

class ExtractionTests(SimpleTestCase):
    def docx(self,text):
        from xml.sax.saxutils import escape
        out=BytesIO()
        with ZipFile(out,'w',compression=ZIP_DEFLATED) as z:
            z.writestr('[Content_Types].xml','<Types><Override ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
            z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'+escape(text)+'</w:t></w:r></w:p></w:body></w:document>')
        return out.getvalue()
    def test_text_pages_and_redaction(self):
        from apps.ai_assistant.extractors import extract_bytes,redact
        pages=extract_bytes(self.docx('Example email person@example.org phone 13800138000 and token '+'sk-'+'abcdefghijklmnopqrstuvwx'),'docx')
        text=redact(pages[0]['text']);self.assertIn('Example',text);self.assertNotIn('person@example.org',text);self.assertNotIn('13800138000',text);self.assertNotIn('sk-',text)
    def test_empty_scan_malformed_oversize(self):
        from apps.ai_assistant.extractors import extract_bytes,ExtractionError
        from pypdf import PdfWriter
        out=BytesIO();w=PdfWriter();w.add_blank_page(width=100,height=100);w.write(out)
        for data,kind in [(out.getvalue(),'pdf'),(self.docx(''),'docx'),(b'bad','pdf'),(b'a'*(20*1024*1024+1),'docx')]:
            with self.assertRaises(ExtractionError):extract_bytes(data,kind)
    def test_zip_bomb_and_path_traversal(self):
        from apps.ai_assistant.extractors import extract_bytes,ExtractionError
        for name,text in [('../evil.xml','<x/>'),('word/bomb.xml','<root>'+'x'*2000000+'</root>')]:
            out=BytesIO(self.docx('Real text'))
            with ZipFile(out,'a',compression=ZIP_DEFLATED) as z:z.writestr(name,text)
            with self.assertRaises(ExtractionError):extract_bytes(out.getvalue(),'docx')
    def test_spaced_card_and_formatted_phone_are_removed(self):
        from apps.ai_assistant.extractors import redact
        source='Card 4111 1111 1111 1111; 手机: 138-0013-8000; 电话: 010-12345678'
        clean=redact(source)
        self.assertNotIn('4111',clean);self.assertNotIn('138-',clean);self.assertNotIn('010-',clean)
