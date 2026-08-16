/**
 * Trade Grades page: a per-owner ledger and a card for every completed trade.
 *
 * Grades come from the build, which measures each player against a replacement
 * at his own position rather than on raw points — see build_transactions_data.py.
 */
(function () {
  TxnControls.load(render);

  function render() {
    const owner = TxnControls.owner();
    const trades = TxnControls.collect('trades');
    renderLedger(trades);
    renderReplacement();
    renderTrades(owner
      ? trades.filter(t => t.sides.some(s => s.owner === owner))
      : trades, owner);
  }

  // ---- Per-owner ledger --------------------------------------------------

  function renderLedger(trades) {
    const mount = document.getElementById('trade-ledger');
    const rows = new Map();
    trades.forEach(t => t.sides.forEach(s => {
      const row = rows.get(s.owner) ||
        { owner: s.owner, n: 0, value: 0, perWeek: 0, wins: 0 };
      row.n += 1;
      row.value += s.net;
      row.perWeek += s.net / t.weeks_remaining;
      if (s.net > 0.01) row.wins += 1;
      rows.set(s.owner, row);
    }));

    const list = [...rows.values()].sort((a, b) => b.value - a.value);
    if (!list.length) { mount.innerHTML = ''; return; }

    mount.innerHTML = `
      <table class="stats-table">
        <thead><tr>
          <th>Owner</th><th>Trades</th><th>Won</th>
          <th>Net Value</th><th>Per Week</th>
        </tr></thead>
        <tbody>${list.map(r => `
          <tr>
            <td class="owner-cell">${r.owner}</td>
            <td>${r.n}</td>
            <td>${r.wins}&ndash;${r.n - r.wins}</td>
            <td class="${r.value >= 0 ? 'value-pos' : 'value-neg'}">${
              (r.value >= 0 ? '+' : '') + r.value.toFixed(1)}</td>
            <td class="${r.perWeek >= 0 ? 'value-pos' : 'value-neg'}">${
              (r.perWeek >= 0 ? '+' : '') + (r.perWeek / r.n).toFixed(1)}</td>
          </tr>`).join('')}</tbody>
      </table>`;
    if (window.TableMobile) TableMobile.init(document.getElementById('ledger-scroll'));
  }

  /** The bar each position had to clear, shown when one season is in view. */
  function renderReplacement() {
    const mount = document.getElementById('replacement-line');
    const repl = TxnControls.replacement();
    if (!repl) {
      mount.innerHTML = '<p class="method-caveat">Pick a single season to see the ' +
        'replacement level each position was measured against.</p>';
      return;
    }
    const order = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF'].filter(p => repl[p] != null);
    mount.innerHTML = `<p>Replacement level in ${TxnControls.activeSeasons()[0]},
      in points per week: ${order.map(p =>
        `<span class="repl-chip"><span class="pos-badge pos-${p}">${p}</span> ${
          repl[p].toFixed(1)}</span>`).join(' ')}</p>`;
  }

  // ---- Trade cards -------------------------------------------------------

  function renderTrades(trades, owner) {
    const mount = document.getElementById('trade-list');
    trades = [...trades].sort((a, b) =>
      (b.season || '').localeCompare(a.season || '') || b.week - a.week);

    if (!trades.length) {
      mount.innerHTML = '<p class="placeholder-text">No trades on record for this filter.</p>';
      return;
    }

    mount.innerHTML = trades.map(t => `
      <div class="trade-card">
        <div class="trade-head">
          <span class="trade-date">${t.date}</span>
          <span class="trade-week">${t.preseason ? 'Preseason' : `Week ${t.week}`}</span>
          <span class="trade-window">${t.weeks_remaining} wk${
            t.weeks_remaining === 1 ? '' : 's'} left</span>
          ${t.teams > 2 ? `<span class="trade-tag">${t.teams}-team</span>` : ''}
          ${TxnControls.isAllTime() ? `<span class="season-badge">${t.season}</span>` : ''}
        </div>
        <div class="trade-sides">
          ${t.sides.map(s => renderSide(s, owner)).join('')}
        </div>
      </div>`).join('');
  }

  function renderSide(side, owner) {
    const highlight = owner && side.owner === owner ? ' is-filtered' : '';
    const lines = [
      ...side.received.map(p => line(p, 'in')),
      ...side.sent.map(p => line(p, 'out')),
    ].join('');
    return `
      <div class="trade-side${highlight}">
        <div class="trade-side-head">
          <span class="grade grade-${side.grade}">${side.grade}</span>
          <span class="trade-owner">${side.owner}</span>
          <span class="trade-net ${side.net >= 0 ? 'value-pos' : 'value-neg'}">${
            (side.net >= 0 ? '+' : '') + side.net.toFixed(1)}</span>
        </div>
        <ul class="trade-players">${lines || '<li class="trade-empty">&mdash;</li>'}</ul>
        <div class="trade-side-foot">got ${side.vor_in.toFixed(1)} &bull; gave ${
          side.vor_out.toFixed(1)} above replacement</div>
      </div>`;
  }

  function line(p, dir) {
    const to = dir === 'out' && p.to_owner ? ` <span class="trade-to">&rarr; ${p.to_owner}</span>` : '';
    return `<li class="trade-player ${dir}">
      <span class="io">${dir === 'in' ? '+' : '&minus;'}</span>
      <span class="trade-player-name">${p.player}${to}</span>
      <span class="pos-badge pos-${p.pos}">${p.pos}</span>
      <span class="trade-pts" title="${p.pts.toFixed(1)} points against ${
        p.repl.toFixed(1)} for a replacement ${p.pos}">${p.pts.toFixed(1)}</span>
      <span class="trade-vor ${p.vor > 0 ? 'value-pos' : 'value-flat'}">${
        p.vor > 0 ? '+' + p.vor.toFixed(0) : '0'}</span>
    </li>`;
  }
})();
