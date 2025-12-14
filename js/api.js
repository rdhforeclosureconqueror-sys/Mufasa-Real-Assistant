async function askMufasa(question) {
  const r = await fetch(`${MUFASA_CFG.API_BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!r.ok) throw new Error("API error");
  const data = await r.json();
  return data.answer || "(no response)";
}
