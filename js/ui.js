const portalBox = document.getElementById("portal-tabs");
const chatWin = document.getElementById("chat-window");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const micBtn = document.getElementById("mic-btn");
const canvas = document.getElementById("reveal-canvas");
const ctx = canvas.getContext("2d");

// ── build portal buttons ──
MUFASA_CFG.PORTALS.forEach(p => {
  const b = document.createElement("button");
  b.textContent = p.title;
  b.onclick = () => { userInput.value = p.start; sendBtn.click(); };
  portalBox.appendChild(b);
});

// ── append message ──
function addMsg(role, txt) {
  const div = document.createElement("div");
  div.className = "message " + role;
  div.textContent = txt;
  chatWin.appendChild(div);
  chatWin.scrollTop = chatWin.scrollHeight;
}

// ── speech synthesis ──
function speak(txt) {
  if (!window.speechSynthesis) return;
  const u = new SpeechSynthesisUtterance(txt);
  u.lang = "en-US";
  u.rate = 1;
  u.pitch = 1;
  window.speechSynthesis.speak(u);
  revealImage(txt); // trigger art reveal while speaking
}

// ── speech recognition ──
let recognition;
if ("webkitSpeechRecognition" in window) {
  recognition = new webkitSpeechRecognition();
  recognition.lang = "en-US";
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.onresult = e => {
    userInput.value = e.results[0][0].transcript;
    sendBtn.click();
  };
}
micBtn.onclick = () => recognition && recognition.start();

// ── AI-generated image reveal (local draw) ──
function revealImage(prompt) {
  // Placeholder: load from Unsplash AI-like endpoint
  const url = `https://source.unsplash.com/700x400/?${encodeURIComponent(prompt)}`;
  const img = new Image();
  img.crossOrigin = "anonymous";
  img.onload = () => {
    canvas.width = img.width;
    canvas.height = img.height;
    ctx.globalAlpha = 0;
    ctx.drawImage(img, 0, 0);
    let alpha = 0;
    const fade = setInterval(() => {
      alpha += 0.02;
      ctx.globalAlpha = alpha;
      ctx.drawImage(img, 0, 0);
      if (alpha >= 1) clearInterval(fade);
    }, 80);
  };
  img.src = url;
}

// ── send question ──
sendBtn.onclick = async () => {
  const q = userInput.value.trim();
  if (!q) return;
  addMsg("user", q);
  userInput.value = "";
  try {
    const ans = await askMufasa(q);
    addMsg("bot", ans);
    speak(ans);
  } catch (e) {
    addMsg("bot", "⚠️ Connection error.");
  }
};
