/**
 * Data loader with in-memory cache.
 */
const DataLoader = (() => {
  const cache = {};

  async function load(url) {
    if (cache[url]) return cache[url];
    const resp = await fetch(url);
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
  };
})();
