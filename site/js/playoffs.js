const PLAYOFF_TEAMS = 8;
const LEAGUE_TEAMS = 16;
const REGULAR_SEASON_WEEKS = 14;
const TRIALS = 10_000;
const LEAGUE_AVERAGE_WEIGHT = 4;
const SNAPSHOT_URL = 'https://raw.githubusercontent.com/mpg000f/free-chee-rankings/main/yahoo_data/playoff_snapshot.json';
const SNAPSHOT_MAX_AGE = 36 * 60 * 60 * 1000;
const toCents = score => Math.round(Number(score) * 100);
const record = ({ wins, losses, ties }) => ties ? `${wins}-${losses}-${ties}` : `${wins}-${losses}`;

export function seasonFromSchedule(data) {
  const season = Math.max(...[...data.games, ...data.upcoming].map(game => Number(game.season)));
  const regular = game => Number(game.season) === season && !game.playoff && game.week <= REGULAR_SEASON_WEEKS;
  const completed = data.games.filter(regular).sort((a, b) => a.week - b.week);
  const upcoming = data.upcoming.filter(regular).sort((a, b) => a.week - b.week);
  const byOwner = new Map();

  for (const game of completed) {
    const scores = [toCents(game.p1), toCents(game.p2)];
    for (const [side, owner] of [game.o1, game.o2].entries()) {
      const team = byOwner.get(owner) ?? { owner, scores: [], weeks: new Set(), wins: 0, losses: 0, ties: 0, points: 0 };
      if (team.weeks.has(game.week) || !Number.isFinite(scores[side])) throw new Error('Invalid completed matchup');
      team.name = side === 0 ? game.t1 : game.t2;
      team.weeks.add(game.week);
      team.scores.push(scores[side]);
      team.points += scores[side];
      const result = Math.sign(scores[side] - scores[1 - side]);
      team.wins += Number(result > 0);
      team.losses += Number(result < 0);
      team.ties += Number(result === 0);
      byOwner.set(owner, team);
    }
  }

  const teams = [...byOwner.values()].sort((a, b) => a.owner.localeCompare(b.owner));
  const teamIndex = new Map(teams.map((team, index) => [team.owner, index]));
  const games = upcoming.map((game, id) => {
    const [a, b] = [game.o1, game.o2].map(owner => teamIndex.get(owner));
    for (const team of [teams[a], teams[b]]) {
      if (!team || team.weeks.has(game.week)) throw new Error('Invalid remaining schedule');
      team.weeks.add(game.week);
    }
    const live = game.live;
    if (live && ![live.p1, live.p2].every(Number.isFinite)) throw new Error('Invalid live score');
    return { a, b, id, week: game.week, live };
  });
  if (teams.length !== LEAGUE_TEAMS || teams.some(team => team.weeks.size !== REGULAR_SEASON_WEEKS)) {
    throw new Error('Incomplete regular-season schedule');
  }
  return { season, teams, games, lastCompleted: completed.at(-1)?.week };
}

// A fixed seed keeps comparisons and resets reproducible.
function randomSource(seed) {
  return () => {
    seed = (Math.imul(1664525, seed) + 1013904223) >>> 0;
    return (seed + .5) / 4294967296;
  };
}

