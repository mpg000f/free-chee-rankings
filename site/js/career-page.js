/**
 * Per-owner shareable career page. Reads window.CAREER_OWNER (set inline in the
 * page) and renders that owner's profile using the shared renderer.
 */
(function () {
  const owner = window.CAREER_OWNER;
  const content = document.getElementById('career-content');

  DataLoader.loadJSON('data/careers.json').then(d => {
    const c = d.careers[owner];
    content.innerHTML = buildCareerProfile(c) +
      '<p class="career-share"><a href="careers.html">&larr; All owner careers</a></p>';
  }).catch(() => {
    content.innerHTML = '<p style="color:var(--red)">Error loading career data.</p>';
  });
})();
