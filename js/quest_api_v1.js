(function () {
  const API_BASE = window.location.origin;
  const TOKEN_KEY = "quest_v1_token";

  function token() {
    return localStorage.getItem(TOKEN_KEY) || "";
  }

  function saveToken(value) {
    if (value) {
      localStorage.setItem(TOKEN_KEY, value);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  }

  async function request(path, { method = "GET", body, auth = true, form = false } = {}) {
    const headers = {};
    if (!form) headers["Content-Type"] = "application/json";
    if (auth && token()) headers.Authorization = `Bearer ${token()}`;

    const res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: form ? body : (body ? JSON.stringify(body) : undefined),
    });

    const contentType = res.headers.get("content-type") || "";
    const payload = contentType.includes("application/json") ? await res.json() : await res.text();
    if (!res.ok) {
      const message = payload?.detail || payload || `Request failed (${res.status})`;
      throw new Error(typeof message === "string" ? message : JSON.stringify(message));
    }
    return payload;
  }

  const api = {
    token,
    saveToken,
    register: (data) => request("/api/v1/auth/register", { method: "POST", body: data, auth: false }),
    login: (email, password) => {
      const params = new URLSearchParams();
      params.append("username", email);
      params.append("password", password);
      return request("/api/v1/auth/login", { method: "POST", body: params, auth: false, form: true });
    },
    me: () => request("/api/v1/auth/me"),
    createOrg: (data) => request("/api/v1/orgs", { method: "POST", body: data }),
    members: (orgId) => request(`/api/v1/orgs/${orgId}/members`),
    createQuest: (data) => request("/api/v1/quests", { method: "POST", body: data }),
    createCheckpoint: (data) => request("/api/v1/quests/checkpoints", { method: "POST", body: data }),
    enroll: (data) => request("/api/v1/quests/enroll", { method: "POST", body: data }),
    checkin: (data) => request("/api/v1/checkins", { method: "POST", body: data }),
    progress: (questId) => request(`/api/v1/progress/${questId}`),
    leaderboard: (questId) => request(`/api/v1/leaderboard/${questId}`),
    report: (questId) => request(`/api/v1/reports/quest/${questId}`),
  };

  window.QuestApiV1 = api;
})();
