/**
 * Rankings browser: week selector + content renderer
 */
(async function() {
  const index = await DataLoader.getRankingsIndex();

  const seasonToggle = document.getElementById('season-toggle');
  const weekPills = document.getElementById('week-pills');
  const graphicPanel = document.getElementById('ranking-graphic');
  const articlePanel = document.getElementById('rankings-article');

  let currentSeason = '2025';
  let currentWeekId = null;

  // Build season buttons
  function renderSeasons() {
    seasonToggle.innerHTML = index.seasons.map(s =>
      `<button class="season-btn ${s === currentSeason ? 'active' : ''}" data-season="${s}">${s}</button>`
    ).join('');
  }

  // Build week pills for current season
  function renderWeekPills() {
    const weeks = index.weeks.filter(w => w.season === currentSeason);
    weekPills.innerHTML = weeks.map(w =>
      `<button class="week-pill ${w.week_id === currentWeekId ? 'active' : ''}" data-week="${w.week_id}">${w.label}</button>`
    ).join('');
  }

  // Build the ranking graphic sidebar
  function renderGraphic(weekData) {
    if (!weekData || !weekData.teams) {
      graphicPanel.innerHTML = '';
      return;
    }
    graphicPanel.innerHTML = weekData.teams.map(t => {
      let tierClass = '';
      if (t.rank <= 4) tierClass = 'tier-1';
      else if (t.rank <= 8) tierClass = 'tier-2';
      else if (t.rank <= 12) tierClass = 'tier-3';
      else tierClass = 'tier-4';

      let movement = '';
      if (t.movement !== null && t.movement !== undefined) {
        const diff = t.movement;
        if (diff > 0) movement = `<span class="movement up">&#9650;${diff}</span>`;
        else if (diff < 0) movement = `<span class="movement down">&#9660;${Math.abs(diff)}</span>`;
        else movement = `<span class="movement same">&#8212;</span>`;
      }

      return `<div class="ranking-graphic-card ${tierClass}" data-rank="${t.rank}" data-target="${weekData.week_id}-rank-${t.rank}">
        <span class="rank-num">${t.rank}</span>
        <span class="team-label">${t.team_name}<br><span class="owner-label">${t.owner}</span></span>
        ${movement}
      </div>`;
    }).join('');
  }

  // Load and render a week
  async function loadWeek(weekId) {
    currentWeekId = weekId;
    renderWeekPills();

    // Update URL hash
    history.replaceState(null, '', '#' + weekId);

    // Show loading
    articlePanel.innerHTML = '<div class="loading"><div class="spinner"></div>Loading...</div>';

    try {
      const [weekData, weekHTML] = await Promise.all([
        DataLoader.getWeekData(weekId),
        DataLoader.getWeekHTML(weekId),
      ]);

      renderGraphic(weekData);

      // Build the PDF download link
      const pdfName = weekData.title || weekId;
      const downloadBtn = `<a href="pdfs/${weekData.week_id}.pdf" class="download-btn" style="display:none">&#128196; Download PDF</a>`;

      articlePanel.innerHTML = weekHTML + downloadBtn;

      // Execute any inline <script> tags (e.g. Chart.js charts)
      articlePanel.querySelectorAll('script').forEach(oldScript => {
        const newScript = document.createElement('script');
        newScript.textContent = oldScript.textContent;
        oldScript.parentNode.replaceChild(newScript, oldScript);
      });

      // Mobile: setup accordion behavior
      setupAccordion();
    } catch (err) {
      articlePanel.innerHTML = `<p style="color:var(--red)">Error loading week: ${err.message}</p>`;
    }
  }

  // Mobile accordion for team cards
  function setupAccordion() {
    if (window.innerWidth > 768) return;
    document.querySelectorAll('.team-card .team-header').forEach(header => {
      header.addEventListener('click', () => {
        header.parentElement.classList.toggle('expanded');
      });
    });
  }

  // Event: season toggle
  seasonToggle.addEventListener('click', e => {
    const btn = e.target.closest('.season-btn');
    if (!btn) return;
    currentSeason = btn.dataset.season;
    renderSeasons();
    // Load first week of new season
    const weeks = index.weeks.filter(w => w.season === currentSeason);
    if (weeks.length) loadWeek(weeks[0].week_id);
  });

  // Event: week pill click
  weekPills.addEventListener('click', e => {
    const pill = e.target.closest('.week-pill');
    if (!pill) return;
    loadWeek(pill.dataset.week);
  });

  // Event: graphic card click -> scroll to team
  graphicPanel.addEventListener('click', e => {
    const card = e.target.closest('.ranking-graphic-card');
    if (!card) return;
    const target = card.dataset.target;
    const el = document.getElementById(target);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      // On mobile, expand it
      if (window.innerWidth <= 768) {
        el.classList.add('expanded');
      }
      // Highlight briefly
      el.style.borderColor = 'var(--accent)';
      setTimeout(() => { el.style.borderColor = ''; }, 1500);
    }
  });

  // Initialize
  renderSeasons();

  // Check URL hash for deep link
  const hash = window.location.hash.slice(1);
  if (hash) {
    // Find the week
    const week = index.weeks.find(w => w.week_id === hash);
    if (week) {
      currentSeason = week.season;
      renderSeasons();
      loadWeek(hash);
    } else {
      // Default to most recent
      const weeks = index.weeks.filter(w => w.season === currentSeason);
      if (weeks.length) loadWeek(weeks[weeks.length - 1].week_id);
    }
  } else {
    // Default: load most recent week of current season
    const weeks = index.weeks.filter(w => w.season === currentSeason);
    if (weeks.length) loadWeek(weeks[weeks.length - 1].week_id);
  }
})();
