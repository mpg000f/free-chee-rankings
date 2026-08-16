/**
 * Season and owner controls shared by the Waiver Wire and Trade Grades pages.
 *
 * Both pages read the same data/transactions.json and slice it the same two
 * ways, so the tab strip, the owner select and the all-time fan-out live here
 * instead of twice. A page calls load() with a render function and then asks for
 * whichever list it cares about.
 */
(function () {
  const ALL_TIME = 'All-Time';

  let data = null;
  let seasons = [];
  let season = null;
  let owner = '';
  let redraw = null;

  function load(onChange) {
    redraw = onChange;
    return DataLoader.loadJSON('data/transactions.json').then(d => {
      data = d;
      seasons = d.seasons || [];
      season = seasons[seasons.length - 1] || ALL_TIME;
      buildTabs();
      buildOwners();
      redraw();
    }).catch(() => {
      document.querySelector('.page-container').innerHTML +=
        '<p style="color:var(--red)">Error loading transaction data.</p>';
    });
  }

  function buildTabs() {
    const mount = document.getElementById('season-toggle');
    if (!mount) return;
    mount.replaceChildren();
    [...seasons, ALL_TIME].forEach(s => {
      const btn = document.createElement('button');
      btn.className = 'season-btn' + (s === season ? ' active' : '');
      btn.textContent = s;
      btn.addEventListener('click', () => {
        season = s;
        owner = '';
        mount.querySelectorAll('.season-btn').forEach(b =>
          b.classList.toggle('active', b.textContent === s));
        buildOwners();
        redraw();
      });
      mount.appendChild(btn);
    });
  }

  function buildOwners() {
    const mount = document.getElementById('owner-filter');
    if (!mount) return;
    const owners = [...new Set(activeSeasons()
      .flatMap(s => (data.data[s] || {}).owners || []))].sort();
    mount.innerHTML =
      `<select id="owner-select" class="team-select">
        <option value="">All Owners</option>
        ${owners.map(o => `<option value="${o}">${o}</option>`).join('')}
      </select>`;
    document.getElementById('owner-select').addEventListener('change', e => {
      owner = e.target.value;
      redraw();
    });
  }

  /** Seasons feeding the current view — one, or all of them under All-Time. */
  function activeSeasons() {
    return season === ALL_TIME ? seasons : [season];
  }

  /** Rows of one kind across the active seasons, each tagged with its season. */
  function collect(key) {
    return activeSeasons().flatMap(s =>
      ((data.data[s] || {})[key] || []).map(row => ({ ...row, season: s })));
  }

  /** Replacement points per week by position, for the one selected season. */
  function replacement() {
    const active = activeSeasons();
    if (active.length !== 1) return null;
    return (data.data[active[0]] || {}).replacement || null;
  }

  window.TxnControls = {
    ALL_TIME,
    load,
    collect,
    replacement,
    activeSeasons,
    isAllTime: () => season === ALL_TIME,
    owner: () => owner,
  };
})();
