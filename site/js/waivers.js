/**
 * Waiver Wire page: the best in-season adds, with a sortable full leaderboard.
 */
(function () {
  const COLUMNS = [
    { key: 'rank', label: '#', sort: 'num' },
    { key: 'player', label: 'Player', sort: 'str' },
    { key: 'pos', label: 'Pos', sort: 'str' },
    { key: 'owner', label: 'Owner', sort: 'str' },
    { key: 'week', label: 'Added', sort: 'num' },
    { key: 'weeks_rostered', label: 'Weeks Held', sort: 'num' },
    { key: 'pts', label: 'Points', sort: 'num' },
    { key: 'ppg', label: 'Per Week', sort: 'num' },
    { key: 'vor', label: 'Over Repl.', sort: 'num' },
  ];

  const TOP_N = 25;
  const sortState = { key: 'pts', asc: false };
  let showAll = false;

  TxnControls.load(render);

  function render() {
    showAll = false;
    const owner = TxnControls.owner();
    const pickups = TxnControls.collect('pickups')
      .filter(p => !owner || p.owner === owner);
    renderHighlights(pickups);
    renderTable(pickups);
  }

  function renderHighlights(pickups) {
    const mount = document.getElementById('pickup-highlights');
    const top = [...pickups].sort((a, b) => b.pts - a.pts).slice(0, 3);
    if (!top.length) { mount.innerHTML = ''; return; }

    const medals = ['tier-1', 'tier-2', 'tier-3'];
    mount.innerHTML = top.map((p, i) => `
      <div class="pickup-card ${medals[i]}">
        <div class="pickup-rank">${i + 1}</div>
        <div class="pickup-body">
          <div class="pickup-name">${p.player}
            <span class="pos-badge pos-${p.pos}">${p.pos}</span></div>
          <div class="pickup-meta">${p.owner}${
            TxnControls.isAllTime() ? ` <span class="season-badge">${p.season}</span>` : ''
          } &bull; added Week ${p.week}</div>
        </div>
        <div class="pickup-pts">${p.pts.toFixed(1)}<span>pts</span></div>
      </div>`).join('');
  }

  function renderTable(pickups) {
    const thead = document.getElementById('pickup-thead');
    const tbody = document.getElementById('pickup-tbody');
    const columns = TxnControls.isAllTime()
      ? [...COLUMNS.slice(0, 4), { key: 'season', label: 'Season', sort: 'str' }, ...COLUMNS.slice(4)]
      : COLUMNS;

    thead.innerHTML = columns.map(col => {
      const arrow = sortState.key === col.key ? (sortState.asc ? '&#9650;' : '&#9660;') : '';
      return `<th data-sort="${col.key}">${col.label} <span class="sort-arrow">${arrow}</span></th>`;
    }).join('');

    thead.querySelectorAll('th').forEach(th => {
      th.addEventListener('click', () => {
        const key = th.dataset.sort;
        if (key === 'rank') return;
        if (sortState.key === key) sortState.asc = !sortState.asc;
        else { sortState.key = key; sortState.asc = key === 'player' || key === 'owner'; }
        renderTable(pickups);
      });
    });

    const col = columns.find(c => c.key === sortState.key);
    const sorted = [...pickups].sort((a, b) => {
      let va = a[sortState.key], vb = b[sortState.key];
      if (col && col.sort === 'str') { va = String(va).toLowerCase(); vb = String(vb).toLowerCase(); }
      return sortState.asc ? (va < vb ? -1 : va > vb ? 1 : 0) : (va > vb ? -1 : va < vb ? 1 : 0);
    });

    const shown = showAll ? sorted : sorted.slice(0, TOP_N);
    tbody.innerHTML = shown.map((p, i) => `
      <tr>
        <td>${i + 1}</td>
        <td class="player-name">${p.player}</td>
        <td><span class="pos-badge pos-${p.pos}">${p.pos}</span></td>
        <td class="owner-cell">${p.owner}</td>
        ${TxnControls.isAllTime() ? `<td>${p.season}</td>` : ''}
        <td>Wk ${p.week}${p.claimed ? ' <span class="claim-tag" title="Claimed off another roster">claim</span>' : ''}</td>
        <td>${p.weeks_rostered}${p.held_to_end ? ' <span class="held-tag" title="Held through Week 17">&#9679;</span>' : ''}</td>
        <td class="value-pos">${p.pts.toFixed(1)}</td>
        <td>${p.ppg.toFixed(1)}</td>
        <td class="${p.vor >= 0 ? 'value-pos' : 'value-neg'}">${
          (p.vor >= 0 ? '+' : '') + p.vor.toFixed(1)}</td>
      </tr>`).join('');

    const toggle = document.getElementById('pickup-toggle');
    if (sorted.length <= TOP_N) {
      toggle.innerHTML = '';
    } else {
      toggle.innerHTML = `<button class="season-btn">${
        showAll ? 'Show top 25' : `Show all ${sorted.length}`}</button>`;
      toggle.querySelector('button').addEventListener('click', () => {
        showAll = !showAll;
        renderTable(pickups);
      });
    }

    if (window.TableMobile) TableMobile.init(document.getElementById('pickup-scroll'));
  }
})();
