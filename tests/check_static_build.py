"""Validate generated routes, browser script syntax, and local asset references."""
import json
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.current = None
        self.styles = 0
        self.references = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'style':
            self.styles += 1
        if tag == 'script':
            self.current = '' if not attrs.get('src') and attrs.get('type', '') not in {'application/ld+json', 'module'} else None
        if tag in {'a', 'img', 'script', 'link'}:
            reference = attrs.get('href') if tag in {'a', 'link'} else attrs.get('src')
            if reference:
                self.references.append(reference)
    def handle_data(self, data):
        if self.current is not None:
            self.current += data
    def handle_endtag(self, tag):
        if tag == 'script' and self.current is not None:
            self.scripts.append(self.current)
            self.current = None

pages = list(DIST.rglob('*.html'))
assert len(pages) > 100, 'Build all SEO and blog pages, not just legacy frontend files'
scripts = []
for path in pages:
    html = path.read_text()
    if path.name == '404.html':
        continue
    page = Page()
    page.feed(html)
    assert page.styles >= 2, f'{path}: shared and page styles missing'
    assert ':root' in html and '--surface:' in html, f'{path}: missing shared CSS'
    assert '{%' not in html and '{{' not in html, f'{path}: unrendered template'
    assert 'ad-sidebar' not in html and 'globeoptimiser_sidebar' not in html, f'{path}: sidebar ads returned'
    for reference in page.references:
        url = urlsplit(reference)
        if url.scheme or url.netloc or not url.path.startswith('/'):
            continue
        local = url.path.lstrip('/')
        if local in {'converter', 'optimiser'}:
            continue
        assert (DIST / local).is_file() or (DIST / local / 'index.html').is_file(), f'{path}: broken local reference {reference}'
    scripts.extend({'page': str(path.relative_to(DIST)), 'source': source} for source in page.scripts)
result = subprocess.run(['node', '--input-type=commonjs', '-e', '''
const fs = require('fs'), vm = require('vm');
for (const item of JSON.parse(fs.readFileSync(0, 'utf8'))) {
  try { new vm.Script(item.source, {filename: item.page}); }
  catch (error) { console.error(error); process.exit(1); }
}
'''], input=json.dumps(scripts), text=True)
assert result.returncode == 0, 'Generated inline JavaScript is invalid'
for node in ElementTree.fromstring((DIST / 'sitemap.xml').read_text()).iter():
    if node.tag.endswith('}loc'):
        path = urlsplit(node.text).path.lstrip('/')
        assert (DIST / path / 'index.html').is_file(), f'Sitemap references missing page {path}'
print(f'Passed: {len(pages)} generated pages, {len(scripts)} inline scripts, local links/assets and sitemap.')
