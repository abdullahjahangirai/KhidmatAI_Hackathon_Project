/* ================================================================
   KhidmatAI — Admin Dashboard Application (admin.js)
   All data synced live with SQLite via /api endpoints.
   ================================================================ */

const A = { token: localStorage.getItem('kai_admin_token') || '' };

// ---------------------------------------------------------------------------
// API helper
// ---------------------------------------------------------------------------
async function api(method, url, body) {
  const opts = { method, headers: {} };
  if (A.token) opts.headers['X-Admin-Key'] = A.token;
  if (body) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  const r = await fetch(url, opts);
  if (r.status === 401) { adminLogout(); throw new Error('Session expired'); }
  return r.json();
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------
async function adminLogin() {
  const user = document.getElementById('loginUser').value.trim();
  const pass = document.getElementById('loginPass').value;
  const errEl = document.getElementById('loginError');
  errEl.style.display = 'none';
  try {
    const r = await fetch('/api/admin/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: user, password: pass }) });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'Login failed');
    A.token = d.token;
    localStorage.setItem('kai_admin_token', d.token);
    showDashboard();
  } catch (e) { errEl.textContent = e.message; errEl.style.display = 'block'; }
}

function adminLogout() {
  A.token = '';
  localStorage.removeItem('kai_admin_token');
  document.getElementById('loginScreen').style.display = 'flex';
  document.getElementById('adminDashboard').style.display = 'none';
}

function showDashboard() {
  document.getElementById('loginScreen').style.display = 'none';
  document.getElementById('adminDashboard').style.display = 'flex';
  loadOverview();
  loadSlides();
  loadLandingSlides();
  loadAlerts();
  loadContactSettings();
  loadOrgs();
  loadOrgPosts();
}

// ---------------------------------------------------------------------------
// Panel navigation
// ---------------------------------------------------------------------------
function showPanel(id) {
  document.querySelectorAll('.admin-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.admin-nav-item[data-panel]').forEach(n => n.classList.remove('active'));
  const panel = document.getElementById('panel-' + id);
  if (panel) panel.classList.add('active');
  const nav = document.querySelector('.admin-nav-item[data-panel="' + id + '"]');
  if (nav) nav.classList.add('active');
  const titles = { overview: 'Dashboard Overview', analytics: 'Analytics', 'landing-hero': 'Landing Page Hero', hero: 'Dashboard Hero Slider', ticker: 'Ticker & Alerts', contact: 'Contact Settings', organizations: 'Organization Registrations', 'org-posts': 'Organization Posts', programs: 'Welfare Programs', facilities: 'Facility Locations' };
  document.getElementById('adminPanelTitle').textContent = titles[id] || id;
  if (id === 'programs') loadAdminPrograms();
  if (id === 'facilities') loadDbFacilities();
  if (id === 'landing-hero') loadLandingSlides();
  if (id === 'analytics') loadAnalytics();
  if (id === 'org-posts') loadOrgPosts();
}

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------
function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.style.display = 'block';
  setTimeout(() => { el.style.display = 'none'; }, 2500);
}

// ---------------------------------------------------------------------------
// Overview stats
// ---------------------------------------------------------------------------
async function loadOverview() {
  try {
    const [health, settings, orgs] = await Promise.all([
      api('GET', '/api/health'),
      api('GET', '/api/admin/settings'),
      api('GET', '/api/admin/organizations'),
    ]);
    document.getElementById('stat-programs').textContent = health.programs_count || 0;
    document.getElementById('stat-orgs').textContent = (orgs.organizations || []).length;
    const pending = (orgs.organizations || []).filter(o => o.status === 'pending').length;
    document.getElementById('stat-pending').textContent = pending;
    document.getElementById('stat-slides').textContent = (settings.hero_slides || []).length;
    const badge = document.getElementById('pendingBadge');
    if (pending > 0) { badge.textContent = pending; badge.style.display = 'inline'; }
    else badge.style.display = 'none';
  } catch (e) { console.error('Overview load error', e); }
}

// ---------------------------------------------------------------------------
// Analytics (real SQLite counts — lightweight hackathon analytics)
// ---------------------------------------------------------------------------
async function loadAnalytics() {
  try {
    const d = await api('GET', '/api/admin/analytics');
    const a = d.analytics || {};
    const set = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = (v == null ? 0 : v); };
    set('an-users', a.total_users);
    set('an-programs', a.total_programs);
    set('an-verified-orgs', a.verified_orgs);
    set('an-pending-orgs', a.pending_orgs);
    set('an-org-posts', a.org_posts);
    set('an-ai-queries', a.ai_queries);
    set('an-matches', a.program_matches);
    set('an-searches', a.searches);
  } catch (e) { console.error('Analytics load error', e); }
}

// ---------------------------------------------------------------------------
// Hero Slides (rich slides: title / description / image / video / button)
// ---------------------------------------------------------------------------
let _slides = [];

async function loadSlides() {
  try {
    const d = await api('GET', '/api/admin/settings');
    _slides = (d.hero_slides || []).slice().sort((a, b) => (a.order || 0) - (b.order || 0));
    renderSlides(_slides);
  } catch (e) { /* silent */ }
}

