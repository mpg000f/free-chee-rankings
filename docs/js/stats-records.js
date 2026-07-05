/**
 * Stats page: all-time records table (W-L, win%, PF, PA, PPG) from careers.json.
 */
(function () {
  const body = document.getElementById('records-table-body');
  if (!body) return;
  const headers = document.querySelectorAll('#records-table th[data-sort]');
  let rows = [];
  let sortKey = 'win_pct';
  let sortAsc = false;

  DataLoader.loadJSON('data/careers.json?v=h2h1').then(d => {
    rows = Object.values(d.careers);
    render();
    headers.forEach(th => th.addEventListener('click', () => {
      const k = th.dataset.sort;
      if (sortKey === k) sortAsc = !sortAsc;
      else { sortKey = k; sortAsc = (k === 'name'); }
      headers.forEach(h => {
        const a = h.querySelector('.sort-arrow');
        if (a) a.textContent = h.dataset.sort === sortKey ? (sortAsc ? '▲' : '▼') : '';
      });
      render();
    }));
  }).catch(() => {
    body.innerHTML = '<tr><td colspan="6" style="color:var(--red)">Error loading records.</td></tr>';
  });

  function val(o, k) {
    if (k === 'name') return o.owner.toLowerCase();
    if (k === 'wins') return o.wins;       // W-L column sorts by wins
    return o[k];
  }

  function render() {
    const sorted = [...rows].sort((a, b) => {
      const va = val(a, sortKey), vb = val(b, sortKey);
      if (sortAsc) return va < vb ? -1 : va > vb ? 1 : 0;
      return va > vb ? -1 : va < vb ? 1 : 0;
    });
    body.innerHTML = sorted.map(o => {
      const rec = `${o.wins}-${o.losses}${o.ties ? '-' + o.ties : ''}`;
      return `<tr>
        <td class="owner-cell">${o.owner}</td>
        <td>${rec}</td>
        <td>${(o.win_pct * 100).toFixed(1)}%</td>
        <td>${o.pf.toFixed(0)}</td>
        <td>${o.pa.toFixed(0)}</td>
        <td>${o.ppg.toFixed(1)}</td>
      </tr>`;
    }).join('');
  }
})();