function makeSamples(teams, games) {
  const gameCount = teams.reduce((n, team) => n + team.scores.length, 0);
  const leagueAverage = teams.reduce((pf, team) => pf + team.points, 0) / gameCount;
  const means = teams.map(team => (team.points + leagueAverage * LEAGUE_AVERAGE_WEIGHT) /
    (team.scores.length + LEAGUE_AVERAGE_WEIGHT));
  const residuals = teams.reduce((sum, team) => {
    const average = team.points / team.scores.length;
    return sum + team.scores.reduce((total, score) => total + (score - average) ** 2, 0);
  }, 0);
  const deviation = Math.max(1000, Math.sqrt(residuals / Math.max(1, gameCount - teams.length)));
  const random = randomSource(20261125);
  return games.map(({ a, b, live }) => {
    const floor = live ? [toCents(live.p1), toCents(live.p2)] : null;
    const centers = [a, b].map((id, side) => {
      const projection = live?.[`projected${side + 1}`];
      const average = Number.isFinite(projection) ? toCents(projection) : means[id];
      return floor ? Math.max(floor[side], average) : average;
    });
    const spreads = centers.map((center, side) => {
      if (!floor) return deviation;
      const remaining = Math.max(0, center - floor[side]);
      const share = Math.min(1, remaining / Math.max(1, center));
      return deviation * Math.sqrt(share);
    });
    const sampleGame = () => {
      const radius = Math.sqrt(-2 * Math.log(random()));
      const angle = 2 * Math.PI * random();
      const scores = centers.map((center, side) =>
        Math.round(center + spreads[side] * radius * (side === 0 ? Math.cos(angle) : Math.sin(angle))));
      return floor ? scores.map((score, side) => Math.max(floor[side], score)) : scores;
    };
    const open = [], first = [], second = [];
    const sums = [[0, 0], [0, 0]];
    const wins = [0, 0];
    for (let i = 0; i < TRIALS; i++) {
      const draw = sampleGame();
      open.push(draw);
      const result = Math.sign(draw[0] - draw[1]);
      wins[0] += Number(result > 0);
      wins[1] += Number(result < 0);
      // Reuse the open draw when it already satisfies the pick. Otherwise,
      // resample this matchup only, preserving the scores associated with a win.
      for (const [side, pool] of [first, second].entries()) {
        const direction = side === 0 ? 1 : -1;
        let pair = draw;
        let attempts = 0;
        while (direction * (pair[0] - pair[1]) <= 0 && attempts++ < 48) pair = sampleGame();
        if (direction * (pair[0] - pair[1]) <= 0) {
          // Preserve points already scored when stress-testing an extreme upset.
          pair = [...pair];
          pair[side] = pair[1 - side] + 1;
        }
        pool.push(pair);
        sums[side][0] += pair[0];
        sums[side][1] += pair[1];
      }
    }
    return { open, first, second, favorite: wins[0] >= wins[1] ? 0 : 1,
      average: sums.map(pair => pair.map(score => Math.round(score / TRIALS))) };
  });
}

function applyGame(wins, points, { a, b }, scores, multiplier = 1) {
  const difference = Math.sign(scores[0] - scores[1]);
  wins[a] += (1 + difference) * multiplier;
  wins[b] += (1 - difference) * multiplier;
  points[a] += scores[0] * multiplier;
  points[b] += scores[1] * multiplier;
}

