/* CineMatch front-end — talks only to our own Flask backend (/api/*). No third-party code or APIs. */
const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const api = async (path) => { const r = await fetch(path); const j = await r.json().catch(() => ({})); if (!r.ok) throw Object.assign(new Error(j.error || r.statusText), { data: j }); return j; };
const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/* ---------- procedural posters (no images / APIs needed) ---------- */
const GEN = { Action: ['#ff6a3d', '#7a1e1e', '💥'], Adventure: ['#2fb67c', '#0f4c5c', '🧭'], Animation: ['#ffb347', '#d1478c', '🎨'], "Children's": ['#ffd166', '#06a77d', '🧸'],
  Comedy: ['#ffd23f', '#ee6c4d', '😂'], Crime: ['#6b7280', '#1f2937', '🕵️'], Documentary: ['#38bdf8', '#14532d', '🎥'], Drama: ['#a78bfa', '#312e81', '🎭'], Fantasy: ['#c084fc', '#4c1d95', '🐉'],
  'Film-Noir': ['#94a3b8', '#0f172a', '🎩'], Horror: ['#dc2626', '#1c0a0a', '👻'], Musical: ['#f472b6', '#6d28d9', '🎵'], Mystery: ['#5eead4', '#134e4a', '🔍'], Romance: ['#fb7185', '#9f1239', '💘'],
  'Sci-Fi': ['#22d3ee', '#1e1b4b', '🚀'], Thriller: ['#f97316', '#18181b', '⚡'], War: ['#a3a380', '#3f3f2c', '🎖️'], Western: ['#e0a458', '#7c3f00', '🤠'] };
const gstyle = g => { const [a, b] = GEN[g[0]] || ['#888', '#222', '🎬']; const rot = (g.join('').length * 37) % 360; return { bg: `linear-gradient(${rot}deg,${a},${b})`, glyph: (GEN[g[0]] || [])[2] || '🎬', c2: a }; };
const initials = t => t.replace(/^(the|a|an)\s+/i, '').trim()[0]?.toUpperCase() || '?';
const poster = (m, extra = '') => { const s = gstyle(m.genres); return `<div class="poster" style="background:${s.bg}">${extra}<span class="ini">${esc(initials(m.title))}</span><span class="glyph">${s.glyph}</span><div class="t">${esc(m.title)}</div><div class="y">${m.year}</div></div>`; };
const stars = v => `<span class="stars" style="--p:${v / 5 * 100}">★★★★★</span>`;

/* ---------- tabs ---------- */
let analyticsLoaded = false;
$$('#nav button').forEach(b => b.onclick = () => {
  $$('#nav button').forEach(x => x.classList.toggle('on', x === b)); $$('.tab').forEach(t => t.classList.toggle('on', t.id === 'tab-' + b.dataset.tab));
  if (b.dataset.tab === 'analytics' && !analyticsLoaded) loadAnalytics(); window.scrollTo({ top: 0, behavior: 'smooth' });
});

/* ---------- autocomplete (shared) ---------- */
function autocomplete(input, list, onPick) {
  let t, items = [], act = -1;
  const close = () => { list.classList.remove('show'); act = -1; };
  input.addEventListener('input', () => { clearTimeout(t); const q = input.value.trim(); if (!q) return close(); t = setTimeout(async () => {
    try { items = await api('/api/search?q=' + encodeURIComponent(q) + '&limit=7'); } catch { return; }
    list.innerHTML = items.map((m, i) => `<li data-i="${i}"><span class="mini" style="background:${gstyle(m.genres).bg}"></span><div><b>${esc(m.title)}</b><small>${m.year} · ${m.genres.join(', ')} · ★ ${m.avg_rating}</small></div></li>`).join('');
    list.classList.toggle('show', items.length > 0); $$('li', list).forEach(li => li.onclick = () => { onPick(items[li.dataset.i]); close(); }); }, 140); });
  input.addEventListener('keydown', e => { const li = $$('li', list); if (!li.length || !list.classList.contains('show')) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); act = (act + (e.key === 'ArrowDown' ? 1 : -1) + li.length) % li.length; li.forEach((x, i) => x.classList.toggle('act', i === act)); }
    else if (e.key === 'Enter' && act >= 0) { e.preventDefault(); e.stopImmediatePropagation(); onPick(items[act]); close(); } else if (e.key === 'Escape') close(); }, true);
  document.addEventListener('click', e => { if (!list.contains(e.target) && e.target !== input) close(); });
}

