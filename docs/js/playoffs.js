const PLAYOFF_TEAMS = 8;
const LEAGUE_TEAMS = 16;
const REGULAR_SEASON_WEEKS = 14;
const CHAMPIONSHIP_WEEK = 17;
const QUARTERFINALS = [[0, 7], [3, 4], [1, 6], [2, 5]];
const TRIALS = 10_000;
const LEAGUE_AVERAGE_WEIGHT = 11;
const TEAM_STRENGTH_SD = 660;
const MIN_LIVE_SD = 300;
const SNAPSHOT_URL = 'https://raw.githubusercontent.com/mpg000f/free-chee-rankings/main/yahoo_data/playoff_snapshot.json';
const CHAMPIONSHIP_SNAPSHOT_URL = new URL('championship_snapshot.json', SNAPSHOT_URL);
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
    return { a, b, id, week: game.week, live, optimized: game.optimized, yahoo: game.yahoo };
  });
  if (teams.length !== LEAGUE_TEAMS || teams.some(team => team.weeks.size !== REGULAR_SEASON_WEEKS)) {
    throw new Error('Incomplete regular-season schedule');
  }
  return { season, teams, games, lastCompleted: completed.at(-1)?.week,
    postseason: (data.postseason ?? data.games).filter(game => Number(game.season) === season &&
      game.playoff && game.week > REGULAR_SEASON_WEEKS),
    playoffProjections: data.playoffProjections ?? {} };
}

// A fixed seed keeps comparisons and resets reproducible.
function randomSource(seed) {
  return () => {
    seed = (Math.imul(1664525, seed) + 1013904223) >>> 0;
    return (seed + .5) / 4294967296;
  };
}

function scoringModel(teams, leagueAverageWeight) {
  const gameCount = teams.reduce((n, team) => n + team.scores.length, 0);
  const leagueAverage = teams.reduce((pf, team) => pf + team.points, 0) / gameCount;
  const means = teams.map(team => (team.points + leagueAverage * leagueAverageWeight) /
    (team.scores.length + leagueAverageWeight));
  const residuals = teams.reduce((sum, team) => {
    const average = team.points / team.scores.length;
    return sum + team.scores.reduce((total, score) => total + (score - average) ** 2, 0);
  }, 0);
  const deviation = Math.max(1000, Math.sqrt(residuals / Math.max(1, gameCount - teams.length)));
  function scoreParameters(id, projection, actual, remaining) {
    const mean = Number.isFinite(projection) ? toCents(projection) : means[id];
    const floor = Number.isFinite(actual) ? toCents(actual) : null;
    if (floor === null) return { center: mean, spread: deviation, floor };
    if (remaining === false) return { center: floor, spread: 0, floor };
    const center = Math.max(floor + (remaining === true ? 200 : 0), mean);
    const share = Math.min(1, (center - floor) / Math.max(1, center));
    const spread = Math.max(remaining === true ? MIN_LIVE_SD : 0, deviation * Math.sqrt(share));
    return { center, spread, floor };
  }
  return scoreParameters;
}

function normalDraw(random) {
  const radius = Math.sqrt(-2 * Math.log(random()));
  const angle = 2 * Math.PI * random();
  return [radius * Math.cos(angle), radius * Math.sin(angle)];
}

function drawScore({ center, spread, floor }, normal, shift = 0) {
  const score = Math.round(center + shift + spread * normal);
  return floor === null ? score : Math.max(floor, score);
}

export function matchupProjections({ live, optimized, yahoo }) {
  const optimizedScores = [optimized?.p1, optimized?.p2];
  if (optimizedScores.every(Number.isFinite)) return { values: optimizedScores, source: 'Optimized lineup' };
  const yahooScores = [live?.projected1 ?? yahoo?.p1, live?.projected2 ?? yahoo?.p2];
  if (yahooScores.every(Number.isFinite)) return { values: yahooScores, source: 'Yahoo lineup' };
  return { values: [null, null], source: 'Historical scoring' };
}

