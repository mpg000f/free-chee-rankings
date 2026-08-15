/**
 * Mobile affordances for wide stats tables.
 *
 * Drives the existing header-click sorting from a dropdown (so you never have to
 * reach a header that's scrolled offscreen) and keeps scroll-state classes on the
 * host so CSS can fade the right edge only while there's more table to reach.
 *
 * Markup:
 *   <div class="table-scroll table-pinned" id="...">
 *     <div class="table-toolbar"><div class="table-sort"></div>
 *       <span class="table-swipe-hint">Swipe &rarr;</span></div>
 *     <div class="table-wrapper"><table>...</table></div>
 *   </div>
 *
 * Call TableMobile.init(host) after the table's header listeners are wired.
 */
(function () {
  const ASC = '▲', DESC = '▼';

  function activeHeader(headers) {
    return headers.find(h => {
      const a = h.querySelector('.sort-arrow');
      return a && a.textContent.trim();
    });
  }

  function buildSortControl(host, table) {
    const mount = host.querySelector('.table-sort');
    const headers = [...table.querySelectorAll('th[data-sort]')];
    if (!mount || !headers.length) return;
    // Pages that re-render their header row re-init on every draw; start clean
    // so the control is replaced rather than stacked up.
    mount.replaceChildren();

    const label = document.createElement('span');
    label.className = 'table-sort-label';
    label.textContent = 'Sort';

    const select = document.createElement('select');
    select.className = 'table-sort-select';
    select.setAttribute('aria-label', 'Sort table by column');
    headers.forEach(th => {
      const opt = document.createElement('option');
      opt.value = th.dataset.sort;
      // headers carry a sort arrow and terse labels like "#1s"; prefer a spelled-out name
      opt.textContent = th.dataset.sortLabel ||
        th.textContent.replace(new RegExp('[' + ASC + DESC + ']', 'g'), '').trim();
      select.appendChild(opt);
    });

    const dir = document.createElement('button');
    dir.type = 'button';
    dir.className = 'table-sort-dir';

    function sync() {
      const th = activeHeader(headers);
      if (!th) return;
      select.value = th.dataset.sort;
      const asc = th.querySelector('.sort-arrow').textContent.trim() === ASC;
      dir.textContent = asc ? ASC : DESC;
      dir.setAttribute('aria-label',
        asc ? 'Sorted low to high, tap to reverse' : 'Sorted high to low, tap to reverse');
    }

    select.addEventListener('change', () => {
      const th = table.querySelector('th[data-sort="' + select.value + '"]');
      if (th) th.click();
      sync();
    });
    dir.addEventListener('click', () => {
      const th = activeHeader(headers);
      if (th) th.click();
      sync();
    });

    mount.append(label, select, dir);
    sync();
  }

  function trackScroll(host, table) {
    const scroller = host.querySelector('.table-wrapper');
    if (!scroller) return function () {};

    function update() {
      const max = scroller.scrollWidth - scroller.clientWidth;
      host.classList.toggle('has-overflow', max > 1);
      host.classList.toggle('can-scroll-right', max > 1 && scroller.scrollLeft < max - 1);
    }

    scroller.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    // watch the table, not the wrapper: rows arrive async and only the table's box grows
    if (window.ResizeObserver) new ResizeObserver(update).observe(table);
    update();
    return update;
  }

  window.TableMobile = {
    init(host) {
      if (typeof host === 'string') host = document.getElementById(host);
      if (!host) return function () {};
      const table = host.querySelector('table');
      if (!table) return function () {};
      buildSortControl(host, table);
      return trackScroll(host, table);
    }
  };
})();
