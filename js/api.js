async function askMufasa(payload) {
  const res = await fetch(`${CONFIG.API_BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return res.json();
}
