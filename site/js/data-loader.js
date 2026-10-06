/**
 * Data loader with in-memory cache.
 */
const DataLoader = (() => {
  const cache = {};
  // Stamped by stamp_cache_bust.py from the contents of data/. Without it the
  // browser keeps a stale data file for up to GitHub Pages' 10-minute TTL, so a
  // rebuilt week can keep rendering the previous version.
  const DATA_V = 'e02f7997db';

  function versioned(url) {
    return url.includes('?') ? `${url}&v=${DATA_V}` : `${url}?v=${DATA_V}`;
  }

  async function load(url) {
    if (cache[url]) return cache[url];
    const resp = await fetch(versioned(url));
    if (!resp.ok) throw new Error(`Failed to load ${url}: ${resp.status}`);
    const contentType = resp.headers.get('content-type') || '';
    let data;
    if (contentType.includes('json')) {
      data = await resp.json();
    } else {
      data = await resp.text();
    }
    cache[url] = data;
    return data;
  }

  return {
    loadJSON: (url) => load(url),
    loadHTML: (url) => load(url),
    getRankingsIndex: () => load('data/rankings.json'),
    getOwners: () => load('data/owners.json'),
    getWeekData: (weekId) => load(`data/${weekId}.json`),
    getWeekHTML: (weekId) => load(`data/${weekId}.html`),
    getLookback: () => load('data/lookback.json'),
    getLookbackHTML: () => load('data/lookback_content.html'),
    getRosters: () => load('data/rosters_data.json'),
    getDraftValue: () => load('data/draft_value.json'),
  };
})();