function renderSlides(slides) {
  const el = document.getElementById('slidesList');
  if (!slides.length) {
    el.innerHTML = '<p class="empty-hint">No slides yet. Click "Add Slide" to create your first hero slide.</p>';
    return;
  }
  el.innerHTML = slides.map((s, i) => {
    const preview = s.video
      ? '<div class="slide-preview video-bg"><i class="fa-solid fa-film"></i></div>'
      : s.image
        ? '<div class="slide-preview" style="background:url(\'' + esc(s.image) + '\') center/cover"></div>'
        : '<div class="slide-preview" style="background:' + (s.bg_color || 'linear-gradient(110deg,#075c4b,#0d8067)') + '"></div>';
    const mediaBadge = s.video
      ? '<span class="slide-badge video"><i class="fa-solid fa-film"></i> video</span>'
      : (s.image
        ? '<span class="slide-badge image"><i class="fa-solid fa-image"></i> image</span>'
        : '<span class="slide-badge color"><i class="fa-solid fa-palette"></i> color</span>');
    const activeBadge = '<span class="slide-badge ' + (s.active ? 'on' : 'off') + '"><i class="fa-solid fa-circle-' + (s.active ? 'check' : 'xmark') + '"></i> ' + (s.active ? 'active' : 'hidden') + '</span>';
    return '<div class="slide-row' + (s.active ? '' : ' inactive') + '">' + preview +
      '<div class="slide-info"><b>' + esc(s.title || 'Untitled slide') + '</b>' +
      '<small>' + esc((s.description || '').slice(0, 90)) + '</small>' +
      '<div class="slide-badges">' + mediaBadge + activeBadge + '</div></div>' +
      '<div class="slide-actions">' +
        '<button class="btn-icon" title="Move up" onclick="moveSlide(\'' + s.id + '\', -1)"' + (i === 0 ? ' disabled' : '') + '><i class="fa-solid fa-arrow-up"></i></button>' +
        '<button class="btn-icon" title="Move down" onclick="moveSlide(\'' + s.id + '\', 1)"' + (i === slides.length - 1 ? ' disabled' : '') + '><i class="fa-solid fa-arrow-down"></i></button>' +
        '<button class="btn-icon" title="' + (s.active ? 'Disable' : 'Enable') + '" onclick="toggleSlide(\'' + s.id + '\')"><i class="fa-solid fa-power-off"></i></button>' +
        '<button class="btn-outline" title="Edit" onclick="openSlideModal(\'' + s.id + '\')"><i class="fa-solid fa-pen"></i></button>' +
        '<button class="btn-outline" title="Preview" onclick="previewSlide(\'' + s.id + '\')"><i class="fa-solid fa-eye"></i></button>' +
        '<button class="btn-danger" title="Delete" onclick="deleteSlide(\'' + s.id + '\')"><i class="fa-solid fa-trash"></i></button>' +
      '</div></div>';
  }).join('');
}

function openSlideModal(editId) {
  const s = editId ? _slides.find(x => x.id === editId) : null;
  document.getElementById('slideModalTitle').textContent = s ? 'Edit Hero Slide' : 'Add Hero Slide';
  document.getElementById('slideEditId').value = s ? s.id : '';
  document.getElementById('slideTitle').value = s ? (s.title || '') : '';
  document.getElementById('slideDescription').value = s ? (s.description || '') : '';
  document.getElementById('slideImage').value = s ? (s.image || '') : '';
  document.getElementById('slideVideo').value = s ? (s.video || '') : '';
  document.getElementById('slideButtonText').value = s ? (s.button_text || '') : '';
  document.getElementById('slideButtonUrl').value = s ? (s.button_url || '') : '';
  document.getElementById('slideActive').checked = s ? s.active !== false : true;
  document.getElementById('slideImageFile').value = '';
  document.getElementById('slideVideoFile').value = '';
  renderSlideUploadPreview('image');
  renderSlideUploadPreview('video');
  document.getElementById('slideModal').style.display = 'flex';
}

function closeSlideModal() {
  document.getElementById('slideModal').style.display = 'none';
}

function renderSlideUploadPreview(kind) {
  const url = document.getElementById(kind === 'image' ? 'slideImage' : 'slideVideo').value.trim();
  const box = document.getElementById(kind === 'image' ? 'slideImagePreview' : 'slideVideoPreview');
  box.innerHTML = '';
  if (!url) return;
  if (kind === 'image') {
    const img = document.createElement('img');
    img.src = url;
    img.alt = 'preview';
    box.appendChild(img);
  } else {
    const v = document.createElement('video');
    v.src = url;
    v.muted = true;
    v.autoplay = true;
    v.loop = true;
    v.playsInline = true;
    box.appendChild(v);
  }
}

