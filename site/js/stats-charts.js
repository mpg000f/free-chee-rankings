/**
 * Stats page: sortable table + Chart.js visualizations
 */
(async function() {
  const owners = await DataLoader.getOwners();
  const index = await DataLoader.getRankingsIndex();

  // ===== SORTABLE TABLE =====
  const tableBody = document.getElementById('stats-table-body');
  const tableHeaders = document.querySelectorAll('.stats-table th[data-sort]');
  let sortKey = 'avg_rank';
  let sortAsc = true;

  function renderTable() {
    const entries = Object.values(owners).sort((a, b) => {
      let va = a[sortKey], vb = b[sortKey];
      if (typeof va === 'string') va = va.toLowerCase();
      if (typeof vb === 'string') vb = vb.toLowerCase();
      if (sortAsc) return va < vb ? -1 : va > vb ? 1 : 0;
      return va > vb ? -1 : va < vb ? 1 : 0;
    });

    tableBody.innerHTML = entries.map(o => {
      const seasonBadges = o.seasons.map(s => `<span style="font-size:.7rem;background:var(--surface-light);padding:.1rem .3rem;border-radius:3px;margin-left:.25rem">${s}</span>`).join('');
      return `<tr>
        <td class="owner-cell">${o.name}${seasonBadges}</td>
        <td>${o.avg_rank}</td>
        <td>${o.best_rank}</td>
        <td>${o.worst_rank}</td>
        <td>${o.total_weeks}</td>
        <td>${o.weeks_at_1}</td>
        <td>${o.weeks_at_16}</td>
      </tr>`;
    }).join('');
  }

  tableHeaders.forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.sort;
      if (sortKey === key) {
        sortAsc = !sortAsc;
      } else {
        sortKey = key;
        sortAsc = key === 'name' ? true : true;
      }
      // Update sort indicators
      tableHeaders.forEach(h => {
        const arrow = h.querySelector('.sort-arrow');
        if (arrow) arrow.textContent = h.dataset.sort === sortKey ? (sortAsc ? '▲' : '▼') : '';
      });
      renderTable();
    });
  });

  renderTable();

  // ===== RANKING HISTORY CHART =====
  const ctx = document.getElementById('ranking-chart').getContext('2d');

  // Build chart data
  // Get all unique week_ids in order
  const allWeeks = index.weeks.map(w => w.week_id);
  const weekLabels = index.weeks.map(w => `${w.season} ${w.label}`);

  // Colors for owners (deterministic)
  const palette = [
    '#f5a623', '#e8443a', '#27ae60', '#3498db', '#9b59b6',
    '#e67e22', '#1abc9c', '#e74c3c', '#2ecc71', '#f39c12',
    '#8e44ad', '#16a085', '#d35400', '#2980b9', '#c0392b',
    '#7f8c8d', '#2c3e50', '#f1c40f', '#95a5a6', '#34495e',
    '#e91e63', '#00bcd4',
  ];

  // Only show owners with 5+ weeks by default
  const mainOwners = Object.entries(owners)
    .filter(([_, o]) => o.total_weeks >= 5)
    .sort((a, b) => a[1].avg_rank - b[1].avg_rank);

  const datasets = mainOwners.map(([name, data], i) => {
    const points = allWeeks.map(weekId => {
      const r = data.rankings.find(r => r.week_id === weekId);
      return r ? r.rank : null;
    });
    return {
      label: name,
      data: points,
      borderColor: palette[i % palette.length],
      backgroundColor: palette[i % palette.length] + '20',
      borderWidth: 2,
      pointRadius: 3,
      pointHoverRadius: 6,
      tension: 0.3,
      spanGaps: true,
    };
  });

  const chart = new Chart(ctx, {
    type: 'line',
    data: { labels: weekLabels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'nearest', intersect: false },
      scales: {
        y: {
          reverse: true,
          min: 1, max: 16,
          ticks: {
            stepSize: 1,
            color: '#9b98a0',
            font: { family: 'Oswald' },
          },
          grid: { color: '#1a1d2e' },
          title: { display: true, text: 'Ranking', color: '#9b98a0', font: { family: 'Oswald' } },
        },
        x: {
          ticks: {
            color: '#9b98a0',
            maxRotation: 45,
            font: { size: 10 },
          },
          grid: { color: '#1a1d2e' },
        },
      },
      plugins: {
        legend: {
          display: false,
        },
        tooltip: {
          backgroundColor: '#1a1d2e',
          borderColor: '#f5a623',
          borderWidth: 1,
          titleFont: { family: 'Oswald' },
          bodyFont: { family: 'Inter' },
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: #${ctx.raw}`,
          },
        },
      },
    },
  });

  // ===== OWNER FILTER =====
  const filterToggle = document.getElementById('owner-filter-toggle');
  const filterDropdown = document.getElementById('owner-filter-dropdown');
  const filterSearch = document.getElementById('owner-filter-search');
  const filterList = document.getElementById('owner-filter-list');
  const filterLabel = document.getElementById('owner-filter-label');
  const selectAllBtn = document.getElementById('owner-select-all');
  const selectNoneBtn = document.getElementById('owner-select-none');

  // Build checkbox list
  mainOwners.forEach(([name], i) => {
    const item = document.createElement('label');
    item.className = 'owner-filter-item';
    item.dataset.name = name.toLowerCase();
    item.innerHTML = `<input type="checkbox" checked data-index="${i}"><span class="owner-filter-swatch" style="background:${palette[i % palette.length]}"></span>${name}`;
    filterList.appendChild(item);
  });

  function updateFilterLabel() {
    const boxes = filterList.querySelectorAll('input[type="checkbox"]');
    const checked = [...boxes].filter(b => b.checked).length;
    if (checked === boxes.length) {
      filterLabel.textContent = 'All Owners';
    } else if (checked === 0) {
      filterLabel.textContent = 'No Owners';
    } else if (checked <= 3) {
      const names = [...boxes].filter(b => b.checked).map(b => mainOwners[+b.dataset.index][0]);
      filterLabel.textContent = names.join(', ');
    } else {
      filterLabel.textContent = `${checked} Owners`;
    }
  }

  function applyOwnerFilter() {
    const boxes = filterList.querySelectorAll('input[type="checkbox"]');
    boxes.forEach(box => {
      const idx = +box.dataset.index;
      const meta = chart.getDatasetMeta(idx);
      meta.hidden = !box.checked;
    });
    chart.update();
    updateFilterLabel();
  }

  filterList.addEventListener('change', applyOwnerFilter);

  selectAllBtn.addEventListener('click', () => {
    filterList.querySelectorAll('input[type="checkbox"]').forEach(b => b.checked = true);
    applyOwnerFilter();
  });
  selectNoneBtn.addEventListener('click', () => {
    filterList.querySelectorAll('input[type="checkbox"]').forEach(b => b.checked = false);
    applyOwnerFilter();
  });

  // Toggle dropdown
  filterToggle.addEventListener('click', () => {
    filterDropdown.classList.toggle('open');
    if (filterDropdown.classList.contains('open')) filterSearch.focus();
  });

  // Close dropdown on outside click
  document.addEventListener('click', e => {
    if (!e.target.closest('.owner-filter')) {
      filterDropdown.classList.remove('open');
    }
  });

  // Search filter
  filterSearch.addEventListener('input', () => {
    const q = filterSearch.value.toLowerCase();
    filterList.querySelectorAll('.owner-filter-item').forEach(item => {
      item.style.display = item.dataset.name.includes(q) ? '' : 'none';
    });
  });

  // Season filter buttons
  let currentSeason = 'all';
  document.getElementById('chart-controls').addEventListener('click', e => {
    const btn = e.target.closest('.season-btn');
    if (!btn) return;
    currentSeason = btn.dataset.season;

    // Update active state
    document.querySelectorAll('#chart-controls .season-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    updateChartSeason();
  });

  function updateChartSeason() {
    if (currentSeason === 'all') {
      chart.data.labels = weekLabels;
      datasets.forEach((ds, i) => {
        ds.data = allWeeks.map(weekId => {
          const r = mainOwners[i][1].rankings.find(r => r.week_id === weekId);
          return r ? r.rank : null;
        });
      });
    } else {
      const filteredWeeks = index.weeks.filter(w => w.season === currentSeason);
      const filteredIds = filteredWeeks.map(w => w.week_id);
      const filteredLabels = filteredWeeks.map(w => w.label);
      chart.data.labels = filteredLabels;
      datasets.forEach((ds, i) => {
        ds.data = filteredIds.map(weekId => {
          const r = mainOwners[i][1].rankings.find(r => r.week_id === weekId);
          return r ? r.rank : null;
        });
      });
    }
    chart.update();
  }
})();
