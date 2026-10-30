const PROCESSING_PATHS = new Set(['/optimize', '/resize', '/process', '/convert', '/contact']);
const MAX_REQUEST_BYTES = 3 * 1024 * 1024;
const REDIRECTS = new Map([['/converter', '/convert-image'], ['/optimiser', '/']]);

function jsonError(status, code, message) {
  return Response.json({ code, message, detail: message }, {
    status, headers: { 'Cache-Control': 'no-store' },
  });
}

async function readBoundedBody(request) {
  if (Number(request.headers.get('Content-Length')) > MAX_REQUEST_BYTES) return null;
  if (!request.body) return new Uint8Array();
  const reader = request.body.getReader();
  const chunks = [];
  let length = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > MAX_REQUEST_BYTES) { await reader.cancel(); return null; }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  const body = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength; }
  return body;
}

async function proxyProcessing(request, env, url) {
  if (request.method !== 'POST') return new Response('Method not allowed', { status: 405, headers: { Allow: 'POST' } });
  const origin = request.headers.get('Origin');
  if (origin && origin !== url.origin) return jsonError(403, 'invalid_origin', 'Use the tool on this website to submit files.');
  let upstream;
  try {
    upstream = new URL(env.API_ORIGIN);
    const ownHosts = new Set([url.hostname, 'globeoptimiser.com', 'www.globeoptimiser.com', 'globeoptimiser.sorinolag.workers.dev']);
    if (upstream.protocol !== 'https:' || upstream.username || upstream.password || upstream.search || upstream.hash || upstream.pathname !== '/' || ownHosts.has(upstream.hostname)) throw new Error('Invalid backend origin');
  } catch {
    return jsonError(503, 'backend_not_configured', 'File processing is temporarily unavailable. Please try again later.');
  }
  const body = await readBoundedBody(request);
  if (body === null) return jsonError(413, 'request_too_large', 'The complete upload must be smaller than 3 MiB.');
  upstream.pathname = url.pathname;
  // Do not forward browser cookies, authorisation or visitor IP headers.
  const headers = new Headers();
  const contentType = request.headers.get('Content-Type');
  if (contentType) headers.set('Content-Type', contentType);
  try {
    const response = await fetch(upstream, { method: 'POST', headers, body, redirect: 'manual', signal: AbortSignal.timeout(120_000) });
    if (response.status >= 300 && response.status < 400) return jsonError(502, 'backend_redirect', 'The processing service could not complete this request.');
    if (response.ok && (response.headers.get('Content-Type') ?? '').includes('text/html')) return jsonError(502, 'unexpected_backend_response', 'The processing service returned an unexpected response.');
    const resultHeaders = new Headers({ 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' });
    for (const name of ['Content-Type', 'Content-Disposition', 'Content-Length']) {
      const value = response.headers.get(name);
      if (value) resultHeaders.set(name, value);
    }
    return new Response(response.body, { status: response.status, headers: resultHeaders });
  } catch {
    return jsonError(502, 'backend_unavailable', 'The processing service is temporarily unavailable. Please try again later.');
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.hostname === 'www.globeoptimiser.com') {
      url.hostname = 'globeoptimiser.com';
      return Response.redirect(url.toString(), 308);
    }
    const path = url.pathname.replace(/\/+$/, '') || '/';
    if (path === '/health' && ['GET', 'HEAD'].includes(request.method)) return new Response(request.method === 'HEAD' ? null : JSON.stringify({ status: 'ok', runtime: 'cloudflare-workers' }), {
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
    });
    if (PROCESSING_PATHS.has(path) && (path !== '/contact' || !['GET', 'HEAD'].includes(request.method))) {
      const target = new URL(request.url); target.pathname = path;
      return proxyProcessing(request, env, target);
    }
    if (!['GET', 'HEAD'].includes(request.method)) return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET, HEAD' } });
    if (REDIRECTS.has(path)) { url.pathname = REDIRECTS.get(path); return Response.redirect(url.toString(), 301); }
    return env.ASSETS.fetch(request);
  },
};
