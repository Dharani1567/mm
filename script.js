// Global JS for layout & helpers
const API_BASE = window.API_BASE || window.location.origin;

// Sidebar toggle
document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('btnToggleSidebar');
  const sidebar = document.getElementById('sidebar');

  if (btn && sidebar) {
    btn.addEventListener('click', () => sidebar.classList.toggle('open'));
  }

  // If page provides initDashboard, call it
  if (typeof initDashboard === 'function') {
    try { initDashboard(); } catch(e){ console.error(e); }
  }

  // global search: if input typed, dispatch event
  const globalSearch = document.getElementById('globalSearch');
  if (globalSearch) {
    globalSearch.addEventListener('input', (e) => {
      const ev = new CustomEvent('global-search', { detail: e.target.value });
      window.dispatchEvent(ev);
    });
  }
});

// helper fetch wrapper
async function apiFetch(path, opts = {}) {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`;
  const res = await fetch(url, opts);
  if (!res.ok) {
    let err = { status: res.status, text: await res.text() };
    try { err.json = await res.json(); } catch(e){}
    throw err;
  }
  return res.json().catch(()=>null);
}
