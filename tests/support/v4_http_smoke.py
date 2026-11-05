"""Real TCP/Session/CSRF V4 smoke against disposable PostgreSQL and loopback API."""
from http.cookiejar import CookieJar
import json
from pathlib import Path
import secrets
import sys
from urllib.error import HTTPError
from urllib.request import build_opener,HTTPCookieProcessor,Request
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'browser'))
from support import Environment


def main():
    env=Environment()
    checks=0
    try:
        env.start()
        jar=CookieJar(); opener=build_opener(HTTPCookieProcessor(jar))
        def call(method,path,data=None,csrf=True):
            headers={'Content-Type':'application/json'}
            if csrf and method!='GET':
                headers['X-CSRFToken']=next(c.value for c in jar if c.name=='csrftoken')
            req=Request(env.url+path,data=json.dumps(data).encode() if data is not None else None,headers=headers,method=method)
            try:
                with opener.open(req,timeout=15) as res:
                    return res.status,json.loads(res.read() or b'{}')
            except HTTPError as exc:
                return exc.code,json.loads(exc.read() or b'{}')
        def status(method,path,expected,data=None,csrf=True):
            nonlocal checks
            code,body=call(method,path,data,csrf)
            assert code==expected,(method,path,code,expected)
            checks+=1
            return body
        status('GET','/api/health/',200)
        status('GET','/api/auth/csrf/',200)
        account={'username':'v4_smoke_'+secrets.token_hex(4),'password':secrets.token_urlsafe(24)+'!7a'}
        body=status('POST','/api/auth/register/',201,account)
        assert body['role']=='CUSTOMER'
        status('POST','/api/auth/login/',200,account)
        assert status('GET','/api/members/me/draft/',200)['draft'] is None
        draft=status('POST','/api/members/me/draft/',201,{})
        assert status('POST','/api/members/me/draft/',200,{})['id']==draft['id']
        status('PATCH','/api/members/me/draft/',400,{'lock_version':0,'role':'ADMIN'})
        changed=status('PATCH','/api/members/me/draft/',200,{'lock_version':0,'display_name':'V4 HTTP test'})
        assert changed['lock_version']==1
        assert status('GET','/api/members/me/draft/',200)['draft']['display_name']=='V4 HTTP test'
        status('PATCH','/api/members/me/draft/',409,{'lock_version':0,'bio':'stale'})
        status('PATCH','/api/members/me/draft/',403,{'lock_version':1,'bio':'missing CSRF'},csrf=False)
        assert status('GET','/api/members/me/overview/',200)['published_content_count']==0
        assert status('GET','/api/content/participations/',200)['count']==0
        status('POST','/api/auth/logout/',204,{})
        status('GET','/api/members/me/draft/',403)
        result=env.orm("from apps.members.models import MemberProfile; u=User.objects.get(username=data['username']); p=MemberProfile.objects.get(user=u); result={'role':u.role,'profiles':MemberProfile.objects.filter(user=u).count(),'version':p.lock_version}",{'username':account['username']})
        assert result=={'role':'CUSTOMER','profiles':1,'version':1}
        print(f'PASS: {checks} real HTTP assertions; CUSTOMER, one profile, version persisted; no production data used.')
    finally:
        env.close()


if __name__=='__main__':
    main()