/* ---------- DISCOVER ---------- */
let mix = [], mode = 'hybrid';
const grid = $('#grid');
function renderMix() { $('#mix').classList.toggle('hidden', !mix.length);
  $('#chips').innerHTML = mix.map(m => `<span class="chip">${esc(m.title)} <button data-id="${m.movie_id}" title="remove">×</button></span>`).join('');
  $$('#chips button').forEach(b => b.onclick = () => { mix = mix.filter(m => m.movie_id != b.dataset.id); renderMix(); mix.length ? recommend() : loadTop(); }); }
function addToMix(m, replace = false) { if (replace) mix = []; if (!mix.find(x => x.movie_id === m.movie_id) && mix.length < 5) mix.push(m); renderMix(); recommend(); }
autocomplete($('#q'), $('#suggest'), m => { $('#q').value = ''; addToMix(m, !event?.shiftKey && true); });
$('#goBtn').onclick = async () => { const q = $('#q').value.trim(); if (!q) return; $('#suggest').classList.remove('show');
  const r = await api('/api/search?q=' + encodeURIComponent(q) + '&limit=1').catch(() => []); if (!r.length) return showMsg(`No movie found for “${q}”. Try another title.`); $('#q').value = ''; addToMix(r[0], true); };
$('#q').addEventListener('keydown', e => { if (e.key === 'Enter') $('#goBtn').click(); });
$$('.quick button').forEach(b => b.onclick = async () => { const r = await api('/api/search?q=' + encodeURIComponent(b.textContent) + '&limit=1'); if (r[0]) addToMix(r[0], true); });
$('#clearMix').onclick = () => { mix = []; renderMix(); loadTop(); };
$$('#modeSeg button').forEach(b => b.onclick = () => { mode = b.dataset.m; $$('#modeSeg button').forEach(x => x.classList.toggle('on', x === b)); $('#alphaBox').style.display = mode === 'hybrid' ? '' : 'none'; if (mix.length) recommend(); });
$('#alpha').oninput = e => $('#alphaV').textContent = (+e.target.value).toFixed(2);
['alpha', 'genre', 'ymin', 'ymax', 'nres'].forEach(id => $('#' + id).addEventListener('change', () => mix.length ? recommend() : loadTop()));
function showMsg(t, el = $('#msg')) { el.textContent = t; el.classList.remove('hidden'); } const hideMsg = (el = $('#msg')) => el.classList.add('hidden');
const skeleton = (el, n = 8) => el.innerHTML = Array(n).fill('<div class="skel"></div>').join('');

function bar(label, v, color) { return `<div class="bar"><span>${label}</span><i><s style="width:${Math.round(v * 100)}%;background:${color}"></s></i><span>${Math.round(v * 100)}%</span></div>`; }
function card(m, i, opts = {}) {
  const why = m.shared_genres ? `<div class="why">${m.shared_genres.length ? 'Shared genres: ' + m.shared_genres.join(', ') : 'Taste-based match'}${m.shared_keywords?.length ? '<br>Shared themes: ' + m.shared_keywords.map(esc).join(', ') : ''}</div>` : '';
  return `<article class="mc" style="animation-delay:${i * 45}ms">${poster(m, m.match ? `<span class="match">${m.match}% match</span>` : '')}
   <div class="mbody"><div class="tags">${m.genres.map(g => `<span class="tag ${m.shared_genres?.includes(g) ? 'hit' : ''}">${esc(g)}</span>`).join('')}</div>
   <div class="meta"><span>★ <b>${m.avg_rating}</b> avg</span><span>${m.n_ratings.toLocaleString()} ratings</span></div>
   ${opts.pred ? `<div class="pred">${stars(m.predicted)} ${m.predicted.toFixed(2)} <small style="color:var(--mute);font-weight:400">predicted</small></div>` : ''}
   ${opts.semantic ? `<div class="pred">Semantic similarity ${m.semantic_score.toFixed(3)}</div>` : ''}${m.content !== undefined ? `<div class="bars">${bar('Content', m.content, 'var(--teal)')}${bar('Collab.', m.collab, 'var(--violet)')}</div>` : ''}${why}
   <div class="acts">${opts.pred ? `<button data-pred="${m.movie_id}">Predict</button>` : `<button data-sim="${m.movie_id}">Find similar</button><button data-add="${m.movie_id}">+ Mix</button>`}</div></div></article>`;
}
function wireCards(el, list) { $$('[data-sim]', el).forEach(b => b.onclick = () => { addToMix(list.find(x => x.movie_id == b.dataset.sim), true); window.scrollTo({ top: 0, behavior: 'smooth' }); });
  $$('[data-add]', el).forEach(b => b.onclick = () => addToMix(list.find(x => x.movie_id == b.dataset.add))); }
