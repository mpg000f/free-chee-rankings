/**
 * Head-to-Head: pick two owners, see their all-time series.
 */
(function () {
  let games = [];
  let owners = [];

  const selA = document.getElementById('owner-a');
  const selB = document.getElementById('owner-b');
  const content = document.getElementById('h2h-content');

  DataLoader.loadJSON('data/matchups_all.json').then(d => {
    games = d.games;
    owners = d.owners;
    fillSelect(selA, owners[0]);
    fillSelect(selB, owners[1]);
    selA.addEventListener('change', render);
    selB.addEventListener('change', render);
    render();
  }).catch(() => {
    content.innerHTML = '<p style="color:var(--red)">Error loading matchup data.</p>';
  });

  function fillSelect(sel, def) {
    sel.innerHTML = owners.map(o => `<option value="${o}">${o}</option>`).join('');
    sel.value = def;
  }

  function render() {
    const a = selA.value, b = selB.value;
    if (a === b) {
      content.innerHTML = '<p class="placeholder-text">Pick two different owners.</p>';
      return;
    }

    const meetings = games
      .filter(g => [g.o1, g.o2].includes(a) && [g.o1, g.o2].includes(b))
      .map(g => {
        const aPts = g.o1 === a ? g.p1 : g.p2;
        const bPts = g.o1 === a ? g.p2 : g.p1;
        return { season: g.season, week: g.week, playoff: g.playoff, aPts, bPts };
      })
      .sort((x, y) => (y.season + String(y.week).padStart(2, '0')).localeCompare(x.season + String(x.week).padStart(2, '0')));

    if (!meetings.length) {
      content.innerHTML = `<p class="placeholder-text">${a} and ${b} have never played.</p>`;
      return;
    }

    let aw = 0, bw = 0, ties = 0, aTot = 0, bTot = 0;
    let aBig = null, bBig = null;
    meetings.forEach(m => {
      aTot += m.aPts; bTot += m.bPts;
      const margin = m.aPts - m.bPts;
      if (margin > 0) { aw++; if (!aBig || margin > aBig.margin) aBig = { ...m, margin }; }
      else if (margin < 0) { bw++; if (!bBig || -margin > bBig.margin) bBig = { ...m, margin: -margin }; }
      else ties++;
    });

    // current streak (most recent first); who and how long
    let streakOwner = null, streakLen = 0;
    for (const m of meetings) {
      const w = m.aPts > m.bPts ? a : m.bPts > m.aPts ? b : null;
      if (w === null) break;
      if (streakOwner === null) { streakOwner = w; streakLen = 1; }
      else if (w === streakOwner) streakLen++;
      else break;
    }

    const n = meetings.length;
    const leader = aw > bw ? a : bw > aw ? b : null;
    const leadText = leader ? `${leader} leads the series` : 'Series is dead even';

    content.innerHTML = `
      <div class="h2h-scoreboard">
        <div class="h2h-side ${aw > bw ? 'h2h-winning' : ''}">
          <div class="h2h-owner">${a}</div>
          <div class="h2h-wins">${aw}</div>
          <div class="h2h-sub">${avg(aTot, n)} avg pts</div>
        </div>
        <div class="h2h-mid">
          <div class="h2h-dash">—</div>
          <div class="h2h-meta">${n} game${n === 1 ? '' : 's'}${ties ? ` &bull; ${ties} tie` : ''}</div>
        </div>
        <div class="h2h-side ${bw > aw ? 'h2h-winning' : ''}">
          <div class="h2h-owner">${b}</div>
          <div class="h2h-wins">${bw}</div>
          <div class="h2h-sub">${avg(bTot, n)} avg pts</div>
        </div>
      </div>

      <p class="h2h-headline">${leadText}${streakOwner ? ` &bull; ${streakOwner} has won ${streakLen} straight` : ''}.</p>

      <div class="h2h-facts">
        ${aBig ? factCard(`${a}'s best win`, `${aBig.aPts.toFixed(1)}–${aBig.bPts.toFixed(1)}`, `${seasonWeek(aBig)} &bull; by ${aBig.margin.toFixed(1)}`) : ''}
        ${bBig ? factCard(`${b}'s best win`, `${bBig.bPts.toFixed(1)}–${bBig.aPts.toFixed(1)}`, `${seasonWeek(bBig)} &bull; by ${bBig.margin.toFixed(1)}`) : ''}
        ${factCard('Total points', `${aTot.toFixed(0)} – ${bTot.toFixed(0)}`, `${a} vs ${b}`)}
      </div>

      <h2 class="h2h-log-title">Every Meeting</h2>
      <div class="table-wrapper">
        <table class="roster-table h2h-table">
          <thead><tr><th>Season</th><th>Week</th><th>${a}</th><th>${b}</th><th>Result</th></tr></thead>
          <tbody>
            ${meetings.map(m => {
              const aWon = m.aPts > m.bPts, tie = m.aPts === m.bPts;
              const res = tie ? 'T' : (aWon ? a : b);
              return `<tr>
                <td>${m.season}</td>
                <td>${m.playoff ? `<span class="po-badge">PO</span> ` : ''}${m.week}</td>
                <td class="${aWon ? 'result-win' : ''}">${m.aPts.toFixed(1)}</td>
                <td class="${!aWon && !tie ? 'result-win' : ''}">${m.bPts.toFixed(1)}</td>
                <td>${res}</td>
              </tr>`;
            }).join('')}
          </tbody>
        </table>
      </div>
    `;
  }

  function avg(total, n) { return n ? (total / n).toFixed(1) : '0.0'; }
  function seasonWeek(m) { return `${m.season} Wk ${m.week}${m.playoff ? ' (PO)' : ''}`; }
  function factCard(label, value, detail) {
    return `<div class="record-card">
      <div class="record-title">${label}</div>
      <div class="record-value">${value}</div>
      <div class="record-detail">${detail}</div>
    </div>`;
  }
})();