export function createModel({ teams, games }) {
  const samples = makeSamples(teams, games);
  const teamIds = teams.map((_, i) => i);
  const initialWins = teams.map(team => 2 * team.wins + team.ties);
  const initialPoints = teams.map(team => team.points);
  const random = randomSource(114);
  const tiePriorities = Array.from({ length: TRIALS }, () => teams.map(random));

  function run(picks) {
    const qualifying = teams.map(() => 0);
    const scenarioWins = [...initialWins];
    const scenarioPoints = [...initialPoints];
    const scenarioTies = teams.map(team => team.ties);
    const pools = games.map((game, idx) => {
      const pick = picks[idx];
      const sample = samples[idx];
      const fixed = Array.isArray(pick);
      const side = pick === 'first' ? 0 : pick === 'second' ? 1 : sample.favorite;
      const scenarioScore = fixed ? pick : sample.average[side];
      applyGame(scenarioWins, scenarioPoints, game, scenarioScore);
      if (scenarioScore[0] === scenarioScore[1]) {
        scenarioTies[game.a]++;
        scenarioTies[game.b]++;
      }
      if (fixed) return { fixed: pick };
      return { draws: sample[pick || 'open'] };
    });
    const projected = [...teamIds].sort((a, b) =>
      scenarioWins[b] - scenarioWins[a] || scenarioPoints[b] - scenarioPoints[a] || a - b);
    const standings = projected.map(id => {
      const ties = scenarioTies[id];
      const wins = (scenarioWins[id] - ties) / 2;
      const losses = REGULAR_SEASON_WEEKS - wins - ties;
      return { id, record: record({ wins, losses, ties }), pf: scenarioPoints[id] / 100 };
    });
    const leverage = games.map(() => ({ win: [0, 0], loss: [0, 0] }));

    for (let trial = 0; trial < TRIALS; trial++) {
      const wins = [...initialWins];
      const points = [...initialPoints];
      const priority = tiePriorities[trial];
      const compare = (a, b) => wins[b] - wins[a] || points[b] - points[a] || priority[a] - priority[b] || a - b;
      const chosenScore = pool => pool.fixed ?? pool.draws[trial];
      for (const game of games) applyGame(wins, points, game, chosenScore(pools[game.id]));
      const order = [...teamIds].sort(compare);
      for (const id of order.slice(0, PLAYOFF_TEAMS)) qualifying[id]++;

      for (const game of games) {
        const { a, b, id } = game;
        const selected = chosenScore(pools[id]);
        const { first, second } = samples[id];
        const { win, loss } = leverage[id];
        applyGame(wins, points, game, selected, -1);
        applyGame(wins, points, game, first[trial]);
        let aheadA = 0, aheadB = 0;
        for (const other of teamIds) {
          aheadA += Number(compare(other, a) < 0);
          aheadB += Number(compare(other, b) < 0);
        }
        win[0] += Number(aheadA < PLAYOFF_TEAMS);
        loss[1] += Number(aheadB < PLAYOFF_TEAMS);
        applyGame(wins, points, game, first[trial], -1);
        applyGame(wins, points, game, second[trial]);
        aheadA = 0;
        aheadB = 0;
        for (const other of teamIds) {
          aheadA += Number(compare(other, a) < 0);
          aheadB += Number(compare(other, b) < 0);
        }
        loss[0] += Number(aheadA < PLAYOFF_TEAMS);
        win[1] += Number(aheadB < PLAYOFF_TEAMS);
        applyGame(wins, points, game, second[trial], -1);
        applyGame(wins, points, game, selected);
      }
    }
    return { standings, qualifying, leverage };
  }
  return { run };
}

const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
const percent = count => {
  if (count > 0 && count / TRIALS < .001) return '<0.1%';
  if (count < TRIALS && count / TRIALS > .999) return '>99.9%';
  return `${(100 * count / TRIALS).toFixed(1)}%`;
};

const swing = (win, loss) => `${win > loss ? '+' : ''}${(100 * (win - loss) / TRIALS).toFixed(1)} pp`;
const score = value => Number.isFinite(value) ? value.toFixed(2) : '—';

async function loadSchedule() {
  const [base, snapshot] = await Promise.allSettled([
    DataLoader.loadJSON('data/matchups_all.json'),
    fetch(SNAPSHOT_URL, { cache: 'no-store', signal: AbortSignal.timeout(4500) }).then(response => {
      if (!response.ok) throw new Error('Scoreboard unavailable');
      return response.json();
    }),
  ]);
  let published;
  if (base.status === 'fulfilled') {
    try {
      published = seasonFromSchedule(base.value);
    } catch {
      // A valid scoreboard snapshot can supply the schedule on its own.
    }
  }
  if (snapshot.status === 'fulfilled') {
    try {
      const current = seasonFromSchedule(snapshot.value);
      const asOf = new Date(snapshot.value.asOf);
      if (Number.isFinite(asOf.getTime()) && (!published ||
        (current.season === published.season && current.games.length <= published.games.length))) {
        return { ...current, asOf };
      }
    } catch {
      // A missing or incomplete snapshot must not block the published schedule.
    }
  }
  if (!published) throw new Error('No complete schedule');
  return published;
}

