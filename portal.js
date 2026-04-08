/* ================================================================
   MUFASA PORTAL JS — Bright Royal Edition
   Handles chat logic, AI fetch, journal, TTS, STT, and progress
   ================================================================ */

// 🌍 API base (edit if deployed elsewhere)
const API_BASE = window.MUFASA_CFG?.API_BASE || window.location.origin;

// 🦁 Elements
const portalSelector = document.getElementById("portal-selector");
const chatWindow = document.getElementById("chat-window");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const speakBtn = document.getElementById("speak-btn");
const journalInput = document.getElementById("journal-input");
const saveJournalBtn = document.getElementById("save-journal-btn");
const progressFill = document.getElementById("progress-fill");
const progressText = document.getElementById("progress-text");
const calendar = document.getElementById("calendar");


// 🧠 Persistent memory (localStorage)
let currentPortal = localStorage.getItem("mufasa_portal") || "";
let currentDay = parseInt(localStorage.getItem("mufasa_day") || "1");
let journals = JSON.parse(localStorage.getItem("mufasa_journals") || "{}");

// 🎙️ Voice setup
const synth = window.speechSynthesis;
let recognition;
if ("webkitSpeechRecognition" in window) {
  recognition = new webkitSpeechRecognition();
  recognition.continuous = false;
  recognition.lang = "en-US";
}

// 🔊 Text-to-Speech function (silent by default toggleable later)
function speakText(text) {
  if (!text || !synth) return;
  const utter = new SpeechSynthesisUtterance(text);
  utter.voice = synth.getVoices().find(v => v.name.includes("Female")) || null;
  utter.rate = 1;
  utter.pitch = 1;
  synth.cancel();
  synth.speak(utter);
}

// 🗣️ Speech-to-Text listener
if (recognition) {
  speakBtn.addEventListener("click", () => {
    recognition.start();
  });

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    userInput.value = transcript;
  };
}

// 🪶 Display chat messages
function addMessage(text, sender = "user") {
  const msg = document.createElement("div");
  msg.className = `message ${sender}`;
  msg.textContent = text;
  chatWindow.appendChild(msg);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

// 🕊️ Send to backend
async function sendToAI(text) {
  if (!text.trim()) return;

  addMessage(text, "user");
  userInput.value = "";

  const payload = {
    question: `${currentPortal ? `[${currentPortal}] ` : ""}${text}`,
    user_id: "browser-client",
  };

  try {
   const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();

    const reply = data.answer || "(no reply)";
    addMessage(reply, "bot");
    speakText(reply); // 🎧 Mufasa speaks here

    // Mark progress and calendar
    updateProgress();
    markCalendar();
  } catch (err) {
    console.error(err);
    addMessage("⚠️ Error reaching AI service.", "bot");
  }
}

// ✉️ Send Button
sendBtn.addEventListener("click", () => {
  const text = userInput.value;
  sendToAI(text);
});

// 🔄 Portal change
portalSelector.addEventListener("change", (e) => {
  currentPortal = e.target.value;
  localStorage.setItem("mufasa_portal", currentPortal);
  chatWindow.innerHTML = "";
  addMessage(`You’ve entered the ${e.target.selectedOptions[0].text} portal.`, "bot");
});

// 📓 Journal save
saveJournalBtn.addEventListener("click", () => {
  const note = journalInput.value.trim();
  if (!note) return;
  const today = new Date().toISOString().split("T")[0];
  journals[today] = note;
  localStorage.setItem("mufasa_journals", JSON.stringify(journals));
  addMessage("📝 Journal saved.", "bot");
  journalInput.value = "";
});

// 📅 Calendar generator
function buildCalendar() {
  const now = new Date();
  const monthName = now.toLocaleString("default", { month: "long" });
  const year = now.getFullYear();

  const first = new Date(year, now.getMonth(), 1);
  const daysInMonth = new Date(year, now.getMonth() + 1, 0).getDate();

  let html = `<h4>${monthName} ${year}</h4><div class="cal-grid">`;
  for (let i = 1; i <= daysInMonth; i++) {
    const dayStr = `${year}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(i).padStart(2, "0")}`;
    const marked = journals[dayStr] ? "marked" : "";
    html += `<div class="day ${marked}">${i}</div>`;
  }
  html += "</div>";
  calendar.innerHTML = html;
}

// ✅ Mark current day
function markCalendar() {
  buildCalendar();
}

// 📈 Progress bar
function updateProgress() {
  currentDay = Math.min(currentDay + 1, 30);
  localStorage.setItem("mufasa_day", currentDay);
  const pct = (currentDay / 30) * 100;
  progressFill.style.width = `${pct}%`;
  progressText.textContent = `Day ${currentDay} of 30`;
}

// 🪩 Restore saved state
function initState() {
  if (currentPortal) {
    portalSelector.value = currentPortal;
    addMessage(`Resuming ${portalSelector.selectedOptions[0].text} portal.`, "bot");
  }
  buildCalendar();
  updateProgress();
}

initState();
window.addEventListener("load", () => {
  const introScreen = document.getElementById("intro-screen");
  const introVideo = document.getElementById("intro-video");
  const app = document.getElementById("app");

  function showApp() {
    console.log("Revealing app...");
    introScreen.style.display = "none"; // Hide intro completely
    app.classList.remove("hidden");     // Show main app
    app.style.opacity = 0;
    app.style.transition = "opacity 1s ease";
    setTimeout(() => (app.style.opacity = 1), 100); // Fade in
  }

  function endIntro() {
    introScreen.classList.add("fade-out");
    setTimeout(showApp, 1500); // Wait for fade-out animation
  }

  // Auto end after 6 seconds
  setTimeout(endIntro, 6000);

  // Also end when video ends (backup trigger)
  introVideo.addEventListener("ended", endIntro);
});
