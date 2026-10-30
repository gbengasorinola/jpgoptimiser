import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../worker/index.js';

const root = 'https://globeoptimiser.example';
const assets = { fetch: async request => new Response(`asset:${new URL(request.url).pathname}`) };
const env = { ASSETS: assets, API_ORIGIN: 'https://processing.example' };

test('serves assets and the GET contact page without contacting the backend', async () => {
  for (const path of ['/', '/contact', '/contact/', '/images/icon.png', '/blog']) {
    const response = await worker.fetch(new Request(root + path), env);
    assert.equal(await response.text(), `asset:${path}`);
  }
});

test('health works independently of the processing service', async () => {
  const response = await worker.fetch(new Request(root + '/health'), {});
  assert.deepEqual(await response.json(), { status: 'ok', runtime: 'cloudflare-workers' });
  assert.equal(await (await worker.fetch(new Request(root + '/health', { method: 'HEAD' }), {})).text(), '');
});

test('redirects legacy paths and www, preserving query parameters', async () => {
  for (const [from, to] of [['/converter', '/convert-image'], ['/optimiser/', '/']]) {
    const response = await worker.fetch(new Request(root + from + '?utm_source=test'), env);
    assert.equal(response.status, 301);
    assert.equal(response.headers.get('Location'), root + to + '?utm_source=test');
  }
  const response = await worker.fetch(new Request('https://www.globeoptimiser.com/resize-image?x=1'), env);
  assert.equal(response.status, 308);
  assert.equal(response.headers.get('Location'), 'https://globeoptimiser.com/resize-image?x=1');
});

test('proxies original multipart bytes, filename and status without leaking browser credentials', async t => {
  const form = new FormData();
  form.append('images', new File(['sample bytes'], 'sample.png', { type: 'image/png' }));
  form.append('target_width', '320');
  const request = new Request(root + '/resize', { method: 'POST', body: form, headers: {
    Origin: root, Cookie: 'private=value', Authorization: 'Bearer private', 'X-Forwarded-For': '192.0.2.1',
  }});
  const original = await request.clone().arrayBuffer();
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url.toString(), 'https://processing.example/resize');
    assert.deepEqual(options.body, new Uint8Array(original));
    assert.match(options.headers.get('Content-Type'), /^multipart\/form-data; boundary=/);
    for (const name of ['cookie', 'authorization', 'x-forwarded-for']) assert.equal(options.headers.get(name), null);
    assert.equal(options.redirect, 'manual');
    return new Response('processed', { headers: { 'Content-Type': 'image/png', 'Content-Disposition': 'attachment; filename="resized.png"', 'Set-Cookie': 'upstream=secret' } });
  });
  const response = await worker.fetch(request, env);
  assert.equal(await response.text(), 'processed');
  assert.equal(response.headers.get('Content-Disposition'), 'attachment; filename="resized.png"');
  assert.equal(response.headers.get('Set-Cookie'), null);
  assert.equal(response.headers.get('Cache-Control'), 'no-store');
});

test('POST contact reaches backend, while non-API methods are rejected', async t => {
  t.mock.method(globalThis, 'fetch', async url => { assert.equal(url.pathname, '/contact'); return new Response('received'); });
  assert.equal((await worker.fetch(new Request(root + '/contact', { method: 'POST', body: '{}' }), env)).status, 200);
  assert.equal((await worker.fetch(new Request(root + '/', { method: 'POST' }), env)).status, 405);
  assert.equal((await worker.fetch(new Request(root + '/resize'), env)).status, 405);
});

test('blocks missing or recursive backends and foreign origins', async () => {
  for (const API_ORIGIN of [undefined, 'http://processing.example', root, 'https://globeoptimiser.com', 'https://processing.example/path']) {
    const response = await worker.fetch(new Request(root + '/optimize', { method: 'POST', body: 'x' }), { ...env, API_ORIGIN });
    assert.equal(response.status, 503);
    assert.equal((await response.json()).code, 'backend_not_configured');
  }
  assert.equal((await worker.fetch(new Request(root + '/convert', { method: 'POST', body: 'x', headers: { Origin: 'https://foreign.example' } }), env)).status, 403);
});

test('rejects oversized bodies even without content-length', async () => {
  const body = new ReadableStream({ start(controller) { controller.enqueue(new Uint8Array(3 * 1024 * 1024 + 1)); controller.close(); } });
  const request = new Request(root + '/optimize', { method: 'POST', body, duplex: 'half' });
  assert.equal((await worker.fetch(request, env)).status, 413);
});

test('preserves validation errors and reports backend failures instead of successful HTML downloads', async t => {
  for (const [upstream, expected] of [
    [new Response('{"detail":"Invalid file"}', { status: 422, headers: { 'Content-Type': 'application/json' } }), 422],
    [new Response('<h1>Sign in</h1>', { headers: { 'Content-Type': 'text/html' } }), 502],
    [new Response(null, { status: 302, headers: { Location: 'https://sign-in.example' } }), 502],
  ]) {
    const mocked = t.mock.method(globalThis, 'fetch', async () => upstream);
    assert.equal((await worker.fetch(new Request(root + '/convert', { method: 'POST', body: 'x' }), env)).status, expected);
    mocked.mock.restore();
  }
  t.mock.method(globalThis, 'fetch', async () => { throw new Error('offline'); });
  assert.equal((await worker.fetch(new Request(root + '/convert', { method: 'POST', body: 'x' }), env)).status, 502);
});
