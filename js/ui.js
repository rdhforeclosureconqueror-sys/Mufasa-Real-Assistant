const app = document.getElementById("app");

function speak(text) {
  const synth = window.speechSynthesis;
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = "en-US";
  synth.cancel();
  synth.speak(utter);
}

function renderDashboard() {
  app.innerHTML = `
    <h2>Choose a Portal</h2>
    <div id="portals">
      ${Object.values(CONFIG.PORTALS).map(p => `
        <div class="card">
          <h3>${p.title}</h3>
          <button onclick="openPortal('${p.id}')">Enter</button>
        </div>`).join("")}
    </div>
  `;
}

function openPortal(portalId) {
  const portal = CONFIG.PORTALS[portalId];
  const resume = loadProgress(portalId) || "START";
  app.innerHTML = `
    <div id="chat">
      <h2>${portal.title}</h2>
      <div id="messages"></div>
      <textarea id="input" placeholder="Type or press Continue..."></textarea>
      <button id="sendBtn">Send</button>
      <button id="contBtn">Continue</button>
      <button id="speakBtn">🔊 Read Aloud</button>
      <button id="shareBtn">📤 Share</button>
      <textarea id="notes" placeholder="Your notes...">${loadNotes(portalId)}</textarea>
    </div>
  `;

  const messages = document.getElementById("messages");
  const input = document.getElementById("input");

  async function send(msg) {
    messages.innerHTML += `<div class="chat-msg user">🧑 ${msg}</div>`;
    const data = await askMufasa({ question: msg, portal_id: portalId, resume_code: resume });
    messages.innerHTML += `<div class="chat-msg bot">🤖 ${data.answer}</div>`;
    saveProgress(portalId, data.next_resume_code || "");
    document.getElementById("notes").addEventListener("change", e => saveNotes(portalId, e.target.value));
  }

  document.getElementById("sendBtn").onclick = () => send(input.value);
  document.getElementById("contBtn").onclick = () => send("Continue");
  document.getElementById("speakBtn").onclick = () => speak(messages.innerText);
  document.getElementById("shareBtn").onclick = () => shareResponse(messages.innerText);
}

renderDashboard();
