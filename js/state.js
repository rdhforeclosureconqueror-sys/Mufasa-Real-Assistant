// localStorage helpers
window.AppState = {
  save(key, val) { localStorage.setItem(key, JSON.stringify(val)); },
  load(key, def) {
    try { return JSON.parse(localStorage.getItem(key)) ?? def; }
    catch { return def; }
  }
};
