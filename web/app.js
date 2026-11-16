import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const $ = (s) => document.querySelector(s);
const api = async (path, opts = {}) => {
  if (opts.json) { opts.body = JSON.stringify(opts.json); opts.headers = { 'content-type': 'application/json' }; }
  const r = await fetch('/api' + path, opts);
  if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch {} throw new Error(m); }
  return (r.headers.get('content-type') || '').includes('json') ? r.json() : r.text();
};
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
let toastT;
const toast = (msg, err) => { const t = $('#toast'); t.textContent = msg; t.className = err ? 'err' : ''; t.hidden = false; clearTimeout(toastT); toastT = setTimeout(() => (t.hidden = true), err ? 6000 : 2600); };

const state = { meta: null, mode: 'text', images: [], modelUpload: null, refSel: new Set(), refs: [], builds: [], current: null, fav: false, busy: false };
const STAGE = { intake: '输入整理', references: '找参考', brief: '需求分析', program: '生成指令', repair: '校验修复', critique: '看图自评', voxelize: '体素化', remap: '换材质', export: '导出入库', render: '渲染', error: '出错' };
const ST = { run: '进行中', done: '完成', warn: '注意', error: '失败' };

/* ---------- 3D 视图 ---------- */
const canvas = $('#canvas');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 5000);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
scene.add(new THREE.HemisphereLight(0xdfe9ff, 0x5a5346, 2.1));
const sun = new THREE.DirectionalLight(0xfff2dd, 2.2); sun.position.set(0.6, 1, 0.45); scene.add(sun);
let modelRoot = null, grid = null, home = null;
function resize() {
  const r = canvas.parentElement.getBoundingClientRect();
  renderer.setSize(r.width, r.height, false); camera.aspect = r.width / Math.max(1, r.height); camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(canvas.parentElement);
(function loop() { controls.update(); renderer.render(scene, camera); requestAnimationFrame(loop); })();

function showModel(url) {
  new GLTFLoader().load(url, (gltf) => {
    if (modelRoot) scene.remove(modelRoot);
    if (grid) scene.remove(grid);
    modelRoot = gltf.scene;
    modelRoot.traverse((o) => {
      if (!o.isMesh) return;
      const m = o.material;
      if (m.map) { m.map.magFilter = THREE.NearestFilter; m.map.minFilter = THREE.NearestMipmapLinearFilter; m.map.generateMipmaps = true; m.map.needsUpdate = true; }
      if (m.name.includes('translucent')) { m.transparent = true; m.depthWrite = false; } else { m.alphaTest = 0.5; m.transparent = false; }
    });
    scene.add(modelRoot);
    const box = new THREE.Box3().setFromObject(modelRoot), size = box.getSize(new THREE.Vector3()), c = box.getCenter(new THREE.Vector3());
    const span = Math.max(size.x, size.z);
    grid = new THREE.GridHelper(Math.ceil(span / 2) * 2 + 16, Math.ceil(span / 2) * 2 + 16, 0x3a4150, 0x2a2f3a); grid.position.y = -0.01; scene.add(grid);
    const r = size.length() / 2, d = r / Math.sin((camera.fov * Math.PI) / 360) * 1.05;
    home = { pos: new THREE.Vector3(c.x + d * 0.62, c.y + d * 0.45, c.z + d * 0.65), target: c };
    camera.position.copy(home.pos); controls.target.copy(c); camera.near = Math.max(0.1, d / 200); camera.far = d * 20; camera.updateProjectionMatrix();
    $('#vp-empty').hidden = true;
  }, undefined, (e) => toast('3D 预览加载失败: ' + e.message, true));
}
$('#vp-reset').onclick = () => { if (home) { camera.position.copy(home.pos); controls.target.copy(home.target); } };
$('#vp-spin').onclick = (e) => { controls.autoRotate = !controls.autoRotate; e.target.classList.toggle('on', controls.autoRotate); };

/* ---------- 标签页 ---------- */
function tabs(sel, attr, onChange) {
  document.querySelectorAll(sel + ' button').forEach((b) => (b.onclick = () => {
    document.querySelectorAll(sel + ' button').forEach((x) => x.classList.toggle('on', x === b)); onChange(b.dataset[attr]);
  }));
}
tabs('#mode-tabs', 'mode', (m) => { state.mode = m; $('#mode-text').hidden = m !== 'text'; $('#mode-model').hidden = m !== 'model'; $('#size-row').hidden = m === 'model'; });
tabs('#detail-tabs', 'tab', (t) => ['flow', 'report', 'materials', 'program', 'renders'].forEach((n) => ($('#tab-' + n).hidden = n !== t)));
tabs('#lib-tabs', 'lib', (t) => { $('#lib-builds').hidden = t !== 'builds'; $('#lib-refs').hidden = t !== 'refs'; });
const openTab = (t) => document.querySelector(`#detail-tabs button[data-tab=${t}]`).click();

/* ---------- 上传 ---------- */
async function upload(file) { const fd = new FormData(); fd.append('file', file); return api('/upload', { method: 'POST', body: fd }); }
function dropzone(zone, input, onFiles) {
  zone.onclick = () => input.click();
  input.onchange = () => { onFiles([...input.files]); input.value = ''; };
  zone.ondragover = (e) => { e.preventDefault(); zone.classList.add('over'); };
  zone.ondragleave = () => zone.classList.remove('over');
  zone.ondrop = (e) => { e.preventDefault(); zone.classList.remove('over'); onFiles([...e.dataTransfer.files]); };
}
dropzone($('#drop-images'), $('#file-images'), async (files) => {
  for (const f of files) { try { state.images.push(await upload(f)); } catch (e) { toast(e.message, true); } }
  renderImageChips();
});
function renderImageChips() {
  $('#chips-images').innerHTML = state.images.map((u, i) => `<span class="chip" data-i="${i}">${esc(u.original)}<b>×</b></span>`).join('');
  $('#chips-images').querySelectorAll('.chip').forEach((c) => (c.onclick = () => { state.images.splice(+c.dataset.i, 1); renderImageChips(); }));
}
dropzone($('#drop-model'), $('#file-model'), async ([f]) => {
  if (!f) return;
  try { state.modelUpload = await upload(f); $('#drop-model').textContent = f.name; $('#drop-model').classList.add('has'); } catch (e) { toast(e.message, true); }
});
dropzone($('#drop-refs'), $('#file-refs'), async (files) => {
  for (const f of files) {
    const fd = new FormData(); fd.append('file', f); fd.append('as_build', $('#ref-as-build').checked);
    try { await api('/refs', { method: 'POST', body: fd }); } catch (e) { toast(`${f.name}: ${e.message}`, true); }
  }
  await loadRefs(); await loadBuilds();
});

/* ---------- 参考库 ---------- */
async function loadRefs() {
  state.refs = await api('/refs');
  $('#ref-list').innerHTML = state.refs.map((r) => {
    const s = r.summary || {};
    const meta = r.kind === 'structure' ? `${(s.size_xyz || []).join('×')} · ${s.blocks} 块 · ${esc(s.format || '')}<br>${(s.materials || []).slice(0, 4).map((m) => esc(m.block)).join('、')}` : '图片';
    return `<div class="refcard"><div class="row"><b>${esc(r.name)}</b><button class="ghost small danger" data-del="${r.id}">删除</button></div><div class="m">${meta}</div></div>`;
  }).join('') || '<p class="muted">还没有参考文件。</p>';
  $('#ref-list').querySelectorAll('[data-del]').forEach((b) => (b.onclick = async () => { await api('/refs/' + b.dataset.del, { method: 'DELETE' }); state.refSel.delete(b.dataset.del); loadRefs(); }));
  $('#chips-refs').innerHTML = state.refs.map((r) => `<span class="chip ${state.refSel.has(r.id) ? 'on' : ''}" data-id="${r.id}">${esc(r.name)}</span>`).join('') || '<span class="muted">参考库为空</span>';
  $('#chips-refs').querySelectorAll('.chip').forEach((c) => (c.onclick = () => { state.refSel.has(c.dataset.id) ? state.refSel.delete(c.dataset.id) : state.refSel.add(c.dataset.id); c.classList.toggle('on'); }));
}

/* ---------- 作品库 ---------- */
async function loadBuilds() {
  state.builds = await api(`/builds?q=${encodeURIComponent($('#lib-q').value)}&favorite=${state.fav}`);
  $('#build-list').innerHTML = state.builds.map((b) => `
    <div class="card ${state.current?.id === b.id ? 'sel' : ''}" data-id="${b.id}">
      <img src="/api/builds/${b.id}/file/thumb.png" alt="" loading="lazy">
      <div><div class="t">${esc(b.title)}</div>
        <div class="m">${b.size.join('×')} · ${b.blocks} 块 · ${esc(b.version)}</div>
        <div class="m">${{ text: '文字', model: '3D 模型', import: '导入', mcp: 'MCP' }[b.mode] || b.mode}${b.parent_id ? ' · 修改版' : ''}${b.tags.length ? ' · ' + esc(b.tags.join(' ')) : ''}</div>
        <div class="acts"><button class="fav ${b.favorite ? 'on' : ''}" data-a="fav" title="收藏">★</button><button data-a="rename">改名</button><button data-a="tags">标签</button><button data-a="del" class="danger">删除</button></div>
      </div></div>`).join('') || '<p class="muted">作品库是空的。</p>';
  $('#build-list').querySelectorAll('.card').forEach((card) => {
    const id = card.dataset.id, b = state.builds.find((x) => x.id === id);
    card.onclick = () => openBuild(id);
    card.querySelectorAll('[data-a]').forEach((btn) => (btn.onclick = async (e) => {
      e.stopPropagation(); const a = btn.dataset.a;
      if (a === 'fav') await api('/builds/' + id, { method: 'PATCH', json: { favorite: !b.favorite } });
      if (a === 'rename') { const t = prompt('新标题', b.title); if (!t) return; await api('/builds/' + id, { method: 'PATCH', json: { title: t } }); }
      if (a === 'tags') { const t = prompt('标签（空格分隔）', b.tags.join(' ')); if (t === null) return; await api('/builds/' + id, { method: 'PATCH', json: { tags: t.split(/[\s,，]+/).filter(Boolean) } }); }
      if (a === 'del') { if (!confirm(`删除「${b.title}」及其全部文件？`)) return; await api('/builds/' + id, { method: 'DELETE' }); if (state.current?.id === id) state.current = null; }
      loadBuilds();
    }));
  });
}
$('#lib-q').oninput = () => loadBuilds();
$('#lib-fav').onclick = (e) => { state.fav = !state.fav; e.target.classList.toggle('on', state.fav); e.target.style.color = state.fav ? 'var(--warn)' : ''; loadBuilds(); };

async function openBuild(id, keepTab) {
  const b = (state.current = await api('/builds/' + id));
  showModel(`/api/builds/${id}/file/model.glb?t=${Date.now()}`);
  $('#vp-title').innerHTML = `${esc(b.title)}<small>${b.size.join(' × ')} · ${b.blocks} 块 · Java ${esc(b.version)}</small>`;
  $('#iterate-box').hidden = !b.program;
  const rep = b.report || {}, st = rep.stats || {};
  const issues = [...(rep.dsl_errors || []).map((m) => ['err', '指令错误：' + m]), ...(rep.errors || []).map((m) => ['err', m]), ...(rep.warnings || []).map((m) => ['warn', m])];
  $('#tab-report').innerHTML = `<div class="kv">
      <div><span>尺寸 (x·y·z)</span>${b.size.join(' × ')}</div><div><span>方块数</span>${b.blocks}</div><div><span>方块种类</span>${st.palette ?? '-'}</div>
      <div><span>自动补连接</span>${st.autoconnected ?? 0} 处</div><div><span>预览网格</span>${rep.mesh?.triangles ?? '-'} 三角面</div><div><span>用时</span>${rep.seconds ?? '-'} s</div>
      <div><span>模型</span>${esc(b.provider || '-')} ${esc(b.model || '')}</div><div><span>来源</span>${esc(rep.source?.format || b.mode)}</div></div>` +
    (issues.length ? issues.map(([k, m]) => `<div class="issue ${k}">${esc(m)}</div>`).join('') : '<div class="issue ok">校验通过：方块 id 全部有效，结构连通且落地。</div>') +
    (b.prompt ? `<p class="muted" style="margin-top:10px">描述：${esc(b.prompt)}</p>` : '') +
    (b.brief?.concept ? `<p class="muted">方案：${esc(b.brief.concept)}</p>` : '');
  const mats = rep.materials || [];
  $('#tab-materials').innerHTML = mats.length ? `<table><tr><th>方块</th><th>数量</th><th>约合组（64）</th></tr>${mats.map((m) => `<tr><td>${esc(m.block.replace('minecraft:', ''))}</td><td class="num">${m.count}</td><td class="num">${(m.count / 64).toFixed(1)}</td></tr>`).join('')}</table>` : '<p class="muted">无数据</p>';
  $('#program-json').textContent = b.program ? JSON.stringify(b.program, null, 1) : '这个作品不是由指令生成的（3D 模型转换或导入）。';
  renderRenders(b);
  document.querySelectorAll('#build-list .card').forEach((c) => c.classList.toggle('sel', c.dataset.id === id));
  if (!keepTab && issues.some(([k]) => k === 'err')) openTab('report');
}

function renderRenders(b) {
  const f = (n) => `/api/builds/${b.id}/file/${n}`;
  const renders = b.files.filter((n) => n.startsWith('render_') && n.endsWith('.png'));
  $('#tab-renders').innerHTML = `
    <div class="btnrow">
      <a href="${f('build.litematic')}?download=1">下载 .litematic</a><a href="${f('build.schem')}?download=1">下载 .schem (v3)</a>
      <a href="#" data-x="schem2">.schem (v2 旧版)</a><a href="#" data-x="obj">OBJ + 贴图 (Blender / MCprep)</a>
      <a href="${f('model.glb')}?download=1">GLB</a>${b.program ? `<a href="${f('program.json')}?download=1">指令 JSON</a>` : ''}
    </div>
    <div class="render-opts">
      <label>宽<input id="r-w" type="number" value="1600"></label><label>高<input id="r-h" type="number" value="1200"></label>
      <label>采样<input id="r-s" type="number" value="64"></label><label>方位角<input id="r-az" type="number" value="35"></label>
      <label>俯角<input id="r-el" type="number" value="28"></label><label>张数<input id="r-n" type="number" value="1" min="1" max="12"></label>
      <button id="btn-render" class="primary" style="flex:none" ${state.meta.blender ? '' : 'disabled title="未找到 Blender，见设置"'}>Blender 渲染</button>
      <button id="btn-snippet" style="flex:none" title="交给已连接 Blender MCP 的模型执行">复制 Blender MCP 脚本</button>
    </div>
    <div class="renders"><a href="${f('preview.png')}" target="_blank"><img src="${f('preview.png')}?t=${Date.now()}" alt="四视角预览"></a>
      ${renders.map((n) => `<a href="${f(n)}" target="_blank"><img src="${f(n)}" alt="${n}"></a>`).join('')}</div>`;
  $('#tab-renders').querySelectorAll('[data-x]').forEach((a) => (a.onclick = async (e) => {
    e.preventDefault();
    try { const r = await api(`/builds/${b.id}/export/${a.dataset.x}`, { method: 'POST' }); location.href = f(r.file) + '?download=1'; } catch (err) { toast(err.message, true); }
  }));
  $('#btn-render').onclick = async () => {
    const body = { width: +$('#r-w').value, height: +$('#r-h').value, samples: +$('#r-s').value, azimuth: +$('#r-az').value, elevation: +$('#r-el').value, views: +$('#r-n').value };
    try { const { job_id } = await api(`/builds/${b.id}/render`, { method: 'POST', json: body }); openTab('flow'); await follow(job_id, false); await openBuild(b.id, true); openTab('renders'); } catch (e) { toast(e.message, true); }
  };
  $('#btn-snippet').onclick = async () => {
    const code = await api(`/builds/${b.id}/blender_snippet`);
    try { await navigator.clipboard.writeText(code); toast('已复制。把它交给 Blender MCP 的“执行代码”工具即可在你的 Blender 里渲染。'); } catch { toast('复制失败，请在 /api/builds/' + b.id + '/blender_snippet 手动获取', true); }
  };
}

/* ---------- 生成 ---------- */
function addEvent(ev) {
  const tl = $('#timeline');
  const last = tl.lastElementChild;
  const html = `<span class="st">${STAGE[ev.stage] || ev.stage} · ${ST[ev.status] || ev.status}</span><span>${esc(ev.message)}</span>`;
  if (last && last.dataset.stage === ev.stage && last.classList.contains('run')) { last.className = ev.status; last.innerHTML = html; }
  else { const li = document.createElement('li'); li.className = ev.status; li.dataset.stage = ev.stage; li.innerHTML = html; tl.appendChild(li); }
  tl.parentElement.scrollTop = tl.parentElement.scrollHeight;
}
async function follow(jobId, clear = true) {
  if (clear) $('#timeline').innerHTML = '';
  let since = 0;
  for (;;) {
    const j = await api(`/jobs/${jobId}?since=${since}`);
    j.events.forEach(addEvent); since = j.next;
    if (j.status === 'done') return j.result;
    if (j.status === 'error') throw new Error(j.error);
    await new Promise((r) => setTimeout(r, 500));
  }
}
async function generate(extra = {}) {
  if (state.busy) return;
  const body = {
    mode: state.mode, version: $('#version').value, prompt: state.mode === 'text' ? $('#prompt').value : $('#model-prompt').value,
    style: $('#style').value, max_size: [+$('#size-x').value, +$('#size-y').value, +$('#size-z').value],
    image_uploads: state.images.map((u) => u.name), ref_ids: [...state.refSel],
    model_upload: state.modelUpload?.name, voxel: { size: +$('#vox-size').value, palette: $('#vox-palette').value, solid: $('#vox-solid').checked, up: $('#vox-up').value }, ...extra,
  };
  state.busy = true; $('#btn-generate').disabled = $('#btn-iterate').disabled = true; $('#btn-generate').textContent = '生成中…';
  openTab('flow');
  try {
    const { job_id } = await api('/generate', { method: 'POST', json: body });
    const rec = await follow(job_id);
    await loadBuilds(); await openBuild(rec.id);
  } catch (e) { toast(e.message, true); }
  finally { state.busy = false; $('#btn-generate').disabled = $('#btn-iterate').disabled = false; $('#btn-generate').textContent = '生成'; }
}
$('#btn-generate').onclick = () => generate();
$('#btn-iterate').onclick = () => {
  const p = $('#iterate-prompt').value.trim();
  if (!p || !state.current) return toast('请写下要怎么改', true);
  generate({ mode: 'text', prompt: p, parent_id: state.current.id, version: state.current.version });
};

/* ---------- 设置 ---------- */
function applyMeta(m) {
  state.meta = m;
  $('#version').innerHTML = m.versions.map((v) => `<option value="${v.id}">Java ${v.id}${v.type !== 'release' ? '（快照）' : ''}</option>`).join('');
  $('#version').value = m.config.default_version || m.latest;
  $('#vox-palette').innerHTML = m.palettes.map((p) => `<option value="${p}">${{ all: '全部实心方块', color: '混凝土 + 羊毛 + 陶瓦', concrete: '仅混凝土', wool: '仅羊毛', terracotta: '仅陶瓦', stone: '石质', wood: '木板' }[p]}</option>`).join('');
  const c = m.config, badge = $('#provider-badge');
  badge.textContent = c.provider === 'mock' ? '离线模拟（未接入模型）' : `${c.provider} · ${c.model || '未填模型名'}`;
  badge.className = 'badge' + (c.provider === 'mock' ? ' mock' : '');
}
$('#btn-settings').onclick = () => {
  const m = state.meta, c = m.config;
  $('#cfg-provider').innerHTML = Object.entries(m.presets).map(([k, p]) => `<option value="${k}">${k} — ${esc(p.note)}</option>`).join('');
  $('#cfg-provider').value = c.provider; $('#cfg-model').value = c.model; $('#cfg-base').value = c.base_url; $('#cfg-key').value = '';
  $('#cfg-key-hint').textContent = c.has_key ? '已保存' : '未设置';
  $('#cfg-repair').value = c.repair_rounds; $('#cfg-critique').value = c.critique_rounds; $('#cfg-vision').checked = c.vision;
  $('#cfg-searx').value = c.searxng_url; $('#cfg-blender').value = c.blender_path;
  $('#cfg-blender-hint').textContent = m.blender ? '已找到' : '未找到';
  const upd = () => { const p = m.presets[$('#cfg-provider').value]; $('#cfg-base').placeholder = p.base_url || '必填'; $('#cfg-note').textContent = 'Key 只保存在本机 workspace/config.json；也可以用环境变量 ATELIER_API_KEY。'; };
  $('#cfg-provider').onchange = upd; upd();
  $('#dlg-settings').showModal();
};
$('#cfg-save').onclick = async (e) => {
  e.preventDefault();
  try {
    applyMeta(await api('/config', { method: 'POST', json: {
      provider: $('#cfg-provider').value, model: $('#cfg-model').value.trim(), base_url: $('#cfg-base').value.trim(), api_key: $('#cfg-key').value,
      repair_rounds: +$('#cfg-repair').value, critique_rounds: +$('#cfg-critique').value, vision: $('#cfg-vision').checked,
      searxng_url: $('#cfg-searx').value.trim(), blender_path: $('#cfg-blender').value.trim() || 'blender' } }));
    $('#dlg-settings').close(); toast('已保存');
  } catch (err) { toast(err.message, true); }
};

/* ---------- 启动 ---------- */
(async () => {
  try {
    applyMeta(await api('/meta')); await loadRefs(); await loadBuilds();
    if (state.builds[0]) openBuild(state.builds[0].id);
  } catch (e) { toast('无法连接后端: ' + e.message, true); }
  resize();
})();
