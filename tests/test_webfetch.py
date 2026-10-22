import socket
import pytest
from researchflow import webfetch as wf
from researchflow.process import process_sources

@pytest.mark.parametrize('bad', [
    'ftp://example.com/file', 'http://localhost:8080/a', 'http://127.0.0.1/latest',
    'http://169.254.169.254/latest/meta-data', 'http://192.168.1.1',
    'https://private.local', 'https://user:pass@example.com/',
    'https://example.com:8080/', 'file:///etc/passwd',
    'https://[::1]/', 'https://example.com/\nHost:evil',
])
def test_public_url_blocked(bad):
    with pytest.raises(wf.FetchError):
        wf.validate_public_url(bad)

def test_public_url_normalization():
    assert wf.validate_public_url(' HTTPS://Example.COM:443/a?b=c#frag ') == 'https://example.com/a?b=c'

def test_public_dns_rejects_mixed_private(monkeypatch):
    def getaddrinfo(*args,**kw):
        return [(socket.AF_INET, socket.SOCK_STREAM,0,'',('93.184.215.14',443)),(socket.AF_INET,socket.SOCK_STREAM,0,'',('10.0.0.3',443))]
    monkeypatch.setattr(wf.socket, 'getaddrinfo',getaddrinfo)
    with pytest.raises(wf.FetchError,match='private'):
        wf.resolve_public_ip('example.com',443)

def test_public_dns_pin(monkeypatch):
    monkeypatch.setattr(wf.socket,'getaddrinfo',lambda *a,**k:[(socket.AF_INET,socket.SOCK_STREAM,0,'',('93.184.215.14',443))])
    assert wf.resolve_public_ip('example.com',443)=='93.184.215.14'

def test_redirect_cannot_reach_loopback(monkeypatch):
    counter=[]
    def request_once(url,*,max_bytes):
        counter.append(url)
        return 302,{'location':'http://127.0.0.1:80/private'},b''
    monkeypatch.setattr(wf,'_request_once',request_once)
    with pytest.raises(wf.FetchError):
        wf._follow('https://www.example.com/a',max_bytes=1000)
    assert len(counter)==1

def test_robots_disallow(monkeypatch):
    monkeypatch.setattr(wf,'_follow',lambda *a,**k:(200,{'content-type':'text/plain'},b'User-agent: *\nDisallow: /\n', 'https://www.example.com/robots.txt'))
    with pytest.raises(wf.FetchError,match='robots.txt'):
        wf._check_robots('https://www.example.com/private')

def test_public_page_fetch_uses_robots_and_checks_type(monkeypatch):
    urls=[]
    def fake_follow(url,*,max_bytes,is_robots=False):
        urls.append(url)
        if url.endswith('robots.txt'):
            return 404,{},b'',url
        return 200,{'content-type':'text/html;charset=utf-8'},'<html><title>公開情報</title></html>'.encode('utf-8'),url
    monkeypatch.setattr(wf,'_follow',fake_follow)
    page=wf.fetch_public_page('https://www.example.com/info')
    assert page.url == 'https://www.example.com/info'
    assert '公開情報' in page.html
    assert len(urls)==2

def test_multi_url_fetch_pipeline(monkeypatch):
    htmls={
        'https://www.example.com/a': '''<html><head><title>カフェ案内</title><meta name="description" content="焼き菓子とコーヒーがあるカフェ"></head><body><h1>カフェ</h1></body></html>''',
        'https://www.example.com/b': '''<html><head><title>秋の催し</title><meta name="description" content="週末マルシェのイベント開催"></head><body><h1>マルシェ</h1></body></html>'''
    }
    def fetcher(url): return wf.FetchedPage(url,htmls[url],200)
    sources, errors=wf.gather_web_sources(['https://www.example.com/a','https://www.example.com/a','https://www.example.com/b'],fetcher=fetcher)
    assert len(sources)==2
    assert len(errors)==1
    records, parse_errors=process_sources(sources)
    assert len(records)==2 and not parse_errors
    assert all(r.source_kind == '公開URL' for r in records)
    assert all(r.url.startswith('https://') for r in records)
    assert all(r.review_status == '要確認' for r in records)


def test_robots_redirect_to_other_domain_is_checked(monkeypatch):
    called=[]
    def get_once(url,*,max_bytes):
        called.append(url)
        if url == 'https://www.example.com/article':
            return 302, {'location':'https://news.example.net/article'}, b''
        return 200,{'content-type':'text/html'},b'hello'
    monkeypatch.setattr(wf,'_request_once',get_once)
    monkeypatch.setattr(wf,'_check_robots',lambda u: called.append('robots:'+u))
    status,headers,body,final=wf._follow('https://www.example.com/article',max_bytes=1000)
    assert final == 'https://news.example.net/article'
    assert 'robots:https://news.example.net/article' in called
