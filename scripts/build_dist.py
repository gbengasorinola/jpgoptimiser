"""Pre-render the working production templates for Cloudflare static assets."""
from __future__ import annotations
import json
import re
import shutil
import sys
from html import escape
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from backend.seo_config import BLOG_ARTICLES, get_all_paths, get_related_links, resolve_seo_data

DIST_DIR = PROJECT_ROOT / 'dist'
DOMAIN = 'https://globeoptimiser.com'
ENV = Environment(loader=FileSystemLoader(PROJECT_ROOT / 'backend/templates'), autoescape=select_autoescape(['html', 'xml']))

def static_body(page):
    source = (PROJECT_ROOT / 'frontend' / f'{page}.html').read_text(encoding='utf-8')
    match = re.search(r'<(article|div)\b[^>]*class="about-card"[^>]*>(.*?)</\1>', source, re.S)
    if not match:
        raise ValueError(f'Missing informational content for {page}')
    return re.sub(r'<h1\b[^>]*>.*?</h1>', '', match.group(2), flags=re.S)

def tool_schema(path, seo):
    crumbs = [{'@type': 'ListItem', 'position': 1, 'name': 'Home', 'item': DOMAIN + '/'}]
    if path:
        crumbs.append({'@type': 'ListItem', 'position': 2, 'name': path.replace('-', ' ').title(), 'item': DOMAIN + '/' + path})
    schemas = [
        {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': crumbs},
        {'@context': 'https://schema.org', '@type': 'SoftwareApplication', 'name': seo['title'], 'operatingSystem': 'All',
         'applicationCategory': 'ImageApplication', 'offers': {'@type': 'Offer', 'price': '0.00', 'priceCurrency': 'USD'}},
    ]
    if seo.get('faqs'):
        schemas.append({'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [
            {'@type': 'Question', 'name': f['q'], 'acceptedAnswer': {'@type': 'Answer', 'text': f['a']}} for f in seo['faqs']
        ]})
    return json.dumps(schemas).replace('</', '<\\/')

def render_page(path):
    if path == 'blog':
        return ENV.get_template('blog_list.html').render(articles=BLOG_ARTICLES, seo_data={
            'title': 'Blog — Image Optimization Insights | globeoptimiser.com',
            'meta_description': 'Image optimisation, formats and web performance insights.',
            'canonical': '/blog', 'active_tab': 'blog'})
    if path.startswith('blog/'):
        slug = path.removeprefix('blog/')
        post = dict(BLOG_ARTICLES[slug])
        paragraphs = [p.strip() for p in post['content'].split('</p>') if p.strip()]
        midpoint = len(paragraphs) // 2
        if midpoint:
            ad = '''<div class="ad-slot ad-in-content" aria-label="Advertisement"><span class="ad-label">Advertisement</span>
<div id="div-gpt-ad-1790268002577-0" style="min-width:200px;min-height:50px">
<script>googletag.cmd.push(function(){googletag.display("div-gpt-ad-1790268002577-0");});</script></div></div>'''
            paragraphs.insert(midpoint, ad)
            post['content'] = ''.join(p if p == ad else p + '</p>' for p in paragraphs)
        seo = {'title': f"{post['title']} | globeoptimiser.com Blog", 'meta_description': post['summary'], 'canonical': '/' + path, 'active_tab': 'blog'}
        schema = {'@context': 'https://schema.org', '@type': 'BlogPosting', 'headline': post['title'], 'description': post['summary'],
                  'datePublished': '2026-07-10', 'author': {'@type': 'Organization', 'name': 'globeoptimiser.com'}}
        return ENV.get_template('blog_post.html').render(post=post, seo_data=seo, schema_json=json.dumps(schema))
    seo = resolve_seo_data(path)
    if not seo:
        raise ValueError(f'No SEO configuration for {path!r}')
    if path in {'about', 'privacy', 'terms', 'contact'}:
        return ENV.get_template('static_page.html').render(seo_data=seo, page_name=path,
            title_header={'about': 'About Us', 'privacy': 'Privacy Policy', 'terms': 'Terms of Use', 'contact': 'Contact Us'}[path],
            subtitle="Have questions or feedback? Drop us a line below and we'll get back to you shortly." if path == 'contact' else '',
            html_content=static_body(path) if path != 'contact' else '')
    return ENV.get_template('tool.html').render(seo_data=seo, related_links=get_related_links(path), schema_json=tool_schema(path, seo))

def main():
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir()
    paths = sorted(set(['', 'blog', *get_all_paths()]))
    for path in paths:
        target = DIST_DIR / path / 'index.html'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('\n'.join(line.rstrip() for line in render_page(path).splitlines()) + '\n', encoding='utf-8')
    shutil.copytree(PROJECT_ROOT / 'images', DIST_DIR / 'images')
    for name in ('favicon.png', 'favicon.ico'):
        shutil.copy2(PROJECT_ROOT / 'images/favicon.png', DIST_DIR / name)
    (DIST_DIR / '404.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Page not found | GlobeOptimiser</title><h1>Page not found</h1><p><a href="/">Return to GlobeOptimiser</a></p></html>', encoding='utf-8')
    (DIST_DIR / 'robots.txt').write_text(f'User-agent: *\nAllow: /\n\nSitemap: {DOMAIN}/sitemap.xml\n', encoding='utf-8')
    urls = '\n'.join(f'  <url><loc>{escape(DOMAIN + "/" + path)}</loc></url>' for path in paths)
    (DIST_DIR / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + '\n</urlset>\n', encoding='utf-8')
    print(f'Rendered {len(paths)} styled pages and supporting assets to {DIST_DIR}')

if __name__ == '__main__':
    main()
