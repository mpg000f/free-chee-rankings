/**
 * Draft Value page: season tabs, owner filter, draft board table, scatter plot.
 */
(function () {
  const SEASONS = ['2022', '2023', '2024', '2025'];
  const COLUMNS = [
    { key: 'rank', label: 'Rank', sort: 'num' },
    { key: 'player', label: 'Player', sort: 'str' },
    { key: 'pos', label: 'Pos', sort: 'str' },
    { key: 'owner', label: 'Owner', sort: 'str' },
    { key: 'cost', label: 'Cost', sort: 'num', fmt: v => `$${v}` },
    { key: 'pts', label: 'Total Pts', sort: 'num', fmt: v => v.toFixed(1) },
    { key: 'value', label: 'Value (Pts vs Expected)', sort: 'num', fmt: v => (v >= 0 ? '+' : '') + v.toFixed(1) },
  ];

  const POS_COLORS = {
    QB: '#e8443a', RB: '#3498db', WR: '#27ae60', TE: '#f5a623',
    DEF: '#7f8c8d',
  };

  let data = null;
  let currentSeason = '2025';
  let currentOwner = '';
  let chart = null;

  const sortState = { key: 'value', asc: false };

  DataLoader.loadJSON('data/draft_value.json').then(d => {
    data = d;
    buildSeasonTabs();
    selectSeason(currentSeason);
  }).catch(() => {
    document.querySelector('.page-container').innerHTML +=
      '<p style="color:var(--red)">Error loading draft value data.</p>';
  });

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
    currentOwner = '';
    document.querySelectorAll('#season-toggle .season-btn').forEach(btn => {
      btn.classList.toggle('active', btn.textContent === season);
    });
    buildOwnerFilter();
    render();
  }

  function buildOwnerFilter() {
    const container = document.getElementById('owner-filter');
    if (!container) return;
    const seasonData = data[currentSeason];
    if (!seasonData) return;

    const owners = seasonData.owners || [];
    container.innerHTML = `<select id="owner-select" class="team-select">
      <option value="">All Owners</option>
      ${owners.map(o => `<option value="${o}">${o}</option>`).join('')}
    </select>`;

    document.getElementById('owner-select').addEventListener('change', (e) => {
      currentOwner = e.target.value;
      render();
    });
  }

  function getFilteredPlayers() {
    const seasonData = data[currentSeason];
    if (!seasonData) return [];
    let players = seasonData.players;
    if (currentOwner) {
      players = players.filter(p => p.owner === currentOwner);
    }
    return players;
  }

  function render() {
    const players = getFilteredPlayers();
    renderTable(players);
    renderChart(players);
  }

  function renderTable(allPlayers) {
    const thead = document.getElementById('draft-thead');
    const tbody = document.getElementById('draft-tbody');

    thead.innerHTML = COLUMNS.map(col => {
      const arrow = sortState.key === col.key ? (sortState.asc ? '&#9650;' : '&#9660;') : '';
      return `<th data-col="${col.key}">${col.label} <span class="sort-arrow">${arrow}</span></th>`;
    }).join('');

    thead.querySelectorAll('th').forEach(th => {
      th.addEventListener('click', () => {
        const key = th.dataset.col;
        if (sortState.key === key) sortState.asc = !sortState.asc;
        else { sortState.key = key; sortState.asc = key === 'player' || key === 'owner'; }
        renderTable(allPlayers);
      });
    });

    const col = COLUMNS.find(c => c.key === sortState.key);
    const sorted = [...allPlayers].sort((a, b) => {
      let va = a[sortState.key];
      let vb = b[sortState.key];
      if (col && col.sort === 'str') {
        va = String(va).toLowerCase();
        vb = String(vb).toLowerCase();
      }
      return sortState.asc ? (va < vb ? -1 : va > vb ? 1 : 0) : (va > vb ? -1 : va < vb ? 1 : 0);
    });

    tbody.innerHTML = sorted.map((p, i) => {
      const valueClass = p.value > 0 ? 'value-pos' : p.value < 0 ? 'value-neg' : '';
      return `<tr>
        <td>${i + 1}</td>
        <td class="player-name">${p.player}</td>
        <td><span class="pos-badge pos-${p.pos}">${p.pos}</span></td>
        <td>${p.owner}</td>
        <td>$${p.cost}</td>
        <td>${p.pts.toFixed(1)}</td>
        <td class="${valueClass}">${(p.value >= 0 ? '+' : '') + p.value.toFixed(1)}</td>
      </tr>`;
    }).join('');
  }

  function renderChart(players) {
    const canvas = document.getElementById('draft-scatter');
    if (chart) chart.destroy();

    const datasets = [];
    const positions = [...new Set(players.map(p => p.pos))].filter(p => POS_COLORS[p]);

    positions.forEach(pos => {
      const posPlayers = players.filter(p => p.pos === pos);
      datasets.push({
        label: pos,
        data: posPlayers.map(p => ({ x: p.cost, y: p.pts, player: p.player, owner: p.owner })),
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
                return `${p.player} (${p.owner}) — $${p.x}, ${p.y.toFixed(1)} pts`;
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
