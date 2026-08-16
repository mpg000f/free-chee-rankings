/**
 * Mobile nav menu.
 *
 * Seven top-level items need 737px of measured width; below 900px they collapse
 * behind a toggle, the slack being cover against a font fallback laying out
 * wider than Inter. Before the toggle existed the strip scrolled sideways with
 * its scrollbar hidden, which left only four of twelve links reachable on a
 * phone and the rest of the site effectively invisible.
 *
 * Markup: a .nav-toggle button, the .nav-links list, and any number of
 * .nav-group items inside it, all wired by id.
 */
(function () {
  const BAR_FITS_ABOVE = 900;

  const toggle = document.getElementById('nav-toggle');
  const links = document.getElementById('nav-links');
  if (!toggle || !links) return;

  const groups = [...links.querySelectorAll('.nav-group')];

  function setOpen(open) {
    links.classList.toggle('open', open);
    toggle.classList.toggle('open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    if (!open) closeGroups();
  }

  function closeGroups(except) {
    groups.forEach(group => {
      if (group === except) return;
      group.classList.remove('open');
      const btn = group.querySelector('.nav-group-btn');
      if (btn) btn.setAttribute('aria-expanded', 'false');
    });
  }

  // Grouped items expand in place inside the mobile panel and drop down from
  // the wide bar; the class is the same, only the CSS differs.
  groups.forEach(group => {
    const btn = group.querySelector('.nav-group-btn');
    if (!btn) return;
    btn.addEventListener('click', event => {
      event.stopPropagation();
      const open = !group.classList.contains('open');
      closeGroups(group);
      group.classList.toggle('open', open);
      btn.setAttribute('aria-expanded', String(open));
    });
  });

  toggle.addEventListener('click', event => {
    event.stopPropagation();
    setOpen(!links.classList.contains('open'));
  });

  // Tapping a link navigates; close first so a same-page anchor doesn't leave
  // the panel covering what it just jumped to.
  links.addEventListener('click', event => {
    if (event.target.closest('a')) setOpen(false);
  });

  document.addEventListener('click', event => {
    if (links.contains(event.target) || toggle.contains(event.target)) return;
    setOpen(false);
    closeGroups();
  });

  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    setOpen(false);
    closeGroups();
  });

  // Rotating to landscape can cross back into the full bar; drop the open state
  // so the panel's styles don't linger on a layout that no longer uses them.
  window.addEventListener('resize', () => {
    if (window.innerWidth >= BAR_FITS_ABOVE) setOpen(false);
  });
})();