function makeSamples(games, scoreParameters, offsets) {
  const random = randomSource(20261125);
  return games.map(game => {
    const { a, b, live, optimized } = game;
    const { values } = matchupProjections(game);
    const parameters = [a, b].map((id, side) => {
      const projection = offsets ? values[side] : optimized?.[`p${side + 1}`] ?? live?.[`projected${side + 1}`];
      const params = scoreParameters(id, projection, live?.[`p${side + 1}`],
        offsets ? live?.[`remaining${side + 1}`] ?? (live ? true : undefined) : undefined);
      const shared = offsets ? Math.min(TEAM_STRENGTH_SD, params.spread * .6) : 0;
      return { ...params, shared, spread: Math.sqrt(params.spread ** 2 - shared ** 2) };
    });
    const sampleGame = trial => normalDraw(random).map((normal, side) => {
      const params = parameters[side];
      const shift = offsets ? params.shared * offsets[trial][side === 0 ? a : b] : 0;
      return drawScore(params, normal, shift);
    });
    const open = [], first = [], second = [];
    const sums = [[0, 0], [0, 0]];
    const wins = [0, 0];
    for (let i = 0; i < TRIALS; i++) {
      const draw = sampleGame(i);
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
        while (direction * (pair[0] - pair[1]) <= 0 && attempts++ < 48) pair = sampleGame(i);
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

function championshipSimulator(teams, postseason, playoffProjections, scoreParameters) {
  const index = new Map(teams.map(({ owner }, id) => [owner, id]));
  const matchupKey = (a, b) => Math.min(a, b) * teams.length + Math.max(a, b);
  const rounds = [];
  const random = randomSource(20261215);
  for (let week = REGULAR_SEASON_WEEKS + 1; week <= CHAMPIONSHIP_WEEK; week++) {
    const games = new Map();
    const active = new Map();
    for (const game of postseason.filter(game => game.week === week)) {
      const [a, b] = [index.get(game.o1), index.get(game.o2)];
      if (a === undefined || b === undefined) continue;
      if (Number.isFinite(game.p1) && Number.isFinite(game.p2)) {
        const winner = game.winner === 1 || (game.winner == null && game.p1 > game.p2) ? a :
          game.winner === 2 || (game.winner == null && game.p2 > game.p1) ? b : null;
        games.set(matchupKey(a, b), winner);
      }
      for (const [side, id] of [a, b].entries()) {
        if (game.live) active.set(id, { points: game.live[`p${side + 1}`], projection: game.live[`projected${side + 1}`] });
        else if (game.optimized) active.set(id, { projection: game.optimized[`p${side + 1}`] });
      }
    }
    const draws = teams.map(({ owner }, id) => {
      const live = active.get(id);
      const parameters = scoreParameters(id, playoffProjections[week]?.[owner] ?? live?.projection, live?.points);
      const scores = new Int32Array(TRIALS);
      for (let trial = 0; trial < TRIALS; trial += 2) {
        const normals = normalDraw(random);
        scores[trial] = drawScore(parameters, normals[0]);
        scores[trial + 1] = drawScore(parameters, normals[1]);
      }
      return scores;
    });
    rounds.push({ games, draws });
  }
  function advance(round, a, b, trial) {
    const { games, draws } = rounds[round];
    // Callers supply the higher seed first, including after semifinal reseeding.
    const actual = games.get(matchupKey(a, b));
    return actual ?? (actual === null || draws[a][trial] >= draws[b][trial] ? a : b);
  }
  return function champion(order, trial) {
    const survivors = QUARTERFINALS.map(([a, b]) => advance(0, order[a], order[b], trial));
    survivors.sort((a, b) => order.indexOf(a) - order.indexOf(b));
    const finalists = [advance(1, survivors[0], survivors[3], trial), advance(1, survivors[1], survivors[2], trial)];
    finalists.sort((a, b) => order.indexOf(a) - order.indexOf(b));
    return advance(2, ...finalists, trial);
  };
}

export function createModel({ teams, games, postseason = [], playoffProjections = {} }, { weeklyBoard = false } = {}) {
  const scoreParameters = scoringModel(teams, weeklyBoard ? 4 : LEAGUE_AVERAGE_WEIGHT);
  const strengthRandom = randomSource(20261126);
  const offsets = weeklyBoard ? null : Array.from({ length: TRIALS }, () =>
    Array.from({ length: teams.length / 2 }, () => normalDraw(strengthRandom)).flat());
  const samples = makeSamples(games, scoreParameters, offsets);
  let champion;
  const teamIds = teams.map((_, i) => i);
  const initialWins = teams.map(team => 2 * team.wins + team.ties);
  const initialPoints = teams.map(team => team.points);
  const random = randomSource(114);
  const tiePriorities = Array.from({ length: TRIALS }, () => teams.map(random));

  function run(picks, { includeLeverage = true, includeTitles = true } = {}) {
    if (includeTitles) champion ??= championshipSimulator(teams, postseason, playoffProjections, scoreParameters);
    const titles = teams.map(() => 0);
    const finishes = teams.map(() => Array(teams.length).fill(0));
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
      for (let place = 0; place < order.length; place++) finishes[order[place]][place]++;

      if (includeTitles) titles[champion(order, trial)]++;
      if (!includeLeverage) continue;

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
    const qualifying = finishes.map(counts => counts.slice(0, PLAYOFF_TEAMS).reduce((sum, count) => sum + count, 0));
    const minWins = [...initialWins];
    const maxWins = [...initialWins];
    const ignoredPoints = teams.map(() => 0);
    for (const game of games) {
      const pick = picks[game.id];
      if (!pick) {
        maxWins[game.a] += 2;
        maxWins[game.b] += 2;
        continue;
      }
      const scores = Array.isArray(pick) ? pick : pick === 'first' ? [1, 0] : [0, 1];
      applyGame(minWins, ignoredPoints, game, scores);
      applyGame(maxWins, ignoredPoints, game, scores);
    }
    const guaranteed = teamIds.map(id =>
      teamIds.filter(other => other !== id && maxWins[other] >= minWins[id]).length < PLAYOFF_TEAMS ||
      teamIds.filter(other => minWins[other] > maxWins[id]).length >= PLAYOFF_TEAMS);
    return { standings, qualifying, leverage, finishes, titles, guaranteed };
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

function playoffPercent(count, guaranteed) {
  if (!guaranteed && count === 0) return '<0.1%';
  if (!guaranteed && count === TRIALS) return '>99.9%';
  return percent(count);
}

export function americanOdds(count) {
  if (count <= 0 || count >= TRIALS) return '—';
  if (count === TRIALS / 2) return '+100';
  const other = TRIALS - count;
  const magnitude = 100 * Math.max(count, other) / Math.min(count, other);
  return roundAmericanLine(count < other ? magnitude : -magnitude);
}

export function roundAmericanLine(line) {
  return `${line < 0 ? '−' : '+'}${Math.round(Math.abs(line) / 10) * 10}`;
}

export async function loadWeeklyTitleOdds() {
  const response = await fetch(CHAMPIONSHIP_SNAPSHOT_URL, { cache: 'no-store', signal: AbortSignal.timeout(6000) });
  if (!response.ok) throw new Error('Weekly championship snapshot unavailable');
  const schedule = seasonFromSchedule(await response.json());
  const { titles } = createModel(schedule, { weeklyBoard: true }).run([], { includeLeverage: false });
  return {
    season: schedule.season,
    lines: new Map(schedule.teams.map(({ owner }, id) => [owner, americanOdds(titles[id])])),
  };
}

const swing = (win, loss) => `${win > loss ? '+' : ''}${(100 * (win - loss) / TRIALS).toFixed(1)} pp`;
const score = value => Number.isFinite(value) ? value.toFixed(2) : '—';

export async function loadSchedule() {
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
        const postseason = new Map();
        for (const game of [...(published?.postseason ?? []), ...current.postseason]) {
          const key = `${game.week}:${[game.o1, game.o2].sort().join(':')}`;
          if (!Number.isFinite(postseason.get(key)?.p1) || Number.isFinite(game.p1)) postseason.set(key, game);
        }
        return { ...current, postseason: [...postseason.values()], asOf, lineupsAsOf: snapshot.value.lineupsAsOf };
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
    const [schedule, weeklyBoard] = await Promise.all([loadSchedule(), loadWeeklyTitleOdds().catch(() => null)]);
    const { season, teams, games, lastCompleted, asOf, lineupsAsOf } = schedule;
    const model = createModel(schedule);
    const matchups = get('playoff-matchups');
    const titleLines = weeklyBoard?.season === season ? weeklyBoard.lines : new Map();
    if (!titleLines.size) get('playoff-title-note').textContent = 'Weekly title lines are temporarily unavailable.';
    const teamSelect = get('playoff-team');
    const gameSelect = get('playoff-game');
    const personalGames = get('playoff-personal-games');
    const gameControls = [];
    let picks = Array(games.length).fill('');
    let lastPicks, result;
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
    if (lineupsAsOf && games.some(game => game.optimized)) {
      const timestamp = new Intl.DateTimeFormat('en-US', {
        timeZone: 'America/New_York', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short',
      }).format(new Date(lineupsAsOf));
      get('playoff-lineups').textContent = `Optimized lineups use Yahoo rosters pulled ${timestamp}.`;
    }
    if (!games.length) {
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
      for (const game of slate) {
        const { a, b, id, live } = game;
        const row = document.createElement('div');
        row.className = 'playoff-match';
        const [first, second] = [teams[a].owner, teams[b].owner].map(escapeHtml);
        const { values, source } = matchupProjections(game);
        const liveScore = `<p class="playoff-live-score">
          <strong>${source}</strong> ${values.every(Number.isFinite) ? `${score(values[0])}–${score(values[1])}` : ''}
          ${live ? `<span>Score so far ${score(live.p1)}–${score(live.p2)}</span>` : ''}
        </p>`;
        row.innerHTML = `<label>${first} vs. ${second}
          <select aria-label="Week ${week}, ${first} vs. ${second}" data-game="${id}">
            <option value="">Leave outcome open</option>
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
            <thead><tr><th scope="col">Team</th><th scope="col" class="playoff-scenario">Scenario odds</th><th scope="col">If win</th><th scope="col">If lose</th><th scope="col">Swing</th></tr></thead>
            <tbody>${[first, second].map((name, side) => `<tr>
              <th scope="row">${name}</th><td class="playoff-scenario" data-scenario="${side}"></td><td data-win="${side}"></td><td data-loss="${side}"></td>
              <td data-swing="${side}"></td>
            </tr>`).join('')}</tbody>
          </table>`;
        gameControls[id] = row.querySelector('select');
        details.append(row);
      }
      matchups.append(details);
    }

    teamSelect.innerHTML = option('', 'Choose your team') +
      teams.map(({ owner, name }, id) => option(id, `${owner} — ${name}`)).join('');

    function updateTeamView() {
      const selected = teamSelect.value !== '';
      const team = Number(teamSelect.value);
      const slate = selected ? games.filter(({ a, b }) => a === team || b === team) : [];
      const matchupLabel = ({ a, b, week }) => `Week ${week} vs. ${teams[a === team ? b : a].owner}`;
      get('playoff-personal-body').hidden = !selected;
      get('playoff-leverage').hidden = !slate.length;
      gameSelect.innerHTML = slate.map(game => option(game.id, matchupLabel(game))).join('');
      personalGames.innerHTML = slate.map(game => {
        const opponent = teams[game.a === team ? game.b : game.a].owner;
        const win = game.a === team ? 'first' : 'second';
        const loss = game.a === team ? 'second' : 'first';
        return `<label>${escapeHtml(matchupLabel(game))}
          <select data-personal-game="${game.id}">
            ${option('', 'Leave outcome open')}
            ${option(win, `${teams[team].owner} wins`)}
            ${option(loss, `${opponent} wins`)}
            <option value="scores" hidden disabled>Exact scores entered</option>
          </select></label>`;
      }).join('') || '<p class="playoff-note">No remaining games for this team.</p>';
    }

    function render() {
      const team = teamSelect.value === '' ? -1 : Number(teamSelect.value);
      const pickKey = JSON.stringify(picks);
      if (lastPicks !== pickKey) {
        result = model.run(picks, { includeTitles: false });
        lastPicks = pickKey;
        for (const detail of matchups.children) {
          const open = [...detail.querySelectorAll('select')].filter(select => !picks[Number(select.dataset.game)]).length;
          detail.querySelector('[data-week-count]').textContent = `${open} open`;
        }
        for (const select of gameControls) {
          const id = Number(select.dataset.game);
          const { win, loss } = result.leverage[id];
          const { a, b } = games[id];
          const row = select.closest('.playoff-match');
          for (const [side, teamId] of [a, b].entries()) {
            row.querySelector(`[data-scenario="${side}"]`).textContent = playoffPercent(result.qualifying[teamId], result.guaranteed[teamId]);
            row.querySelector(`[data-win="${side}"]`).textContent = playoffPercent(win[side], false);
            row.querySelector(`[data-loss="${side}"]`).textContent = playoffPercent(loss[side], false);
            row.querySelector(`[data-swing="${side}"]`).textContent = swing(win[side], loss[side]);
          }
        }
      }
      const { standings, qualifying, leverage, finishes, guaranteed } = result;
      if (team >= 0) {
        for (const select of personalGames.querySelectorAll('select')) {
          const pick = picks[Number(select.dataset.personalGame)];
          const exact = Array.isArray(pick);
          select.querySelector('option[value="scores"]').hidden = !exact;
          select.value = exact ? 'scores' : pick;
        }
        const mostLikely = Math.max(...finishes[team]);
        const places = finishes[team].flatMap((count, index) => count === mostLikely ? [`#${index + 1}`] : []);
        get('personal-playoff-odds').textContent = playoffPercent(qualifying[team], guaranteed[team]);
        get('personal-title-odds').textContent = titleLines.get(teams[team].owner) ?? '—';
        get('personal-finish').textContent = places.join(' or ');
        get('personal-finish-odds').textContent = `${percent(mostLikely)} of simulations${places.length > 1 ? ' each' : ''}`;
      }
      if (gameSelect.value !== '') {
        const focus = Number(gameSelect.value);
        const side = games[focus].a === team ? 0 : 1;
        const { win, loss } = leverage[focus];
        get('odds-win').textContent = playoffPercent(win[side], false);
        get('odds-loss').textContent = playoffPercent(loss[side], false);
        get('odds-swing').textContent = swing(win[side], loss[side]);
      }
      get('playoff-standings').innerHTML = standings.map(({ id, record: projected, pf }, index) => {
        const classes = [index < PLAYOFF_TEAMS ? 'playoff-qualified' : '',
          index === PLAYOFF_TEAMS - 1 ? 'playoff-cutoff' : '', id === team ? 'playoff-selected' : ''].join(' ');
        const { owner, name } = teams[id];
        return `<tr class="${classes}"><td>${index + 1}</td><th scope="row">${escapeHtml(owner)}<small>${escapeHtml(name)}</small></th>
          <td>${record(teams[id])}</td><td>${projected}</td><td>${pf.toFixed(2)}</td>
          <td>${escapeHtml(playoffPercent(qualifying[id], guaranteed[id]))}</td><td>${titleLines.get(owner) ?? '—'}</td></tr>`;
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
    personalGames.addEventListener('change', event => {
      const control = gameControls[Number(event.target.dataset.personalGame)];
      if (!control) return;
      clearTimeout(scoreTimer);
      control.value = event.target.value;
      updatePick(control);
      render();
    });
    get('playoff-reset').addEventListener('click', () => {
      clearTimeout(scoreTimer);
      picks = Array(games.length).fill('');
      for (const select of gameControls) select.value = '';
      for (const input of matchups.querySelectorAll('input')) input.value = '';
      for (const inputs of matchups.querySelectorAll('.playoff-score-inputs')) inputs.hidden = true;
      render();
    });
    teamSelect.addEventListener('change', () => { updateTeamView(); render(); });
    gameSelect.addEventListener('change', render);
    updateTeamView();
    render();
    content.hidden = false;
  } catch (error) {
    status.textContent = 'The playoff model could not load a complete league schedule.';
    console.error(error);
  }
}

if (typeof document !== 'undefined' && document.getElementById('playoff-content')) init();
