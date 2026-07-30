/**
 * Schedule page: one owner's full slate for one season, week by week.
 *
 * Reads data/matchups_all.json (every game 2022-present, both sides + scores).
 * Playoff games are flagged but not labeled by round -- the source data has a
 * single boolean, and each playoff week runs a championship game alongside
 * consolation games with nothing to tell them apart.
 */
(async function () {
  const content = document.getElementById('schedule-content');
  const ownerSelect = document.getElementById('owner-select');
  const seasonToggle = document.getElementById('season-toggle');

  let games, owners, seasons;
  let season, owner;

  try {
    const data = await DataLoader.loadJSON('data/matchups_all.json');
    games = data.games;
    owners = data.owners.slice().sort();
    seasons = [...new Set(games.map(g => g.season))].sort();
  } catch (e) {
    content.innerHTML = '<p class="placeholder-text" style="color:var(--red)">Could not load schedule data.</p>';
    return;
  }

  season = seasons[seasons.length - 1];
  owner = owners[0];

  // ===== CONTROLS =====
  seasonToggle.innerHTML = seasons
    .map(s => `<button class="season-btn${s === season ? ' active' : ''}" data-season="${s}">${s}</button>`)
    .join('');
  ownerSelect.innerHTML = owners.map(o => `<option value="${o}">${o}</option>`).join('');
  ownerSelect.value = owner;

  seasonToggle.addEventListener('click', e => {
    const btn = e.target.closest('.season-btn');
    if (!btn) return;
    season = btn.dataset.season;
    seasonToggle.querySelectorAll('.season-btn').forEach(b => b.classList.toggle('active', b === btn));
    render();
  });
  ownerSelect.addEventListener('change', () => { owner = ownerSelect.value; render(); });

  // ===== DATA SHAPING =====
  /** One owner's games for one season, normalised to "me vs them" and sorted by week. */
  function slate() {
    return games
      .filter(g => g.season === season && (g.o1 === owner || g.o2 === owner))
      .map(g => {
        const home = g.o1 === owner;
        const mine = home ? g.p1 : g.p2;
        const theirs = home ? g.p2 : g.p1;
        return {
          week: g.week,
          playoff: !!g.playoff,
          round: g.round || '',
          myTeam: home ? g.t1 : g.t2,
          opp: home ? g.o2 : g.o1,
          oppTeam: home ? g.t2 : g.t1,
          mine, theirs,
          margin: mine - theirs,
          result: mine > theirs ? 'W' : mine < theirs ? 'L' : 'T',
        };
      })
      .sort((a, b) => a.week - b.week);
  }

  function tally(rows) {
    const t = { w: 0, l: 0, t: 0, pf: 0, pa: 0 };
    rows.forEach(r => {
      if (r.result === 'W') t.w++; else if (r.result === 'L') t.l++; else t.t++;
      t.pf += r.mine;
      t.pa += r.theirs;
    });
    return t;
  }

  const rec = t => `${t.w}-${t.l}${t.t ? '-' + t.t : ''}`;

  /** Final placing, read off the last placement game they played. */
  const PLACING = {
    'Championship': ['Champion', 'Runner-up'],
    '3rd Place Game': ['3rd place', '4th place'],
    '5th Place Game': ['5th place', '6th place'],
    '7th Place Game': ['7th place', '8th place'],
  };
  function finish(playoffRows) {
    const last = playoffRows[playoffRows.length - 1];
    const pair = last && PLACING[last.round];
    if (!pair) return '';
    return last.result === 'W' ? pair[0] : pair[1];
  }
  const num = n => n.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 });

  /** Team name the owner used that season — the one they carried for the most weeks. */
  function teamName(rows) {
    const counts = {};
    rows.forEach(r => { counts[r.myTeam] = (counts[r.myTeam] || 0) + 1; });
    return Object.keys(counts).sort((a, b) => counts[b] - counts[a])[0] || '';
  }

  // ===== RENDER =====
  function resultCell(r) {
    const sign = r.margin > 0 ? '+' : r.margin < 0 ? '−' : '';
    const cls = r.result === 'W' ? 'result-win' : r.result === 'L' ? 'result-loss' : '';
    return `<span class="sched-result ${cls}">${r.result}</span>
            <span class="sched-margin">${sign}${num(Math.abs(r.margin))}</span>`;
  }

  /** Bracket round chip; the title game gets the filled treatment. */
  function roundChip(r) {
    if (!r.round) return '';
    const cls = r.round === 'Championship' ? ' round-championship'
      : /Consolation|5th|7th/.test(r.round) ? ' round-minor' : '';
    return `<span class="sched-round${cls}">${r.round}</span>`;
  }

  function rowsHTML(rows) {
    return rows.map(r => `<tr>
      <td class="sched-week">${r.week}</td>
      <td class="sched-opp">
        <div class="sched-opp-top">
          <span class="sched-opp-name">${r.opp}</span>
          ${roundChip(r)}
        </div>
        <span class="sched-opp-team">${r.oppTeam}</span>
      </td>
      <td class="sched-score">${num(r.mine)} <span class="sched-dash">–</span> ${num(r.theirs)}</td>
      <td class="sched-verdict">${resultCell(r)}</td>
    </tr>`).join('');
  }

  function tableHTML(rows, playoffRows) {
    let body = rowsHTML(rows);
    if (playoffRows.length) {
      const weeks = playoffRows.map(r => r.week);
      const range = weeks.length > 1 ? `Weeks ${Math.min(...weeks)}–${Math.max(...weeks)}` : `Week ${weeks[0]}`;
      body += `<tr class="sched-divider"><td colspan="4">Playoffs <span class="muted">${range}</span></td></tr>`;
      body += rowsHTML(playoffRows);
    }
    return `<div class="table-wrapper">
      <table class="stats-table sched-table">
        <thead>
          <tr>
            <th>Wk</th>
            <th>Opponent</th>
            <th>Score</th>
            <th>Result</th>
          </tr>
        </thead>
        <tbody>${body}</tbody>
      </table>
    </div>`;
  }

  function formStrip(rows) {
    return `<div class="sched-form" aria-label="Results in order">` + rows.map(r =>
      `<span class="sched-pip pip-${r.result.toLowerCase()}${r.playoff ? ' pip-playoff' : ''}" title="${r.round || 'Week ' + r.week} vs ${r.opp}: ${r.result}">${r.result}</span>`
    ).join('') + `</div>`;
  }

  function render() {
    const all = slate();
    if (!all.length) {
      content.innerHTML = `<p class="placeholder-text">No games found for ${owner} in ${season}.</p>`;
      return;
    }

    const reg = all.filter(r => !r.playoff);
    const po = all.filter(r => r.playoff);
    const tReg = tally(reg), tPo = tally(po), tAll = tally(all);

    const madePlayoffs = po.length > 0;
    const summary = [
      `<div class="sched-stat"><div class="summary-label">Regular season</div><div class="summary-value">${rec(tReg)}</div></div>`,
      madePlayoffs
        ? `<div class="sched-stat"><div class="summary-label">Playoffs</div><div class="summary-value">${rec(tPo)}</div>
           ${finish(po) ? `<div class="summary-sub">${finish(po)}</div>` : ''}</div>`
        : `<div class="sched-stat"><div class="summary-label">Playoffs</div><div class="summary-value summary-small muted">Missed</div></div>`,
      `<div class="sched-stat"><div class="summary-label">Overall</div><div class="summary-value">${rec(tAll)}</div></div>`,
      `<div class="sched-stat"><div class="summary-label">Points for</div><div class="summary-value">${num(tAll.pf)}</div></div>`,
      `<div class="sched-stat"><div class="summary-label">Points against</div><div class="summary-value">${num(tAll.pa)}</div></div>`,
    ].join('');

    content.innerHTML = `
      <div class="sched-header">
        <div class="sched-identity">
          <div class="sched-owner">${owner}</div>
          <div class="sched-team">${teamName(all)} &middot; ${season}</div>
        </div>
        ${formStrip(all)}
      </div>
      <div class="sched-summary">${summary}</div>
      ${tableHTML(reg, po)}
    `;
  }

  render();
})();
