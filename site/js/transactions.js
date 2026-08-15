/**
 * Waivers & Trades page: season tabs, owner filter, pickup leaderboard, trade grades.
 */
(function () {
  const ALL_TIME = 'All-Time';
  const COLUMNS = [
    { key: 'rank', label: '#', sort: 'num' },
    { key: 'player', label: 'Player', sort: 'str' },
    { key: 'pos', label: 'Pos', sort: 'str' },
    { key: 'owner', label: 'Owner', sort: 'str' },
    { key: 'week', label: 'Added', sort: 'num' },
    { key: 'weeks_rostered', label: 'Weeks Held', sort: 'num' },
    { key: 'pts', label: 'Points', sort: 'num' },
    { key: 'ppg', label: 'Per Week', sort: 'num' },
  ];

  let data = null;
  let seasons = [];
  let currentSeason = null;
  let currentOwner = '';
  let showAll = false;

  const TOP_N = 25;
  const sortState = { key: 'pts', asc: false };

  DataLoader.loadJSON('data/transactions.json').then(d => {
    data = d;
    seasons = d.seasons || [];
    currentSeason = seasons[seasons.length - 1] || ALL_TIME;
    buildSeasonTabs();
    selectSeason(currentSeason);
  }).catch(() => {
    document.querySelector('.page-container').innerHTML +=
      '<p style="color:var(--red)">Error loading transaction data.</p>';
  });

  function buildSeasonTabs() {
    const container = document.getElementById('season-toggle');
    [...seasons, ALL_TIME].forEach(s => {
      const btn = document.createElement('button');
      btn.className = 'season-btn' + (s === currentSeason ? ' active' : '');
      btn.textContent = s;
      btn.addEventListener('click', () => selectSeason(s));
      container.appendChild(btn);
    });
  }

  function selectSeason(season) {
    currentSeason = season;
    currentOwner = '';
    showAll = false;
    document.querySelectorAll('#season-toggle .season-btn').forEach(btn => {
      btn.classList.toggle('active', btn.textContent === season);
    });
    buildOwnerFilter();
    render();
  }

  /** Seasons feeding the current view — one, or all of them under All-Time. */
  function activeSeasons() {
    return currentSeason === ALL_TIME ? seasons : [currentSeason];
  }

  function allPickups() {
    return activeSeasons().flatMap(s =>
      (data.data[s].pickups || []).map(p => ({ ...p, season: s })));
  }

  function allTrades() {
    return activeSeasons().flatMap(s =>
      (data.data[s].trades || []).map(t => ({ ...t, season: s })));
  }

  function buildOwnerFilter() {
    const owners = [...new Set(activeSeasons()
      .flatMap(s => data.data[s].owners || []))].sort();
    document.getElementById('owner-filter').innerHTML =
      `<select id="owner-select" class="team-select">
        <option value="">All Owners</option>
        ${owners.map(o => `<option value="${o}">${o}</option>`).join('')}
      </select>`;
    document.getElementById('owner-select').addEventListener('change', e => {
      currentOwner = e.target.value;
      showAll = false;
      render();
    });
  }

  function render() {
    const pickups = currentOwner
      ? allPickups().filter(p => p.owner === currentOwner)
      : allPickups();
    renderHighlights(pickups);
    renderPickups(pickups);
    renderTrades();
  }

  // ---- Best pickups ------------------------------------------------------

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
            currentSeason === ALL_TIME ? ` <span class="season-badge">${p.season}</span>` : ''
          } &bull; added Week ${p.week}</div>
        </div>
        <div class="pickup-pts">${p.pts.toFixed(1)}<span>pts</span></div>
      </div>`).join('');
  }

  function renderPickups(pickups) {
    const thead = document.getElementById('pickup-thead');
    const tbody = document.getElementById('pickup-tbody');
    const columns = currentSeason === ALL_TIME
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
        renderPickups(pickups);
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
        ${currentSeason === ALL_TIME ? `<td>${p.season}</td>` : ''}
        <td>Wk ${p.week}${p.claimed ? ' <span class="claim-tag" title="Claimed off another roster">claim</span>' : ''}</td>
        <td>${p.weeks_rostered}${p.held_to_end ? ' <span class="held-tag" title="Held through Week 17">&#9679;</span>' : ''}</td>
        <td class="value-pos">${p.pts.toFixed(1)}</td>
        <td>${p.ppg.toFixed(1)}</td>
      </tr>`).join('');

    const toggle = document.getElementById('pickup-toggle');
    if (sorted.length <= TOP_N) {
      toggle.innerHTML = '';
    } else {
      toggle.innerHTML = `<button class="season-btn">${
        showAll ? 'Show top 25' : `Show all ${sorted.length}`}</button>`;
      toggle.querySelector('button').addEventListener('click', () => {
        showAll = !showAll;
        renderPickups(pickups);
      });
    }

    if (window.TableMobile) TableMobile.init(document.getElementById('pickup-scroll'));
  }

  // ---- Trade grades ------------------------------------------------------

  function renderTrades() {
    const mount = document.getElementById('trade-list');
    let trades = allTrades();
    if (currentOwner) {
      trades = trades.filter(t => t.sides.some(s => s.owner === currentOwner));
    }
    trades.sort((a, b) => (b.season || '').localeCompare(a.season || '') || b.week - a.week);

    if (!trades.length) {
      mount.innerHTML = '<p class="placeholder-text">No trades on record for this filter.</p>';
      return;
    }

    mount.innerHTML = trades.map(t => `
      <div class="trade-card">
        <div class="trade-head">
          <span class="trade-date">${t.date}</span>
          <span class="trade-week">${t.preseason ? 'Preseason' : `Week ${t.week}`}</span>
          ${t.teams > 2 ? `<span class="trade-tag">${t.teams}-team</span>` : ''}
        </div>
        <div class="trade-sides">
          ${t.sides.map(s => renderSide(s, t)).join('')}
        </div>
      </div>`).join('');
  }

  function renderSide(side, trade) {
    const highlight = currentOwner && side.owner === currentOwner ? ' is-filtered' : '';
    const lines = [
      ...side.received.map(p => line(p, 'in')),
      ...side.sent.map(p => line(p, 'out')),
    ].join('');
    return `
      <div class="trade-side${highlight}">
        <div class="trade-side-head">
          <span class="grade grade-${side.grade}">${side.grade}</span>
          <span class="trade-owner">${side.owner}</span>
          <span class="trade-net ${side.net >= 0 ? 'value-pos' : 'value-neg'}">${
            (side.net >= 0 ? '+' : '') + side.net.toFixed(1)}</span>
        </div>
        <ul class="trade-players">${lines || '<li class="trade-empty">&mdash;</li>'}</ul>
        <div class="trade-side-foot">${side.pts.toFixed(1)} in &bull; ${side.gave.toFixed(1)} out
          &bull; ${trade.weeks_remaining} wk${trade.weeks_remaining === 1 ? '' : 's'} left</div>
      </div>`;
  }

  function line(p, dir) {
    const to = dir === 'out' && p.to_owner ? ` <span class="trade-to">&rarr; ${p.to_owner}</span>` : '';
    return `<li class="trade-player ${dir}">
      <span class="io">${dir === 'in' ? '+' : '&minus;'}</span>
      <span class="trade-player-name">${p.player}${to}</span>
      <span class="pos-badge pos-${p.pos}">${p.pos}</span>
      <span class="trade-pts">${p.pts.toFixed(1)}</span>
    </li>`;
  }
})();
