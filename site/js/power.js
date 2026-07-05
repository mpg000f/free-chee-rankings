/**
 * Fantasy IQ: render the forward-looking rating from power_ratings.json.
 */
(function () {
  const content = document.getElementById('power-content');

  DataLoader.loadJSON('data/power_ratings.json').then(d => {
    content.innerHTML = render(d);
  }).catch(() => {
    content.innerHTML = '<p style="color:var(--red)">Error loading power ratings.</p>';
  });

  function bar(label, pct) {
    return `<div class="pr-metric">
      <span class="pr-metric-label">${label}</span>
      <span class="pr-bar"><span class="pr-bar-fill" style="width:${pct}%"></span></span>
      <span class="pr-metric-pct">${pct}</span>
    </div>`;
  }

  function move(m) {
    if (!m) return '<span class="pr-move pr-move-flat">&bull;</span>';
    if (m > 0) return `<span class="pr-move pr-move-up">&#9650;${m}</span>`;
    return `<span class="pr-move pr-move-down">&#9660;${Math.abs(m)}</span>`;
  }

  function render(d) {
    const rows = d.ratings.map(r => `
      <div class="pr-row" data-rank="${r.rank}">
        <div class="pr-rank">${r.rank}</div>
        <div class="pr-main">
          <div class="pr-top">
            <span class="pr-owner">${r.owner}</span>
            <span class="pr-rating">${r.rating.toFixed(1)}</span>
            ${d.updated_through ? move(r.movement) : ''}
          </div>
          <div class="pr-metrics">
            ${bar('Scoring', r.scoring_pct)}
            ${bar('Draft', r.draft_pct)}
            ${bar('Consistency', r.consistency_pct)}
          </div>
        </div>
      </div>`).join('');

    const w = d.weights;
    return `
      <div class="pr-header">
        <span class="pr-label">${d.label}</span>
        <p class="pr-note">${d.note}</p>
      </div>
      <div class="pr-list">${rows}</div>
      <div class="pr-method">
        <h2>How it works</h2>
        <p>Fantasy IQ scores each team like an IQ: <strong>100 is the league average</strong>,
        and every ~15 points is a big step. It's forward-looking — how good a team is
        <em>right now</em>, built only from repeatable skills, not trophies. Each factor is
        scored against the league and weighted:</p>
        <ul>
          <li><strong>Scoring — ${Math.round(w.scoring * 100)}%.</strong> Points per game. The most predictive stat in fantasy.</li>
          <li><strong>Draft — ${Math.round(w.draft * 100)}%.</strong> Value squeezed out of the draft. Good drafters keep drafting well.</li>
          <li><strong>Consistency — ${Math.round(w.consistency * 100)}%.</strong> Week-to-week reliability. High floor beats boom-or-bust.</li>
        </ul>
        <p>Wins, championships, playoff finishes and points-against are ignored on purpose —
        they're mostly schedule luck, not skill. Recent seasons count more than old ones, and
        once the season starts the rating blends in live results (heavier as more games are played).</p>
      </div>
    `;
  }
})();
