/**
 * Draft Value page: season tabs, best/worst tables, scatter plot.
 */
(function () {
  const SEASONS = ['2022', '2023', '2024', '2025'];
  const COLUMNS = [
    { key: 'rank', label: 'Rank', sort: 'num' },
    { key: 'player', label: 'Player', sort: 'str' },
    { key: 'pos', label: 'Pos', sort: 'str' },
    { key: 'team', label: 'Team', sort: 'str' },
    { key: 'cost', label: 'Cost', sort: 'num', fmt: v => `$${v}` },
    { key: 'pts', label: 'Total Pts', sort: 'num', fmt: v => v.toFixed(1) },
    { key: 'ppd', label: 'Pts/$', sort: 'num', fmt: v => v.toFixed(1) },
    { key: 'value', label: 'Value Score', sort: 'num', fmt: v => (v >= 0 ? '+' : '') + v.toFixed(1) },
  ];

  const POS_COLORS = {
    QB: '#e8443a', RB: '#3498db', WR: '#27ae60', TE: '#f5a623',
    K: '#9b59b6', DEF: '#7f8c8d',
  };

  let data = null;
  let currentSeason = '2025';
  let chart = null;

  // Sort state per table
  const sortState = { best: { key: 'value', asc: false }, worst: { key: 'value', asc: true } };

  DataLoader.loadJSON('data/draft_value.json').then(d => {
    data = d;
    buildSeasonTabs();
    selectSeason(currentSeason);
  }).catch(() => {
    document.querySelector('.page-container').innerHTML +=
      '<p style="color:var(--red)">Error loading draft value data.</p>';
  });

  // ===== SEASON TABS =====
  function buildSeasonTabs() {
    const container = document.getElementById('season-toggle');
    SEASONS.forEach(s => {
      if (!data[s]) return;
      const btn = document.createElement('button');
      btn.className = 'season-btn' + (s === currentSeason ? ' active' : '');
      btn.textContent = s;
      btn.addEventListener('click', () => selectSeason(s));
      container.appendChild(btn);
    });
  }

  function selectSeason(season) {
    currentSeason = season;
    document.querySelectorAll('#season-toggle .season-btn').forEach(btn => {
      btn.classList.toggle('active', btn.textContent === season);
    });
    render();
  }

  // ===== RENDER =====
  function render() {
    const seasonData = data[currentSeason];
    if (!seasonData) return;

    const players = seasonData.players;

    // Best = top 25 by value, Worst = bottom 25 by value
    renderTable('best', players.slice(0, 25), 'best');
    renderTable('worst', players.slice(-25).reverse(), 'worst');
    renderChart(players);
  }

  function renderTable(prefix, players, tableId) {
    const thead = document.getElementById(`${prefix}-thead`);
    const tbody = document.getElementById(`${prefix}-tbody`);
    const state = sortState[tableId];

    // Build header
    thead.innerHTML = COLUMNS.map(col => {
      const arrow = state.key === col.key ? (state.asc ? '&#9650;' : '&#9660;') : '';
      return `<th data-col="${col.key}">${col.label} <span class="sort-arrow">${arrow}</span></th>`;
    }).join('');

    // Attach sort handlers
    thead.querySelectorAll('th').forEach(th => {
      th.addEventListener('click', () => {
        const key = th.dataset.col;
        if (state.key === key) state.asc = !state.asc;
        else { state.key = key; state.asc = key === 'player' || key === 'team'; }
        renderTable(prefix, players, tableId);
      });
    });

    // Sort
    const col = COLUMNS.find(c => c.key === state.key);
    const sorted = [...players].sort((a, b) => {
      let va = state.key === 'rank' ? players.indexOf(a) : a[state.key];
      let vb = state.key === 'rank' ? players.indexOf(b) : b[state.key];
      if (col && col.sort === 'str') {
        va = String(va).toLowerCase();
        vb = String(vb).toLowerCase();
      }
      return state.asc ? (va < vb ? -1 : va > vb ? 1 : 0) : (va > vb ? -1 : va < vb ? 1 : 0);
    });

    // Build rows
    tbody.innerHTML = sorted.map((p, i) => {
      const valueClass = p.value > 0 ? 'value-pos' : p.value < 0 ? 'value-neg' : '';
      return `<tr>
        <td>${i + 1}</td>
        <td class="player-name">${p.player}</td>
        <td><span class="pos-badge pos-${p.pos}">${p.pos}</span></td>
        <td>${p.team}</td>
        <td>$${p.cost}</td>
        <td>${p.pts.toFixed(1)}</td>
        <td>${p.ppd.toFixed(1)}</td>
        <td class="${valueClass}">${(p.value >= 0 ? '+' : '') + p.value.toFixed(1)}</td>
      </tr>`;
    }).join('');
  }

  // ===== SCATTER CHART =====
  function renderChart(players) {
    const canvas = document.getElementById('draft-scatter');
    if (chart) chart.destroy();

    // Group by position for separate datasets
    const datasets = [];
    const positions = [...new Set(players.map(p => p.pos))].filter(p => POS_COLORS[p]);

    positions.forEach(pos => {
      const posPlayers = players.filter(p => p.pos === pos);
      datasets.push({
        label: pos,
        data: posPlayers.map(p => ({ x: p.cost, y: p.pts, player: p.player, team: p.team })),
        backgroundColor: POS_COLORS[pos] + 'cc',
        borderColor: POS_COLORS[pos],
        borderWidth: 1,
        pointRadius: 5,
        pointHoverRadius: 8,
      });
    });

    chart = new Chart(canvas, {
      type: 'scatter',
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: { color: '#e8e6e3', font: { family: 'Inter' } },
          },
          tooltip: {
            backgroundColor: '#1a1d2e',
            borderColor: '#f5a623',
            borderWidth: 1,
            callbacks: {
              label: ctx => {
                const p = ctx.raw;
                return `${p.player} (${ctx.dataset.label}) — $${p.x}, ${p.y.toFixed(1)} pts`;
              },
            },
          },
        },
        scales: {
          x: {
            title: { display: true, text: 'Draft Cost ($)', color: '#9b98a0' },
            ticks: { color: '#9b98a0' },
            grid: { color: '#1a1d2e44' },
          },
          y: {
            title: { display: true, text: 'Total Points', color: '#9b98a0' },
            ticks: { color: '#9b98a0' },
            grid: { color: '#1a1d2e44' },
          },
        },
      },
    });
  }
})();
