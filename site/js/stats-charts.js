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
          position: 'bottom',
          labels: {
            color: '#e8e6e3',
            usePointStyle: true,
            padding: 12,
            font: { size: 11 },
          },
          onClick: (e, legendItem, legend) => {
            // Toggle visibility
            const idx = legendItem.datasetIndex;
            const meta = chart.getDatasetMeta(idx);
            meta.hidden = !meta.hidden;
            chart.update();
          },
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

  // Season filter buttons
  document.getElementById('chart-controls').addEventListener('click', e => {
    const btn = e.target.closest('.season-btn');
    if (!btn) return;
    const season = btn.dataset.season;

    // Update active state
    document.querySelectorAll('#chart-controls .season-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    if (season === 'all') {
      chart.data.labels = weekLabels;
      datasets.forEach((ds, i) => {
        ds.data = allWeeks.map(weekId => {
          const r = mainOwners[i][1].rankings.find(r => r.week_id === weekId);
          return r ? r.rank : null;
        });
      });
    } else {
      const filteredWeeks = index.weeks.filter(w => w.season === season);
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
  });
})();
