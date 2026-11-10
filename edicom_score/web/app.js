(() => {
'use strict';
/* ====================================================================== utils */
const SVGNS = 'http://www.w3.org/2000/svg';
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'style' && typeof v === 'object') { for (const [sk, sv_] of Object.entries(v)) sk.startsWith('--') ? el.style.setProperty(sk, sv_) : (el.style[sk] = sv_); }
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'html') el.innerHTML = v;            // trusted static markup only
    else el.setAttribute(k, v === true ? '' : v);
  }
  add(el, kids); return el;
}
function add(el, kids) { for (const k of kids.flat(Infinity)) { if (k == null || k === false) continue; el.append(k.nodeType ? k : document.createTextNode(String(k))); } }
function sv(tag, attrs, ...kids) {
  const el = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs || {})) if (v != null) el.setAttribute(k, v);
  add(el, kids); return el;
}
const $ = (s, r = document) => r.querySelector(s);
const nf = new Intl.NumberFormat('fr-FR');
const n0 = v => v == null ? 'n.d.' : nf.format(Math.round(v));
const pc = (v, d = 0) => v == null ? 'n.d.' : (v * 100).toFixed(d).replace('.', ',') + ' %';
const dh = v => {
  if (v == null) return 'n.d.'; const a = Math.abs(v), s = v < 0 ? '−' : '';
  const f = (x, d) => x.toFixed(d).replace('.', ',').replace(/,0+$/, '');
  if (a >= 1e9) return `${s}${f(a / 1e9, 2)} Md DH`; if (a >= 1e6) return `${s}${f(a / 1e6, 2)} M DH`; if (a >= 1e3) return `${s}${f(a / 1e3, 0)} k DH`; return `${s}${n0(a)} DH`;
};
const csv = s => (s || '').split(',').filter(Boolean);
const nn = s => (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '');
const slug = s => nn(s || 'entreprise').replace(/[^A-Za-z0-9]+/g, '_').replace(/^_|_$/g, '');
const dateFr = iso => { try { return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' }); } catch { return ''; } };

const CLS = {
  A: { n: 'Très solide', risk: 'Risque très faible', lo: 75, hi: 100, col: '#1E9E5A' }, B: { n: 'Solide', risk: 'Risque faible', lo: 60, hi: 75, col: '#7CB518' },
  C: { n: 'Vigilance', risk: 'Risque modéré', lo: 45, hi: 60, col: '#F2A900' }, D: { n: 'Fragile', risk: 'Risque élevé', lo: 30, hi: 45, col: '#E8590C' },
  E: { n: 'Détresse', risk: 'Risque très élevé', lo: 0, hi: 30, col: '#C92A2A' }, NR: { n: 'Non notée', risk: 'Données insuffisantes', col: '#9CA3AF' }
};
const ORDER = ['E', 'D', 'C', 'B', 'A'];
const STS = {
  INACTIVE: { n: 'Probablement inactive', col: '#C0272D', ink: '#fff' }, VERIFY: { n: 'Activité non confirmée', col: '#F2A900', ink: '#3a2800' },
  PROBABLE: { n: 'Probablement active', col: '#13A89E', ink: '#fff' }, ACTIVE: { n: 'Entreprise active', col: '#1E9E5A', ink: '#fff' }
};
const STORDER = ['INACTIVE', 'VERIFY', 'PROBABLE', 'ACTIVE'];
const ADV = { A: 2.8, B: 4.1, C: 14.2, D: 45.7, E: 92 };

/* ====================================================================== api */
let KEY = ''; try { KEY = localStorage.getItem('edicom_key') || ''; } catch { }
class ApiError extends Error { constructor(status, msg) { super(msg || ('Erreur ' + status)); this.status = status; } }
async function api(path, opts = {}) {
  const { raw, ...o } = opts;
  const r = await fetch(path, { ...o, headers: { ...(KEY ? { 'X-API-Key': KEY } : {}), ...(o.headers || {}) } });
  if (r.status === 401) { await askKey(!!KEY); return api(path, opts); }
  if (!r.ok) { let m; try { m = (await r.json()).detail; } catch { } throw new ApiError(r.status, typeof m === 'string' ? m : null); }
  return raw ? r : r.json();
}
const cache = {};
const overview = async () => cache.ov || (cache.ov = await api('/v1/overview'));
const facets = async () => cache.fa || (cache.fa = await api('/v1/facets'));
const caps = async () => cache.caps || (cache.caps = (await (await fetch('/health')).json()).capabilities || { import: true, batch_async: true, batch_max: 1000 });
function resetCache() { delete cache.ov; delete cache.fa; }

/* ====================================================================== ui bits */
function toast(msg, err) { const t = h('div', { class: 'toast' + (err ? ' err' : '') }, msg); $('#toast-root').append(t); setTimeout(() => t.remove(), 3600); }
function modal(content, wide) {
  const prev = document.activeElement;
  const box = h('div', { class: 'modal' + (wide ? ' wide' : ''), role: 'dialog', 'aria-modal': 'true' }, content);
  const scrim = h('div', { class: 'scrim', onmousedown: e => { if (e.target === scrim) close(); } }, box);
  function close() { scrim.remove(); document.removeEventListener('keydown', esc); prev && prev.focus && prev.focus(); }
  function esc(e) { if (e.key === 'Escape') close(); }
  document.addEventListener('keydown', esc); $('#modal-root').append(scrim);
  const f = box.querySelector('input,button'); f && f.focus();
  return { close, box };
}
function askKey(wrong) {
  return new Promise(res => {
    const inp = h('input', { class: 'field', type: 'password', placeholder: 'Clé d\'accès', style: { width: '100%' }, autocomplete: 'off' });
    const m = modal([h('h2', {}, 'Clé d\'accès requise'), h('p', {}, 'Cette installation est protégée. Saisissez la clé fournie par votre administrateur.'), wrong ? h('p', { style: { color: 'var(--E)', fontWeight: 500 } }, 'Cette clé n\'est pas valide. Vérifiez-la et réessayez.') : null, inp,
    h('div', { class: 'row' }, h('button', { class: 'btn primary', onclick: () => { KEY = inp.value.trim(); try { localStorage.setItem('edicom_key', KEY); } catch { } m.close(); res(); } }, 'Valider'))]);
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') { KEY = inp.value.trim(); try { localStorage.setItem('edicom_key', KEY); } catch { } m.close(); res(); } });
  });
}
function saveBlob(blob, name) { const u = URL.createObjectURL(blob); const a = h('a', { href: u, download: name }); document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(u), 4000); }
const loading = (t = 'Chargement') => h('div', { class: 'wrap' }, h('div', { class: 'loading' }, h('span', { class: 'spin' }), t));

function glyph(code, sz = 16) {
  const c = { ACTIVE: '#168A4E', PROBABLE: '#0E8F86', VERIFY: '#9A6700', INACTIVE: '#C0272D' }[code] || '#8794A8';
  const s = sv('svg', { width: sz, height: sz, viewBox: '0 0 16 16', 'aria-hidden': 'true' });
  if (code === 'ACTIVE') s.append(sv('circle', { cx: 8, cy: 8, r: 7, fill: c }), sv('path', { d: 'M4.6 8.3l2.2 2.2 4.6-4.8', fill: 'none', stroke: '#fff', 'stroke-width': 1.9, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }));
  else if (code === 'PROBABLE') s.append(sv('circle', { cx: 8, cy: 8, r: 6.2, fill: 'none', stroke: c, 'stroke-width': 1.6 }), sv('path', { d: 'M8 3.2a4.8 4.8 0 0 0 0 9.6z', fill: c }));
  else if (code === 'VERIFY') s.append(sv('circle', { cx: 8, cy: 8, r: 6.2, fill: 'none', stroke: c, 'stroke-width': 1.6 }), sv('text', { x: 8, y: 11.3, 'text-anchor': 'middle', 'font-size': 9.5, 'font-weight': 700, fill: c, 'font-family': 'IBM Plex Sans, sans-serif' }, '?'));
  else s.append(sv('circle', { cx: 8, cy: 8, r: 6.2, fill: 'none', stroke: c, 'stroke-width': 1.6 }), sv('path', { d: 'M4.2 11.8l7.6-7.6', stroke: c, 'stroke-width': 1.6, 'stroke-linecap': 'round' }));
  return s;
}
const statusEl = (code, label, conf) => h('span', { class: 'st ' + code }, glyph(code), label || (STS[code] || {}).n, conf ? h('span', { class: 'conf' }, conf) : null);
const clsBadge = (c, lg) => h('span', { class: 'cls ' + c + (lg ? ' lg' : ''), title: c === 'NR' ? 'Non notée' : `Classe ${c} : ${CLS[c].n}` }, c);
function spectrum(score, o = {}) {
  const el = h('div', { class: 'spec', style: { '--h': (o.h || 8) + 'px', '--w': o.w || '100%', '--pin': (o.pin || 12) + 'px' }, role: 'img', 'aria-label': score == null ? 'Non noté' : 'Score ' + score });
  if (score == null) { el.append(h('i', { style: { flex: 1, background: '#E3E7ED' } })); return el; }
  for (const c of ORDER) el.append(h('i', { style: { flex: `${CLS[c].hi - CLS[c].lo} 0 0`, background: CLS[c].col } }));
  el.append(h('b', { class: 'pin', style: { left: Math.max(1, Math.min(99, score)) + '%' } })); return el;
}
const ico = {
  down: () => sv('svg', { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, sv('path', { d: 'M12 3v12M7 11l5 5 5-5M5 21h14' })),
  pdf: () => sv('svg', { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, sv('path', { d: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M9 14h6M9 17h4' })),
  back: () => sv('svg', { width: 14, height: 14, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 2.2, 'stroke-linecap': 'round' }, sv('path', { d: 'M15 5l-7 7 7 7' })),
  chev: () => sv('svg', { width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round' }, sv('path', { d: 'M9 5l7 7-7 7' })),
  search: () => sv('svg', { width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', stroke: '#8794A8', 'stroke-width': 2, 'stroke-linecap': 'round' }, sv('circle', { cx: 11, cy: 11, r: 7 }), sv('path', { d: 'M20 20l-3.5-3.5' })),
  xls: () => sv('svg', { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, sv('rect', { x: 3, y: 3, width: 18, height: 18, rx: 2 }), sv('path', { d: 'M3 9h18M3 15h18M9 3v18' })),
  zip: () => sv('svg', { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, sv('path', { d: 'M21 8l-9-5-9 5v8l9 5 9-5zM3 8l9 5 9-5M12 13v8' })),
  ok: () => sv('svg', { width: 18, height: 18, viewBox: '0 0 16 16' }, sv('path', { d: 'M3.5 8.4l3 3 6-6.4', fill: 'none', stroke: '#168A4E', 'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' })),
  no: () => sv('svg', { width: 18, height: 18, viewBox: '0 0 16 16' }, sv('path', { d: 'M4.5 4.5l7 7M11.5 4.5l-7 7', stroke: '#C0272D', 'stroke-width': 2, 'stroke-linecap': 'round' })),
  dot: () => sv('svg', { width: 18, height: 18, viewBox: '0 0 16 16' }, sv('circle', { cx: 8, cy: 8, r: 2.4, fill: '#9AA6B8' })),
  warn: () => sv('svg', { width: 18, height: 18, viewBox: '0 0 16 16' }, sv('path', { d: 'M8 2.5l6 10.5H2z', fill: 'none', stroke: '#B7791F', 'stroke-width': 1.7, 'stroke-linejoin': 'round' }), sv('path', { d: 'M8 6.8v2.8M8 11.4v.1', stroke: '#B7791F', 'stroke-width': 1.7, 'stroke-linecap': 'round' }))
};

/* ====================================================================== PDF helpers */
async function fetchPdf(code) { const r = await api(`/v1/companies/${code}/report.pdf`, { raw: true }); return r.blob(); }
async function openPdf(code, name, btn) {
  const w = window.open('', '_blank');
  if (w) w.document.write('<title>Rapport en cours…</title><body style="font:16px system-ui;padding:40px;color:#0B2545">Génération du rapport…</body>');
  const orig = btn && btn.innerHTML; if (btn) { btn.disabled = true; btn.replaceChildren(h('span', { class: 'spin' }), 'Génération'); }
  try { const blob = await fetchPdf(code); const u = URL.createObjectURL(blob); if (w) w.location = u; else saveBlob(blob, `${slug(name)}_${code}.pdf`); }
  catch (e) { if (w) w.close(); toast('Le rapport n\'a pas pu être généré : ' + e.message, true); }
  finally { if (btn) { btn.disabled = false; btn.innerHTML = orig; } }
}
async function downloadPdf(code, name) { saveBlob(await fetchPdf(code), `${slug(name)}_${code}.pdf`); }
async function jobModal(title, start) {
  const bar = h('i', { style: { width: '3%' } }), lab = h('p', {}, 'Démarrage…');
  const m = modal([h('h2', {}, title), lab, h('div', { class: 'prog' }, bar)]);
  try {
    let job = await start();
    while (job.status === 'running') { await new Promise(r => setTimeout(r, 450)); job = await api('/v1/jobs/' + job.id); bar.style.width = Math.max(3, job.progress * 100) + '%'; lab.textContent = job.label; }
    m.close(); if (job.status === 'error') throw new Error(job.error); return job;
  } catch (e) { m.close(); throw e; }
}

/* ====================================================================== search box */
function hl(text, q) {
  if (!text) return ''; const t = nn(q).toLowerCase().split(/\s+/).filter(Boolean)[0]; const nt = nn(text);
  if (!t || nt.length !== text.length) return text; const i = nt.toLowerCase().indexOf(t); if (i < 0) return text;
  return [text.slice(0, i), h('mark', {}, text.slice(i, i + t.length)), text.slice(i + t.length)];
}
function searchBox(big) {
  const input = h('input', { type: 'text', placeholder: big ? 'Nom, ICE ou numéro de RC' : 'Rechercher une entreprise', 'aria-label': 'Rechercher une entreprise', autocomplete: 'off', spellcheck: 'false', role: 'combobox', 'aria-expanded': 'false', 'data-search': '1' });
  const drop = h('div', { class: 'drop', hidden: true, role: 'listbox' });
  const root = h('div', { class: 'search' + (big ? ' big' : '') }, h('div', { class: 'search-box' }, ico.search(), input, big ? h('kbd', {}, '/') : null), drop);
  let items = [], act = -1, timer, seq = 0;
  const close = () => { drop.hidden = true; input.setAttribute('aria-expanded', 'false'); act = -1; };
  const go = code => { close(); input.value = ''; location.hash = '#/entreprise/' + code; };
  const mark = () => [...drop.querySelectorAll('.sg')].forEach((e, i) => { e.setAttribute('aria-selected', i === act ? 'true' : 'false'); if (i === act) e.scrollIntoView({ block: 'nearest' }); });
  function render(d, q) {
    items = d.items; drop.replaceChildren();
    if (!items.length) drop.append(h('div', { class: 'none' }, `Aucune entreprise ne correspond à « ${q} ». Vérifiez l'orthographe ou essayez le numéro ICE.`));
    for (const it of items) drop.append(h('a', { class: 'sg', href: '#/entreprise/' + it.code, role: 'option', onmousedown: e => e.preventDefault(), onclick: () => { close(); input.value = ''; } },
      h('div', { style: { minWidth: 0 } }, h('div', { class: 'nm' }, hl(it.name, q)), h('div', { class: 'sub' }, [it.city, it.form].filter(Boolean).join(' – '), ' ', it.act ? statusEl(it.act, STS[it.act].n) : null)),
      h('div', { class: 'right' }, it.score != null ? h('b', { style: { font: '700 17px var(--display)' } }, Math.round(it.score)) : null, it.score != null ? spectrum(it.score, { w: '64px', h: 6, pin: 10 }) : null),
      clsBadge(it.cls)));
    if (d.total > items.length) drop.append(h('div', { class: 'more' }, h('span', {}, `${n0(d.total)} résultats`), h('span', {}, 'Entrée pour voir toute la liste')));
    drop.hidden = false; input.setAttribute('aria-expanded', 'true'); act = items.length ? 0 : -1; mark();
  }
  input.addEventListener('input', () => {
    clearTimeout(timer); const q = input.value.trim(); if (q.length < 2) { close(); return; }
    timer = setTimeout(async () => { const my = ++seq; try { const d = await api('/v1/suggest?q=' + encodeURIComponent(q)); if (my === seq) render(d, q); } catch (e) { if (e.status !== 503) toast(e.message, true); } }, 140);
  });
  input.addEventListener('keydown', e => {
    if (e.key === 'ArrowDown') { e.preventDefault(); if (!drop.hidden && items.length) { act = (act + 1) % items.length; mark(); } }
    else if (e.key === 'ArrowUp') { e.preventDefault(); if (!drop.hidden && items.length) { act = (act - 1 + items.length) % items.length; mark(); } }
    else if (e.key === 'Escape') { close(); input.blur(); }
    else if (e.key === 'Enter') { e.preventDefault(); const q = input.value.trim(); if (q.length < 2) return; if (e.shiftKey || act < 0 || !items.length) { close(); location.hash = '#/entreprises?q=' + encodeURIComponent(q); } else go(items[act].code); }
  });
  input.addEventListener('blur', () => setTimeout(close, 120));
  input.addEventListener('focus', () => { if (items.length && input.value.trim().length >= 2) { drop.hidden = false; input.setAttribute('aria-expanded', 'true'); } });
  return root;
}

/* ====================================================================== pages */
const view = $('#view');
async function pageHome() {
  const example = h('div', { class: 'ex', 'aria-hidden': 'true' }, h('div', { class: 'ex-t' }, 'Exemple de résultat'),
    h('div', { class: 'ex-n' }, 'Atlas Menuiserie SARL'), h('div', { class: 'small muted' }, 'SARL – Casablanca – créée en 2008'),
    h('div', { class: 'ex-s' }, h('b', {}, '72'), h('div', {}, h('div', { class: 'ex-c' }, clsBadge('B'), h('span', {}, 'Solide')), h('div', { class: 'small muted' }, 'Risque faible'))), spectrum(72, { h: 10, pin: 16 }),
    h('div', { class: 'ex-a' }, statusEl('ACTIVE', 'Entreprise active')), h('div', { class: 'ex-b' }, ico.pdf(), 'Rapport PDF de 3 pages'));
  const hero = h('section', { class: 'hero' }, h('div', { class: 'wrap hero-grid' }, h('div', {},
    h('h1', {}, 'Solide et toujours en activité ?'),
    h('p', { class: 'lead' }, 'Cherchez une entreprise par son nom, son ICE ou son numéro de RC. Son score de santé financière et son statut d\'activité s\'affichent tout de suite, avec le rapport PDF en un clic.'),
    searchBox(true),
    h('p', { class: 'hero-hint' }, 'Astuce : appuyez sur ', h('kbd', { style: { font: '500 12px var(--text)', border: '1px solid var(--line)', borderRadius: '5px', padding: '1px 7px', background: '#fff' } }, '/'), ' depuis n\'importe quelle page pour lancer une recherche.')), example));
  let ov;
  try { ov = await overview(); } catch (e) { if (e.status === 503) { view.replaceChildren(onboarding()); return; } throw e; }
  const sc = ov.n_scorable, cc = ov.class_counts, sc2 = ov.status_counts;
  const ribbon = (title, sub, keys, counts, meta, link, total) => h('div', {},
    h('div', { class: 'rib-t' }, h('b', {}, title), h('span', { class: 'small muted' }, sub)),
    h('div', { class: 'rib' }, keys.map(k => h('a', { href: link(k), style: { flex: `${Math.max(counts[k], 1)} 0 0`, background: meta[k].col, color: meta[k].ink || (k === 'B' ? '#10270a' : k === 'C' ? '#3a2800' : '#fff') }, title: `${meta[k].n} : ${n0(counts[k])}` }, counts[k] / total > .045 ? h('span', {}, k.length === 1 ? k : pc(counts[k] / total)) : null))),
    h('div', { class: 'rib-l' }, keys.map(k => h('div', { style: { flex: `${Math.max(counts[k], 1)} 0 0` } }, counts[k] / total > .045 ? [h('b', {}, n0(counts[k])), h('span', {}, meta[k].n)] : ''))));
  const actShare = (sc2.ACTIVE + sc2.PROBABLE) / ov.n_firms;
  const overviewSec = h('section', { class: 'sect' }, h('div', { class: 'wrap' },
    h('div', { class: 'sect-h' }, h('h2', {}, 'Le panel en un coup d\'œil'), h('span', { class: 'muted' }, `Exercice ${ov.fy} – cliquez sur un segment pour voir les entreprises`)),
    h('div', { class: 'ribbons' },
      ribbon('Santé financière', `${n0(sc)} entreprises notées`, ORDER, cc, CLS, k => `#/entreprises?class=${k}`, sc),
      ribbon('Activité', `${n0(ov.n_firms)} entreprises`, STORDER, sc2, STS, k => `#/entreprises?activity=${k}`, ov.n_firms)),
    h('div', { class: 'facts' },
      h('div', { class: 'fact' }, h('b', {}, n0(ov.n_firms)), h('span', {}, 'entreprises dans la base')),
      h('div', { class: 'fact' }, h('b', {}, Math.round(ov.median_score)), h('span', {}, 'score médian sur 100')),
      h('div', { class: 'fact' }, h('b', {}, pc(actShare)), h('span', {}, 'actives ou probablement actives')),
      h('div', { class: 'fact' }, h('b', {}, n0(cc.NR)), h('span', {}, 'non notées (bilan trop petit ou absent)')))));
  const ins = h('section', { class: 'sect' }, h('div', { class: 'wrap' },
    h('div', { class: 'sect-h' }, h('h2', {}, 'À regarder en priorité')),
    h('div', { class: 'insights' }, ov.insights.map(i => h('a', { class: 'ins', href: '#/entreprises?' + new URLSearchParams(i.q).toString() }, h('b', { class: 'big' }, n0(i.n)), h('div', {}, h('div', { class: 'ins-t' }, i.title), h('div', { class: 'ins-h' }, i.hint)), ico.chev())))));
  const mx = Math.max(...ov.hist.map(b => b.n), 1);
  const hist = h('div', { class: 'hist', role: 'img', 'aria-label': 'Répartition des scores' }, ov.hist.map(b => {
    const c = ORDER.find(k => b.lo >= CLS[k].lo && b.lo < CLS[k].hi) || 'A'; const ht = Math.max(2, 150 * b.n / mx * .86);
    return h('a', { href: `#/entreprises?smin=${b.lo}&smax=${b.hi === 100 ? 100 : b.hi - 0.1}`, title: `Scores ${b.lo} à ${b.hi} : ${n0(b.n)} entreprises`, style: { '--bh': ht + 'px' } }, h('em', {}, n0(b.n)), h('i', { style: { height: ht + 'px', background: CLS[c].col } }));
  }));
  const two = h('section', { class: 'sect' }, h('div', { class: 'wrap two' },
    h('div', {}, h('h2', { style: { marginBottom: '16px' } }, 'Répartition des scores'), hist, h('div', { class: 'hist-x' }, ov.hist.map(b => h('span', {}, b.lo))), h('p', { class: 'small muted', style: { marginTop: '12px' } }, 'Les barres reprennent les couleurs des classes : rouge (E, moins de 30) à vert (A, 75 et plus).')),
    h('div', {}, h('h2', { style: { marginBottom: '16px' } }, 'Principales villes'), h('table', { class: 'cities' }, h('thead', {}, h('tr', {}, h('th', {}, 'Ville'), h('th', {}, 'Entreprises'), h('th', {}, 'Score moyen'), h('th', {}, 'Actives'))),
      h('tbody', {}, ov.cities.slice(0, 8).map(c => h('tr', {}, h('td', {}, h('a', { href: '#/entreprises?city=' + encodeURIComponent(c.city) }, c.city)), h('td', {}, n0(c.n)), h('td', {}, c.avg == null ? '–' : Math.round(c.avg)), h('td', {}, pc(c.active)))))))));
  view.replaceChildren(hero, overviewSec, ins, two);
}
function onboarding() {
  return h('div', { class: 'wrap' }, h('div', { class: 'onboard' }, h('h1', {}, 'Bienvenue. Commençons par vos données.'),
    h('p', {}, 'Aucune donnée n\'est encore chargée. Déposez vos fichiers Excel (bilans OMPIC et base Edicom) : le système détecte tout seul les feuilles et les années, calcule les scores en quelques secondes et prépare les rapports PDF.'),
    h('a', { class: 'btn primary', href: '#/donnees' }, 'Importer mes données')));
}

/* ---------------------------------------------------------------- list */
async function pageList(params) {
  let ov, fa, CAP;
  try { [ov, fa, CAP] = await Promise.all([overview(), facets(), caps()]); } catch (e) { if (e.status === 503) { location.hash = '#/donnees'; return; } throw e; }
  const S = { q: params.get('q') || '', cls: new Set(csv(params.get('class'))), act: new Set(csv(params.get('activity'))), city: params.get('city') || '', form: params.get('form') || '', persp: params.get('persp') || '',
    smin: params.get('smin') || '', smax: params.get('smax') || '', sort: params.get('sort') || 'score', order: params.get('order') || 'desc', page: +params.get('page') || 1, size: +params.get('size') || 25 };
  const sel = new Map();                       // code -> name, across pages
  const qs = (extra = {}) => {
    const p = new URLSearchParams(); const set = (k, v) => { if (v !== '' && v != null && !(v instanceof Set && !v.size)) p.set(k, v instanceof Set ? [...v].join(',') : v); };
    set('q', S.q); set('class', S.cls); set('activity', S.act); set('city', S.city); set('form', S.form); set('persp', S.persp); set('smin', S.smin); set('smax', S.smax);
    for (const [k, v] of Object.entries(extra)) p.set(k, v); return p;
  };
  const filterObj = () => ({ q: S.q || null, class: [...S.cls].join(',') || null, activity: [...S.act].join(',') || null, city: S.city || null, form: S.form || null, persp: S.persp || null, smin: S.smin || null, smax: S.smax || null, sort: S.sort, order: S.order });
  const hasFilters = () => S.q || S.cls.size || S.act.size || S.city || S.form || S.persp || S.smin || S.smax;
  let data = null, timer;

  const countEl = h('p', { class: 'count' }), tbody = h('tbody'), pager = h('div', { class: 'pager' }), summary = h('div', { class: 'small muted' });
  const qIn = h('input', { class: 'field', type: 'search', placeholder: 'Nom, ICE ou n° de RC', value: S.q, style: { width: '260px' }, 'aria-label': 'Filtrer par nom, ICE ou RC', oninput: e => { S.q = e.target.value.trim(); S.page = 1; debounce(); } });
  const cityIn = h('input', { class: 'field', list: 'cities', placeholder: 'Toutes les villes', value: S.city, style: { width: '170px' }, 'aria-label': 'Ville', onchange: e => { S.city = e.target.value.trim(); S.page = 1; load(); } });
  const cityDl = h('datalist', { id: 'cities' }, fa.cities.slice(0, 300).map(c => h('option', { value: c.v })));
  const formSel = h('select', { class: 'field', 'aria-label': 'Forme juridique', onchange: e => { S.form = e.target.value; S.page = 1; load(); } }, h('option', { value: '' }, 'Toutes formes'), fa.forms.map(f => h('option', { value: f.v, selected: f.v === S.form }, `${f.v} (${n0(f.n)})`)));
  const perSel = h('select', { class: 'field', 'aria-label': 'Évolution', onchange: e => { S.persp = e.target.value; S.page = 1; load(); } }, [['', 'Toute évolution'], ['En amélioration', 'En amélioration'], ['Stable', 'Stable'], ['En dégradation', 'En dégradation']].map(([v, l]) => h('option', { value: v, selected: v === S.persp }, l)));
  const minIn = h('input', { class: 'field', type: 'number', min: 0, max: 100, placeholder: '0', value: S.smin, 'aria-label': 'Score minimum', onchange: e => { S.smin = e.target.value; S.page = 1; load(); } });
  const maxIn = h('input', { class: 'field', type: 'number', min: 0, max: 100, placeholder: '100', value: S.smax, 'aria-label': 'Score maximum', onchange: e => { S.smax = e.target.value; S.page = 1; load(); } });
  const chipsCls = h('div', { class: 'fgrp' }), chipsAct = h('div', { class: 'fgrp' });
  function chips() {
    chipsCls.replaceChildren(...[...ORDER].reverse().concat('NR').map(k => h('button', { class: 'chip', 'aria-pressed': S.cls.has(k), onclick: () => { S.cls.has(k) ? S.cls.delete(k) : S.cls.add(k); S.page = 1; chips(); load(); } },
      h('span', { class: 'cls ' + k, style: { width: '20px', height: '20px', fontSize: '12px', borderRadius: '5px' } }, k), CLS[k].n, h('span', { class: 'n' }, n0(ov.class_counts[k])))));
    chipsAct.replaceChildren(...[...STORDER].reverse().map(k => h('button', { class: 'chip', 'aria-pressed': S.act.has(k), onclick: () => { S.act.has(k) ? S.act.delete(k) : S.act.add(k); S.page = 1; chips(); load(); } },
      glyph(k, 15), STS[k].n, h('span', { class: 'n' }, n0(ov.status_counts[k])))));
  }
  chips();
  const reset = h('button', { class: 'btn sm ghost reset', onclick: () => { Object.assign(S, { q: '', cls: new Set(), act: new Set(), city: '', form: '', persp: '', smin: '', smax: '', page: 1 }); qIn.value = cityIn.value = minIn.value = maxIn.value = ''; formSel.value = perSel.value = ''; chips(); load(); } }, 'Tout réinitialiser');
  const filters = h('div', { class: 'filters' },
    h('div', { class: 'frow' }, qIn, cityIn, cityDl, formSel, perSel, h('div', { class: 'score-rng' }, h('span', { class: 'flab', style: { minWidth: 0 } }, 'Score de'), minIn, h('span', { class: 'flab', style: { minWidth: 0 } }, 'à'), maxIn), reset),
    h('div', { class: 'frow' }, h('span', { class: 'flab' }, 'Classe'), chipsCls), h('div', { class: 'frow' }, h('span', { class: 'flab' }, 'Activité'), chipsAct));

  const thSort = (key, label) => h('th', { 'aria-sort': S.sort === key ? (S.order === 'asc' ? 'ascending' : 'descending') : null }, h('button', { onclick: () => { if (S.sort === key) S.order = S.order === 'asc' ? 'desc' : 'asc'; else { S.sort = key; S.order = key === 'score' || key === 'created' ? 'desc' : 'asc'; } S.page = 1; load(); } }, label, S.sort === key ? (S.order === 'asc' ? '▲' : '▼') : ''));
  const allCb = h('input', { class: 'cb', type: 'checkbox', 'aria-label': 'Sélectionner la page', onchange: e => { (data ? data.items : []).forEach(it => e.target.checked ? sel.set(it.code, it.name) : sel.delete(it.code)); rows(); bulk(); } });
  const thead = h('thead'); const table = h('table', { class: 'tbl' }, thead, tbody);
  const heads = () => thead.replaceChildren(h('tr', {}, h('th', { style: { width: '38px' } }, allCb), thSort('name', 'Entreprise'), thSort('score', 'Score'), h('th', {}, 'Classe'), h('th', {}, 'Activité'), h('th', {}, 'Évolution'), thSort('city', 'Ville'), thSort('created', 'Créée'), h('th', {}, h('span', { class: 'vh' }, 'Rapport'))));

  function rows() {
    tbody.replaceChildren();
    if (!data.items.length) { tbody.append(h('tr', {}, h('td', { colspan: 9 }, h('div', { class: 'empty' }, h('h3', {}, 'Aucune entreprise ne correspond'), h('p', {}, 'Élargissez les filtres ou retirez-en un.'), h('p', { style: { marginTop: '14px' } }, h('button', { class: 'btn', onclick: () => reset.click() }, 'Tout réinitialiser')))))); return; }
    for (const it of data.items) {
      const cb = h('input', { class: 'cb', type: 'checkbox', checked: sel.has(it.code), 'aria-label': 'Sélectionner ' + it.name, onclick: e => e.stopPropagation(), onchange: e => { e.target.checked ? sel.set(it.code, it.name) : sel.delete(it.code); tr.classList.toggle('sel', e.target.checked); bulk(); } });
      const pb = h('button', { class: 'btn sm', onclick: e => { e.stopPropagation(); openPdf(it.code, it.name, e.currentTarget); } }, ico.pdf(), 'PDF');
      const tr = h('tr', { class: sel.has(it.code) ? 'sel' : '', onclick: () => { location.hash = '#/entreprise/' + it.code; } },
        h('td', {}, cb),
        h('td', {}, h('a', { class: 'co', href: '#/entreprise/' + it.code, onclick: e => e.stopPropagation() }, it.name || it.code), h('div', { class: 'sub' }, [it.form, it.ice && 'ICE ' + it.ice].filter(Boolean).join('   '))),
        h('td', {}, it.score == null ? h('span', { class: 'faint' }, '–') : h('div', { class: 'sc' }, h('b', {}, Math.round(it.score)), spectrum(it.score, { w: '84px', h: 6, pin: 10 }))),
        h('td', {}, clsBadge(it.cls)),
        h('td', {}, it.act ? statusEl(it.act, STS[it.act].n, null) : '–', it.act_conf ? h('div', { class: 'conf', style: { paddingLeft: '22px' } }, 'Fiabilité ' + it.act_conf.toLowerCase()) : null),
        h('td', {}, h('span', { class: 'trend ' + (it.persp === 'En amélioration' ? 'up' : it.persp === 'En dégradation' ? 'down' : '') }, it.persp === 'En amélioration' ? '▲ En hausse' : it.persp === 'En dégradation' ? '▼ En baisse' : it.persp === 'Stable' ? 'Stable' : '–')),
        h('td', {}, it.city || '–'), h('td', {}, it.created ? Math.round(it.created) : '–'), h('td', { style: { textAlign: 'right' } }, pb));
      tbody.append(tr);
    }
    allCb.checked = data.items.length > 0 && data.items.every(i => sel.has(i.code));
  }
  function pagerRender() {
    const pg = data.pages, cur = data.page; const btns = [];
    const mk = (n, label, dis, curr) => h('button', { disabled: dis, 'aria-current': curr ? 'true' : null, 'aria-label': 'Page ' + n, onclick: () => { S.page = n; load(true); } }, label || n);
    btns.push(mk(cur - 1, '‹', cur <= 1)); const set = new Set([1, pg, cur - 1, cur, cur + 1].filter(n => n >= 1 && n <= pg)); let last = 0;
    for (const n of [...set].sort((a, b) => a - b)) { if (n - last > 1) btns.push(h('span', { style: { padding: '6px 4px' } }, '…')); btns.push(mk(n, null, false, n === cur)); last = n; }
    btns.push(mk(cur + 1, '›', cur >= pg));
    const from = data.total ? (cur - 1) * data.size + 1 : 0, to = Math.min(cur * data.size, data.total);
    pager.replaceChildren(h('span', {}, `${n0(from)} à ${n0(to)} sur ${n0(data.total)}`), h('div', { class: 'pg' }, btns),
      h('label', {}, 'Lignes par page ', h('select', { class: 'field', style: { padding: '5px 8px' }, onchange: e => { S.size = +e.target.value; S.page = 1; load(); } }, [25, 50, 100].map(n => h('option', { value: n, selected: n === S.size }, n)))));
  }
  const bulkEl = h('div', { class: 'bulk', hidden: true }); document.body.append(bulkEl); cleanup.push(() => bulkEl.remove());
  function bulk() {
    const n = sel.size; bulkEl.hidden = n === 0; if (!n) return;
    bulkEl.replaceChildren(h('b', {}, `${n} sélectionnée${n > 1 ? 's' : ''}`),
      n >= 2 && n <= 3 ? h('button', { class: 'btn', onclick: () => compare([...sel.keys()]) }, 'Comparer') : null,
      h('button', { class: 'btn light', onclick: () => zip({ codes: [...sel.keys()] }) }, ico.zip(), 'Rapports PDF (ZIP)'),
      h('button', { class: 'btn', onclick: () => { sel.clear(); rows(); bulk(); } }, 'Effacer'));
  }
  async function zip(body) {
    try {
      if (CAP.batch_async) {
        const job = await jobModal('Préparation des rapports', () => api('/v1/batch', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }));
        const r = await api(`/v1/jobs/${job.id}/download`, { raw: true }); saveBlob(await r.blob(), job.result.name); toast(`${job.result.count} rapports téléchargés`);
      } else {
        const m = modal([h('h2', {}, 'Préparation des rapports'), h('p', {}, 'Quelques secondes. Ne fermez pas la page.'), h('div', { class: 'prog ind' }, h('i'))]);
        try { const r = await api('/v1/batch.zip', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); saveBlob(await r.blob(), 'Rapports_Edicom.zip'); toast('Rapports téléchargés'); } finally { m.close(); }
      }
    } catch (e) { toast(e.message, true); }
  }
  async function exportXls(btn) {
    btn.disabled = true; try { const r = await api('/v1/export.xlsx?' + qs({ sort: S.sort, order: S.order }), { raw: true }); saveBlob(await r.blob(), `Edicom_Scores_${data.total}_entreprises.xlsx`); toast('Export Excel téléchargé'); }
    catch (e) { toast(e.message, true); } finally { btn.disabled = false; }
  }
  function debounce() { clearTimeout(timer); timer = setTimeout(() => load(), 260); }
  let seq = 0;
  async function load(keepScroll) {
    const my = ++seq; heads();
    const p = qs({ sort: S.sort, order: S.order, page: S.page, size: S.size });
    history.replaceState(null, '', '#/entreprises?' + qs({ ...(S.sort !== 'score' ? { sort: S.sort } : {}), ...(S.order !== 'desc' ? { order: S.order } : {}), ...(S.page > 1 ? { page: S.page } : {}), ...(S.size !== 25 ? { size: S.size } : {}) }).toString());
    const d = await api('/v1/companies?' + p).catch(e => { toast(e.message, true); return null; }); if (!d || my !== seq) return;
    data = d; countEl.textContent = `${n0(d.total)} entreprise${d.total > 1 ? 's' : ''}${hasFilters() ? ' correspondent aux filtres' : ' dans la base'}`;
    reset.hidden = !hasFilters(); rows(); pagerRender(); if (keepScroll) window.scrollTo({ top: table.getBoundingClientRect().top + scrollY - 140 });
  }
  const xlsBtn = h('button', { class: 'btn', onclick: e => exportXls(e.currentTarget) }, ico.xls(), 'Exporter en Excel');
  const zipBtn = h('button', { class: 'btn', onclick: () => { if (!data || !data.total) return; if (data.total > CAP.batch_max) { toast(`Maximum ${n0(CAP.batch_max)} rapports par archive : affinez les filtres (${n0(data.total)} entreprises).`, true); return; } zip({ filter: filterObj() }); } }, ico.zip(), 'Tous les rapports PDF (ZIP)');
  view.replaceChildren(h('div', { class: 'wrap' }, h('div', { class: 'page-h' }, h('div', {}, h('h1', {}, 'Entreprises'), countEl), h('div', { class: 'acts' }, xlsBtn, zipBtn)), filters, h('div', { class: 'tbl-wrap' }, table), pager));
  await load();
}

/* ---------------------------------------------------------------- company */
function evIcon(s) { return s === '+' ? ico.ok() : s === '-' ? ico.no() : ico.dot(); }
async function pageCompany(code) {
  let d;
  try { d = await api('/v1/companies/' + encodeURIComponent(code)); }
  catch (e) { if (e.status === 404) { view.replaceChildren(h('div', { class: 'wrap' }, h('div', { class: 'empty', style: { paddingTop: '90px' } }, h('h3', {}, 'Entreprise introuvable'), h('p', {}, 'Ce code ne correspond à aucune entreprise du panel actuel.'), h('a', { class: 'btn', href: '#/entreprises', style: { marginTop: '14px' } }, 'Voir la liste')))); return; } if (e.status === 503) { location.hash = '#/donnees'; return; } throw e; }
  document.title = `${d.name} – Edicom Score`;
  const sc = d.score, A = d.activity, scored = sc.value != null && sc.cls !== 'NR';
  const contact = [d.phone && h('span', {}, h('span', { class: 'k' }, 'Tél.'), d.phone), d.email && h('span', {}, h('span', { class: 'k' }, 'E-mail'), h('a', { href: 'mailto:' + d.email }, d.email)), d.web && h('span', {}, h('span', { class: 'k' }, 'Web'), h('a', { href: /^https?:/.test(d.web) ? d.web : 'https://' + d.web, target: '_blank', rel: 'noopener' }, d.web))].filter(Boolean);
  const head = h('div', { class: 'co-head' }, h('div', {}, h('h1', {}, d.name),
    h('div', { class: 'meta' }, d.form && h('span', {}, d.form), d.city && h('span', {}, h('span', { class: 'k' }, 'RC'), `${d.city}${d.rc ? ' n° ' + d.rc : ''}`), d.created && h('span', {}, h('span', { class: 'k' }, 'Créée en'), Math.round(d.created)), d.ice && h('span', {}, h('span', { class: 'k' }, 'ICE'), d.ice)),
    h('div', { class: 'meta' }, (d.manager && !/^n\.?d\.?$/i.test(String(d.manager).trim()) && String(d.manager).trim()) ? h('span', {}, h('span', { class: 'k' }, 'Dirigeant'), String(d.manager).trim() + (d.manager_role ? ` (${d.manager_role})` : '')) : null, d.headcount > 0 ? h('span', {}, h('span', { class: 'k' }, 'Effectif'), Math.round(d.headcount) + ' salarié(s)') : null, d.ca ? h('span', {}, h('span', { class: 'k' }, 'CA déclaré'), `${dh(d.ca)}${d.ca_year ? ' en ' + Math.round(d.ca_year) : ''}`) : null, contact)),
    h('div', { style: { display: 'flex', gap: '10px', flexWrap: 'wrap' } }, h('button', { class: 'btn primary only-narrow', onclick: () => { if (!iframe) loadPdf(); pane.scrollIntoView({ behavior: 'smooth', block: 'start' }); } }, ico.pdf(), 'Rapport PDF'),
    h('button', { class: 'btn', onclick: async () => { try { await navigator.clipboard.writeText(location.href); toast('Lien copié'); } catch { toast('Copiez l\'adresse depuis la barre du navigateur', true); } } }, 'Copier le lien')));

  // verdict
  const lbl = (x, c) => h('span', { style: { left: x + '%' } }, c);
  const scale = h('div', { class: 'scale' }, spectrum(scored ? sc.value : null, { h: 14, pin: 20 }), h('div', { class: 'scale-l' }, [30, 45, 60, 75].map(x => lbl(x, x)), ORDER.map(k => h('span', { class: 'lt', style: { left: ((CLS[k].lo + CLS[k].hi) / 2) + '%' } }, k))));
  const persp = sc.perspective && sc.perspective !== 'n.d.' ? `${sc.perspective}${sc.score_prev != null && sc.score_static != null ? ` (${Math.round(sc.score_prev)} en ${d.pfy}, ${Math.round(sc.score_static)} en ${d.fy})` : ''}` : 'Non disponible';
  const verdict = h('div', { class: 'blk' },
    h('h2', {}, 'Santé financière'),
    scored ? [h('div', { class: 'verdict' }, h('div', { class: 'bignum' }, Math.round(sc.value)), h('div', { class: 'vt' }, clsBadge(sc.cls, true), h('div', {}, h('b', {}, `Classe ${sc.cls}, ${sc.label}`), h('span', {}, sc.risk)))), scale,
      h('div', { class: 'stats3' }, h('div', { class: 'stat' }, h('b', {}, `Mieux noté que ${Math.round(sc.percentile)} %`), h('span', {}, `des ${n0(sc.n_firms)} entreprises du panel`)), h('div', { class: 'stat' }, h('b', {}, persp.split(' (')[0]), h('span', {}, persp.includes('(') ? '(' + persp.split(' (')[1] : `entre ${d.pfy} et ${d.fy}`)), h('div', { class: 'stat' }, h('b', {}, 'Fiabilité ' + (sc.reliability || '').toLowerCase()), h('span', {}, `des données (${sc.reliability_pts}/100)`))),
      sc.cap_note ? h('div', { class: 'note' }, sc.cap_note) : null,
      sc.adverse != null ? h('p', { class: 'small muted', style: { marginTop: '14px' } }, `Dans le test rétrospectif, ${(sc.adverse * 100).toFixed(1).replace('.', ',').replace(/,0$/, '')} % des entreprises de classe ${sc.cls} étaient en situation défavorable un an plus tard. `, h('a', { href: '#/aide', style: { color: 'var(--blue)' } }, 'Comment lire ce score ?')) : null]
      : [h('div', { class: 'verdict' }, h('div', { class: 'vt' }, clsBadge('NR', true), h('div', {}, h('b', {}, 'Entreprise non notée'), h('span', {}, 'Aucun score n\'est calculé : le bilan est absent ou trop petit pour être significatif (moins de 10 k DH).')))), ]);
  const lastLine = A.last_proof ? `Dernière preuve d'activité : ${A.last_proof}.` : 'Aucune preuve récente d\'activité.';
  const activity = h('div', { class: 'blk' }, h('h2', {}, 'Statut d\'activité'),
    h('div', { class: 'act-h' }, statusEl(A.status, A.label), h('span', { class: 'conf' }, `Fiabilité de l'indication : ${A.confidence.toLowerCase()}`)),
    h('p', { class: 'act-reason' }, A.reason), h('ul', { class: 'ev' }, A.evidence.map(e => h('li', {}, evIcon(e.sign), h('span', {}, e.text)))),
    h('div', { class: 'dorm' }, h('div', { class: 'small', style: { marginBottom: '8px', fontWeight: 500 } }, `Ressemblance du bilan à celui d'une société dormante : ${Math.round(A.p_dormant * 100)} %`),
      h('div', { class: 'bar' }, h('i', { style: { left: Math.max(1, Math.min(99, A.p_dormant * 100)) + '%' } })), h('div', { class: 'l' }, h('span', {}, 'Bilan opérationnel'), h('span', {}, 'Ambigu'), h('span', {}, 'Type dormant'))),
    h('p', { class: 'verify' }, 'Ce statut est une estimation. Pour une certitude, vérifiez : ', h('a', { href: 'https://www.ice.gov.ma', target: '_blank', rel: 'noopener' }, 'ICE (ice.gov.ma)'), h('a', { href: 'https://www.ompic.ma', target: '_blank', rel: 'noopener' }, 'Registre du commerce (OMPIC)'), h('a', { href: 'https://www.tax.gov.ma', target: '_blank', rel: 'noopener' }, 'Attestation fiscale (DGI)')));
  const reco = h('div', { class: 'blk' }, h('div', { class: 'reco' }, h('b', {}, 'Recommandation indicative'), h('p', {}, d.reco)));
  const colFor = v => v == null ? '#9CA3AF' : v >= 75 ? '#1E9E5A' : v >= 60 ? '#7CB518' : v >= 45 ? '#F2A900' : v >= 30 ? '#E8590C' : '#C92A2A';
  const pillars = scored ? h('div', { class: 'blk' }, h('h2', {}, 'Ce qui compose le score'), h('div', { class: 'pl' }, d.pillars.map(p => h('div', { class: 'pl-r' }, h('div', { class: 'nm' }, p.name), h('div', { class: 'bar' }, h('i', { style: { width: (p.score || 0) + '%', background: colFor(p.score) } })), h('div', { class: 'v' }, p.score == null ? '–' : Math.round(p.score)), h('div', { class: 'w' }, Math.round(p.weight * 100) + ' %'))))) : null;
  const points = scored && (d.strengths.length || d.watch.length) ? h('div', { class: 'blk' }, h('div', { class: 'cols2' },
    h('div', {}, h('h3', {}, 'Points forts'), h('ul', { class: 'pts' }, d.strengths.length ? d.strengths.map(t => h('li', {}, ico.ok(), t)) : h('li', {}, ico.dot(), 'Aucun point fort marquant.'))),
    h('div', {}, h('h3', {}, 'Points de vigilance'), h('ul', { class: 'pts' }, d.watch.length ? d.watch.map(t => h('li', {}, ico.warn(), t)) : h('li', {}, ico.dot(), 'Aucun point de vigilance marquant.'))))) : null;
  const inds = scored ? h('div', { class: 'blk' }, h('h2', {}, 'Indicateurs clés'), h('table', { class: 'dt' }, h('thead', {}, h('tr', {}, h('th', {}, 'Indicateur'), h('th', { class: 'r' }, 'Valeur'), h('th', {}, 'Note sur 100'), h('th', { class: 'r' }, 'Médiane du panel'))),
    h('tbody', {}, d.indicators.map(i => h('tr', {}, h('td', {}, i.label), h('td', { class: 'r' }, i.text), h('td', {}, h('span', { class: 'mini' }, h('i', { style: { width: (i.sub || 0) + '%', background: colFor(i.sub) } })), i.sub == null ? '–' : Math.round(i.sub)), h('td', { class: 'r muted' }, i.median_text || '–')))))) : null;
  const vr = (c, p) => { if (c == null || p == null || p === 0) return '–'; const v = Math.round((c - p) / Math.abs(p) * 100); return v === 0 ? '0 %' : (v > 0 ? '+' : '−') + Math.abs(v) + ' %'; };
  const figs = h('div', { class: 'blk' }, h('h2', {}, 'Chiffres clés'), h('table', { class: 'dt' }, h('thead', {}, h('tr', {}, h('th', {}, ''), h('th', { class: 'r' }, d.pfy), h('th', { class: 'r' }, d.fy), h('th', { class: 'r' }, 'Variation'))),
    h('tbody', {}, d.figures.map(f => h('tr', {}, h('td', {}, f.label), h('td', { class: 'r' }, f.prev_text), h('td', { class: 'r' }, f.cur_text), h('td', { class: 'r muted' }, f.label === 'Capital social' ? '–' : vr(f.cur, f.prev)))))));

  // PDF pane
  const body = h('div', { class: 'pdf-b' }); let blobUrl = null, iframe = null;
  const dl = h('button', { class: 'btn sm', onclick: () => downloadPdf(code, d.name) }, ico.down(), 'Télécharger');
  const pr = h('button', { class: 'btn sm', onclick: () => { try { iframe.contentWindow.focus(); iframe.contentWindow.print(); } catch { window.open(blobUrl, '_blank'); } } }, 'Imprimer');
  const gen = h('button', { class: 'btn primary', onclick: loadPdf }, ico.pdf(), 'Générer le rapport PDF');
  function ph() { body.replaceChildren(h('div', { class: 'pdf-ph' }, ico.pdf().cloneNode(true), h('b', {}, 'Rapport de 3 pages'), h('p', { class: 'small muted' }, 'Score, statut d\'activité, indicateurs, recommandation et méthode, prêts à imprimer ou à envoyer.'), gen)); dl.disabled = pr.disabled = true; }
  async function loadPdf() {
    body.replaceChildren(h('div', { class: 'loading' }, h('span', { class: 'spin' }), 'Génération du rapport'));
    try { const blob = await fetchPdf(code); if (blobUrl) URL.revokeObjectURL(blobUrl); blobUrl = URL.createObjectURL(blob); iframe = h('iframe', { src: blobUrl + '#view=FitH', title: 'Rapport PDF de ' + d.name }); body.replaceChildren(iframe); dl.disabled = pr.disabled = false; }
    catch (e) { body.replaceChildren(h('div', { class: 'pdf-ph' }, h('b', {}, 'Le rapport n\'a pas pu être généré'), h('p', { class: 'small muted' }, e.message), gen)); }
  }
  ph();
  const pane = h('aside', { class: 'pdfpane', 'aria-label': 'Rapport PDF' }, h('div', { class: 'pdf-h' }, h('b', {}, 'Rapport PDF'), h('div', { class: 'acts' }, pr, dl)), body);
  if (innerWidth >= 1100) loadPdf();
  const main = h('div', {}, verdict, activity, reco, pillars, points, inds, figs);
  view.replaceChildren(h('div', { class: 'wrap' }, h('a', { class: 'back', href: '#/entreprises' }, ico.back(), 'Retour à la liste'), head, h('div', { class: 'co-grid' }, main, pane)));
}

async function compare(codes) {
  const ds = await Promise.all(codes.map(c => api('/v1/companies/' + c)));
  const row = (label, fn, best) => { const vals = ds.map(fn); const b = best ? Math.max(...vals.map(v => typeof v === 'number' ? v : -1)) : null; return h('tr', {}, h('td', {}, label), ds.map((d, i) => h('td', { class: best && vals[i] === b && b >= 0 ? 'best' : '' }, typeof vals[i] === 'number' ? Math.round(vals[i]) : (vals[i] ?? '–')))); };
  const m = modal([h('h2', {}, 'Comparaison'), h('table', { class: 'cmp' },
    h('thead', {}, h('tr', {}, h('th', {}), ds.map(d => h('th', {}, h('a', { href: '#/entreprise/' + d.code, onclick: () => m.close() }, d.name))))),
    h('tbody', {}, row('Score', d => d.score.value, true), h('tr', {}, h('td', {}, 'Classe'), ds.map(d => h('td', {}, clsBadge(d.score.cls)))), h('tr', {}, h('td', {}, 'Activité'), ds.map(d => h('td', {}, statusEl(d.activity.status, d.activity.label)))),
      h('tr', {}, h('td', {}, 'Évolution'), ds.map(d => h('td', {}, d.score.perspective || '–'))),
      ...[0, 1, 2, 3, 4].map(i => row(ds[0].pillars[i].name, d => d.pillars[i].score, true)),
      row('Total bilan', d => dh(d.figures[0].cur)), row('Capitaux propres', d => dh(d.figures[1].cur)), row('Résultat net', d => dh(d.figures[3].cur)), row('Effectif', d => d.headcount > 0 ? Math.round(d.headcount) : null))),
  h('div', { class: 'row' }, h('button', { class: 'btn', onclick: () => m.close() }, 'Fermer'))], true);
}

/* ---------------------------------------------------------------- import */
async function pageData() {
  const hh = await api('/health').catch(() => ({ status: 'empty' }));
  const RO = hh.capabilities && hh.capabilities.import === false;
  const root = h('div', { class: 'wrap' }); view.replaceChildren(root);
  const st = { phase: 'idle', plan: null, id: null, job: null, result: null, files: [] };
  const fileIn = h('input', { type: 'file', multiple: true, accept: '.xlsx,.xlsm', class: 'vh', onchange: e => scan([...e.target.files]) });
  async function scan(files) {
    if (!files.length) return; st.phase = 'scanning'; st.files = files; render();
    const fd = new FormData(); files.forEach(f => fd.append('files', f));
    try { const d = await api('/v1/import/scan', { method: 'POST', body: fd }); st.plan = d; st.id = d.id; st.phase = 'report'; }
    catch (e) { st.phase = 'idle'; toast('Lecture impossible : ' + e.message, true); }
    render();
  }
  async function build() {
    st.phase = 'building'; st.job = { step: 0, total: 5, label: 'Lecture des fichiers', progress: .03 }; render();
    try {
      let job = await api(`/v1/import/${st.id}/build`, { method: 'POST' });
      while (job.status === 'running') { st.job = job; render(); await new Promise(r => setTimeout(r, 450)); job = await api('/v1/jobs/' + job.id); }
      if (job.status === 'error') throw new Error(job.error);
      st.result = job.result; st.phase = 'done'; resetCache(); footer();
    } catch (e) { st.phase = 'report'; toast('Le calcul a échoué : ' + e.message, true); }
    render();
  }
  function current() {
    if (hh.status !== 'ok' || st.phase === 'done') return null;
    return h('div', { class: 'cur-ds' }, h('div', { class: 'fact' }, h('b', {}, 'Exercice ' + hh.fiscal_year), h('span', {}, 'données actuellement chargées')), h('div', { class: 'fact' }, h('b', {}, n0(hh.firms)), h('span', {}, 'entreprises')), h('div', { class: 'fact' }, h('b', {}, dateFr(hh.built_at)), h('span', {}, 'dernier calcul')),
      h('a', { class: 'btn', href: '#/entreprises', style: { marginLeft: 'auto' } }, 'Voir les entreprises'));
  }
  function dropzone() {
    const z = h('div', { class: 'drop-z', ondragover: e => { e.preventDefault(); z.classList.add('over'); }, ondragleave: () => z.classList.remove('over'), ondrop: e => { e.preventDefault(); z.classList.remove('over'); scan([...e.dataTransfer.files].filter(f => /\.xlsx?m?$/i.test(f.name))); } },
      h('h2', {}, 'Déposez vos fichiers Excel ici'), h('p', {}, 'Un seul classeur ou plusieurs fichiers, dans l\'ordre que vous voulez. Les feuilles, les années et la base Edicom sont reconnues automatiquement.'),
      h('button', { class: 'btn primary', onclick: () => fileIn.click() }, 'Choisir des fichiers'), fileIn);
    return [z, h('div', { class: 'fmt' }, h('div', {}, h('b', {}, 'Un seul classeur (le plus simple)'), 'Trois feuilles : ', h('code', {}, '2018'), ' ', h('code', {}, '2019'), ' (bilans : colonnes Actif et Passif ensemble) et ', h('code', {}, 'Edicom'), '.'),
      h('div', {}, h('b', {}, 'Ou vos fichiers d\'origine'), 'OMPIC de chaque année (feuilles ', h('code', {}, 'Actif 2019'), ' et ', h('code', {}, 'Passif 2019'), ') et le fichier Edicom des entreprises.'))];
  }
  const KIND = { actif: 'Bilan Actif', passif: 'Bilan Passif', bilan: 'Bilan (Actif + Passif)', edicom: 'Base Edicom' };
  function report() {
    const p = st.plan, rows = p.sheets.filter(s => s.kind !== 'ignored');
    const items = rows.map(s => h('li', {}, ico.ok(), h('div', {}, h('div', { class: 'k' }, `${KIND[s.kind]}${s.year ? ' ' + s.year : ''}`), h('div', { class: 'd' }, `Feuille « ${s.sheet} » du fichier ${s.file}`)), h('div', { class: 'small muted' }, `${n0(s.rows)} lignes`)));
    const ign = p.sheets.filter(s => s.kind === 'ignored');
    return [h('h2', { style: { margin: '6px 0 14px' } }, p.ready ? 'Tout est reconnu' : 'Il manque quelque chose'), h('ul', { class: 'chk' }, items, ign.length ? h('li', {}, ico.dot(), h('div', {}, h('div', { class: 'k muted' }, `${ign.length} feuille${ign.length > 1 ? 's' : ''} ignorée${ign.length > 1 ? 's' : ''}`), h('div', { class: 'd' }, ign.map(s => s.sheet).join(', '))), '') : null),
      p.errors.map(e => h('div', { class: 'msg err' }, e)), p.warnings.map(e => h('div', { class: 'msg warn' }, e)),
      p.ready ? h('div', { class: 'msg warn', style: { background: '#fff', borderColor: 'var(--line)' } }, `Le score portera sur l'exercice ${p.fy}, avec ${p.fy - 1} pour mesurer l'évolution. `, hh.status === 'ok' ? 'Ce calcul remplacera les données actuelles.' : '') : null,
      h('div', { style: { display: 'flex', gap: '10px', marginTop: '18px' } }, h('button', { class: 'btn primary', disabled: !p.ready, onclick: build }, p.ready ? `Calculer les scores ${p.fy}` : 'Calculer les scores'), h('button', { class: 'btn', onclick: () => { st.phase = 'idle'; render(); } }, 'Changer de fichiers'))];
  }
  const STEPS = ['Lecture des fichiers', 'Calcul des indicateurs comptables', 'Calcul des scores', 'Détection de l\'activité', 'Enregistrement'];
  function building() {
    const j = st.job; const idx = Math.max(0, STEPS.indexOf(j.label));
    return [h('h2', { style: { margin: '6px 0 6px' } }, 'Calcul en cours'), h('p', { class: 'muted' }, 'Quelques secondes. Vous pouvez laisser cette page ouverte.'),
      h('div', { class: 'steps' }, STEPS.map((s, i) => h('div', { class: i < idx ? 'ok' : i === idx ? 'on' : '' }, i < idx ? ico.ok() : i === idx ? h('span', { class: 'spin' }) : h('span', { style: { width: '18px' } }), s))), h('div', { class: 'prog' }, h('i', { style: { width: Math.max(4, (j.progress || 0) * 100) + '%' } }))];
  }
  function done() {
    const r = st.result; return [h('h2', { style: { margin: '6px 0 6px' } }, 'Les scores sont prêts'), h('p', { class: 'muted' }, `Exercice ${r.fy}. Les rapports PDF peuvent être générés dès maintenant.`),
      h('div', { class: 'res' }, h('div', { class: 'fact' }, h('b', {}, n0(r.n_firms)), h('span', {}, 'entreprises')), h('div', { class: 'fact' }, h('b', {}, n0((r.class_counts.A || 0) + (r.class_counts.B || 0))), h('span', {}, 'classes A et B')), h('div', { class: 'fact' }, h('b', {}, n0((r.status_counts.ACTIVE || 0) + (r.status_counts.PROBABLE || 0))), h('span', {}, 'actives ou probablement actives')), h('div', { class: 'fact' }, h('b', {}, n0(r.status_counts.INACTIVE || 0)), h('span', {}, 'probablement inactives'))),
      h('div', { style: { display: 'flex', gap: '10px' } }, h('a', { class: 'btn primary', href: '#/entreprises' }, 'Voir les entreprises'), h('a', { class: 'btn', href: '#/' }, 'Aller à l\'accueil'), h('button', { class: 'btn ghost', onclick: () => { st.phase = 'idle'; render(); } }, 'Importer d\'autres fichiers'))];
  }
  function readonlyBody() {
    return [h('h2', { style: { margin: '6px 0 10px' } }, 'Les données se mettent à jour depuis votre ordinateur'),
      h('p', { class: 'muted', style: { maxWidth: '64ch', marginBottom: '14px' } }, 'Cette version en ligne est en lecture seule : elle affiche les scores calculés au moment du dernier déploiement. Pour la mettre à jour avec de nouveaux bilans :'),
      h('ol', { class: 'ro-steps' }, h('li', {}, 'Lancez l\'application en local (', h('code', {}, 'lancer.bat'), ') et importez les nouveaux fichiers.'), h('li', {}, 'Dans le dossier du projet, exécutez ', h('code', {}, 'python -m edicom_score vercel'), ' : les données calculées sont copiées dans le projet.'), h('li', {}, 'Déployez : ', h('code', {}, 'vercel --prod'), '.'))];
  }
  function render() {
    const body = RO ? readonlyBody() : st.phase === 'idle' ? dropzone() : st.phase === 'scanning' ? h('div', { class: 'loading' }, h('span', { class: 'spin' }), 'Lecture des fichiers…') : st.phase === 'report' ? report() : st.phase === 'building' ? building() : done();
    root.replaceChildren(...[h('div', { class: 'page-h' }, h('div', {}, h('h1', {}, 'Données'), h('p', { class: 'count' }, 'Importez les bilans et la base Edicom pour calculer ou mettre à jour les scores.'))), current(), body].flat(Infinity).filter(Boolean));
  }
  render();
}

/* ---------------------------------------------------------------- help */
async function pageHelp() {
  const rows = ORDER.slice().reverse().map(k => h('tr', {}, h('td', {}, clsBadge(k)), h('td', {}, h('b', {}, `${CLS[k].n}`), ` (${k === 'A' ? '75 et plus' : k === 'E' ? 'moins de 30' : CLS[k].lo + ' à ' + CLS[k].hi})`, h('div', { class: 'small muted' }, `${CLS[k].risk}. ${String(ADV[k]).replace('.', ',')} % des entreprises de cette classe étaient en situation défavorable un an plus tard.`))));
  view.replaceChildren(h('div', { class: 'wrap' }, h('div', { class: 'page-h' }, h('div', {}, h('h1', {}, 'Comment lire le score'), h('p', { class: 'count' }, 'En deux minutes : ce que le score mesure, ce qu\'il ne dit pas.'))), h('div', { class: 'prose' },
    h('h2', {}, 'Le score de santé financière'),
    h('p', {}, 'Une note de 0 à 100 calculée sur le dernier bilan déposé à l\'OMPIC, complétée par le profil de l\'entreprise dans la base Edicom (ancienneté, capital, taille, joignabilité). Plus la note est haute, plus l\'entreprise est solide.'),
    h('table', { class: 'cls-t' }, h('tbody', {}, rows, h('tr', {}, h('td', {}, clsBadge('NR')), h('td', {}, h('b', {}, 'Non notée'), h('div', { class: 'small muted' }, 'Bilan absent ou inférieur à 10 000 DH : aucun score n\'est calculé.'))))),
    h('h2', {}, 'Les cinq piliers'),
    h('dl', { class: 'dl' }, h('dt', {}, 'Solvabilité (30 %)'), h('dd', {}, 'Les fonds propres couvrent-ils le capital et les dettes ? Deux plafonds légaux s\'appliquent : sous le quart du capital social, le score ne dépasse pas 45 ; avec des fonds propres négatifs, il ne dépasse pas 30.'),
      h('dt', {}, 'Liquidité (10 %)'), h('dd', {}, 'Fonds de roulement et capacité à payer les dettes à court terme.'), h('dt', {}, 'Rentabilité (28 %)'), h('dd', {}, 'Résultat net et bénéfices accumulés par rapport au total du bilan.'),
      h('dt', {}, 'Dynamique (10 %)'), h('dd', {}, 'Évolution des fonds propres et du bilan sur un an, et pertes consécutives.'), h('dt', {}, 'Profil Edicom (22 %)'), h('dd', {}, 'Ancienneté, capital, tranche de chiffre d\'affaires, effectif, forme juridique et coordonnées.')),
    h('h2', {}, 'Le statut d\'activité'),
    h('p', {}, 'Il répond à une autre question : l\'entreprise travaille-t-elle encore ? Il se déduit d\'un chiffre d\'affaires récent, de l\'empreinte du bilan (clients, fournisseurs, CNSS, impôts) et de sa ressemblance à celui des sociétés dormantes.'),
    h('dl', { class: 'dl' }, STORDER.slice().reverse().map(k => [h('dt', {}, statusEl(k, STS[k].n)), h('dd', {}, { ACTIVE: 'Un chiffre d\'affaires récent est déclaré.', PROBABLE: 'Le bilan montre une exploitation réelle, sans donnée plus récente : à reconfirmer.', VERIFY: 'Signaux insuffisants ou contradictoires, par exemple un bilan important sans chiffre d\'affaires (projet en cours, société patrimoniale).', INACTIVE: 'Aucun chiffre d\'affaires et un bilan de type dormant.' }[k])])),
    h('p', {}, 'C\'est une estimation, pas un statut légal. Avant tout engagement important, vérifiez au registre du commerce (OMPIC), sur ice.gov.ma et avec les attestations fiscale (DGI) et sociale (CNSS).'),
    h('h2', {}, 'Limites à connaître'),
    h('p', {}, 'Les scores reposent sur le bilan de l\'exercice indiqué en bas de page. Ils ne tiennent pas compte du compte de produits et charges, du secteur d\'activité ni d\'éventuelles procédures judiciaires. Les taux d\'entreprises en situation défavorable viennent d\'un test rétrospectif sur le panel, pas d\'une mesure nationale.'))));
}

/* ====================================================================== shell */
const cleanup = [];
function footer() {
  api('/health').then(hh => {
    $('#foot').replaceChildren(h('p', {}, hh.status === 'ok' ? `Exercice ${hh.fiscal_year}, ${n0(hh.firms)} entreprises, calcul du ${dateFr(hh.built_at)}.` : 'Aucune donnée chargée.'),
      h('p', {}, 'Indications statistiques fournies à titre informatif : elles ne constituent ni un conseil en crédit ni une garantie. Les comptes déposés peuvent ne plus refléter la situation actuelle.'));
    $('#keyBtn').hidden = !hh.auth;
  }).catch(() => { });
}
const ROUTES = [[/^#\/?$/, 'home', () => pageHome()], [/^#\/entreprises/, 'list', (m, p) => pageList(p)], [/^#\/entreprise\/([^?]+)/, 'list', m => pageCompany(decodeURIComponent(m[1]))], [/^#\/donnees/, 'data', () => pageData()], [/^#\/aide/, 'help', () => pageHelp()]];
let navSeq = 0;
async function route() {
  while (cleanup.length) cleanup.pop()();
  const hash = location.hash || '#/'; const [path, q] = hash.split('?'); const params = new URLSearchParams(q || ''); const my = ++navSeq;
  const r = ROUTES.find(([re]) => re.test(path)) || ROUTES[0]; const m = path.match(r[0]);
  document.querySelectorAll('.nav a').forEach(a => a.getAttribute('data-nav') === r[1] ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current'));
  document.title = { home: 'Edicom Score Entreprise', list: 'Entreprises – Edicom Score', data: 'Données – Edicom Score', help: 'Aide – Edicom Score' }[r[1]];
  const ts = $('#topSearch'); ts.replaceChildren(); if (r[1] !== 'home') ts.append(searchBox(false));
  view.replaceChildren(loading());
  try { await r[2](m, params); } catch (e) { if (my !== navSeq) return; view.replaceChildren(h('div', { class: 'wrap' }, h('div', { class: 'empty', style: { paddingTop: '90px' } }, h('h3', {}, 'Une erreur est survenue'), h('p', {}, e.message), h('button', { class: 'btn', style: { marginTop: '14px' }, onclick: route }, 'Réessayer')))); }
  if (my === navSeq && !/^#\/entreprises/.test(path)) window.scrollTo(0, 0);
}
window.addEventListener('hashchange', route);
document.addEventListener('keydown', e => { if (e.key === '/' && !/INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName) && !e.metaKey && !e.ctrlKey) { const s = $('input[data-search]'); if (s) { e.preventDefault(); s.focus(); s.select(); } } });
$('#keyBtn').addEventListener('click', () => askKey());
footer(); route();
})();
