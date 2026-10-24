/* Local-only UI fixtures. Intentionally no backend API calls. */
(() => {
  const queue = document.querySelector('#queue-list');
  const search = document.querySelector('#queue-search');
  let profiles = [];
  let currentId = null;
  const safe = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = amount => Number(amount).toFixed(2);
  function renderQueue() {
    const q = search.value.trim().toLowerCase();
    const shown = profiles.filter(p => (`${p.account} ${p.id}`).toLowerCase().includes(q));
    queue.innerHTML = shown.length ? shown.map(p => {
      const steps = p.transactions.map(t => t.step);
      return `<button type="button" class="queue-item" data-id="${safe(p.id)}" aria-pressed="${p.id === currentId}"><div class="queue-item-top"><span>${safe(p.id)}</span><span>↗</span></div><div class="queue-item-sub">Account ${safe(p.account)} · UI sample only</div><span class="tiny-badge">${p.transactions.length} rows</span><span class="tiny-badge">Steps ${Math.min(...steps)}–${Math.max(...steps)}</span></button>`;
    }).join('') : '<p class="muted">No preview accounts match that search.</p>';
    queue.querySelectorAll('[data-id]').forEach(button => button.addEventListener('click', () => {
      currentId = button.dataset.id;
      renderQueue();
      renderDetail();
    }));
  }
  function renderDetail() {
    const p = profiles.find(item => item.id === currentId);
    if (!p) return;
    const steps = p.transactions.map(t => t.step);
    document.querySelector('#detail-title').textContent = p.title;
    document.querySelector('#detail-subtitle').textContent = `${p.id} · ${p.transactions.length} source rows · steps ${Math.min(...steps)}–${Math.max(...steps)}`;
    document.querySelector('#stat-account').textContent = p.account;
    document.querySelector('#stat-transfers').textContent = p.transactions.length;
    document.querySelector('#stat-range').textContent = `${Math.min(...steps)}–${Math.max(...steps)}`;
    document.querySelector('#tx-count').textContent = `${p.transactions.length} records`;
    document.querySelector('#tx-list').innerHTML = p.transactions.map(t => `<div class="tx-row"><span class="tx-step">STEP ${t.step}</span><div><strong>${safe(t.source)} → ${safe(t.target)}</strong><small>${safe(t.id)} · raw synthetic transfer</small></div><span class="tx-value">${fmt(t.value)} units</span></div>`).join('');
  }
  fetch('data/demo_cases.json')
    .then(r => { if (!r.ok) throw new Error('Missing local fixtures'); return r.json(); })
    .then(data => {
      profiles = data.profiles || [];
      currentId = profiles[0]?.id || null;
      renderQueue();
      renderDetail();
    })
    .catch(() => { queue.innerHTML = '<p class="muted">Unable to load preview data. Start the local frontend server as described in README.md.</p>'; });
  search.addEventListener('input', renderQueue);
})();