function renderTrace(el, steps, total, title) { el.innerHTML = `<h4><span>${title}</span><span>${total} ms total</span></h4>` + steps.map((s, i) => `<div class="tstep"><span class="n">${i + 1}</span><div><b>${esc(s.step)}</b>${s.ms !== undefined ? `<em>${s.ms} ms</em>` : ''}<p>${esc(s.detail)}</p></div></div>`).join(''); el.classList.remove('hidden'); }

async function semanticSearch() {
  const query = $('#semanticQ').value.trim(), results = $('#semanticResults'), message = $('#semanticMsg');
  if (!query) { showMsg('Describe the kind of movie you want.', message); return; }
  hideMsg(message); skeleton(results, 6);
  $('#semanticStatus').textContent = 'Loading the local embedding model and searching…';
  try {
    const data = await api('/api/semantic-search?' + new URLSearchParams({ q: query, n: 12 }));
    results.innerHTML = data.results.map((m, i) => card(m, i, { semantic: true })).join('');
    wireCards(results, data.results);
    $('#semanticStatus').textContent = `${data.model} · ${data.source} · ${data.total_ms} ms`;
  } catch (e) {
    results.innerHTML = '';
    if (e.message === 'Failed to fetch') {
      $('#health').classList.remove('ok');
      $('#health').classList.add('bad');
      $('#healthTxt').textContent = 'backend offline';
      showMsg('Cannot reach the CineMatch backend. Start run.bat and keep its window open, then try again.', message);
      $('#semanticStatus').textContent = 'Backend offline — start run.bat, then open http://127.0.0.1:5000.';
    } else {
      showMsg(e.message, message);
      $('#semanticStatus').textContent = 'Search failed. Check the backend logs and, on first use, confirm model download access.';
    }
  }
}
$('#semanticBtn').onclick = semanticSearch;
$('#semanticQ').addEventListener('keydown', e => { if (e.key === 'Enter') semanticSearch(); });

async function recommend() {
  if (!mix.length) return; hideMsg(); skeleton(grid);
  const p = new URLSearchParams({ ids: mix.map(m => m.movie_id).join(','), mode, n: $('#nres').value, alpha: $('#alpha').value });
  if ($('#genre').value) p.set('genre', $('#genre').value); if ($('#ymin').value) p.set('year_min', $('#ymin').value); if ($('#ymax').value) p.set('year_max', $('#ymax').value);
  try { const d = await api('/api/recommend?' + p);
    $('#resTitle').innerHTML = mix.length > 1 ? `Blended from ${mix.length} movies` : `Because you liked <em style="color:var(--amb)">${esc(d.query.title)}</em>`;
    grid.innerHTML = d.results.length ? d.results.map((m, i) => card(m, i)).join('') : '<p class="note">No movies match these filters — widen the genre/year range.</p>'; wireCards(grid, d.results);
    renderTrace($('#trace'), d.trace, d.total_ms, 'Behind the scenes — what the backend just did'); }
  catch (e) { grid.innerHTML = ''; showMsg(e.message); }
}
async function loadTop() { $('#trace').classList.add('hidden'); skeleton(grid, 6); const g = $('#genre').value; const l = await api('/api/top?n=' + $('#nres').value + (g ? '&genre=' + encodeURIComponent(g) : ''));
  $('#resTitle').textContent = 'Top rated on CineMatch' + (g ? ' · ' + g : ''); grid.innerHTML = l.map((m, i) => card(m, i)).join(''); wireCards(grid, l); }

