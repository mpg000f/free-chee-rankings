/**
 * Fantasy IQ: render the forward-looking rating from power_ratings.json.
 * Layout: how-it-works, an IQ chart, then a per-owner breakdown of component IQs.
 */
(function () {
  const content = document.getElementById('power-content');

  // ?v is bumped when the JSON schema changes so a freshly-deployed power.js
  // never reads a stale cached data file (they'd desync and crash).
  DataLoader.loadJSON('data/power_ratings.json?v=iq2').then(d => {
    content.innerHTML = render(d);
    try { drawChart(d); } catch (e) { /* chart is an enhancement; never block the page */ }
  }).catch(() => {
    content.innerHTML = '<p style="color:var(--red)">Error loading Fantasy IQ.</p>';
  });

  // ---- helpers ----
  function move(m) {
    if (!m) return '<span class="pr-move pr-move-flat">&bull;</span>';
    if (m > 0) return `<span class="pr-move pr-move-up">&#9650;${m}</span>`;
    return `<span class="pr-move pr-move-down">&#9660;${Math.abs(m)}</span>`;
  }

  // component bar centered on 100; fills right (gold) when above average, left (red) when below
  function compRow(label, iq, weight) {
    const frac = Math.max(-1, Math.min(1, (iq - 100) / 30));   // ±30 IQ = full half-bar
    const side = frac >= 0
      ? `left:50%;width:${frac * 50}%;background:var(--accent)`
      : `left:${50 + frac * 50}%;width:${-frac * 50}%;background:var(--red)`;
    return `<div class="pr-comp">
      <span class="pr-comp-label">${label} <span class="pr-comp-wt">${weight}%</span></span>
      <span class="pr-comp-track"><span class="pr-comp-mid"></span><span class="pr-comp-fill" style="${side}"></span></span>
      <span class="pr-comp-iq">${iq.toFixed(0)}</span>
    </div>`;
  }

  function tag(r) {
    const comps = [
      { k: 'Scoring', v: r.scoring_iq },
      { k: 'Draft', v: r.draft_iq },
      { k: 'Consistency', v: r.consistency_iq },
    ].sort((a, b) => b.v - a.v);
    const top = comps[0], bot = comps[2];
    let s = `Strength: ${top.k} (${top.v.toFixed(0)})`;
    if (bot.v < 97) s += ` &bull; Watch: ${bot.k} (${bot.v.toFixed(0)})`;
    return s;
  }

  function ownerCard(r, showMove) {
    return `<div class="pr-owner-card">
      <div class="pr-owner-head">
        <span class="pr-rank">${r.rank}</span>
        <span class="pr-owner">${r.owner}</span>
        <span class="pr-rating">${r.rating.toFixed(1)}</span>
        ${showMove ? move(r.movement) : ''}
      </div>
      <div class="pr-components">
        ${compRow('Scoring', r.scoring_iq, 55)}
        ${compRow('Draft', r.draft_iq, 30)}
        ${compRow('Consistency', r.consistency_iq, 15)}
      </div>
      <p class="pr-tag">${tag(r)}</p>
    </div>`;
  }

  function render(d) {
    return `
      <div class="pr-header">
        <span class="pr-label">${d.label}</span>
      </div>

      <div class="pr-method">
        <h2>How it works</h2>
        <p>Fantasy IQ scores each team like an IQ: <strong>100 is the league average</strong>,
        and every ~15 points is a big step. It's forward-looking — how good a team is
        <em>right now</em>, built only from repeatable skills, not trophies. Each factor is its
        own IQ on the same scale, and the overall is their weighted average:</p>
        <ul>
          <li><strong>Scoring — 55%.</strong> Points per game. The most predictive stat in fantasy.</li>
          <li><strong>Draft — 30%.</strong> Value squeezed out of the draft. Good drafters keep drafting well.</li>
          <li><strong>Consistency — 15%.</strong> Week-to-week reliability. High floor beats boom-or-bust.</li>
        </ul>
        <p>Wins, championships, playoff finishes and points-against are ignored on purpose —
        they rely on some luck, and this rating weighs entire bodies of work instead. Recent
        seasons count more, and once the season starts the rating blends in live results
        (heavier as more games are played).</p>
      </div>

      <div class="pr-chart-card">
        <h2>The Board</h2>
        <div class="pr-chart-wrap"><canvas id="iq-chart"></canvas></div>
        <p class="pr-chart-note">Dashed line = league average (100), same scale as real IQ.</p>
      </div>

      <h2 class="pr-breakdown-title">Breakdown</h2>
      <div class="pr-owner-list">
        ${d.ratings.map(r => ownerCard(r, !!d.updated_through)).join('')}
      </div>
    `;
  }

  function drawChart(d) {
    const canvas = document.getElementById('iq-chart');
    if (!canvas || typeof Chart === 'undefined') return;
    const css = getComputedStyle(document.documentElement);
    const gold = css.getPropertyValue('--accent').trim() || '#f5a623';
    const dim = css.getPropertyValue('--text-dim').trim() || '#9b98a0';
    const surface = css.getPropertyValue('--surface-light').trim() || '#242840';

    // vertical bars, highest IQ on the left -> data is already sorted descending
    const rows = d.ratings;
    const labels = rows.map(r => r.owner);
    const vals = rows.map(r => r.rating);
    const colors = rows.map(r => r.rating >= 100 ? gold : dim);
    const min = Math.floor(Math.min(...vals) - 3);
    const max = Math.ceil(Math.max(...vals) + 3);

    canvas.parentElement.style.height = '400px';
    new Chart(canvas, {
      type: 'bar',
      data: { labels, datasets: [{ data: vals, backgroundColor: colors, borderRadius: 3 }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: c => `Fantasy IQ ${c.parsed.y.toFixed(1)}` } },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#e8e6e3', font: { size: 11 }, maxRotation: 60, minRotation: 45 } },
          y: { min, max, grid: { color: surface }, ticks: { color: dim } },
        },
      },
      plugins: [{
        id: 'avgline',
        afterDraw(chart) {
          const { left, right } = chart.chartArea;
          const y = chart.scales.y.getPixelForValue(100);
          const ctx = chart.ctx;
          ctx.save();
          ctx.setLineDash([5, 4]);
          ctx.strokeStyle = dim;
          ctx.lineWidth = 1;
          ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(right, y); ctx.stroke();
          ctx.setLineDash([]);
          ctx.fillStyle = dim;
          ctx.font = '11px Inter, sans-serif';
          ctx.textAlign = 'left';
          ctx.textBaseline = 'bottom';
          ctx.fillText('League average (100)', left + 5, y - 2);
          ctx.restore();
        },
      }],
    });
  }
})();
