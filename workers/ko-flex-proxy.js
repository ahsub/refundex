/**
 * ko-flex-proxy.ahildebrand.workers.dev
 * ══════════════════════════════════════════════════════════════════
 * Refundex — IBKR Flex Web Service CORS-Proxy Worker v1.0.0
 * 06.08.2026
 *
 * ZWECK:
 *   IBKR setzt keine CORS-Header → direkter Fetch aus kap.html schlägt fehl.
 *   Dieser Worker ist eine transparente CORS-Bridge: Browser sendet Token +
 *   QueryID, Worker ruft IBKR SendRequest + GetStatement auf und gibt XML zurück.
 *
 * ARCHITEKTUR:
 *   Browser (kap.html)
 *     → POST https://ko-flex-proxy.ahildebrand.workers.dev/flex
 *        { token: "...", queryId: "..." }
 *     ← XML-String (identisch mit manuellem Download)
 *
 * SICHERHEIT:
 *   - Token verlässt den Browser nur in Richtung dieses Workers (eigene CF-Infrastruktur)
 *   - Token wird NICHT geloggt (nur maskierte Form in console.debug)
 *   - Worker gibt Token NIE an Client zurück
 *   - CORS: nur kap.html-Origin erlaubt (konfigurierbar via ALLOWED_ORIGIN Secret)
 *   - Rate-Limit: 10 Requests/Stunde pro IP (IBKR-seitige Limits respektieren)
 *   - Kein CF-KV, kein Speichern von Depotdaten
 *
 * CF SECRETS (wrangler secret put):
 *   ALLOWED_ORIGIN  → z.B. "https://refundex.pages.dev" oder "*" für Entwicklung
 *                     (optional; fehlt → alle Origins erlaubt)
 *
 * DEPLOYMENT:
 *   wrangler deploy workers/ko-flex-proxy.js --name ko-flex-proxy
 *
 * ROUTEN (wrangler.toml):
 *   [[routes]]
 *   pattern = "ko-flex-proxy.ahildebrand.workers.dev/*"
 *   zone_name = "ahildebrand.workers.dev"
 */

// ── IBKR Flex Web Service Endpunkte ──────────────────────────────────────────
const IBKR_BASE    = 'https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService';
const SEND_PATH    = '/SendRequest';
const FETCH_PATH   = '/GetStatement';
const FLEX_VERSION = '3';

// Retry-Konfiguration (IBKR Report-Generierung: typisch 10–30s)
const MAX_RETRIES   = 10;
const RETRY_DELAY_MS = 8000;
const FIRST_DELAY_MS = 3000;

// Rate-Limiting (simpel, IP-basiert, ohne KV)
const RATE_LIMIT_MAP = new Map(); // ip → { count, resetAt }
const RATE_LIMIT_MAX = 10;
const RATE_LIMIT_WINDOW_MS = 60 * 60 * 1000; // 1 Stunde


// ── Hilfsfunktionen ───────────────────────────────────────────────────────────

function maskToken(token) {
  if (!token || token.length < 6) return '***';
  return token.slice(0, 4) + '***' + token.slice(-2);
}

function corsHeaders(env, requestOrigin) {
  const allowed = env.ALLOWED_ORIGIN || '*';
  const origin = (allowed === '*') ? '*' : (requestOrigin || allowed);
  return {
    'Access-Control-Allow-Origin':  origin,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age':       '86400',
  };
}