/* ---------- FOR YOU ---------- */
async function forUser() { const id = +$('#uid').value; hideMsg($('#umsg')); skeleton($('#ugrid'), 6);
  try { const g = $('#ugenre').value; const d = await api(`/api/user/${id}/recommend?n=12` + (g ? '&genre=' + encodeURIComponent(g) : '')); const u = d.user;
    $('#uprof').innerHTML = `<div class="card"><div class="big-n">User ${u.user_id}</div><p>${u.gender === 'F' ? 'Female' : 'Male'} · age group ${u.age}</p><p style="margin-top:10px"><b>${u.n_ratings}</b> ratings · mean <b>${u.mean_rating}</b>★</p><div class="favs">${u.fav_genres.map(([g, c]) => `<span class="tag hit">${esc(g)} · ${c}</span>`).join('')}</div></div>
      <div class="card"><h3>Highest-rated by this user</h3><div class="minis">${u.top_rated.map(m => `<div class="mm">${poster(m)}<small style="color:var(--mute)">gave ${m.your_rating}★</small></div>`).join('')}</div></div>`; $('#uprof').classList.remove('hidden');
    $('#uTitle').style.display = ''; $('#ugrid').innerHTML = d.results.map((m, i) => card(m, i, { pred: true })).join('');
    $$('[data-pred]', $('#ugrid')).forEach(b => b.onclick = () => { $('#pu').value = id; const m = d.results.find(x => x.movie_id == b.dataset.pred); pickPredict(m); $$('#nav button')[2].click(); });
    renderTrace($('#utrace'), d.trace, d.total_ms, 'Behind the scenes — matrix-factorisation pipeline'); }
  catch (e) { $('#ugrid').innerHTML = ''; showMsg(e.message, $('#umsg')); } }
$('#uidBtn').onclick = forUser; $('#uid').addEventListener('keydown', e => e.key === 'Enter' && forUser()); $('#ugenre').onchange = forUser;
$('#uidRand').onclick = () => { $('#uid').value = 1 + Math.floor(Math.random() * 6040); forUser(); };

/* ---------- PREDICT ---------- */
let pMovie = null;
function pickPredict(m) { pMovie = m; $('#pq').value = m.title; predictNow(); }
autocomplete($('#pq'), $('#psuggest'), pickPredict);
async function predictNow() { if (!pMovie) return; const out = $('#pout');
  try { const d = await api(`/api/predict?user=${$('#pu').value}&movie=${pMovie.movie_id}`); const P = d.parts, tot = Math.max(...[P.global_mean, Math.abs(P.user_bias), Math.abs(P.item_bias), Math.abs(P.interaction)]) || 1;
    const part = (l, v, c, abs) => `<div class="bar"><span>${l}</span><i><s style="width:${Math.min(100, Math.abs(v) / (abs ? 5 : 1.2) * 100)}%;background:${v < 0 ? 'var(--rose)' : c}"></s></i><span>${v > 0 && !abs ? '+' : ''}${v.toFixed(2)}</span></div>`;
    out.innerHTML = `<div class="card gauge"><p style="color:var(--mute)">Predicted rating — user ${d.user_id}</p><div class="big">${d.predicted.toFixed(2)}</div>${stars(d.predicted)}<p style="font-weight:600">${esc(d.movie.title)} <span style="color:var(--mute)">(${d.movie.year})</span></p>
      <p style="margin-top:10px;color:var(--mute)">${d.actual ? `This user actually rated it <b style="color:var(--teal)">${d.actual}★</b> → error ${(d.predicted - d.actual).toFixed(2)}` : 'This user has not rated this movie — a true prediction.'}</p></div>
      <div class="card parts"><h3>How the number is built</h3><p class="note" style="margin:0 0 6px">r̂ = μ + b<sub>user</sub> + b<sub>movie</sub> + p<sub>user</sub>·q<sub>movie</sub></p>
      ${part('Global mean μ', P.global_mean, 'var(--mute)', true)}${part('User bias', P.user_bias, 'var(--teal)')}${part('Movie bias', P.item_bias, 'var(--amb)')}${part('Taste match p·q', P.interaction, 'var(--violet)')}
      <p class="note">Positive bars push the rating up (generous user, great movie, taste match); red bars pull it down.</p></div>`; out.classList.remove('hidden'); }
  catch (e) { out.innerHTML = `<div class="msg">${esc(e.message)}</div>`; out.classList.remove('hidden'); } }
