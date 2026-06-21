/**
 * Records: render the league record book from precomputed records.json.
 */
(function () {
  const content = document.getElementById('records-content');

  DataLoader.loadJSON('data/records.json').then(r => {
    content.innerHTML = render(r);
  }).catch(() => {
    content.innerHTML = '<p style="color:var(--red)">Error loading records.</p>';
  });

  const when = x => `${x.season} &bull; Week ${x.week}`;

  function card(title, value, detail, cls) {
    return `<div class="record-card ${cls || ''}">
      <div class="record-title">${title}</div>
      <div class="record-value">${value}</div>
      <div class="record-detail">${detail}</div>
    </div>`;
  }

  function leaders(title, list, suffix) {
    const rows = list.map((x, i) =>
      `<div class="leader-row"><span class="leader-rank">${i + 1}</span>
       <span class="leader-name">${x.owner}</span>
       <span class="leader-count">${x.count} ${suffix}${x.count === 1 ? '' : 's'}</span></div>`
    ).join('');
    return `<div class="record-card record-leaders">
      <div class="record-title">${title}</div>${rows}</div>`;
  }

  function render(r) {
    const high = r.highest_score, low = r.lowest_score;
    const blow = r.biggest_blowout, close = r.closest_game;
    const shoot = r.highest_scoring_game, snooze = r.lowest_scoring_game;
    const hardLuck = r.most_points_in_loss, uglyWin = r.fewest_points_in_win;

    return `
      <h2 class="records-section">Single-Game Glory</h2>
      <div class="records-grid">
        ${card('Highest Score', high.pts.toFixed(1), `${high.owner} vs ${high.opp} (${high.opp_pts.toFixed(1)}) &bull; ${when(high)}`, 'rec-good')}
        ${card('Biggest Blowout', `${blow.margin.toFixed(1)} pts`, `${blow.winner} ${blow.win_pts.toFixed(1)} – ${blow.lose_pts.toFixed(1)} ${blow.loser} &bull; ${when(blow)}`, 'rec-good')}
        ${card('Highest-Scoring Game', `${shoot.total.toFixed(1)} pts`, `${shoot.winner} ${shoot.win_pts.toFixed(1)} – ${shoot.lose_pts.toFixed(1)} ${shoot.loser} &bull; ${when(shoot)}`)}
        ${card('Nail-Biter', `${close.margin.toFixed(1)} pts`, `${close.winner} ${close.win_pts.toFixed(1)} – ${close.lose_pts.toFixed(1)} ${close.loser} &bull; ${when(close)}`)}
        ${card('Longest Win Streak', `${r.longest_win_streak.len} games`, `${r.longest_win_streak.owner}`, 'rec-good')}
        ${card('Most Points in a Loss', hardLuck.pts.toFixed(1), `${hardLuck.owner} lost to ${hardLuck.opp} (${hardLuck.opp_pts.toFixed(1)}) &bull; ${when(hardLuck)}`)}
      </div>

      <h2 class="records-section">Hall of Shame</h2>
      <div class="records-grid">
        ${card('Lowest Score', low.pts.toFixed(1), `${low.owner} vs ${low.opp} (${low.opp_pts.toFixed(1)}) &bull; ${when(low)}`, 'rec-bad')}
        ${card('Ugliest Win', uglyWin.pts.toFixed(1), `${uglyWin.owner} still beat ${uglyWin.opp} (${uglyWin.opp_pts.toFixed(1)}) &bull; ${when(uglyWin)}`, 'rec-bad')}
        ${card('Lowest-Scoring Game', `${snooze.total.toFixed(1)} pts`, `${snooze.winner} ${snooze.win_pts.toFixed(1)} – ${snooze.lose_pts.toFixed(1)} ${snooze.loser} &bull; ${when(snooze)}`, 'rec-bad')}
        ${card('Longest Losing Streak', `${r.longest_losing_streak.len} games`, `${r.longest_losing_streak.owner}`, 'rec-bad')}
      </div>

      <h2 class="records-section">The Ledger</h2>
      <div class="records-grid">
        ${leaders('Most Championships', r.most_championships, 'ring')}
        ${leaders('Most Last-Place Finishes', r.most_last_place, 'finish')}
      </div>
    `;
  }
})();
