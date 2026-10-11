from __future__ import annotations

import html as _html
import os
from typing import TYPE_CHECKING, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from . import Guide
    from .synthesis import Synthesizer
    from .transcript import TranscriptProvider

_bearer = HTTPBearer(auto_error=False)


def _configured_scopes() -> tuple[str, ...]:
    """Scopes from GUIDE_SCOPES env, always includes 'shared'."""
    raw = os.environ.get("GUIDE_SCOPES", "").strip()
    scopes = ["shared"]
    if raw:
        for part in raw.split(","):
            part = part.strip()
            if part and part not in scopes:
                scopes.append(part)
    return tuple(scopes)

_UI_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Founder Guide</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📖</text></svg>"/>
  <style>
    :root {
      --bg: #f4f2ec; --surface: #fbfaf7; --ink: #211f1b; --ink-hover: #35322b;
      --muted: #6a655c; --line: #e2ded4; --line-strong: #c9c3b6;
      --accent: #9a5a1e; --accent-strong: #7e4916;
      --warn: #8a5a00; --err: #a3241b;
      --radius: .55rem;
      --focus: 0 0 0 3px color-mix(in oklab, var(--accent) 32%, transparent);
      font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
      color: var(--ink); background: var(--bg);
      -webkit-font-smoothing: antialiased;
    }
    * { box-sizing: border-box; }
    body { max-width: 42rem; margin: 0 auto; padding: clamp(1.5rem, 4vw, 3.5rem) 1.25rem 4rem; }
    .masthead { margin-bottom: 2.25rem; }
    h1 { font-size: clamp(1.5rem, 4vw, 1.9rem); line-height: 1.1; margin: 0;
      letter-spacing: -.01em; font-weight: 650; }
    .mark { font-weight: 400; }
    .lede { margin: .5rem 0 0; color: var(--muted); font-size: .95rem;
      line-height: 1.5; max-width: 34rem; }
    form { display: flex; flex-direction: column; gap: 1.1rem; }
    .field { display: flex; flex-direction: column; gap: .35rem; }
    label { font-size: .82rem; font-weight: 600; letter-spacing: .01em; }
    .opt { font-weight: 400; color: var(--muted); }
    input, select, textarea {
      font: inherit; width: 100%; background: var(--surface); color: var(--ink);
      border: 1px solid var(--line-strong); border-radius: var(--radius);
      padding: .6rem .7rem; min-height: 2.75rem;
      transition: border-color .15s, box-shadow .15s;
    }
    textarea { min-height: 5rem; resize: vertical; line-height: 1.5; }
    input::placeholder, textarea::placeholder { color: #a49e92; }
    input:hover, select:hover, textarea:hover { border-color: var(--muted); }
    input:focus-visible, select:focus-visible, textarea:focus-visible,
    button:focus-visible, summary:focus-visible, .ex:focus-visible {
      outline: none; border-color: var(--accent); box-shadow: var(--focus);
    }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 1.1rem; }
    @media (max-width: 34rem) { .row { grid-template-columns: 1fr; } }
    .adv summary { cursor: pointer; color: var(--muted); font-size: .85rem;
      font-weight: 600; width: max-content; border-radius: .35rem; padding: .15rem .1rem; }
    .adv[open] summary { margin-bottom: .6rem; }
    button#go {
      align-self: flex-start; background: var(--ink); color: var(--surface);
      border: 0; border-radius: var(--radius); padding: .7rem 1.4rem;
      min-height: 2.75rem; font-weight: 600; letter-spacing: .01em; cursor: pointer;
      transition: background .15s, transform .05s; margin-top: .25rem;
    }
    button#go:hover { background: var(--ink-hover); }
    button#go:active { transform: translateY(1px); }
    button#go:disabled { opacity: .55; cursor: progress; }
    .hint { margin: 0; color: var(--muted); font-size: .78rem; }
    #out { margin-top: 2rem; }
    .empty { color: var(--muted); font-size: .92rem; line-height: 1.55;
      border-top: 1px solid var(--line); padding-top: 1.5rem; }
    .empty p { margin: 0 0 .6rem; }
    .examples { list-style: none; margin: 0; padding: 0;
      display: flex; flex-direction: column; gap: .15rem; }
    .ex { background: none; border: 0; padding: .2rem 0; text-align: left;
      cursor: pointer; color: var(--accent); font: inherit; font-size: .92rem;
      text-decoration: underline; text-underline-offset: 2px;
      text-decoration-color: color-mix(in oklab, var(--accent) 40%, transparent);
      border-radius: .25rem; }
    .ex:hover { color: var(--accent-strong); text-decoration-color: currentColor; }
    .result { animation: rise .25s ease-out both; }
    @keyframes rise { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
    h2 { font-size: .8rem; text-transform: uppercase; letter-spacing: .06em;
      color: var(--muted); font-weight: 700; margin: 1.75rem 0 .6rem; }
    .answer { white-space: pre-wrap; line-height: 1.6; font-size: 1rem; margin: 0; }
    .cite { display: block; margin: .5rem 0; padding: .7rem .85rem;
      background: var(--surface); border: 1px solid var(--line);
      border-radius: var(--radius); color: inherit; text-decoration: none;
      transition: border-color .15s, box-shadow .15s; }
    .cite:hover { border-color: var(--line-strong); box-shadow: 0 1px 3px rgba(33,31,27,.06); }
    .cite .t { display: block; font-weight: 600; color: var(--accent); overflow-wrap: anywhere; }
    .cite:hover .t { color: var(--accent-strong); }
    .cite .t::after { content: " ↗"; font-size: .85em; color: var(--muted); }
    .cite .meta { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap;
      color: var(--muted); font-size: .8rem; margin-top: .3rem; }
    .cite .url { overflow-wrap: anywhere; }
    .ts { font-variant-numeric: tabular-nums;
      background: color-mix(in oklab, var(--accent) 12%, var(--surface));
      color: var(--accent-strong); border-radius: .3rem; padding: .05rem .4rem;
      font-weight: 600; font-size: .78rem; }
    .busy { color: var(--muted); display: flex; align-items: center; gap: .5rem; }
    .spinner { width: .85rem; height: .85rem; border: 2px solid var(--line-strong);
      border-top-color: var(--accent); border-radius: 50%; animation: spin .7s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .notice { border-left: 3px solid var(--warn);
      background: color-mix(in oklab, var(--warn) 8%, var(--surface));
      padding: .75rem .9rem; border-radius: .35rem; color: var(--ink);
      font-size: .92rem; line-height: 1.5; margin: 1rem 0 0; }
    .notice .warn { color: var(--warn); font-weight: 600; }
    .error { border-left: 3px solid var(--err);
      background: color-mix(in oklab, var(--err) 7%, var(--surface));
      padding: .75rem .9rem; border-radius: .35rem; font-size: .92rem;
      line-height: 1.5; margin: 1rem 0 0; }
    .error strong { color: var(--err); }
    .error .detail { color: var(--muted); font-size: .82rem; margin-top: .35rem; overflow-wrap: anywhere; }
    @media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
  </style>
</head>
<body>
  <header class="masthead">
    <h1><span class="mark" aria-hidden="true">📖</span> Founder Guide</h1>
    <p class="lede">Base de conocimiento interna para founders. Pregunta y responde con citas del corpus.</p>
  </header>
  <form id="f" novalidate>
    <div class="field">
      <label for="q">Pregunta</label>
      <textarea id="q" rows="3" required placeholder="¿Cómo validar con usuarios?"></textarea>
    </div>
    <div class="row">
      <div class="field">
        <label for="scope">Espacio</label>
        <select id="scope">__SCOPE_OPTIONS__</select>
      </div>
      <div class="field">
        <label for="stage">Etapa <span class="opt">(opcional)</span></label>
        <input id="stage" type="text" placeholder="idea, mvp, pmf…"/>
      </div>
    </div>
    <details class="adv">
      <summary>Opciones avanzadas</summary>
      <div class="field">
        <label for="token">Token de acceso</label>
        <input id="token" type="password" autocomplete="off" placeholder="Solo si tu espacio lo requiere"/>
      </div>
    </details>
    <button type="submit" id="go">Buscar respuesta</button>
    <p class="hint">Cmd / Ctrl + Enter para enviar.</p>
  </form>
  <div id="out" aria-live="polite" aria-busy="false">
    <div class="empty">
      <p>Escribe una pregunta y responderé usando las fuentes del corpus. Ejemplos:</p>
      <ul class="examples">
        <li><button type="button" class="ex">¿Cómo validar una idea con usuarios?</button></li>
        <li><button type="button" class="ex">¿Cuándo conviene levantar capital?</button></li>
        <li><button type="button" class="ex">¿Cómo priorizar el roadmap del MVP?</button></li>
      </ul>
    </div>
  </div>
  <script>
    const out = document.getElementById('out');
    const go = document.getElementById('go');
    const form = document.getElementById('f');
    const q = document.getElementById('q');
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      out.setAttribute('aria-busy', 'true');
      out.innerHTML = '<p class="busy"><span class="spinner" aria-hidden="true"></span>'
        + 'Buscando en el corpus…</p>';
      go.disabled = true;
      go.textContent = 'Buscando…';
      const headers = { 'Content-Type': 'application/json' };
      const token = document.getElementById('token').value.trim();
      if (token) headers['Authorization'] = 'Bearer ' + token;
      try {
        const res = await fetch('/v1/answers', {
          method: 'POST',
          headers,
          body: JSON.stringify({
            question: q.value,
            scope: document.getElementById('scope').value,
            stage: document.getElementById('stage').value.trim(),
            limit: 10,
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          const detail = typeof data.detail === 'string'
            ? data.detail
            : (data.detail ? JSON.stringify(data.detail) : res.statusText);
          out.innerHTML = '<div class="error result">'
            + '<strong>No se pudo completar la búsqueda.</strong>'
            + '<div class="detail">' + escapeHtml(detail) + '</div></div>';
          return;
        }
        let html = '';
        if (data.answer) {
          html += '<h2>Respuesta</h2><p class="answer">'
            + escapeHtml(data.answer) + '</p>';
        }
        if (data.insufficientEvidence) {
          html += '<div class="notice"><span class="warn">Evidencia insuficiente.</span> '
            + 'No encontré fuentes que respondan con confianza. '
            + 'Prueba reformular la pregunta o cambiar de espacio.</div>';
        }
        const citations = data.citations || [];
        if (citations.length) {
          html += '<h2>Fuentes</h2>';
          for (const c of citations) {
            html += '<a class="cite" href="' + escapeAttr(c.url)
              + '" target="_blank" rel="noopener">'
              + '<span class="t">' + escapeHtml(c.title || c.url) + '</span>'
              + '<span class="meta"><span class="ts">' + formatTs(c.startSeconds) + '</span>'
              + '<span class="url">' + escapeHtml(c.url) + '</span></span></a>';
          }
        }
        if (!html) {
          html = '<div class="notice">Sin resultados para esta consulta.</div>';
        }
        out.innerHTML = '<div class="result">' + html + '</div>';
      } catch (err) {
        out.innerHTML = '<div class="error result">'
          + '<strong>Sin conexión con el servidor.</strong>'
          + '<div class="detail">Revisa tu red e inténtalo de nuevo. '
          + escapeHtml(String(err)) + '</div></div>';
      } finally {
        go.disabled = false;
        go.textContent = 'Buscar respuesta';
        out.setAttribute('aria-busy', 'false');
      }
    });
    q.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        form.requestSubmit();
      }
    });
    document.querySelectorAll('.ex').forEach((b) => {
      b.addEventListener('click', () => { q.value = b.textContent; q.focus(); });
    });
    function formatTs(seconds) {
      const total = Math.max(0, Number(seconds) || 0);
      const m = Math.floor(total / 60);
      const s = Math.floor(total % 60);
      return m + ':' + String(s).padStart(2, '0');
    }
    function escapeHtml(s) {
      return s.replace(/[&<>"']/g, (c) => ({
        '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
      })[c]);
    }
    function escapeAttr(s) { return escapeHtml(s).replace(/`/g, ''); }
  </script>
</body>
</html>
"""


def _render_ui(scopes: tuple[str, ...]) -> str:
    options = "".join(
        f'<option value="{_html.escape(scope, quote=True)}">'
        f"{_html.escape(scope)}</option>"
        for scope in scopes
    )
    return _UI_HTML.replace("__SCOPE_OPTIONS__", options)


class AnswerRequest(BaseModel):
    question: str = ""
    scope: str = "shared"
    stage: str = ""
    limit: int = Field(default=10, ge=1, le=50)


class IngestRequest(BaseModel):
    videoId: str
    languages: list[str] = Field(default_factory=lambda: ["es"])


def create_app(
    guide: "Guide",
    *,
    token: str | None = None,
    transcript_provider: "TranscriptProvider | None" = None,
    synthesizer: "Synthesizer | None" = None,
    scopes: tuple[str, ...] | None = None,
) -> FastAPI:
    app = FastAPI(title="Founder Guide", version="0.1.0")
    if scopes is None:
        scopes = _configured_scopes()
    expected = token if token is not None else os.environ.get("GUIDE_TOKEN", "")

    def _check(
        credentials: HTTPAuthorizationCredentials | None,
    ) -> None:
        if not expected:
            return
        if credentials is None or credentials.credentials != expected:
            raise HTTPException(status_code=401, detail="unauthorized")

    def require_auth(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ) -> None:
        _check(credentials)

    def require_admin(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> str | None:
        _check(credentials)
        # ponytail: key accepted for contract; full replay cache later
        return idempotency_key

    @app.get("/", response_class=HTMLResponse)
    def ui() -> str:
        return _render_ui(scopes)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/search")
    def search(
        q: str = Query(default=""),
        scope: str = Query(default="shared"),
        stage: str = Query(default=""),
        limit: int = Query(default=10, ge=1, le=50),
        _: None = Depends(require_auth),
    ) -> dict[str, Any]:
        try:
            hits = guide.search(q, limit=limit, scope=scope, stage=stage)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {
            "items": [
                {
                    "text": hit.text,
                    "source": {
                        "url": hit.url,
                        "startSeconds": hit.start_seconds,
                        "citationId": hit.citation_id,
                        "title": hit.title,
                    },
                    "score": hit.score,
                }
                for hit in hits
            ],
            "nextCursor": None,
        }

    @app.post("/v1/answers")
    def answers(
        body: AnswerRequest,
        _: None = Depends(require_auth),
    ) -> dict[str, Any]:
        try:
            answer = guide.answer(
                body.question,
                limit=body.limit,
                scope=body.scope,
                stage=body.stage,
                synthesizer=synthesizer,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {
            "answer": answer.text,
            "citations": [
                {
                    "sourceId": citation.citation_id,
                    "url": citation.url,
                    "startSeconds": citation.start_seconds,
                    "title": citation.title,
                }
                for citation in answer.citations
            ],
            "insufficientEvidence": answer.insufficient_evidence,
        }

    @app.post("/v1/admin/ingestions")
    def admin_ingest(
        body: IngestRequest,
        _idem: str | None = Depends(require_admin),
    ) -> dict[str, Any]:
        if transcript_provider is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": {
                        "code": "PROVIDER_UNAVAILABLE",
                        "message": "Transcript provider not configured.",
                    }
                },
            )
        from .transcript import NoCaptionError

        languages = body.languages or ["es"]
        try:
            result = guide.ingest_video(transcript_provider, body.videoId, languages)
        except NoCaptionError:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "NO_CAPTION",
                        "message": "No hay captions disponibles para el video.",
                    }
                },
            ) from None
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {
            "videoId": body.videoId,
            "languages": languages,
            "transcriptKind": result.transcript_kind,
            "transcriptHash": result.transcript_hash,
            "created": result.created,
            "segmentCount": len(result.segments),
        }

    @app.get("/v1/admin/verify")
    def admin_verify(_: str | None = Depends(require_admin)) -> dict[str, Any]:
        return guide.verify_corpus()

    return app


def serve(
    guide: "Guide",
    host: str = "127.0.0.1",
    port: int = 8080,
    *,
    token: str | None = None,
    transcript_provider: "TranscriptProvider | None" = None,
    synthesizer: "Synthesizer | None" = None,
) -> None:
    import json

    import uvicorn

    print(
        json.dumps(
            {
                "listening": f"http://{host}:{port}",
                "auth": bool(token or os.environ.get("GUIDE_TOKEN")),
            },
            ensure_ascii=False,
        )
    )
    uvicorn.run(
        create_app(
            guide,
            token=token,
            transcript_provider=transcript_provider,
            synthesizer=synthesizer,
        ),
        host=host,
        port=port,
        log_level="warning",
    )