$('#pBtn').onclick = predictNow;

/* ---------- ANALYTICS ---------- */
const COL = ['#f5b94a', '#4fd1c5', '#8b7cf6', '#f0647a', '#ff8a4c'];
function barSvg(labels, vals, { color = '#f5b94a', fmt = v => v, h = 230, horizontal = false } = {}) {
  const W = 520, H = h, m = { l: horizontal ? 92 : 36, r: 12, t: 14, b: horizontal ? 8 : 40 }, mx = Math.max(...vals) * 1.1, n = vals.length;
  let s = `<svg viewBox="0 0 ${W} ${horizontal ? Math.max(H, n * 24 + 20) : H}">`;
  if (horizontal) { const hh = Math.max(H, n * 24 + 20), bh = (hh - m.t - m.b) / n; vals.forEach((v, i) => { const w = (W - m.l - m.r - 40) * v / mx, y = m.t + i * bh;
      s += `<text x="${m.l - 8}" y="${y + bh / 2 + 4}" text-anchor="end">${esc(labels[i])}</text><rect x="${m.l}" y="${y + 3}" width="${w}" height="${bh - 6}" rx="4" fill="${color}" opacity=".9"/><text class="val" x="${m.l + w + 6}" y="${y + bh / 2 + 4}">${fmt(v)}</text>`; }); }
  else { const bw = (W - m.l - m.r) / n; for (let g = 0; g <= 4; g++) { const y = m.t + (H - m.t - m.b) * g / 4; s += `<line x1="${m.l}" x2="${W - m.r}" y1="${y}" y2="${y}" stroke="#252d4a"/><text x="${m.l - 6}" y="${y + 4}" text-anchor="end">${fmt(mx * (1 - g / 4))}</text>`; }
    vals.forEach((v, i) => { const bh = (H - m.t - m.b) * v / mx, x = m.l + i * bw + bw * .15; s += `<rect x="${x}" y="${H - m.b - bh}" width="${bw * .7}" height="${bh}" rx="5" fill="${Array.isArray(color) ? color[i % color.length] : color}"/><text class="val" x="${x + bw * .35}" y="${H - m.b - bh - 5}" text-anchor="middle">${fmt(v)}</text><text x="${x + bw * .35}" y="${H - m.b + 16}" text-anchor="middle">${esc(labels[i])}</text>`; }); }
  return s + '</svg>'; }
function lineSvg(xs, ys, { color = '#4fd1c5', logy = false, xl = '', yl = '' } = {}) { const W = 520, H = 240, m = { l: 48, r: 14, t: 14, b: 34 }; const f = logy ? Math.log10 : v => v;
  const fy = ys.map(f), mn = Math.min(...fy) - (logy ? 0 : (Math.max(...fy) - Math.min(...fy)) * .15), mxv = Math.max(...fy) + (logy ? 0.1 : (Math.max(...fy) - Math.min(...fy)) * .1);
  const X = i => m.l + (W - m.l - m.r) * i / (xs.length - 1), Y = v => m.t + (H - m.t - m.b) * (1 - (v - mn) / (mxv - mn));
  let s = `<svg viewBox="0 0 ${W} ${H}">`; for (let g = 0; g <= 4; g++) { const v = mn + (mxv - mn) * g / 4; s += `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="#252d4a"/><text x="${m.l - 6}" y="${Y(v) + 4}" text-anchor="end">${logy ? Math.round(10 ** v) : v.toFixed(3)}</text>`; }
  s += `<polyline fill="none" stroke="${color}" stroke-width="3" stroke-linejoin="round" points="${fy.map((v, i) => `${X(i)},${Y(v)}`).join(' ')}"/>`;
  if (xs.length < 12) fy.forEach((v, i) => s += `<circle cx="${X(i)}" cy="${Y(v)}" r="4.5" fill="${color}"/><text class="val" x="${X(i)}" y="${Y(v) - 10}" text-anchor="middle">${ys[i]}</text>`);
  xs.forEach((x, i) => { if (xs.length < 12 || i % Math.ceil(xs.length / 6) === 0) s += `<text x="${X(i)}" y="${H - 10}" text-anchor="middle">${x}</text>`; });
  return s + `<text x="${W / 2}" y="${H}" text-anchor="middle" opacity="0">${xl}</text></svg>`; }