async function init() {
  const get = id => document.getElementById(id);
  const status = get('playoff-season');
  const content = get('playoff-content');
  try {
    const { season, teams, games, lastCompleted, asOf } = await loadSchedule();
    const model = createModel({ teams, games });
    const matchups = get('playoff-matchups');
    const teamSelect = get('playoff-team');
    const gameSelect = get('playoff-game');
    let picks = Array(games.length).fill('');
    let lastPicks, result;
    const selectable = teams.map((_, id) => id).filter(id => games.some(game => game.a === id || game.b === id));
    const option = (value, label) => `<option value="${value}">${escapeHtml(label)}</option>`;

    status.textContent = games.length
      ? `${season} season · Week ${lastCompleted} results loaded · ${games.length} games remaining`
      : `${season} regular season complete`;
    const feedStatus = get('playoff-feed');
    if (asOf) {
      const timestamp = new Intl.DateTimeFormat('en-US', {
        timeZone: 'America/New_York', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short',
      }).format(asOf);
      feedStatus.textContent = `Yahoo scoreboard as of ${timestamp}${Date.now() - asOf > SNAPSHOT_MAX_AGE && games.length ? ' · refresh overdue' : ''}`;
    } else if (games.length) {
      feedStatus.textContent = 'Using the published schedule. No in-progress Yahoo snapshot is available.';
    }
    if (!games.length) {
      get('leverage-heading').closest('section').hidden = true;
      matchups.closest('section').hidden = true;
      content.classList.add('playoff-final');
      get('standings-heading').textContent = 'Final regular-season standings';
      get('playoff-table-note').textContent = 'The top eight advance to the playoffs.';
    }

    const weeks = [...new Set(games.map(game => game.week))];
    for (const week of weeks) {
      const slate = games.filter(game => game.week === week);
      const details = document.createElement('details');
      details.className = 'playoff-week';
      details.open = week === weeks[0];
      details.innerHTML = `<summary>Week ${week} <span class="playoff-note" data-week-count>${slate.length} open</span></summary>`;
      for (const { a, b, id, live } of slate) {
        const row = document.createElement('div');
        row.className = 'playoff-match';
        const [first, second] = [teams[a].owner, teams[b].owner].map(escapeHtml);
        const liveScore = live ? `<p class="playoff-live-score">
          <strong>In progress</strong> ${score(live.p1)}–${score(live.p2)}
          <span>Yahoo projected final ${score(live.projected1)}–${score(live.projected2)}</span>
        </p>` : '';
        row.innerHTML = `<label>${first} vs. ${second}
          <select aria-label="Week ${week}, ${first} vs. ${second}" data-game="${id}">
            <option value="">Simulate</option>
            ${option('first', `${teams[a].owner} wins`)}
            ${option('second', `${teams[b].owner} wins`)}
            <option value="scores">Enter both scores</option>
          </select></label>
          <div class="playoff-score-inputs" hidden>
            <label>${first} score<input aria-label="Week ${week} ${first} score" type="number" step=".01" inputmode="decimal"></label>
            <label>${second} score<input aria-label="Week ${week} ${second} score" type="number" step=".01" inputmode="decimal"></label>
          </div>
          ${liveScore}
          <table class="playoff-match-leverage" aria-label="Playoff leverage for ${first} and ${second}">
            <thead><tr><th scope="col">Team</th><th scope="col">If win</th><th scope="col">If lose</th><th scope="col">Swing</th></tr></thead>
            <tbody>${[first, second].map((name, side) => `<tr>
              <th scope="row">${name}</th><td data-win="${side}"></td><td data-loss="${side}"></td>
              <td data-swing="${side}"></td>
            </tr>`).join('')}</tbody>
          </table>`;
        details.append(row);
      }
      matchups.append(details);
    }

    teamSelect.innerHTML = selectable.map(id => option(id, `${teams[id].owner} — ${teams[id].name}`)).join('');
    function updateGameList() {
      const team = Number(teamSelect.value);
      gameSelect.innerHTML = games.filter(({ a, b }) => a === team || b === team).map(({ a, b, id, week }) =>
        option(id, `Week ${week} vs. ${teams[a === team ? b : a].owner}`)).join('');
    }

    function render() {
      const team = selectable.length ? Number(teamSelect.value) : -1;
      const pickKey = JSON.stringify(picks);
      if (lastPicks !== pickKey) {
        result = model.run(picks);
        lastPicks = pickKey;
        for (const detail of matchups.children) {
          const open = [...detail.querySelectorAll('select')].filter(select => !picks[Number(select.dataset.game)]).length;
          detail.querySelector('[data-week-count]').textContent = `${open} open`;
        }
        for (const select of matchups.querySelectorAll('select')) {
          const { win, loss } = result.leverage[Number(select.dataset.game)];
          const row = select.closest('.playoff-match');
          for (const side of [0, 1]) {
            row.querySelector(`[data-win="${side}"]`).textContent = percent(win[side]);
            row.querySelector(`[data-loss="${side}"]`).textContent = percent(loss[side]);
            row.querySelector(`[data-swing="${side}"]`).textContent = swing(win[side], loss[side]);
          }
        }
      }
      const { standings, qualifying, leverage } = result;
      if (games.length) {
        const focus = Number(gameSelect.value);
        const side = games[focus].a === team ? 0 : 1;
        const { win, loss } = leverage[focus];
        get('odds-win').textContent = percent(win[side]);
        get('odds-loss').textContent = percent(loss[side]);
        get('odds-swing').textContent = swing(win[side], loss[side]);
      }
      get('playoff-standings').innerHTML = standings.map(({ id, record: projected, pf }, index) => {
        const classes = [index < PLAYOFF_TEAMS ? 'playoff-qualified' : '',
          index === PLAYOFF_TEAMS - 1 ? 'playoff-cutoff' : '', id === team ? 'playoff-selected' : ''].join(' ');
        const { owner, name } = teams[id];
        return `<tr class="${classes}"><td>${index + 1}</td><th scope="row">${escapeHtml(owner)}<small>${escapeHtml(name)}</small></th>
          <td>${record(teams[id])}</td><td>${projected}</td><td>${pf.toFixed(2)}</td>
          <td>${escapeHtml(percent(qualifying[id]))}</td></tr>`;
      }).join('');
      get('playoff-bracket').innerHTML = [0, 3, 1, 2].map(seed => {
        const opponent = PLAYOFF_TEAMS - 1 - seed;
        return `<li><strong>${seed + 1}</strong> ${escapeHtml(teams[standings[seed].id].owner)} vs.
          <strong>${opponent + 1}</strong> ${escapeHtml(teams[standings[opponent].id].owner)}</li>`;
      }).join('');
    }

    function updatePick(target) {
      const row = target.closest('.playoff-match');
      if (!row) return;
      const select = row.querySelector('select');
      const scoreInputs = row.querySelector('.playoff-score-inputs');
      const useScores = select.value === 'scores';
      scoreInputs.hidden = !useScores;
      const inputs = [...scoreInputs.querySelectorAll('input')];
      picks[Number(select.dataset.game)] = useScores
        ? (inputs.every(input => input.validity.valid && Number.isSafeInteger(toCents(input.valueAsNumber)))
          ? inputs.map(input => toCents(input.valueAsNumber)) : '')
        : select.value;
    }

    let scoreTimer;
    matchups.addEventListener('change', event => {
      clearTimeout(scoreTimer);
      updatePick(event.target);
      render();
    });
    matchups.addEventListener('input', event => {
      if (!event.target.matches('input')) return;
      updatePick(event.target);
      clearTimeout(scoreTimer);
      scoreTimer = setTimeout(render, 180);
    });
    get('playoff-reset').addEventListener('click', () => {
      clearTimeout(scoreTimer);
      picks = Array(games.length).fill('');
      for (const select of matchups.querySelectorAll('select')) select.value = '';
      for (const input of matchups.querySelectorAll('input')) input.value = '';
      for (const inputs of matchups.querySelectorAll('.playoff-score-inputs')) inputs.hidden = true;
      render();
    });
    teamSelect.addEventListener('change', () => { updateGameList(); render(); });
    gameSelect.addEventListener('change', render);
    updateGameList();
    render();
    content.hidden = false;
  } catch (error) {
    status.textContent = 'The playoff model could not load a complete league schedule.';
    console.error(error);
  }
}

if (typeof document !== 'undefined') init();
