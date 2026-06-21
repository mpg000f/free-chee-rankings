/**
 * Careers: per-owner career profile from precomputed careers.json.
 */
(function () {
  let careers = {};
  let owners = [];
  const sel = document.getElementById('owner-select');
  const content = document.getElementById('career-content');

  DataLoader.loadJSON('data/careers.json').then(d => {
    careers = d.careers;
    owners = d.owners;
    sel.innerHTML = owners.map(o => `<option value="${o}">${o}</option>`).join('');
    sel.addEventListener('change', () => {
      history.replaceState(null, '', '#' + sel.value);
      render(sel.value);
    });
    const hash = decodeURIComponent(location.hash.slice(1));
    const start = owners.includes(hash) ? hash : owners[0];
    sel.value = start;
    render(start);
  }).catch(() => {
    content.innerHTML = '<p style="color:var(--red)">Error loading career data.</p>';
  });

  function render(owner) {
    const c = careers[owner];
    const share = c
      ? `<p class="career-share"><a href="career-${careerSlug(owner)}.html">&#128279; Shareable card for ${owner} &rarr;</a></p>`
      : '';
    content.innerHTML = buildCareerProfile(c) + share;
  }

  window.addEventListener('hashchange', () => {
    const hash = decodeURIComponent(location.hash.slice(1));
    if (owners.includes(hash) && sel.value !== hash) { sel.value = hash; render(hash); }
  });
})();