function groupedSvg(groups, series, colors) { const W = 520, H = 250, m = { l: 36, r: 10, t: 24, b: 36 }, gw = (W - m.l - m.r) / groups.length, bw = gw * .8 / series.length; const mx = Math.max(...series.flatMap(s => s.v)) * 1.1;
  let s = `<svg viewBox="0 0 ${W} ${H}">`; for (let g = 0; g <= 4; g++) { const y = m.t + (H - m.t - m.b) * g / 4; s += `<line x1="${m.l}" x2="${W - m.r}" y1="${y}" y2="${y}" stroke="#252d4a"/><text x="${m.l - 6}" y="${y + 4}" text-anchor="end">${(mx * (1 - g / 4)).toFixed(2)}</text>`; }
  groups.forEach((g, gi) => { series.forEach((se, si) => { const h = (H - m.t - m.b) * se.v[gi] / mx, x = m.l + gi * gw + gw * .1 + si * bw; s += `<rect x="${x}" y="${H - m.b - h}" width="${bw - 2}" height="${h}" rx="3" fill="${colors[si]}"/>`; }); s += `<text x="${m.l + gi * gw + gw / 2}" y="${H - 14}" text-anchor="middle">${g}</text>`; });
  series.forEach((se, i) => s += `<rect x="${m.l + i * 118}" y="3" width="10" height="10" rx="2" fill="${colors[i]}"/><text x="${m.l + i * 118 + 14}" y="12">${esc(se.n)}</text>`); return s + '</svg>'; }
function cmGrid(el, mat, labels, { pct = false, good = '#2f9e83', bad = '#b4455a' } = {}) { const n = mat.length, tot = mat.map(r => r.reduce((a, b) => a + b, 0)), mx = Math.max(...mat.flat());
  let h = `<div class="cm" style="grid-template-columns:70px repeat(${n},1fr)"><div class="h"></div>${labels.map(l => `<div class="h">Pred ${l}</div>`).join('')}`;
  mat.forEach((r, i) => { h += `<div class="h">Actual ${labels[i]}</div>` + r.map((v, j) => { const k = pct ? v / tot[i] : v / mx, c = i === j ? good : bad; return `<div class="c" style="background:${c};opacity:${.28 + .72 * Math.min(1, pct ? k * (i === j ? 1.1 : 3) : k)}">${pct ? Math.round(v / tot[i] * 100) + '%' : v.toLocaleString()}${!pct ? `<small>${n === 2 ? ['TN', 'FP', 'FN', 'TP'][i * 2 + j] : ''}</small>` : ''}</div>`; }).join(''); }); el.innerHTML = h + '</div>'; }