async function uploadSlideMedia(kind, fileArg) {
  const fileInput = document.getElementById(kind === 'image' ? 'slideImageFile' : 'slideVideoFile');
  const urlInput = document.getElementById(kind === 'image' ? 'slideImage' : 'slideVideo');
  const file = fileArg || (fileInput.files && fileInput.files[0]);
  if (!file) return;
  if (!fileMatchesKind(kind, file)) {
    toast(kind === 'image'
      ? 'Please choose an image file (JPG, PNG, WEBP, GIF).'
      : 'Please choose a video file (MP4, WEBM, MOV).');
    return;
  }
  const btn = document.getElementById(kind === 'image' ? 'uploadImageBtn' : 'uploadVideoBtn');
  const origHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Uploading...';
  try {
    const fd = new FormData();
    fd.append('file', file);
    const r = await fetch('/api/admin/hero-slides/upload', {
      method: 'POST',
      headers: { 'X-Admin-Key': A.token },
      body: fd,
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'Upload failed');
    urlInput.value = d.url;
    renderSlideUploadPreview(kind);
    toast((kind === 'image' ? 'Image' : 'Video') + ' uploaded successfully!');
  } catch (e) {
    toast('Upload failed: ' + (e.message || 'unknown error'));
  } finally {
    btn.disabled = false;
    btn.innerHTML = origHtml;
    fileInput.value = '';
  }
}

async function saveSlide() {
  const editId = document.getElementById('slideEditId').value;
  const title = document.getElementById('slideTitle').value.trim();
  if (!title) { toast('Title is required'); return; }
  const body = {
    title,
    description: document.getElementById('slideDescription').value.trim(),
    image: document.getElementById('slideImage').value.trim(),
    video: document.getElementById('slideVideo').value.trim(),
    button_text: document.getElementById('slideButtonText').value.trim(),
    button_url: document.getElementById('slideButtonUrl').value.trim(),
    active: document.getElementById('slideActive').checked,
  };
  const btn = document.getElementById('slideSaveBtn');
  btn.disabled = true;
  try {
    if (editId) {
      await api('PUT', '/api/admin/hero-slides/' + encodeURIComponent(editId), body);
      toast('Slide updated!');
    } else {
      await api('POST', '/api/admin/hero-slides/add', body);
      toast('Slide added!');
    }
    closeSlideModal();
    loadSlides();
    loadOverview();
  } catch (e) {
    toast('Error saving slide');
  } finally {
    btn.disabled = false;
  }
}

async function moveSlide(id, dir) {
  const ids = _slides.map(s => s.id);
  const i = ids.indexOf(id);
  const j = i + dir;
  if (i < 0 || j < 0 || j >= ids.length) return;
  [ids[i], ids[j]] = [ids[j], ids[i]];
  try {
    await api('POST', '/api/admin/hero-slides/reorder', { ordered_ids: ids });
    loadSlides();
  } catch (e) { toast('Error reordering slides'); }
}

async function toggleSlide(id) {
  const s = _slides.find(x => x.id === id);
  if (!s) return;
  try {
    await api('PUT', '/api/admin/hero-slides/' + encodeURIComponent(id), { active: !s.active });
    toast(s.active ? 'Slide hidden from dashboard' : 'Slide enabled');
    loadSlides();
  } catch (e) { toast('Error updating slide'); }
}

function previewSlide(id) {
  const s = _slides.find(x => x.id === id);
  if (!s) return;
  const stage = document.getElementById('slidePreviewStage');
  stage.innerHTML = '';
  const frame = document.createElement('div');
  frame.className = 'slide-preview-frame';
  if (s.video) {
    const v = document.createElement('video');
    v.src = s.video;
    v.autoplay = true;
    v.muted = true;
    v.loop = true;
    v.playsInline = true;
    frame.appendChild(v);
  } else if (s.image) {
    const img = document.createElement('img');
    img.src = s.image;
    img.alt = s.title || 'preview';
    frame.appendChild(img);
  }
  const overlay = document.createElement('div');
  overlay.className = 'slide-preview-overlay';
  frame.appendChild(overlay);
  const copy = document.createElement('div');
  copy.className = 'slide-preview-copy';
  if (s.title) {
    const h = document.createElement('strong');
    h.textContent = s.title;
    copy.appendChild(h);
  }
  if (s.description) {
    const p = document.createElement('p');
    p.textContent = s.description;
    copy.appendChild(p);
  }
  if (s.button_text) {
    const b = document.createElement('span');
    b.className = 'slide-preview-btn';
    b.textContent = s.button_text;
    copy.appendChild(b);
  }
  frame.appendChild(copy);
  stage.appendChild(frame);
  document.getElementById('slidePreviewModal').style.display = 'flex';
}

function closeSlidePreview() {
  document.getElementById('slidePreviewStage').innerHTML = '';
  document.getElementById('slidePreviewModal').style.display = 'none';
}

async function deleteSlide(id) {
  if (!confirm('Delete this slide?')) return;
  try { await api('DELETE', '/api/admin/hero-slides/' + encodeURIComponent(id)); toast('Slide deleted'); loadSlides(); loadOverview(); }
  catch (e) { toast('Error deleting slide'); }
}

// ---------------------------------------------------------------------------
// Ticker & Alerts
// ---------------------------------------------------------------------------
let _alerts = [];

async function loadAlerts() {
  try {
    const d = await api('GET', '/api/admin/settings');
    _alerts = (d.alerts || []).slice().sort((a, b) => (a.order || 0) - (b.order || 0));
    renderAlerts();
  } catch (e) { /* silent */ }
}

function renderAlerts() {
  const el = document.getElementById('alertsList');
  if (!_alerts.length) {
    el.innerHTML = '<p class="empty-hint">No alerts yet. Add your first announcement below.</p>';
    return;
  }
  el.innerHTML = _alerts.map((a, i) =>
    '<div class="ticker-item-row' + (a.active ? '' : ' inactive') + '">' +
      '<i class="fa-solid fa-bullhorn alert-icon"></i>' +
      '<span>' + esc(a.text) + '</span>' +
      '<div class="alert-actions">' +
        '<button class="btn-icon" title="Move up" onclick="moveAlert(\'' + a.id + '\', -1)"' + (i === 0 ? ' disabled' : '') + '><i class="fa-solid fa-arrow-up"></i></button>' +
        '<button class="btn-icon" title="Move down" onclick="moveAlert(\'' + a.id + '\', 1)"' + (i === _alerts.length - 1 ? ' disabled' : '') + '><i class="fa-solid fa-arrow-down"></i></button>' +
        '<button class="btn-icon" title="' + (a.active ? 'Disable' : 'Enable') + '" onclick="toggleAlert(\'' + a.id + '\')"><i class="fa-solid fa-power-off"></i></button>' +
        '<button class="btn-icon" title="Edit" onclick="editAlert(\'' + a.id + '\')"><i class="fa-solid fa-pen"></i></button>' +
        '<button class="ticker-remove" title="Delete" onclick="deleteAlert(\'' + a.id + '\')"><i class="fa-solid fa-xmark"></i></button>' +
      '</div>' +
    '</div>'
  ).join('');
}

async function addAlert() {
  const inp = document.getElementById('newAlertText');
  const text = inp.value.trim();
  if (!text) { toast('Type an alert message first'); return; }
  try {
    await api('POST', '/api/admin/alerts/add', { text });
    inp.value = '';
    toast('Alert added!');
    loadAlerts();
  } catch (e) { toast('Error adding alert'); }
}

function editAlert(id) {
  const a = _alerts.find(x => x.id === id);
  if (!a) return;
  const text = prompt('Edit alert message:', a.text);
  if (text === null) return;
  const val = text.trim();
  if (!val) { toast('Alert text cannot be empty'); return; }
  api('PUT', '/api/admin/alerts/' + encodeURIComponent(id), { text: val })
    .then(() => { toast('Alert updated!'); loadAlerts(); })
    .catch(() => toast('Error updating alert'));
}

async function toggleAlert(id) {
  const a = _alerts.find(x => x.id === id);
  if (!a) return;
  try {
    await api('PUT', '/api/admin/alerts/' + encodeURIComponent(id), { active: !a.active });
    toast(a.active ? 'Alert hidden from dashboard' : 'Alert enabled');
    loadAlerts();
  } catch (e) { toast('Error updating alert'); }
}

async function deleteAlert(id) {
  if (!confirm('Delete this alert?')) return;
  try { await api('DELETE', '/api/admin/alerts/' + encodeURIComponent(id)); toast('Alert deleted'); loadAlerts(); }
  catch (e) { toast('Error deleting alert'); }
}

async function moveAlert(id, dir) {
  const ids = _alerts.map(a => a.id);
  const i = ids.indexOf(id);
  const j = i + dir;
  if (i < 0 || j < 0 || j >= ids.length) return;
  [ids[i], ids[j]] = [ids[j], ids[i]];
  try { await api('POST', '/api/admin/alerts/reorder', { ordered_ids: ids }); loadAlerts(); }
  catch (e) { toast('Error reordering alerts'); }
}

// ---------------------------------------------------------------------------
// Contact
// ---------------------------------------------------------------------------
async function loadContactSettings() {
  try {
    const d = await api('GET', '/api/admin/settings');
    const ci = d.contact_info || {};
    document.getElementById('contactPhone').value = ci.phone || '';
    document.getElementById('contactEmail').value = ci.email || '';
    document.getElementById('contactHelpline').value = ci.helpline || '';
    document.getElementById('contactAddress').value = ci.address || '';
  } catch (e) { /* silent */ }
}

async function saveContactSettings() {
  const body = {
    phone: document.getElementById('contactPhone').value,
    email: document.getElementById('contactEmail').value,
    helpline: document.getElementById('contactHelpline').value,
    address: document.getElementById('contactAddress').value,
  };
  try {
    await api('POST', '/api/admin/settings/contact', body);
    const msg = document.getElementById('contactSaveMsg');
    msg.style.display = 'block';
    setTimeout(() => { msg.style.display = 'none'; }, 2500);
    toast('Contact settings saved!');
  } catch (e) { toast('Error saving contact'); }
}

// ---------------------------------------------------------------------------
// Drag & drop uploads (shared by dashboard + landing hero slide media)
// ---------------------------------------------------------------------------
function fileMatchesKind(kind, file) {
  if (kind === 'image') return /\.(jpe?g|png|webp|gif)$/i.test(file.name || '') || (file.type || '').startsWith('image/');
  return /\.(mp4|webm|ogg|mov|m4v)$/i.test(file.name || '') || (file.type || '').startsWith('video/');
}

function wireDropZone(zone, onFile) {
  if (!zone) return;
  ['dragenter', 'dragover'].forEach(ev => zone.addEventListener(ev, e => {
    e.preventDefault(); e.stopPropagation();
    zone.classList.add('drag-over');
  }));
  zone.addEventListener('dragleave', e => {
    e.stopPropagation();
    if (!zone.contains(e.relatedTarget)) zone.classList.remove('drag-over');
  });
  zone.addEventListener('drop', e => {
    e.preventDefault(); e.stopPropagation();
    zone.classList.remove('drag-over');
    const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) onFile(f);
  });
}

