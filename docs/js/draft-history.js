/**
 * Draft History page: search a player, see what he cost and returned every year
 * he was drafted. Summary row per player, expandable to the year-by-year detail.
 */
(function () {
  const SEASONS = ['2022', '2023', '2024', '2025'];
  const COLUMNS = [
    { key: 'player', label: 'Player', sort: 'str' },
    { key: 'pos', label: 'Pos', sort: 'str' },
    { key: 'times', label: 'Drafted', sort: 'num' },
    { key: 'spent', label: 'Spent', sort: 'num' },
    { key: 'pts', label: 'Points', sort: 'num' },
    { key: 'value', label: 'Total Value', sort: 'num' },
    { key: 'avgValue', label: 'Value / Yr', sort: 'num' },
  ];

  let players = [];
  let query = '';
  let currentPos = '';
  const expanded = new Set();
  const sortState = { key: 'value', asc: false };

  DataLoader.loadJSON('data/draft_value.json').then(d => {
    players = groupByPlayer(d);
    buildPosFilter();
    wireSearch();
    applyDeepLink();
    render();
  }).catch(() => {
    document.querySelector('.page-container').innerHTML +=
      '<p style="color:var(--red)">Error loading draft data.</p>';
  });

  /** Collapse the per-season draft boards into one row per player. */
  function groupByPlayer(data) {
    const byName = new Map();
    SEASONS.forEach(year => {
      const season = data[year];
      if (!season) return;
      season.players.forEach(p => {
        if (!byName.has(p.player)) {
          byName.set(p.player, { player: p.player, pos: p.pos, years: [] });
        }
        const entry = byName.get(p.player);
        entry.pos = p.pos;
        entry.years.push({
          year, owner: p.owner, cost: p.cost, pts: p.pts, value: p.value,
        });
      });
    });

    return [...byName.values()].map(entry => {
      entry.years.sort((a, b) => a.year.localeCompare(b.year));
      entry.times = entry.years.length;
      entry.spent = entry.years.reduce((s, y) => s + y.cost, 0);
      entry.pts = round(entry.years.reduce((s, y) => s + y.pts, 0));
      entry.value = round(entry.years.reduce((s, y) => s + y.value, 0));
      entry.avgValue = round(entry.value / entry.times);
      return entry;
    });
  }

  const round = n => Math.round(n * 10) / 10;

  function wireSearch() {
    const input = document.getElementById('player-search');
    input.addEventListener('input', () => {
      query = input.value.trim().toLowerCase();
      expanded.clear();
      render();
    });
    document.getElementById('search-clear').addEventListener('click', () => {
      input.value = '';
      query = '';
      expanded.clear();
      input.focus();
      render();
    });
  }

  /** ?q=name deep-links straight to a player, so a row can be shared. */
  function applyDeepLink() {
    const q = new URLSearchParams(location.search).get('q');
    if (!q) return;
    query = q.trim().toLowerCase();
    document.getElementById('player-search').value = q;
    const hit = players.find(p => p.player.toLowerCase() === query);
    if (hit) expanded.add(hit.player);
  }

  function buildPosFilter() {
    const positions = [...new Set(players.map(p => p.pos))].sort();
    document.getElementById('pos-filter').innerHTML =
      `<select id="pos-select" class="team-select">
        <option value="">All Positions</option>
        ${positions.map(p => `<option value="${p}">${p}</option>`).join('')}
      </select>`;
    document.getElementById('pos-select').addEventListener('change', e => {
      currentPos = e.target.value;
      render();
    });
  }

  function filtered() {
    return players.filter(p =>
      (!currentPos || p.pos === currentPos) &&
      (!query || p.player.toLowerCase().includes(query)));
  }

  function render() {
    const rows = filtered();
    renderCount(rows);
    renderTable(rows);
  }

  function renderCount(rows) {
    const el = document.getElementById('result-count');
    if (!rows.length) { el.textContent = ''; return; }
    const drafts = rows.reduce((s, p) => s + p.times, 0);
    el.textContent = `${rows.length} player${rows.length === 1 ? '' : 's'} · ${drafts} draft pick${drafts === 1 ? '' : 's'}`;
  }

  function renderTable(rows) {
    const thead = document.getElementById('history-thead');
    const tbody = document.getElementById('history-tbody');

    thead.innerHTML = COLUMNS.map(col => {
      const arrow = sortState.key === col.key ? (sortState.asc ? '&#9650;' : '&#9660;') : '';
      return `<th data-sort="${col.key}">${col.label} <span class="sort-arrow">${arrow}</span></th>`;
    }).join('');

    thead.querySelectorAll('th').forEach(th => {
      th.addEventListener('click', () => {
        const key = th.dataset.sort;
        if (sortState.key === key) sortState.asc = !sortState.asc;
        else { sortState.key = key; sortState.asc = key === 'player' || key === 'pos'; }
        renderTable(rows);
      });
    });

    const col = COLUMNS.find(c => c.key === sortState.key);
    const sorted = [...rows].sort((a, b) => {
      let va = a[sortState.key], vb = b[sortState.key];
      if (col && col.sort === 'str') { va = String(va).toLowerCase(); vb = String(vb).toLowerCase(); }
      return sortState.asc ? (va < vb ? -1 : va > vb ? 1 : 0) : (va > vb ? -1 : va < vb ? 1 : 0);
    });

    if (!sorted.length) {
      tbody.innerHTML = `<tr><td colspan="${COLUMNS.length}" class="no-results">
        No drafted player matches that search.</td></tr>`;
      return;
    }

    tbody.innerHTML = sorted.map(p => summaryRow(p) + detailRow(p)).join('');

    tbody.querySelectorAll('tr.summary-row').forEach(tr => {
      tr.addEventListener('click', () => {
        const name = tr.dataset.player;
        if (expanded.has(name)) expanded.delete(name); else expanded.add(name);
        renderTable(rows);
      });
    });

    if (window.TableMobile) TableMobile.init(document.getElementById('history-scroll'));
  }

  function summaryRow(p) {
    const open = expanded.has(p.player);
    return `<tr class="summary-row${open ? ' open' : ''}" data-player="${esc(p.player)}">
      <td class="player-name"><span class="expander">${open ? '&#9660;' : '&#9654;'}</span> ${p.player}</td>
      <td><span class="pos-badge pos-${p.pos}">${p.pos}</span></td>
      <td>${p.times}&times;</td>
      <td>$${p.spent}</td>
      <td>${p.pts.toFixed(1)}</td>
      <td class="${cls(p.value)}">${signed(p.value)}</td>
      <td class="${cls(p.avgValue)}">${signed(p.avgValue)}</td>
    </tr>`;
  }

  function detailRow(p) {
    if (!expanded.has(p.player)) return '';
    const years = p.years.map(y => `
      <tr>
        <td>${y.year}</td>
        <td class="owner-cell">${y.owner}</td>
        <td>$${y.cost}</td>
        <td>${y.pts.toFixed(1)}</td>
        <td class="${cls(y.value)}">${signed(y.value)}</td>
      </tr>`).join('');
    return `<tr class="detail-row"><td colspan="${COLUMNS.length}">
      <table class="year-table">
        <thead><tr><th>Year</th><th>Drafted By</th><th>Cost</th><th>Points</th><th>Value</th></tr></thead>
        <tbody>${years}</tbody>
      </table>
    </td></tr>`;
  }

  const cls = v => (v > 0 ? 'value-pos' : v < 0 ? 'value-neg' : '');
  const signed = v => (v >= 0 ? '+' : '') + v.toFixed(1);
  const esc = s => s.replace(/"/g, '&quot;');
})();