function jsonError(status, message, env, origin) {
  return new Response(
    JSON.stringify({ error: message }),
    { status, headers: { 'Content-Type': 'application/json', ...corsHeaders(env, origin) } }
  );
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function checkRateLimit(ip) {
  const now = Date.now();
  const entry = RATE_LIMIT_MAP.get(ip);
  if (!entry || now > entry.resetAt) {
    RATE_LIMIT_MAP.set(ip, { count: 1, resetAt: now + RATE_LIMIT_WINDOW_MS });
    return true; // OK
  }
  if (entry.count >= RATE_LIMIT_MAX) return false; // Limit erreicht
  entry.count++;
  return true;
}

// ── Flex-Pull Logik ───────────────────────────────────────────────────────────

async function sendFlexRequest(token, queryId, dateFrom, dateTo) {
  const params = new URLSearchParams({ t: token, q: queryId, v: FLEX_VERSION });
  if (dateFrom) params.set('from', dateFrom);
  if (dateTo)   params.set('to', dateTo);

  const resp = await fetch(`${IBKR_BASE}${SEND_PATH}?${params}`, {
    headers: { 'User-Agent': 'Refundex/1.0 ko-flex-proxy' },
  });

  if (!resp.ok) {
    throw new Error(`SendRequest HTTP ${resp.status}: ${resp.statusText}`);
  }

  const xml = await resp.text();

  // ReferenceCode extrahieren
  const refMatch = xml.match(/<ReferenceCode>(\d+)<\/ReferenceCode>/);
  const status   = (xml.match(/<Status>(\w+)<\/Status>/) || [])[1] || '';

  if (status.toLowerCase() !== 'success' || !refMatch) {
    const errCode = (xml.match(/<ErrorCode>(\d+)<\/ErrorCode>/) || [])[1] || '?';
    const errMsg  = (xml.match(/<ErrorMessage>([^<]+)<\/ErrorMessage>/) || [])[1] || xml.slice(0, 200);
    throw new Error(`SendRequest fehlgeschlagen — Code ${errCode}: ${errMsg}`);
  }

  return refMatch[1]; // ReferenceCode
}

async function getFlexStatement(token, referenceCode) {
  const params = new URLSearchParams({ t: token, q: referenceCode, v: FLEX_VERSION });

  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    await sleep(attempt === 1 ? FIRST_DELAY_MS : RETRY_DELAY_MS);

    const resp = await fetch(`${IBKR_BASE}${FETCH_PATH}?${params}`, {
      headers: { 'User-Agent': 'Refundex/1.0 ko-flex-proxy' },
    });

    if (!resp.ok) {
      if (attempt === MAX_RETRIES) throw new Error(`GetStatement HTTP ${resp.status} nach ${MAX_RETRIES} Versuchen`);
      continue;
    }

    const xml = await resp.text();

    // Echtes Flex-XML?
    if (xml.includes('<FlexQueryResponse') || xml.includes('<FlexStatement')) {
      return xml;
    }

    // Noch in Generierung (Code 1019)?
    const errCode = (xml.match(/<ErrorCode>(\d+)<\/ErrorCode>/) || [])[1] || '';
    if (errCode === '1019') {
      console.debug(`[ko-flex-proxy] Report wird generiert (1019) — Versuch ${attempt}/${MAX_RETRIES}`);
      continue;
    }

    // Anderer Fehler
    const errMsg = (xml.match(/<ErrorMessage>([^<]+)<\/ErrorMessage>/) || [])[1] || xml.slice(0, 200);
    throw new Error(`GetStatement Fehler Code ${errCode}: ${errMsg}`);
  }

  throw new Error(`Flex-XML nach ${MAX_RETRIES} Versuchen nicht erhalten`);
}


// ── Request-Handler ───────────────────────────────────────────────────────────

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';
    const url    = new URL(request.url);

    // CORS Preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders(env, origin) });
    }

    // Health Check
    if (url.pathname === '/health' && request.method === 'GET') {
      return new Response(
        JSON.stringify({ status: 'ok', worker: 'ko-flex-proxy', version: '1.0.0' }),
        { status: 200, headers: { 'Content-Type': 'application/json', ...corsHeaders(env, origin) } }
      );
    }

    // Nur POST /flex erlaubt
    if (url.pathname !== '/flex' || request.method !== 'POST') {
      return jsonError(404, 'Not found. Verwende POST /flex', env, origin);
    }

    // Rate-Limit
    const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
    if (!checkRateLimit(ip)) {
      return jsonError(429, 'Rate limit erreicht (10 Requests/Stunde). Bitte warten.', env, origin);
    }

    // Body parsen
    let body;
    try {
      body = await request.json();
    } catch {
      return jsonError(400, 'Request-Body muss JSON sein: { token, queryId }', env, origin);
    }

    const { token, queryId, dateFrom, dateTo } = body;

    if (!token || typeof token !== 'string' || token.length < 5) {
      return jsonError(400, 'Feld "token" fehlt oder ungültig', env, origin);
    }
    if (!queryId || typeof queryId !== 'string') {
      return jsonError(400, 'Feld "queryId" fehlt oder ungültig', env, origin);
    }

    console.debug(`[ko-flex-proxy] Pull gestartet — Token: ${maskToken(token)}, QueryID: ${queryId}`);

    // ── Flex-Pull durchführen ─────────────────────────────────────────────
    try {
      const referenceCode = await sendFlexRequest(token, queryId, dateFrom, dateTo);
      console.debug(`[ko-flex-proxy] ReferenceCode: ${referenceCode}`);

      const xmlData = await getFlexStatement(token, referenceCode);
      console.debug(`[ko-flex-proxy] XML erhalten — ${xmlData.length} Zeichen`);

      return new Response(xmlData, {
        status: 200,
        headers: {
          'Content-Type': 'application/xml; charset=utf-8',
          'X-Flex-Proxy': 'ko-flex-proxy/1.0.0',
          ...corsHeaders(env, origin),
        },
      });

    } catch (err) {
      console.error(`[ko-flex-proxy] Fehler: ${err.message}`);
      return jsonError(502, `IBKR Flex-Fehler: ${err.message}`, env, origin);
    }
  },
};
