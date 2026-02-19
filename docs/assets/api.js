/**
 * Grant Hunter AI — Data fetching utilities.
 *
 * Detects environment (local dev vs GitHub Pages) and loads JSON accordingly.
 */

const DATA_BASE = (() => {
  const h = window.location.hostname;
  if (h === 'localhost' || h === '127.0.0.1') return './data';
  // GitHub Pages: data is copied into docs/data by the deploy workflow
  return './data';
})();

const REPO_RAW = 'https://raw.githubusercontent.com/suraganovzh/coreelement-grants-hunter/main/data';

async function fetchJSON(path) {
  // Try local first, fall back to raw GitHub
  for (const base of [DATA_BASE, REPO_RAW]) {
    try {
      const res = await fetch(`${base}/${path}`);
      if (res.ok) return await res.json();
    } catch { /* try next */ }
  }
  return null;
}

async function loadAnalyzed() {
  const data = await fetchJSON('analyzed.json');
  if (!data) return [];
  return Array.isArray(data) ? data : (data.grants || []);
}

async function loadPatterns() {
  return (await fetchJSON('patterns.json')) || {};
}

async function loadWinners() {
  const files = [
    'winners_grants_gov.json', 'winners_sbir.json', 'winners_sbir_p2.json',
    'winners_nsf.json', 'winners_doe.json', 'winners_nih.json',
    'winners_usaspending.json', 'winners_sam.json',
  ];
  const all = [];
  const results = await Promise.allSettled(files.map(f => fetchJSON(f)));
  for (const r of results) {
    if (r.status === 'fulfilled' && r.value) {
      const items = Array.isArray(r.value) ? r.value : (r.value.awards || r.value.winners || []);
      all.push(...items);
    }
  }
  return all;
}

async function loadTeamState() {
  return (await fetchJSON('team_state.json')) || { grants: {}, activity_feed: [] };
}

/* ---- Utility helpers ---- */

function esc(str) {
  const d = document.createElement('div');
  d.textContent = str || '';
  return d.innerHTML;
}

function formatMoney(amount) {
  if (!amount || amount === 0) return '-';
  if (amount >= 1e6) return '$' + (amount / 1e6).toFixed(1) + 'M';
  if (amount >= 1e3) return '$' + (amount / 1e3).toFixed(0) + 'K';
  return '$' + amount.toLocaleString();
}

function daysUntil(dateStr) {
  if (!dateStr) return 999;
  const d = new Date(dateStr);
  if (isNaN(d)) return 999;
  return Math.ceil((d - new Date()) / 86400000);
}

function deadlineText(days) {
  if (days < 0) return 'EXPIRED';
  if (days === 0) return 'TODAY';
  if (days === 1) return 'TOMORROW';
  return days + 'd';
}

function deadlineClass(days) {
  if (days < 0) return 'badge-gray';
  if (days <= 7) return 'badge-red';
  if (days <= 30) return 'badge-amber';
  return 'badge-green';
}

function priorityBadge(priority) {
  if (priority === 'copy_now') return '<span class="badge badge-purple">copy_now</span>';
  if (priority === 'test_first') return '<span class="badge badge-amber">test_first</span>';
  return '<span class="badge badge-gray">skip</span>';
}
