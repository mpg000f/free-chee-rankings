/**
 * Rosters page: season tabs, team dropdown, side-by-side week 1 vs final rosters.
 */
(function () {
  const SEASONS = ['2022', '2023', '2024', '2025'];
  const POS_ORDER = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF'];

  let data = null;
  let currentSeason = '2025';
  let currentTeamKey = '';

  // ===== INIT =====
  DataLoader.loadJSON('data/rosters_data.json').then(d => {
    data = d;
    buildSeasonTabs();
    selectSeason(currentSeason);
  }).catch(() => {
    document.getElementById('roster-content').innerHTML =
      '<p style="color:var(--red)">Error loading roster data.</p>';
  });

  // ===== SEASON TABS =====
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

  // ===== TEAM DROPDOWN =====
  function populateTeams() {
    const select = document.getElementById('team-select');
    select.innerHTML = '<option value="">Select a team...</option>';

    const seasonData = data[currentSeason];
    if (!seasonData) return;

    const teams = Object.entries(seasonData.teams)
      .map(([key, t]) => ({ key, name: t.team_name }))
      .sort((a, b) => a.name.localeCompare(b.name));

    teams.forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.key;
      opt.textContent = t.name;
      select.appendChild(opt);
    });

    select.addEventListener('change', () => {
      currentTeamKey = select.value;
      renderRosters();
    });

    // Auto-select first team
    if (teams.length) {
      select.value = teams[0].key;
      currentTeamKey = teams[0].key;
      renderRosters();
    }
  }

  // ===== RENDER =====
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

    container.innerHTML = `
      <div class="roster-panel">
        <h2>Opening Day Roster <span class="week-label">Week 1</span></h2>
        ${buildRosterTable(team.week1)}
      </div>
      <div class="roster-panel">
        <h2>Final Roster <span class="week-label">Week ${maxWeek}</span></h2>
        ${buildRosterTable(team.final)}
      </div>
    `;
  }

  function buildRosterTable(players) {
    if (!players || !players.length) {
      return '<p class="placeholder-text">No roster data available.</p>';
    }

    // Group by position, sorted by POS_ORDER then by points
    const grouped = {};
    POS_ORDER.forEach(pos => { grouped[pos] = []; });
    grouped['Other'] = [];

    players.forEach(p => {
      const bucket = POS_ORDER.includes(p.pos) ? p.pos : 'Other';
      grouped[bucket].push(p);
    });

    // Sort each group by points descending
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