// ---------------------------------------------------------------------------
// Landing page hero slides (fully separate from the dashboard hero slider)
// ---------------------------------------------------------------------------
let _landingSlides = [];

async function loadLandingSlides() {
  try {
    const d = await api('GET', '/api/admin/landing-hero');
    _landingSlides = (d.landing_hero_slides || []).slice().sort((a, b) => (a.order || 0) - (b.order || 0));
    renderLandingSlides();
  } catch (e) { /* silent */ }
}

function renderLandingSlides() {
  const el = document.getElementById('landingSlidesList');
  if (!el) return;
  if (!_landingSlides.length) {
    el.innerHTML = '<p class="empty-hint">No landing slides yet. Click "Add Slide" to create your first landing page hero slide.</p>';
    return;
  }
  el.innerHTML = _landingSlides.map((s, i) => {
    const preview = s.video
      ? '<div class="slide-preview video-bg"><i class="fa-solid fa-film"></i></div>'
      : s.image
        ? '<div class="slide-preview" style="background:url(\'' + esc(s.image) + '\') center/cover"></div>'
        : '<div class="slide-preview" style="background:#e8f5ef"></div>';
    const mediaBadge = s.video
      ? '<span class="slide-badge video"><i class="fa-solid fa-film"></i> video</span>'
      : (s.image
        ? '<span class="slide-badge image"><i class="fa-solid fa-image"></i> image</span>'
        : '<span class="slide-badge color"><i class="fa-solid fa-palette"></i> text only</span>');
    const activeBadge = '<span class="slide-badge ' + (s.active ? 'on' : 'off') + '"><i class="fa-solid fa-circle-' + (s.active ? 'check' : 'xmark') + '"></i> ' + (s.active ? 'active' : 'hidden') + '</span>';
    return '<div class="slide-row' + (s.active ? '' : ' inactive') + '">' + preview +
      '<div class="slide-info"><b>' + esc(s.title || 'Untitled slide') + '</b>' +
      '<small>' + esc((s.description || '').slice(0, 90)) + '</small>' +
      '<div class="slide-badges">' + mediaBadge + activeBadge + '</div></div>' +
      '<div class="slide-actions">' +
        '<button class="btn-icon" title="Move up" onclick="moveLandingSlide(\'' + s.id + '\', -1)"' + (i === 0 ? ' disabled' : '') + '><i class="fa-solid fa-arrow-up"></i></button>' +
        '<button class="btn-icon" title="Move down" onclick="moveLandingSlide(\'' + s.id + '\', 1)"' + (i === _landingSlides.length - 1 ? ' disabled' : '') + '><i class="fa-solid fa-arrow-down"></i></button>' +
        '<button class="btn-icon" title="' + (s.active ? 'Disable' : 'Enable') + '" onclick="toggleLandingSlide(\'' + s.id + '\')"><i class="fa-solid fa-power-off"></i></button>' +
        '<button class="btn-outline" title="Edit" onclick="openLandingSlideModal(\'' + s.id + '\')"><i class="fa-solid fa-pen"></i></button>' +
        '<button class="btn-outline" title="Preview" onclick="previewLandingSlide(\'' + s.id + '\')"><i class="fa-solid fa-eye"></i></button>' +
        '<button class="btn-danger" title="Delete" onclick="deleteLandingSlide(\'' + s.id + '\')"><i class="fa-solid fa-trash"></i></button>' +
      '</div></div>';
  }).join('');
}

function openLandingSlideModal(editId) {
  const s = editId ? _landingSlides.find(x => x.id === editId) : null;
  document.getElementById('landingSlideModalTitle').textContent = s ? 'Edit Landing Slide' : 'Add Landing Slide';
  document.getElementById('landingSlideEditId').value = s ? s.id : '';
  document.getElementById('landingSlideTitle').value = s ? (s.title || '') : '';
  document.getElementById('landingSlideDescription').value = s ? (s.description || '') : '';
  document.getElementById('landingSlideImage').value = s ? (s.image || '') : '';
  document.getElementById('landingSlideVideo').value = s ? (s.video || '') : '';
  document.getElementById('landingSlideButtonText').value = s ? (s.button_text || '') : '';
  document.getElementById('landingSlideButtonUrl').value = s ? (s.button_url || '') : '';
  document.getElementById('landingSlideActive').checked = s ? s.active !== false : true;
  document.getElementById('landingSlideImageFile').value = '';
  document.getElementById('landingSlideVideoFile').value = '';
  renderLandingUploadPreview('image');
  renderLandingUploadPreview('video');
  document.getElementById('landingSlideModal').style.display = 'flex';
}

function closeLandingSlideModal() {
  document.getElementById('landingSlideModal').style.display = 'none';
}

