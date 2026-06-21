/**
 * Shared career-profile renderer used by the Careers hub and the per-owner
 * shareable pages. Exposes window.buildCareerProfile(careerObj) -> HTML string.
 */
(function () {
  function stat(label, value, sub) {
    return `<div class="summary-stat">
      <div class="summary-label">${label}</div>
      <div class="summary-value">${value}</div>
      ${sub ? `<div class="summary-sub">${sub}</div>` : ''}
    </div>`;
  }

  window.buildCareerProfile = function (c) {
    if (!c) return '<p class="placeholder-text">No data.</p>';

    const rec = `${c.wins}-${c.losses}${c.ties ? `-${c.ties}` : ''}`;
    const trophies = [];
    for (let i = 0; i < c.championships; i++) trophies.push('&#127942;');
    const trophyRow = c.championships
      ? `<div class="career-trophies">${trophies.join(' ')} <span>${c.championships}&times; Champion</span></div>`
      : `<div class="career-trophies career-ringless">No rings yet</div>`;

    const rival = c.rival
      ? `${c.rival.owner} <span class="muted">(${c.rival.wins}-${c.rival.losses})</span>`
      : '—';

    const bp = c.best_pick, wp = c.worst_pick;

    return `
      <div class="career-hero">
        <div class="career-name">${c.owner}</div>
        ${trophyRow}
        ${c.comparison ? `<div class="career-comp"><span class="comparison-label">Presidential Comparison:</span> ${c.comparison.replace(/\s+/g, ' ').trim()}</div>` : ''}
      </div>

      <div class="season-summary">
        <div class="summary-grid">
          ${stat('All-Time Record', rec, `${(c.win_pct * 100).toFixed(1)}% &bull; ${c.seasons_played} seasons`)}
          ${stat('Points / Game', c.ppg, `${c.pf.toFixed(0)} for, ${c.pa.toFixed(0)} against`)}
          ${stat('Best Standing', c.best_finish ? `#${c.best_finish}` : '—', c.last_places ? `${c.last_places}&times; last place` : 'reg. season')}
          ${stat('Playoff Resume', `${c.finals}F / ${c.semis}S`, 'finals / semis reached')}
          ${c.avg_power_rank != null ? stat('Avg Power Rank', c.avg_power_rank, c.best_rank ? `best: #${c.best_rank}` : '') : ''}
          ${c.power_score != null ? stat('Lookback Power Score', c.power_score, 'first-term grade') : ''}
        </div>
      </div>

      <div class="career-cards">
        <div class="record-card"><div class="record-title">Biggest Rival</div>
          <div class="record-value">${rival}</div>
          <div class="record-detail">most-played opponent</div></div>
        ${bp ? `<div class="record-card rec-good"><div class="record-title">Best Draft Pick</div>
          <div class="record-value">${bp.player}</div>
          <div class="record-detail">$${bp.cost} &rarr; ${bp.pts.toFixed(0)} pts (+${bp.value} value)</div></div>` : ''}
        ${wp ? `<div class="record-card rec-bad"><div class="record-title">Worst Draft Pick</div>
          <div class="record-value">${wp.player}</div>
          <div class="record-detail">$${wp.cost} &rarr; ${wp.pts.toFixed(0)} pts (${wp.value} value)</div></div>` : ''}
      </div>
    `;
  };

  // owner -> filename slug used by the shareable pages
  window.careerSlug = function (owner) {
    return owner.toLowerCase().replace(/[^a-z0-9]+/g, '-');
  };
})();
