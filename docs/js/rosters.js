/**
 * Rosters page: season tabs, team dropdown, season summary + side-by-side rosters.
 */
(function () {
  const SEASONS = ['2022', '2023', '2024', '2025'];
  const POS_ORDER = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF'];

  let data = null;
  let currentSeason = '2025';
  let currentTeamKey = '';

  DataLoader.loadJSON('data/rosters_data.json').then(d => {
    data = d;
    buildSeasonTabs();
    selectSeason(currentSeason);
  }).catch(() => {
    document.getElementById('roster-content').innerHTML =
      '<p style="color:var(--red)">Error loading roster data.</p>';
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
    document.querySelectorAll('#season-toggle .season-btn').forEach(btn => {
      btn.classList.toggle('active', btn.textContent === season);
    });
    populateTeams();
  }

  function populateTeams() {
    const select = document.getElementById('team-select');
    select.innerHTML = '<option value="">Select a team...</option>';

    const seasonData = data[currentSeason];
    if (!seasonData) return;

    const teams = Object.entries(seasonData.teams)
      .map(([key, t]) => ({ key, owner: t.owner }))
      .sort((a, b) => a.owner.localeCompare(b.owner));

    teams.forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.key;
      opt.textContent = t.owner;
      select.appendChild(opt);
    });

    // Remove old listener by replacing element
    const newSelect = select.cloneNode(true);
    select.parentNode.replaceChild(newSelect, select);
    newSelect.addEventListener('change', () => {
      currentTeamKey = newSelect.value;
      renderRosters();
    });

    if (teams.length) {
      newSelect.value = teams[0].key;
      currentTeamKey = teams[0].key;
      renderRosters();
    }
  }

  function renderRosters() {
    const container = document.getElementById('roster-content');
    const seasonData = data[currentSeason];
    if (!seasonData || !currentTeamKey) {
      container.innerHTML = '<p class="placeholder-text">Select a season and team to view rosters.</p>';
      return;
    }

    const team = seasonData.teams[currentTeamKey];
    if (!team) {
      container.innerHTML = '<p class="placeholder-text">Team not found.</p>';
      return;
    }

    const maxWeek = seasonData.max_week;
    const summaryHTML = buildSummaryCard(team);

    container.innerHTML = `
      ${summaryHTML}
      <div class="roster-panels">
        <div class="roster-panel">
          <h2>Opening Day Roster <span class="week-label">Week 1</span></h2>
          ${buildRosterTable(team.week1)}
        </div>
        <div class="roster-panel">
          <h2>Final Roster <span class="week-label">Week ${maxWeek}</span></h2>
          ${buildRosterTable(team.final)}
        </div>
      </div>
    `;
  }

  function buildSummaryCard(team) {
    const s = team.summary;
    if (!s || !s.wins && !s.losses) return '';

    const record = `${s.wins}-${s.losses}${s.ties ? `-${s.ties}` : ''}`;
    const finishClass = s.playoff_finish === 'Champion' ? 'finish-champ' :
                        s.playoff_finish === 'Championship Loss' ? 'finish-runner' :
                        s.playoff_finish.includes('Semi') ? 'finish-semi' : '';

    const lastGame = s.last_game_pts
      ? `${s.last_game_pts.toFixed(1)} - ${s.last_game_opp_pts.toFixed(1)} vs ${s.last_game_opp}`
      : '-';
    const lastResult = s.last_game_pts > s.last_game_opp_pts ? 'W' : s.last_game_pts < s.last_game_opp_pts ? 'L' : 'T';
    const resultClass = lastResult === 'W' ? 'result-win' : lastResult === 'L' ? 'result-loss' : '';

    return `
      <div class="season-summary">
        <div class="summary-team-name">${team.team_name}</div>
        <div class="summary-grid">
          <div class="summary-stat">
            <div class="summary-label">Record</div>
            <div class="summary-value">${record}</div>
            <div class="summary-sub">#${s.standing} in standings</div>
          </div>
          <div class="summary-stat">
            <div class="summary-label">Points For</div>
            <div class="summary-value">${s.pf.toFixed(1)}</div>
            <div class="summary-sub">#${s.pf_rank} in league</div>
          </div>
          <div class="summary-stat">
            <div class="summary-label">Points Against</div>
            <div class="summary-value">${s.pa.toFixed(1)}</div>
            <div class="summary-sub">#${s.pa_rank} in league</div>
          </div>
          <div class="summary-stat">
            <div class="summary-label">Playoff Finish</div>
            <div class="summary-value ${finishClass}">${s.playoff_finish}</div>
          </div>
          <div class="summary-stat">
            <div class="summary-label">Final Game</div>
            <div class="summary-value summary-small"><span class="${resultClass}">${lastResult}</span> ${lastGame}</div>
          </div>
        </div>
      </div>
    `;
  }

  function buildRosterTable(players) {
    if (!players || !players.length) {
      return '<p class="placeholder-text">No roster data available.</p>';
    }

    const grouped = {};
    POS_ORDER.forEach(pos => { grouped[pos] = []; });
    grouped['Other'] = [];

    players.forEach(p => {
      const bucket = POS_ORDER.includes(p.pos) ? p.pos : 'Other';
      grouped[bucket].push(p);
    });

    Object.values(grouped).forEach(arr => arr.sort((a, b) => b.pts - a.pts));

    let rows = '';
    for (const pos of [...POS_ORDER, 'Other']) {
      const group = grouped[pos];
      if (!group.length) continue;
      group.forEach(p => {
        const ptsClass = p.pts > 0 ? '' : ' dim';
        rows += `<tr>
          <td class="player-name">${p.name}</td>
          <td><span class="pos-badge pos-${p.pos}">${p.pos}</span></td>
          <td class="pts${ptsClass}">${p.pts.toFixed(1)}</td>
          <td class="pos-rank">${p.pos_rank || '-'}</td>
        </tr>`;
      });
    }

    return `<div class="table-wrapper">
      <table class="roster-table">
        <thead>
          <tr>
            <th>Player</th>
            <th>Pos</th>
            <th>Season Pts</th>
            <th>Pos Rank</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
  }
})();