function renderLandingUploadPreview(kind) {
  const url = document.getElementById(kind === 'image' ? 'landingSlideImage' : 'landingSlideVideo').value.trim();
  const box = document.getElementById(kind === 'image' ? 'landingSlideImagePreview' : 'landingSlideVideoPreview');
  box.innerHTML = '';
  if (!url) return;
  if (kind === 'image') {
    const img = document.createElement('img');
    img.src = url;
    img.alt = 'preview';
    box.appendChild(img);
  } else {
    const v = document.createElement('video');
    v.src = url;
    v.muted = true;
    v.autoplay = true;
    v.loop = true;
    v.playsInline = true;
    box.appendChild(v);
  }
}

async function uploadLandingSlideMedia(kind, fileArg) {
  const fileInput = document.getElementById(kind === 'image' ? 'landingSlideImageFile' : 'landingSlideVideoFile');
  const urlInput = document.getElementById(kind === 'image' ? 'landingSlideImage' : 'landingSlideVideo');
  const file = fileArg || (fileInput.files && fileInput.files[0]);
  if (!file) return;
  if (!fileMatchesKind(kind, file)) {
    toast(kind === 'image'
      ? 'Please choose an image file (JPG, PNG, WEBP, GIF).'
      : 'Please choose a video file (MP4, WEBM, MOV).');
    return;
  }
  const btn = document.getElementById(kind === 'image' ? 'uploadLandingImageBtn' : 'uploadLandingVideoBtn');
  const origHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Uploading...';
  try {
    const fd = new FormData();
    fd.append('file', file);
    const r = await fetch('/api/admin/landing-hero/upload', {
      method: 'POST',
      headers: { 'X-Admin-Key': A.token },
      body: fd,
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'Upload failed');
    urlInput.value = d.url;
    renderLandingUploadPreview(kind);
    toast((kind === 'image' ? 'Image' : 'Video') + ' uploaded successfully!');
  } catch (e) {
    toast('Upload failed: ' + (e.message || 'unknown error'));
  } finally {
    btn.disabled = false;
    btn.innerHTML = origHtml;
    fileInput.value = '';
  }
}

async function saveLandingSlide() {
  const editId = document.getElementById('landingSlideEditId').value;
  const body = {
    title: document.getElementById('landingSlideTitle').value.trim(),
    description: document.getElementById('landingSlideDescription').value.trim(),
    image: document.getElementById('landingSlideImage').value.trim(),
    video: document.getElementById('landingSlideVideo').value.trim(),
    button_text: document.getElementById('landingSlideButtonText').value.trim(),
    button_url: document.getElementById('landingSlideButtonUrl').value.trim(),
    active: document.getElementById('landingSlideActive').checked,
  };
  const btn = document.getElementById('landingSlideSaveBtn');
  btn.disabled = true;
  try {
    if (editId) {
      await api('PUT', '/api/admin/landing-hero/' + encodeURIComponent(editId), body);
      toast('Landing slide updated!');
    } else {
      await api('POST', '/api/admin/landing-hero/add', body);
      toast('Landing slide added!');
    }
    closeLandingSlideModal();
    loadLandingSlides();
  } catch (e) {
    toast('Error saving landing slide');
  } finally {
    btn.disabled = false;
  }
}

async function moveLandingSlide(id, dir) {
  const ids = _landingSlides.map(s => s.id);
  const i = ids.indexOf(id);
  const j = i + dir;
  if (i < 0 || j < 0 || j >= ids.length) return;
  [ids[i], ids[j]] = [ids[j], ids[i]];
  try {
    await api('POST', '/api/admin/landing-hero/reorder', { ordered_ids: ids });
    loadLandingSlides();
  } catch (e) { toast('Error reordering landing slides'); }
}

async function toggleLandingSlide(id) {
  const s = _landingSlides.find(x => x.id === id);
  if (!s) return;
  try {
    await api('PUT', '/api/admin/landing-hero/' + encodeURIComponent(id), { active: !s.active });
    toast(s.active ? 'Slide hidden from the landing page' : 'Slide enabled');
    loadLandingSlides();
  } catch (e) { toast('Error updating slide'); }
}

function previewLandingSlide(id) {
  const s = _landingSlides.find(x => x.id === id);
  if (!s) return;
  const stage = document.getElementById('slidePreviewStage');
  stage.innerHTML = '';
  const frame = document.createElement('div');
  frame.className = 'landing-preview';
  const copy = document.createElement('div');
  copy.className = 'lp-copy';
  const kicker = document.createElement('span');
  kicker.className = 'lp-kicker';
  kicker.textContent = 'AI-POWERED WELFARE SUPPORT PLATFORM';
  copy.appendChild(kicker);
  if (s.title) {
    const h = document.createElement('h3');
    h.textContent = s.title;
    copy.appendChild(h);
  }
  if (s.description) {
    const p = document.createElement('p');
    p.textContent = s.description;
    copy.appendChild(p);
  }
  if (s.button_text) {
    const b = document.createElement('span');
    b.className = 'lp-btn';
    b.textContent = s.button_text + ' →';
    copy.appendChild(b);
  }
  frame.appendChild(copy);
  const media = document.createElement('div');
  media.className = 'lp-media';
  if (s.video) {
    const v = document.createElement('video');
    v.src = s.video;
    v.autoplay = true;
    v.muted = true;
    v.loop = true;
    v.playsInline = true;
    media.appendChild(v);
  } else if (s.image) {
    const img = document.createElement('img');
    img.src = s.image;
    img.alt = s.title || 'preview';
    media.appendChild(img);
  }
  frame.appendChild(media);
  stage.appendChild(frame);
  document.getElementById('slidePreviewModal').style.display = 'flex';
}

async function deleteLandingSlide(id) {
  if (!confirm('Delete this landing slide?')) return;
  try { await api('DELETE', '/api/admin/landing-hero/' + encodeURIComponent(id)); toast('Landing slide deleted'); loadLandingSlides(); }
  catch (e) { toast('Error deleting landing slide'); }
}

// ---------------------------------------------------------------------------
// Organizations
// ---------------------------------------------------------------------------
let _allOrgs = [];
let _orgFilter = 'all';

async function loadOrgs() {
  try {
    const d = await api('GET', '/api/admin/organizations');
    _allOrgs = d.organizations || [];
    renderOrgs();
    loadOverview();
  } catch (e) { /* silent */ }
}

function filterOrgs(filter, btn) {
  _orgFilter = filter;
  if (btn) {
    btn.parentElement.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  }
  renderOrgs();
}

function renderOrgs() {
  const el = document.getElementById('orgsList');
  let orgs = _allOrgs;
  if (_orgFilter !== 'all') orgs = orgs.filter(o => o.status === _orgFilter);
  const pending = _allOrgs.filter(o => o.status === 'pending').length;
  document.getElementById('pendingCount').textContent = pending;

  if (!orgs.length) { el.innerHTML = '<p class="empty-hint">No organizations in this view.</p>'; return; }

  el.innerHTML = orgs.map(o => {
    const badge = '<span class="org-badge ' + o.status + '">' + o.status + '</span>';
    let actions = '';
    if (o.status === 'pending') {
      actions = '<button class="btn-warning" onclick="approveOrg(\'' + o.id + '\')"><i class="fa-solid fa-check"></i> Approve</button>' +
        '<button class="btn-danger" onclick="rejectOrg(\'' + o.id + '\')"><i class="fa-solid fa-xmark"></i> Reject</button>';
    } else if (o.status === 'approved') {
      actions = '<button class="btn-outline" onclick="suspendOrg(\'' + o.id + '\')" style="color:var(--warning);border-color:var(--warning);"><i class="fa-solid fa-pause"></i> Suspend</button>';
    } else if (o.status === 'suspended') {
      actions = '<button class="btn-warning" onclick="reinstateOrg(\'' + o.id + '\')"><i class="fa-solid fa-rotate-left"></i> Reinstate</button>';
    } else if (o.status === 'rejected') {
      actions = '<button class="btn-warning" onclick="approveOrg(\'' + o.id + '\')"><i class="fa-solid fa-check"></i> Approve</button>';
    }
    actions += '<button class="btn-outline" onclick="deleteOrg(\'' + o.id + '\')" style="color:var(--danger);border-color:var(--danger);"><i class="fa-solid fa-trash"></i> Delete</button>';
    return '<div class="org-card"><div class="org-card-head"><h4>' + esc(o.name) + '</h4>' + badge + '</div><div class="org-meta"><span><i class="fa-solid fa-building"></i> ' + esc(o.org_type) + '</span><span><i class="fa-solid fa-envelope"></i> ' + esc(o.email) + '</span><span><i class="fa-solid fa-location-dot"></i> ' + esc(o.province || o.address) + '</span></div>' + (o.description ? '<p style="font-size:13px;color:var(--muted);margin-bottom:8px;">' + esc(o.description) + '</p>' : '') + '<div class="org-actions">' + actions + '</div></div>';
  }).join('');
}

async function approveOrg(id) { try { await api('POST', '/api/admin/organizations/' + id + '/approve'); toast('Approved!'); loadOrgs(); } catch (e) { toast('Error'); } }
async function rejectOrg(id) { if (!confirm('Reject this organization?')) return; try { await api('POST', '/api/admin/organizations/' + id + '/reject'); toast('Rejected'); loadOrgs(); } catch (e) { toast('Error'); } }
async function suspendOrg(id) { if (!confirm('Suspend this organization? Its login and dashboard access will be blocked immediately and its published posts will be hidden from citizens.')) return; try { await api('POST', '/api/admin/organizations/' + id + '/suspend'); toast('Organization suspended'); loadOrgs(); } catch (e) { toast('Error'); } }
async function reinstateOrg(id) { if (!confirm('Reinstate this organization as approved? Its login and published posts will be restored.')) return; try { await api('POST', '/api/admin/organizations/' + id + '/approve'); toast('Organization reinstated'); loadOrgs(); } catch (e) { toast('Error'); } }
async function deleteOrg(id) { if (!confirm('Permanently delete this organization? All of its posts will be removed too.')) return; try { await api('DELETE', '/api/admin/organizations/' + id); toast('Deleted'); loadOrgs(); } catch (e) { toast('Error'); } }

// ---------------------------------------------------------------------------
// Organization Posts (verification queue — every org post passes through here)
// ---------------------------------------------------------------------------
let _orgPosts = [];
let _orgPostsFilter = 'all';

async function loadOrgPosts() {
  try {
    const d = await api('GET', '/api/admin/org-posts?status=all');
    _orgPosts = d.posts || [];
    renderOrgPosts();
  } catch (e) { /* silent */ }
}

function filterOrgPosts(filter, btn) {
  _orgPostsFilter = filter;
  if (btn) {
    btn.parentElement.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  }
  renderOrgPosts();
}

function fmtDate(iso) {
  if (!iso) return '';
  return String(iso).replace('T', ' ').slice(0, 16);
}

function renderOrgPosts() {
  const el = document.getElementById('adminOrgPostsList');
  if (!el) return;
  const pending = _orgPosts.filter(p => p.status === 'pending').length;
  const cnt = document.getElementById('orgPostsPendingCount');
  if (cnt) cnt.textContent = pending;
  const badge = document.getElementById('postsPendingBadge');
  if (badge) {
    if (pending > 0) { badge.textContent = pending; badge.style.display = 'inline'; }
    else badge.style.display = 'none';
  }

  let posts = _orgPosts;
  if (_orgPostsFilter !== 'all') posts = posts.filter(p => p.status === _orgPostsFilter);
  if (!posts.length) { el.innerHTML = '<p class="empty-hint">No posts in this view.</p>'; return; }

  el.innerHTML = posts.map(p => {
    let actions = '';
    if (p.status !== 'approved') {
      actions += '<button class="btn-warning" onclick="approveOrgPost(\'' + p.id + '\')"><i class="fa-solid fa-check"></i> Approve</button>';
    }
    if (p.status !== 'rejected') {
      actions += '<button class="btn-danger" onclick="rejectOrgPost(\'' + p.id + '\')"><i class="fa-solid fa-xmark"></i> Reject</button>';
    }
    actions += '<button class="btn-outline" onclick="deleteOrgPost(\'' + p.id + '\')" style="color:var(--danger);border-color:var(--danger);"><i class="fa-solid fa-trash"></i> Delete</button>';
    const elig = (p.eligibility || []).join(' · ');
    const docs = (p.documents || []).join(' · ');
    return '<div class="org-card">' +
      '<div class="org-card-head"><h4>' + esc(p.title || 'Untitled post') + '</h4><span class="org-badge ' + p.status + '">' + p.status + '</span></div>' +
      '<div class="org-meta"><span><i class="fa-solid fa-building"></i> ' + esc(p.org_name || '') + '</span>' +
      (p.category ? '<span><i class="fa-solid fa-folder"></i> ' + esc(p.category) + '</span>' : '') +
      (p.post_type ? '<span><i class="fa-solid fa-tag"></i> ' + esc(p.post_type) + '</span>' : '') +
      (p.pricing ? '<span><i class="fa-solid fa-money-bill"></i> ' + esc(p.pricing) + '</span>' : '') + '</div>' +
      (p.description ? '<p style="font-size:13px;color:var(--muted);margin-bottom:8px;">' + esc(p.description) + '</p>' : '') +
      '<div class="org-meta">' +
      (p.location ? '<span><i class="fa-solid fa-location-dot"></i> ' + esc(p.location) + '</span>' : '') +
      (p.contact ? '<span><i class="fa-solid fa-phone"></i> ' + esc(p.contact) + '</span>' : '') +
      (p.website ? '<span><i class="fa-solid fa-globe"></i> ' + esc(p.website) + '</span>' : '') +
      (elig ? '<span><i class="fa-solid fa-user-check"></i> ' + esc(elig) + '</span>' : '') +
      (docs ? '<span><i class="fa-solid fa-file-lines"></i> ' + esc(docs) + '</span>' : '') + '</div>' +
      '<div class="org-meta"><span><i class="fa-solid fa-calendar"></i> Submitted: ' + fmtDate(p.created_at) + '</span>' +
      (p.reviewed_at ? '<span><i class="fa-solid fa-clipboard-check"></i> Reviewed: ' + fmtDate(p.reviewed_at) + '</span>' : '') + '</div>' +
      '<div class="org-actions">' + actions + '</div>' +
    '</div>';
  }).join('');
}

async function approveOrgPost(id) { try { await api('POST', '/api/admin/org-posts/' + id + '/approve'); toast('Post approved — now live for citizens'); loadOrgPosts(); } catch (e) { toast('Error approving post'); } }
async function rejectOrgPost(id) { if (!confirm('Reject this post? It will be hidden from citizens but stays with the organization.')) return; try { await api('POST', '/api/admin/org-posts/' + id + '/reject'); toast('Post rejected'); loadOrgPosts(); } catch (e) { toast('Error rejecting post'); } }
async function deleteOrgPost(id) { if (!confirm('Permanently delete this post?')) return; try { await api('DELETE', '/api/admin/org-posts/' + id); toast('Post deleted'); loadOrgPosts(); } catch (e) { toast('Error deleting post'); } }

// ---------------------------------------------------------------------------
// Programs Management
// ---------------------------------------------------------------------------
let _adminPrograms = [];
let _progDebounce = null;

function debounceLoadAdminPrograms() {
  clearTimeout(_progDebounce);
  _progDebounce = setTimeout(() => loadAdminPrograms(), 300);
}

async function loadAdminPrograms() {
  const el = document.getElementById('adminProgramsList');
  el.innerHTML = '<p class="empty-hint">Loading...</p>';
  const q = document.getElementById('progSearchAdmin').value.trim();
  const cat = document.getElementById('progCategoryAdmin').value;
  try {
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (cat !== 'all') params.set('category', cat);
    const d = await api('GET', '/api/admin/programs?' + params.toString());
    _adminPrograms = d.programs || [];
    renderAdminPrograms();
  } catch (e) {
    el.innerHTML = '<p class="empty-hint">Error loading programs.</p>';
  }
}

function renderAdminPrograms() {
  const el = document.getElementById('adminProgramsList');
  if (!_adminPrograms.length) {
    el.innerHTML = '<p class="empty-hint">No programs found. Click "Add Program" to create one.</p>';
    return;
  }
  el.innerHTML = _adminPrograms.map(p => {
    const catClass = (p.category || '').toLowerCase().replace(/\s+/g, '-');
    return '<div class="admin-prog-card">' +
      '<div class="admin-prog-head">' +
        '<h4>' + esc(p.title) + '</h4>' +
        '<span class="prog-cat-tag ' + catClass + '">' + esc(p.category || 'Uncategorized') + '</span>' +
      '</div>' +
      '<p class="admin-prog-desc">' + esc((p.description || '').slice(0, 120)) + (p.description && p.description.length > 120 ? '...' : '') + '</p>' +
      '<div class="admin-prog-meta">' +
        '<span><i class="fa-solid fa-map-pin"></i> ' + esc((p.locations || []).join(', ') || 'N/A') + '</span>' +
        '<span><i class="fa-solid fa-id-card"></i> ' + esc(p.id) + '</span>' +
      '</div>' +
      '<div class="admin-prog-actions">' +
        '<button class="btn-outline" onclick=\'editProgram("' + esc(p.id) + '")\'><i class="fa-solid fa-pen"></i> Edit</button>' +
        '<button class="btn-danger" onclick=\'deleteAdminProgram("' + esc(p.id) + '")\'><i class="fa-solid fa-trash"></i> Delete</button>' +
      '</div>' +
    '</div>';
  }).join('');
}

function openAddProgramModal() {
  document.getElementById('programModalTitle').textContent = 'Add New Program';
  document.getElementById('progEditId').value = '';
  document.getElementById('progId').value = '';
  document.getElementById('progId').disabled = false;
  document.getElementById('progTitle').value = '';
  document.getElementById('progCategory').value = 'Education';
  document.getElementById('progType').value = '';
  document.getElementById('progDescription').value = '';
  document.getElementById('progAddress').value = '';
  document.getElementById('progPhone').value = '';
  document.getElementById('progEligibility').value = '';
  document.getElementById('progDocuments').value = '';
  document.getElementById('progLocations').value = '';
  document.getElementById('progApplication').value = '';
  document.getElementById('progSourceName').value = '';
  document.getElementById('progSourceUrl').value = '';
  document.getElementById('programModal').style.display = 'flex';
}

function editProgram(id) {
  const p = _adminPrograms.find(x => x.id === id);
  if (!p) return;
  document.getElementById('programModalTitle').textContent = 'Edit Program';
  document.getElementById('progEditId').value = p.id;
  document.getElementById('progId').value = p.id;
  document.getElementById('progId').disabled = true;
  document.getElementById('progTitle').value = p.title || '';
  document.getElementById('progCategory').value = p.category || 'Education';
  document.getElementById('progType').value = p.type || '';
  document.getElementById('progDescription').value = p.description || '';
  document.getElementById('progAddress').value = p.address || '';
  document.getElementById('progPhone').value = p.phone_number || '';
  document.getElementById('progEligibility').value = (p.eligibility || []).join(', ');
  document.getElementById('progDocuments').value = (p.documents || []).join(', ');
  document.getElementById('progLocations').value = (p.locations || []).join(', ');
  document.getElementById('progApplication').value = p.application || '';
  document.getElementById('progSourceName').value = p.source_name || '';
  document.getElementById('progSourceUrl').value = p.source_url || '';
  document.getElementById('programModal').style.display = 'flex';
}

function closeProgramModal() {
  document.getElementById('programModal').style.display = 'none';
}

async function saveProgram() {
  const editId = document.getElementById('progEditId').value;
  const title = document.getElementById('progTitle').value.trim();
  if (!title) { toast('Title is required'); return; }

  const data = {
    title: title,
    category: document.getElementById('progCategory').value,
    type: document.getElementById('progType').value.trim(),
    description: document.getElementById('progDescription').value.trim(),
    address: document.getElementById('progAddress').value.trim(),
    phone_number: document.getElementById('progPhone').value.trim(),
    eligibility: document.getElementById('progEligibility').value.split(',').map(s => s.trim()).filter(Boolean),
    documents: document.getElementById('progDocuments').value.split(',').map(s => s.trim()).filter(Boolean),
    locations: document.getElementById('progLocations').value.split(',').map(s => s.trim()).filter(Boolean),
    application: document.getElementById('progApplication').value.trim(),
    source_name: document.getElementById('progSourceName').value.trim(),
    source_url: document.getElementById('progSourceUrl').value.trim(),
  };

  try {
    if (editId) {
      await api('PUT', '/api/admin/programs/' + encodeURIComponent(editId), data);
      toast('Program updated!');
    } else {
      data.id = document.getElementById('progId').value.trim();
      await api('POST', '/api/admin/programs/add', data);
      toast('Program added!');
    }
    closeProgramModal();
    loadAdminPrograms();
    loadOverview();
  } catch (e) { toast('Error saving program: ' + (e.message || e)); }
}

async function deleteAdminProgram(id) {
  if (!confirm('Delete program "' + id + '"? This cannot be undone.')) return;
  try {
    await api('DELETE', '/api/admin/programs/' + encodeURIComponent(id));
    toast('Program deleted');
    loadAdminPrograms();
    loadOverview();
  } catch (e) { toast('Error deleting program'); }
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }

// ---------------------------------------------------------------------------
// Facilities (geo-scraper)
// ---------------------------------------------------------------------------
async function autoCollectFacilities() {
  const btn = document.getElementById('autoCollectBtn');
  const resultEl = document.getElementById('autoCollectResult');
  const city = document.getElementById('autoCollectCity').value;
  const sel = document.getElementById('autoCollectCategories');
  const categories = Array.from(sel.selectedOptions).map(o => o.value);

  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Collecting...';
  resultEl.innerHTML = '';

  try {
    const d = await api('POST', '/api/admin/facilities/auto-collect', { city, categories });
    resultEl.innerHTML = '<div style="background:#ecfdf5;border:1px solid #6ee7b7;border-radius:8px;padding:12px 16px;color:#059669;"><strong>Collection complete!</strong><br>Fetched: ' + d.fetched + '<br>Added: ' + d.added + '<br>Duplicates skipped: ' + d.duplicates_skipped + '<br>Total in DB: ' + d.total_in_db + '</div>';
    toast('Collected ' + d.added + ' new facilities in ' + city);
    loadDbFacilities();
  } catch (e) {
    resultEl.innerHTML = '<div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:12px;color:#dc2626;">Error: ' + esc(e.message || 'Collection failed') + '</div>';
    toast('Error collecting facilities');
  }
  btn.disabled = false;
  btn.innerHTML = '<i class="fa-solid fa-satellite-dish"></i> Auto-Collect from OpenStreetMap';
}

async function loadDbFacilities() {
  const el = document.getElementById('dbFacilitiesList');
  try {
    const r = await fetch('/api/facilities/db?city=all&category=all');
    const d = await r.json();
    const facs = d.facilities || [];
    if (!facs.length) { el.innerHTML = '<p class="empty-hint">No facilities collected yet. Click Auto-Collect above.</p>'; return; }
    el.innerHTML = facs.slice(0, 50).map(f => {
      const catColors = { hospital: '#dc2626', welfare: '#059669', university: '#2563eb' };
      const color = catColors[f.category] || '#64748b';
      return '<div class="org-card"><div class="org-card-head"><h4>' + esc(f.name) + '</h4><span class="org-badge approved" style="background:' + color + '22;color:' + color + ';border-color:' + color + '44;">' + esc(f.category) + '</span></div><div class="org-meta"><span><i class="fa-solid fa-city"></i> ' + esc(f.city) + '</span><span><i class="fa-solid fa-location-dot"></i> ' + esc(f.address || '') + '</span></div><div class="org-meta"><span><i class="fa-solid fa-building"></i> ' + esc(f.facility_type || '') + '</span><span><i class="fa-solid fa-phone"></i> ' + esc(f.phone || 'N/A') + '</span></div></div>';
    }).join('');
  } catch (e) { el.innerHTML = '<p class="empty-hint">Error loading facilities.</p>'; }
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  if (A.token) showDashboard();
  // Drag & drop targets for hero slide uploads (buttons + preview boxes)
  wireDropZone(document.getElementById('slideImageDrop'), f => uploadSlideMedia('image', f));
  wireDropZone(document.getElementById('slideImagePreview'), f => uploadSlideMedia('image', f));
  wireDropZone(document.getElementById('slideVideoDrop'), f => uploadSlideMedia('video', f));
  wireDropZone(document.getElementById('slideVideoPreview'), f => uploadSlideMedia('video', f));
  // Drag & drop targets for landing hero slide uploads
  wireDropZone(document.getElementById('landingSlideImageDrop'), f => uploadLandingSlideMedia('image', f));
  wireDropZone(document.getElementById('landingSlideImagePreview'), f => uploadLandingSlideMedia('image', f));
  wireDropZone(document.getElementById('landingSlideVideoDrop'), f => uploadLandingSlideMedia('video', f));
  wireDropZone(document.getElementById('landingSlideVideoPreview'), f => uploadLandingSlideMedia('video', f));
  // Mobile sidebar drawer
  const menuBtn = document.getElementById('adminMenuToggle');
  const sidebar = document.querySelector('.admin-sidebar');
  if (menuBtn && sidebar) {
    menuBtn.addEventListener('click', () => {
      const open = sidebar.classList.toggle('open');
      menuBtn.setAttribute('aria-expanded', String(open));
    });
    sidebar.querySelectorAll('button, a').forEach(el => el.addEventListener('click', () => {
      sidebar.classList.remove('open');
      menuBtn.setAttribute('aria-expanded', 'false');
    }));
  }
});
