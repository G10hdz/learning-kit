#!/usr/bin/env node
// explainers.mjs <list.txt> <outdir>
// Builds each listed pr-explainer model into <outdir>/<meta.id>.html plus an
// index.html in the hub style.
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';

const [listPath, outdir] = process.argv.slice(2);
if (!listPath || !outdir) {
  console.error('uso: node explainers.mjs <list.txt> <outdir>');
  process.exit(2);
}

const PLAYER_DIR = process.env.PLAYER_DIR || `${process.env.HOME}/agent-configs/_shared/pr-explainer/player`;
if (!existsSync(join(PLAYER_DIR, 'build.mjs'))) {
  console.log('player no disponible, se omiten los explainers');
  process.exit(0);
}

const entries = readFileSync(listPath, 'utf8')
  .split('\n')
  .map(l => l.trim())
  .filter(l => l && !l.startsWith('#'))
  .map(l => l.replace(/^~/, process.env.HOME));

mkdirSync(outdir, { recursive: true });
const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

let ok = 0, miss = 0;
const published = [];
for (const path of entries) {
  if (!existsSync(path)) { console.log(`falta ${path}`); miss++; continue; }
  let model = null;
  try { model = JSON.parse(readFileSync(path, 'utf8')); } catch {}
  const meta = (model && model.meta) || {};
  const id = meta.id || path.split('/').pop().replace(/\.json$/i, '');
  if (!/^[a-z0-9][a-z0-9._-]*$/i.test(id)) { console.log(`!! id inválido en ${path}, no se publica`); miss++; continue; }
  try {
    execFileSync('node', [join(PLAYER_DIR, 'build.mjs'), path, join(outdir, id + '.html')], { stdio: 'pipe' });
    published.push({ id, meta, hasPr: (model?.nodes || []).some(n => n.kind === 'pr') });
    ok++;
  } catch (e) {
    console.log(`!! ${id}: build falló, no se publica`);
    String(e.stdout || '').split('\n').filter(Boolean).forEach(l => console.log('   ' + l));
    miss++;
  }
}

const cards = published.map(({ id, meta, hasPr }) => `  <a class="card" href="${esc(id)}.html">
    <span class="tag">${hasPr ? 'pr' : 'tema'}</span>
    <h2>${esc(meta.title || id)}</h2>
    <p>${esc(meta.eyebrow || '')}</p>
  </a>`).join('\n');

writeFileSync(join(outdir, 'index.html'), `<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>explainers</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; margin: 0; }
  body { font-family: ui-sans-serif, system-ui, sans-serif; background: #0c0d10; color: #e8e9ec; min-height: 100dvh; padding: 1.25rem; }
  header { padding: 1rem 0 1.5rem; }
  h1 { font-size: 1.35rem; font-weight: 650; letter-spacing: -0.01em; }
  .sub { color: #8b8f98; font-size: 0.85rem; margin-top: 0.35rem; }
  main { display: grid; gap: 0.75rem; max-width: 34rem; }
  a.card { display: block; padding: 1.1rem 1.15rem; border-radius: 0.9rem; background: #16181d; border: 1px solid #262930; color: inherit; text-decoration: none; }
  a.card:active { transform: scale(0.985); }
  .card h2 { font-size: 1.02rem; font-weight: 600; }
  .card p { color: #9a9ea8; font-size: 0.82rem; margin-top: 0.3rem; line-height: 1.45; }
  .tag { display: inline-block; font-size: 0.68rem; letter-spacing: 0.04em; text-transform: uppercase; color: #7dd3a8; margin-bottom: 0.5rem; }
  a.back { color: #8b8f98; font-size: 0.85rem; text-decoration: none; }
  footer { color: #5c6068; font-size: 0.75rem; padding: 2rem 0 0.5rem; }
</style>
</head>
<body>
<header>
  <a class="back" href="../">&#8592; surface</a>
  <h1>explainers</h1>
  <p class="sub">pr-explainer · tailnet</p>
</header>
<main>
${cards}
</main>
<footer>${published.length} explainers publicados</footer>
</body>
</html>
`);

console.log(`explainers: ${ok} publicados, ${miss} omitidos`);
