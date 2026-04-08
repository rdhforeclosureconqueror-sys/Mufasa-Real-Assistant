(function () {
  const api = window.QuestApiV1;
  const CATALOG_KEY = "quest_v1_local_catalog";

  const $ = (id) => document.getElementById(id);
  const els = {
    email: $("auth-email"), password: $("auth-password"), name: $("auth-name"), role: $("auth-role"),
    registerBtn: $("register-btn"), loginBtn: $("login-btn"), logoutBtn: $("logout-btn"), sessionStatus: $("session-status"),
    createOrgBtn: $("create-org-btn"), orgOut: $("org-output"), orgName: $("org-name"), orgSlug: $("org-slug"),
    createQuestBtn: $("create-quest-btn"), questOut: $("quest-output"), questOrgId: $("quest-org-id"), questTitle: $("quest-title"), questDescription: $("quest-description"), questOrder: $("quest-order"),
    addCpBtn: $("add-cp-btn"), cpQuestId: $("cp-quest-id"), cpTitle: $("cp-title"), cpPosition: $("cp-position"), cpQr: $("cp-qr"), cpPoints: $("cp-points"),
    loadQuestsBtn: $("load-quests-btn"), questsList: $("participant-quests"), questDetail: $("quest-detail"),
    enrollQuestId: $("enroll-quest-id"), enrollBtn: $("enroll-btn"),
    checkinQuestId: $("checkin-quest-id"), checkinQr: $("checkin-qr"), checkinBtn: $("checkin-btn"),
    metricsQuestId: $("metrics-quest-id"), loadMetricsBtn: $("load-metrics-btn"), progressOut: $("progress-output"), leaderboardOut: $("leaderboard-output"),
    reportQuestId: $("report-quest-id"), loadReportBtn: $("load-report-btn"), reportOut: $("report-output"),
    log: $("activity-log"),
  };

  let me = null;

  function catalog() {
    return JSON.parse(localStorage.getItem(CATALOG_KEY) || "[]");
  }

  function saveCatalog(list) {
    localStorage.setItem(CATALOG_KEY, JSON.stringify(list));
  }

  function addLog(message, isError = false) {
    const row = document.createElement("div");
    row.className = `log-entry${isError ? " error" : ""}`;
    row.textContent = `[${new Date().toISOString()}] ${message}`;
    els.log.prepend(row);
  }

  function upsertQuestLocal(quest) {
    const list = catalog();
    const idx = list.findIndex((x) => x.id === quest.id);
    if (idx >= 0) {
      list[idx] = quest;
    } else {
      list.push(quest);
    }
    saveCatalog(list);
  }

  function addCheckpointLocal(questId, checkpoint) {
    const list = catalog();
    const q = list.find((x) => x.id === questId);
    if (!q) return;
    q.checkpoints = q.checkpoints || [];
    q.checkpoints.push(checkpoint);
    q.checkpoints.sort((a, b) => a.position - b.position);
    saveCatalog(list);
  }

  function renderQuestList() {
    const list = catalog();
    els.questsList.innerHTML = "";
    if (!list.length) {
      els.questsList.innerHTML = "<p class='muted'>No quests in local pilot catalog yet. Partner should create one first from this UI.</p>";
      return;
    }
    for (const q of list) {
      const item = document.createElement("button");
      item.className = "quest-item";
      item.textContent = `#${q.id} · ${q.title} (${q.checkpoints?.length || 0} checkpoints)`;
      item.onclick = () => {
        const cps = (q.checkpoints || []).map((cp) => `${cp.position}. ${cp.title} [${cp.qr_code}] +${cp.points}`).join("\n") || "No checkpoints added yet.";
        els.questDetail.textContent = `Quest #${q.id}\nOrg #${q.org_id}\nTitle: ${q.title}\nDescription: ${q.description || "-"}\nOrder enforced: ${q.enforce_order}\n\nCheckpoint instructions:\n${cps}`;
        els.enrollQuestId.value = q.id;
        els.checkinQuestId.value = q.id;
        els.metricsQuestId.value = q.id;
        els.reportQuestId.value = q.id;
      };
      els.questsList.appendChild(item);
    }
  }

  async function refreshSession() {
    if (!api.token()) {
      me = null;
      els.sessionStatus.textContent = "Not authenticated.";
      return;
    }
    try {
      me = await api.me();
      els.sessionStatus.textContent = `Signed in: ${me.email} (${me.role})`;
    } catch (err) {
      api.saveToken("");
      me = null;
      els.sessionStatus.textContent = "Session invalid. Please sign in again.";
      addLog(`Session refresh failed: ${err.message}`, true);
    }
  }

  els.registerBtn.onclick = async () => {
    try {
      const payload = {
        email: els.email.value.trim(),
        password: els.password.value,
        full_name: els.name.value.trim(),
        role: els.role.value,
      };
      const out = await api.register(payload);
      api.saveToken(out.access_token);
      await refreshSession();
      addLog(`Registered ${payload.email}`);
    } catch (err) {
      addLog(`Register failed: ${err.message}`, true);
    }
  };

  els.loginBtn.onclick = async () => {
    try {
      const out = await api.login(els.email.value.trim(), els.password.value);
      api.saveToken(out.access_token);
      await refreshSession();
      addLog(`Logged in ${els.email.value.trim()}`);
    } catch (err) {
      addLog(`Login failed: ${err.message}`, true);
    }
  };

  els.logoutBtn.onclick = async () => {
    api.saveToken("");
    me = null;
    els.sessionStatus.textContent = "Not authenticated.";
    addLog("Logged out");
  };

  els.createOrgBtn.onclick = async () => {
    try {
      const out = await api.createOrg({ name: els.orgName.value.trim(), slug: els.orgSlug.value.trim() });
      els.orgOut.textContent = `Org created: #${out.id} ${out.name} (${out.slug})`;
      els.questOrgId.value = out.id;
      addLog(`Created org #${out.id}`);
    } catch (err) {
      addLog(`Create org failed: ${err.message}`, true);
    }
  };

  els.createQuestBtn.onclick = async () => {
    try {
      const payload = {
        org_id: Number(els.questOrgId.value),
        title: els.questTitle.value.trim(),
        description: els.questDescription.value.trim(),
        enforce_order: els.questOrder.checked,
      };
      const out = await api.createQuest(payload);
      const localQuest = { ...payload, id: out.id, checkpoints: [] };
      upsertQuestLocal(localQuest);
      renderQuestList();
      els.questOut.textContent = `Quest created: #${out.id} ${out.title}`;
      els.cpQuestId.value = out.id;
      addLog(`Created quest #${out.id}`);
    } catch (err) {
      addLog(`Create quest failed: ${err.message}`, true);
    }
  };

  els.addCpBtn.onclick = async () => {
    try {
      const payload = {
        quest_id: Number(els.cpQuestId.value),
        title: els.cpTitle.value.trim(),
        position: Number(els.cpPosition.value),
        qr_code: els.cpQr.value.trim(),
        points: Number(els.cpPoints.value),
      };
      const out = await api.createCheckpoint(payload);
      addCheckpointLocal(payload.quest_id, payload);
      renderQuestList();
      addLog(`Added checkpoint #${out.id} to quest #${payload.quest_id}`);
    } catch (err) {
      addLog(`Add checkpoint failed: ${err.message}`, true);
    }
  };

  els.loadQuestsBtn.onclick = () => {
    renderQuestList();
    addLog("Loaded local pilot quest list");
  };

  els.enrollBtn.onclick = async () => {
    try {
      if (!me) throw new Error("Login required");
      const questId = Number(els.enrollQuestId.value);
      const out = await api.enroll({ quest_id: questId, user_id: me.id });
      addLog(`Enroll response for quest #${questId}: ${JSON.stringify(out)}`);
    } catch (err) {
      addLog(`Enroll failed: ${err.message}`, true);
    }
  };

  els.checkinBtn.onclick = async () => {
    try {
      const payload = { quest_id: Number(els.checkinQuestId.value), qr_code: els.checkinQr.value.trim() };
      const out = await api.checkin(payload);
      addLog(`Check-in accepted for quest #${payload.quest_id}: ${JSON.stringify(out)}`);
    } catch (err) {
      addLog(`Check-in failed: ${err.message}`, true);
    }
  };

  els.loadMetricsBtn.onclick = async () => {
    try {
      const questId = Number(els.metricsQuestId.value);
      const [progress, leaderboard] = await Promise.all([api.progress(questId), api.leaderboard(questId)]);
      els.progressOut.textContent = JSON.stringify(progress, null, 2);
      els.leaderboardOut.textContent = JSON.stringify(leaderboard, null, 2);
      addLog(`Loaded progress and leaderboard for quest #${questId}`);
    } catch (err) {
      addLog(`Load metrics failed: ${err.message}`, true);
    }
  };

  els.loadReportBtn.onclick = async () => {
    try {
      const questId = Number(els.reportQuestId.value);
      const [report, leaderboard] = await Promise.all([api.report(questId), api.leaderboard(questId)]);
      els.reportOut.textContent = `${JSON.stringify(report, null, 2)}\n\nEnrolled participants (from leaderboard rows):\n${JSON.stringify(leaderboard, null, 2)}`;
      addLog(`Loaded report for quest #${questId}`);
    } catch (err) {
      addLog(`Load report failed: ${err.message}`, true);
    }
  };

  renderQuestList();
  refreshSession();
})();
