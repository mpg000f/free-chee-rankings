/**
 * Lazily loads Chart.js from the CDN on first use, then caches the promise.
 * Keeps the ~200 KB library out of the initial (render-blocking) page load.
 * Usage: await window.loadChart();  // resolves once window.Chart exists
 */
window.loadChart = (function () {
  let pending = null;
  return function loadChart() {
    if (window.Chart) return Promise.resolve(window.Chart);
    if (pending) return pending;
    pending = new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js';
      s.onload = () => resolve(window.Chart);
      s.onerror = () => reject(new Error('Failed to load Chart.js'));
      document.head.appendChild(s);
    });
    return pending;
  };
})();
