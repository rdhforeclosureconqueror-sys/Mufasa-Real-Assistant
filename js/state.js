// Enhanced localStorage manager with per-portal memory
window.AppState = {
  // Save any data
  save(key, val) {
    localStorage.setItem(key, JSON.stringify(val));
  },
  // Load with default
  load(key, def) {
    try {
      const v = JSON.parse(localStorage.getItem(key));
      return v ?? def;
    } catch {
      return def;
    }
  },
  // Portal resume helpers
  savePortal(id, record) {
    const all = this.load("portals", {});
    all[id] = record;
    this.save("portals", all);
  },
  getPortal(id) {
    const all = this.load("portals", {});
    return all[id] || { lastQuestion: "", lastAnswer: "" };
  },
  getAllPortals() {
    return this.load("portals", {});
  },
  clearAll() {
    localStorage.clear();
  }
};
