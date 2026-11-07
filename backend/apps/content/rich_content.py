"""Bounded, versioned document grammar. Never accepts HTML or resource URLs."""
import json
from uuid import UUID
from urllib.parse import urlsplit
from rest_framework.exceptions import ValidationError


def fail(message='正文格式不支持，请刷新编辑器后重试。'):
    raise ValidationError({'rich_body':message})


def validate_document(value):
    if value is None:return None
    try:
        serialized=json.dumps(value,ensure_ascii=False)
        if len(serialized.encode())>512000:fail('正文数据不能超过500 KiB。')
        value=json.loads(serialized)
    except (TypeError,ValueError,RecursionError,UnicodeError):fail()
    if not isinstance(value,dict) or set(value)!={'version','type','content'} or type(value['version']) is not int or value['version']!=1 or value['type']!='doc':fail()
    count=0;chars=0;images=[]
    children={'doc':{'paragraph','heading','bulletList','orderedList','blockquote','table','image','horizontalRule'},'paragraph':{'text','hardBreak'},'heading':{'text','hardBreak'},'bulletList':{'listItem'},'orderedList':{'listItem'},'listItem':{'paragraph','heading','bulletList','orderedList','blockquote','table','image','horizontalRule'},'blockquote':{'paragraph','heading','bulletList','orderedList','blockquote','table','image','horizontalRule'},'table':{'tableRow'},'tableRow':{'tableCell','tableHeader'},'tableCell':{'paragraph'},'tableHeader':{'paragraph'}}
    def walk(node,depth=0,parent=None):
        nonlocal count,chars
        count+=1
        if count>10000 or depth>12 or not isinstance(node,dict):fail('正文结构过长或嵌套过深。')
        kind=node.get('type')
        if not isinstance(kind,str):fail()
        if kind not in set(children)|{'text','hardBreak','image','horizontalRule'}:fail()
        if parent and kind not in children.get(parent,set()):fail()
        allowed={'type','content','attrs'} if kind in children else {'type','text','marks'} if kind=='text' else {'type','attrs'} if kind=='image' else {'type'}
        if set(node)-allowed:fail()
        attrs=node.get('attrs',{})
        if not isinstance(attrs,dict):fail()
        if kind in ('paragraph','heading'):
            if set(attrs)-({'textAlign','level'} if kind=='heading' else {'textAlign'}):fail()
            if attrs.get('textAlign') not in (None,'left','center','right','justify'):fail()
            if kind=='heading' and (type(attrs.get('level')) is not int or attrs['level'] not in (2,3)):fail()
        elif kind=='orderedList':
            if set(attrs)-{'start','type'} or type(attrs.get('start',1)) is not int or not 1<=attrs.get('start',1)<=10000:fail()
            if attrs.get('type') not in (None,'1','a','A','i','I'):fail()
        elif kind in ('tableCell','tableHeader'):
            if attrs.get('align') not in (None,'left','center','right','justify'):fail()
            if set(attrs)-{'colspan','rowspan','colwidth','align'} or attrs.get('colspan',1)!=1 or attrs.get('rowspan',1)!=1 or attrs.get('colwidth') is not None:fail('表格暂不支持合并单元格或自定义列宽。')
        elif kind=='image':
            if set(attrs)-{'asset_id','width','align','caption'}:fail()
            try:aid=str(UUID(attrs['asset_id']))
            except (ValueError,TypeError,KeyError,AttributeError):fail('正文图片标识无效。')
            if type(attrs.get('width',100)) is not int or attrs.get('width',100) not in (25,50,75,100) or attrs.get('align','center') not in ('left','center','right') or not isinstance(attrs.get('caption',''),str) or len(attrs.get('caption',''))>500:fail()
            attrs['asset_id']=aid
            images.append(aid)
            if len(images)>30:fail('正文最多插入30张图片。')
        elif attrs:fail()
        if kind=='text':
            if not isinstance(node.get('text'),str) or not node['text']:fail()
            chars+=len(node['text'])
            if chars>50000:fail('正文文字不能超过50,000字。')
            marks=node.get('marks',[])
            if not isinstance(marks,list) or len(marks)>5:fail()
            seen=set()
            for mark in marks:
                if not isinstance(mark,dict) or set(mark)-{'type','attrs'}:fail()
                m=mark.get('type')
                if not isinstance(m,str):fail()
                if m not in ('bold','italic','underline','strike','link') or m in seen:fail()
                seen.add(m)
                if m=='link':
                    a=mark.get('attrs',{})
                    if not isinstance(a,dict) or set(a)-{'href','target','rel','class'}:fail()
                    href=a.get('href','')
                    if not isinstance(href,str) or len(href)>2000 or any(ord(c)<33 for c in href):fail()
                    try:p=urlsplit(href)
                    except ValueError:fail()
                    if p.scheme not in ('http','https','mailto') or (p.scheme in ('http','https') and (not p.hostname or p.username or p.password)) or (p.scheme=='mailto' and ('@' not in p.path or p.query)):fail('链接仅支持HTTP、HTTPS或邮箱地址。')
                    if a.get('target') not in (None,'_blank') or a.get('class') is not None or a.get('rel') not in (None,'noopener noreferrer nofollow','noopener noreferrer'):fail()
                elif mark.get('attrs'):fail()
        if kind in children:
            content=node.get('content',[])
            if not isinstance(content,list):fail()
            if kind in ('bulletList','orderedList','listItem','blockquote','tableCell','tableHeader') and not content:fail()
            if kind=='listItem' and (not isinstance(content[0],dict) or content[0].get('type')!='paragraph'):fail()
            if kind=='table' and not 1<=len(content)<=20:fail('表格最多20行。')
            if kind=='tableRow' and not 1<=len(content)<=10:fail('表格最多10列。')
            if kind=='table':
                widths=[]
                for row in content:
                    if not isinstance(row,dict) or not isinstance(row.get('content',[]),list):fail()
                    widths.append(len(row.get('content',[])))
                if len(set(widths))!=1:fail('表格各行列数须一致。')
            for child in content:walk(child,depth+1,kind)
    walk({k:v for k,v in value.items() if k!='version'})
    return value


def image_ids(document):
    ids=set()
    def walk(node):
        if node.get('type')=='image':ids.add(node['attrs']['asset_id'])
        for child in node.get('content',[]):walk(child)
    if document:walk(document)
    return ids