async function loadAnalytics() { analyticsLoaded = true; const [M, S] = await Promise.all([api('/api/metrics'), api('/api/stats')]);
  $('#kpis').innerHTML = [[S.n_ratings.toLocaleString(), 'ratings'], [S.n_users.toLocaleString(), 'users'], [S.n_movies.toLocaleString(), 'movies'], [(S.sparsity * 100).toFixed(1) + '%', 'matrix sparsity'], [S.mean_rating, 'mean rating'], [M.params.k, 'latent factors']].map(([a, b]) => `<div class="kpi"><b>${a}</b><span>${b}</span></div>`).join('');
  const best = Math.min(...M.models.map(m => m.rmse)); $('#modelTable').innerHTML = `<table><tr><th>Model</th><th>RMSE</th><th>MAE</th></tr>${M.models.map(m => `<tr class="${m.rmse === best ? 'best' : ''}"><td>${m.model}</td><td>${m.rmse.toFixed(4)}</td><td>${m.mae.toFixed(4)}</td></tr>`).join('')}</table><p class="note">Train ${M.split.train.toLocaleString()} · Test ${M.split.test.toLocaleString()} ratings. Item-kNN evaluated on a 4,000-rating sample.</p>`;
  const c = M.confusion_binary; $('#cmetrics').innerHTML = [['Accuracy', c.accuracy], ['Precision', c.precision], ['Recall', c.recall], ['F1-score', c.f1], ['ROC-AUC', c.auc], ['5★ exact', M.confusion_5.accuracy]].map(([a, b]) => `<div><b>${(b * 100).toFixed(1)}%</b><span>${a}</span></div>`).join('');
  cmGrid($('#cm2'), c.matrix, ['Dislike', 'Like']); $('#cm2note').innerHTML = `TP ${c.tp.toLocaleString()} · TN ${c.tn.toLocaleString()} · FP ${c.fp.toLocaleString()} · FN ${c.fn.toLocaleString()}. Precision = TP/(TP+FP), Recall = TP/(TP+FN).`;
  cmGrid($('#cm5'), M.confusion_5.matrix, [1, 2, 3, 4, 5], { pct: true }); $('#cm5note').textContent = `${(M.confusion_5.within_one_star * 100).toFixed(1)}% of predictions are within ±1 star of the true rating.`;
  $('#chRating').innerHTML = barSvg(['1★', '2★', '3★', '4★', '5★'], Object.values(S.rating_dist), { fmt: v => v >= 1000 ? Math.round(v / 1000) + 'k' : Math.round(v) });
  const g = Object.entries(S.genre_counts).sort((a, b) => a[1] - b[1]); $('#chGenre').innerHTML = barSvg(g.map(x => x[0]), g.map(x => x[1]), { horizontal: true, color: '#4fd1c5', h: 400, fmt: v => v >= 1000 ? Math.round(v / 1000) + 'k' : Math.round(v) });
  $('#chK').innerHTML = lineSvg(M.k_sweep.map(d => d.k), M.k_sweep.map(d => d.rmse), { color: '#4fd1c5' });
  const R = M.ranking, names = ['Random', 'Popularity', 'SVD / ALS', 'SVD + popularity prior (served)']; $('#chRank').innerHTML = groupedSvg(['Prec@10', 'Recall@10', 'NDCG@10', 'Hit@10'], names.map(n => ({ n: n.replace(' (served)', '').replace('SVD + popularity prior', 'SVD+pop'), v: ['precision', 'recall', 'ndcg', 'hit_rate'].map(k => R[n][k]) })), ['#566', '#8b93ad', '#4fd1c5', '#f5b94a']);
  $('#chUser').innerHTML = barSvg(S.user_activity.map(x => x[0]), S.user_activity.map(x => x[1]), { color: '#f0647a', fmt: v => Math.round(v) });
  $('#chTail').innerHTML = lineSvg(S.movie_long_tail.map((_, i) => i * 37), S.movie_long_tail.map(v => Math.max(v, 1)), { color: '#f5b94a', logy: true });
  const imgs = ['01_rating_distribution', '02_genre_popularity', '03_user_activity', '04_long_tail', '05_model_rmse', '06_confusion_binary', '07_confusion_5class', '08_roc_curve', '09_rmse_vs_k', '10_ranking_metrics'];
  $('#gallery').innerHTML = imgs.map(i => `<img loading="lazy" src="/graphs/${i}.png" alt="${i}">`).join(''); $$('#gallery img').forEach(im => im.onclick = () => { const lb = document.createElement('div'); lb.className = 'lightbox'; lb.innerHTML = `<img src="${im.src}">`; lb.onclick = () => lb.remove(); document.body.append(lb); }); }

/* ---------- boot ---------- */
(async () => { try { const h = await api('/api/health'); $('#health').classList.add('ok'); $('#healthTxt').textContent = `${h.ratings.toLocaleString()} ratings · ${h.movies.toLocaleString()} movies`;
  const gs = await api('/api/genres'); ['#genre', '#ugenre'].forEach(id => $(id).innerHTML += gs.map(g => `<option>${g}</option>`).join('')); loadTop();
  const pm = await api('/api/search?q=Inception&limit=1'); if (pm[0]) { pMovie = pm[0]; $('#pq').value = pm[0].title; } }
  catch { $('#health').classList.add('bad'); $('#healthTxt').textContent = 'backend offline'; } })();
