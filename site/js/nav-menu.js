/**
 * Mobile nav menu.
 *
 * The nav bar holds 12 links and needs 1240px to lay them all out; below that
 * the strip scrolls horizontally and quietly hides most of the site (only four
 * links are reachable on a phone). Under that width the links collapse behind a
 * toggle instead, so every page is one tap away and nothing is off-screen.
 *
 * Markup: a .nav-toggle button and the .nav-links list, wired by id.
 */
(function () {
  const BAR_FITS_ABOVE = 1240;

  const toggle = document.getElementById('nav-toggle');
  const links = document.getElementById('nav-links');
  if (!toggle || !links) return;

  function setOpen(open) {
    links.classList.toggle('open', open);
    toggle.classList.toggle('open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
  }

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
    if (!links.contains(event.target) && !toggle.contains(event.target)) setOpen(false);
  });

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') setOpen(false);
  });

  // Rotating to landscape can cross back into the full bar; drop the open state
  // so the panel's styles don't linger on a layout that no longer uses them.
  window.addEventListener('resize', () => {
    if (window.innerWidth >= BAR_FITS_ABOVE) setOpen(false);
  });
})();
