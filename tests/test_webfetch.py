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


# Regression: real media pages often exceed the old 450KB cutoff.

def _mock_http_response(monkeypatch, body, *, content_type='text/html; charset=utf-8', declared_size=None, status=200):
    """Mock only the network transport; exercise the actual response reading code."""
    class FakeResponse:
        def __init__(self):
            self.status = status
            self.reads = []
        def getheaders(self):
            headers = [('Content-Type', content_type)]
            if declared_size is not None:
                headers.append(('Content-Length', str(declared_size)))
            return headers
        def read(self, count):
            self.reads.append(count)
            return body[:count]
    response = FakeResponse()
    class FakeConnection:
        def __init__(self, host, port, *, ip): pass
        def request(self, method, path, headers): pass
        def getresponse(self): return response
        def close(self): pass
    monkeypatch.setattr(wf, '_HTTPSConnection', FakeConnection)
    monkeypatch.setattr(wf, 'resolve_public_ip', lambda host, port: '93.184.215.14')
    return response


def test_large_html_accepted_without_content_length(monkeypatch):
    payload = b'<html><head><title>Large Page</title></head><body>' + b'x' * 700_000 + b'</body></html>'
    response = _mock_http_response(monkeypatch, payload)
    status, headers, body = wf._request_once('https://example.com/', max_bytes=wf.MAX_BYTES)
    assert status == 200
    assert body == payload
    assert len(body) > 450_000
    assert 'x-researchflow-partial' not in headers
    assert response.reads == [wf.MAX_BYTES + 1]


def test_enormous_html_is_bounded_and_marked_partial(monkeypatch):
    prefix = b'<html><head><title>Huge Page</title></head><body><h1>Very large</h1>'
    body = prefix + b'x' * (wf.MAX_BYTES + 2000)
    response = _mock_http_response(monkeypatch, body, declared_size=len(body))
    status, headers, output = wf._request_once('https://example.com/', max_bytes=wf.MAX_BYTES)
    assert len(output) == wf.MAX_BYTES
    assert output.startswith(prefix)
    assert headers['x-researchflow-partial'] == '1'
    assert response.reads == [wf.MAX_BYTES + 1]


def test_partial_robots_not_accepted(monkeypatch):
    response = _mock_http_response(monkeypatch, b'User-agent: *\nAllow: /\n' * 20_000,
                                   content_type='text/plain', declared_size=400_000)
    with pytest.raises(wf.FetchError, match='too large'):
        wf._request_once('https://example.com/robots.txt', max_bytes=wf.MAX_ROBOTS_BYTES)
    assert not response.reads  # Do not use a partial robots file.


def test_large_embedded_code_is_removed_and_title_and_jsonld_preserved(monkeypatch):
    html = ('<html><head><title>秋祭りの案内</title>'
            '<script type="application/ld+json">{"@type":"Event","name":"秋祭り","startDate":"2027-01-15"}</script>'
            '<script>' + 'var x="' + 'x' * 600_000 + '";' + '</script>'
            '<style>' + 'a{color:red}' * 6000 + '</style>'
            '</head><body><main><h1>秋祭り</h1><p>開催情報</p></main></body></html>')
    monkeypatch.setattr(wf, '_check_robots', lambda url: None)
    monkeypatch.setattr(wf, '_follow', lambda *args, **kwargs:(200,{'content-type':'text/html; charset=utf-8'},html.encode(),args[0]))
    page=wf.fetch_public_page('https://example.com/huge')
    assert not page.partial
    assert len(page.html) < 300_000
    assert '<script>' not in page.html
    assert 'application/ld+json' in page.html
    records,errors=process_sources([('URL 1',page.html,page.url,'web-url')])
    assert not errors
    assert len(records)==1
    assert records[0].title == '秋祭りの案内'
    assert records[0].event_date == '2027-01-15'


def test_giant_prose_is_processed_as_labeled_partial(monkeypatch):
    html = '<html><head><title>長い記事</title></head><body><article><h1>長い記事</h1>' + '紹介文' * 200_000 + '</article></body></html>'
    monkeypatch.setattr(wf, '_check_robots', lambda url: None)
    monkeypatch.setattr(wf, '_follow', lambda *args, **kwargs:(200,{'content-type':'text/html'},html.encode('utf8'),args[0]))
    page=wf.fetch_public_page('https://example.com/large')
    assert page.partial
    assert len(page.html)<=300_000
    sources,errors=wf.gather_web_sources([page.url],fetcher=lambda url:page)
    assert not errors
    records,parse_errors=process_sources(sources)
    assert not parse_errors
    assert records[0].source_kind == '公開URL（部分取得）'
    assert '先頭部分のみ' in records[0].review_note
    from researchflow.process import to_csv_bytes
    assert '公開URL（部分取得）' in to_csv_bytes(records).decode('utf-8-sig')


def test_truncated_utf8_never_converts_entire_page_to_cp932():
    original=('タイトル' * 500).encode('utf8')
    html=wf._decode(original[:-1],{'content-type':'text/html; charset=utf-8','x-researchflow-partial':'1'},len(original))
    assert html.startswith('タイトルタイトル')
    assert '�' in html


def test_large_redirect_does_not_download_unneeded_body(monkeypatch):
    response = _mock_http_response(monkeypatch, b'x' * 1_000_000,
                                   content_type='text/html', declared_size=1_000_000, status=302)
    status, headers, output = wf._request_once('https://example.com/', max_bytes=wf.MAX_ROBOTS_BYTES)
    assert status == 302
    assert output == b''
    assert response.reads == []


def test_oversized_non_html_still_rejected(monkeypatch):
    _mock_http_response(monkeypatch, b'A' * (wf.MAX_BYTES + 2000),
                        content_type='application/octet-stream', declared_size=wf.MAX_BYTES + 2000)
    with pytest.raises(wf.FetchError, match='too large'):
        wf._request_once('https://example.com/file', max_bytes=wf.MAX_BYTES)
