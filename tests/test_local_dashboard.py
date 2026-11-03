import hashlib
import http.client
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from scripts import local_dashboard as studio
from test_discover_youtube import test_directory

ROOT=Path(__file__).resolve().parents[1]

class StudioTests(unittest.TestCase):
    def setUp(self):
        self.temp=test_directory()
        self.path=Path(self.temp.__enter__())
        self.addCleanup(lambda:self.temp.__exit__(None,None,None))
        self.app=studio.Studio(ROOT,self.path)
        self.candidate={'id':'test-video','title':'Food tour','city_candidate':'Shanghai','comments':{},'synthetic':False}
        self.app.merge({'candidates':[self.candidate],'mode':'live'})
        self.review={'id':'test-video','decision':'approved','name':'Test restaurant','address':'Test street 1','lat':31.2,'lng':121.4,'verified':True,'notes':'Verified source'}

    def test_approval_requires_verification_name_address_and_coordinates(self):
        for key,value in [('verified',False),('name',''),('address',''),('lat',None),('lng','')]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.app.review(dict(self.review,**{key:value}))
        self.assertEqual(self.app.state['reviews'],{})

    def test_invalid_coordinates_rejected(self):
        for value in ['NaN','Infinity',91,True,'not a number']:
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.app.review(dict(self.review,lat=value))

    def test_demo_cannot_publish(self):
        self.app.discover({'city':'Shanghai','demo':True})
        with self.assertRaisesRegex(ValueError,'Demo'):
            self.app.review(dict(self.review,id='shanghai'))

    def test_prepare_excludes_drafts_and_does_not_modify_repository(self):
        before=hashlib.sha256((ROOT/'index.html').read_bytes()).digest()
        with self.assertRaises(ValueError):self.app.prepare()
        self.app.review(dict(self.review,decision='draft'))
        with self.assertRaises(ValueError):self.app.prepare()
        self.app.review(self.review)
        self.assertEqual(self.app.prepare()['count'],1)
        saved=json.loads((self.path/'prepared/approved-places.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['places'][0]['videoUrl'],'https://www.youtube.com/watch?v=test-video')
        self.assertNotIn('verified',saved['places'][0])
        self.assertEqual(before,hashlib.sha256((ROOT/'index.html').read_bytes()).digest())

    def test_reviews_persist_and_rediscovery_preserves_them(self):
        self.app.review(self.review)
        self.app.merge({'candidates':[self.candidate],'mode':'live'})
        restored=studio.Studio(ROOT,self.path)
        self.assertEqual(restored.state['reviews']['test-video']['decision'],'approved')
        self.assertEqual(len(restored.state['candidates']),1)

    def test_catalog_preserves_existing_and_escapes_script_markup(self):
        self.app.review(dict(self.review,name='</script><script>alert(1)</script>'))
        html,places=self.app.prepared()
        self.assertNotIn('</script><script>alert(1)</script>',html)
        self.assertIn('\\u003c/script',html)
        self.assertIn('965e1367-1c14-4935-83e9-4635dc6f39e3',html)
        self.assertNotIn("published-2026-10-25-v13'",html)

    def test_duplicate_restaurant_rejected(self):
        self.app.review(dict(self.review,name='谈灵农家柴爿菜饭'))
        with self.assertRaisesRegex(ValueError,'already exists'):self.app.prepare()

    def test_import_drops_unknown_fields_and_comment_text(self):
        self.app.merge({'candidates':[dict(self.candidate,token='SECRET',comments={'textDisplay':'PRIVATE'})]})
        raw=(self.path/'state.json').read_text(encoding='utf-8')
        self.assertNotIn('SECRET',raw)
        self.assertNotIn('PRIVATE',raw)

    def test_live_discovery_has_fixed_budget(self):
        fixture=studio.discovery.FixtureAPI(studio.discovery.DEFAULT_FIXTURE)
        with patch.object(self.app,'live_request',return_value=fixture),patch.object(studio.discovery,'discover',wraps=studio.discovery.discover) as discover:
            self.app.discover({'city':'Shanghai','demo':False,'max_searches':1000})
            self.assertEqual(discover.call_args.args[1:3],(1,10))

    def test_oauth_errors_do_not_expose_credentials(self):
        self.app.oauth_token=self.path/'token.json'
        self.app.oauth_token.write_text('invalid-secret-value',encoding='utf-8')
        with patch.dict('os.environ',{},clear=True), self.assertRaises(ValueError) as caught:
            self.app.live_request()
        self.assertNotIn('invalid-secret-value',str(caught.exception))

    def test_http_host_origin_csrf_and_static_allowlist(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),studio.handler_for(self.app))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            def request(method,path,body=None,headers=None):
                conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
                conn.request(method,path,body,headers or {})
                response=conn.getresponse();content=response.read();status=response.status;conn.close()
                return status,content
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            conn.request('GET','/map')
            response=conn.getresponse()
            self.assertEqual(response.getheader('Referrer-Policy'),'strict-origin-when-cross-origin')
            self.assertIn(b'https://tile.openstreetmap.org/',response.read())
            conn.close()
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            conn.request('GET','/api/state')
            response=conn.getresponse()
            self.assertEqual(response.getheader('Referrer-Policy'),'no-referrer')
            response.read();conn.close()
            self.assertEqual(request('GET','/')[0],200)
            self.assertEqual(request('GET','/.local/state.json')[0],404)
            self.assertEqual(request('GET','/api/state',headers={'Host':'evil.example'})[0],403)
            self.assertEqual(request('POST','/api/prepare','{}')[0],403)
            headers={'Origin':f'http://127.0.0.1:{server.server_port}','X-CSRF-Token':self.app.csrf}
            self.assertEqual(request('POST','/api/review',json.dumps(self.review),headers)[0],200)
            self.assertEqual(request('POST','/api/prepare','{}',headers)[0],200)
            self.assertEqual(request('GET','/preview')[0],200)
            headers['Origin']='https://evil.example'
            self.assertEqual(request('POST','/api/prepare','{}',headers)[0],403)
        finally:
            server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
