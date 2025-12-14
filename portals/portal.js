export function importPortal(config) {
  const { portalId, title, defaultPrompt, askEndpoint } = config;
  const chatBox = document.getElementById("chat-container");
  const input = document.getElementById("user-input");
  const notes = document.getElementById("notes");
  const speakBtn = document.getElementById("speak-btn");
  const sendBtn = document.getElementById("send-btn");
  const ttsBtn = document.getElementById("tts-btn");
  const canvas = document.getElementById("art-canvas");
  const ctx = canvas.getContext("2d");

  const storageKey = `portal.${portalId}`;
  const imgDateKey = `${portalId}.lastImageDate`;

  // Load saved journal
  notes.value = localStorage.getItem(`${storageKey}.notes`) || "";
  notes.addEventListener("input", () => {
    localStorage.setItem(`${storageKey}.notes`, notes.value);
  });

  // Draw reveal
  async function revealImage(url) {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.src = url;
    await img.decode();
    const start = performance.now();
    const duration = 20000;
    function draw(now) {
      const progress = Math.min((now - start) / duration, 1);
      const radius = canvas.width * progress;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.save();
      ctx.beginPath();
      ctx.arc(canvas.width/2, canvas.height/2, radius, 0, 2*Math.PI);
      ctx.clip();
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      ctx.restore();
      if (progress < 1) requestAnimationFrame(draw);
    }
    requestAnimationFrame(draw);
  }

  // Add message
  function addMessage(text, cls="bot") {
    const div = document.createElement("div");
    div.className = `message ${cls}`;
    div.textContent = text;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  // TTS
  function speak(text) {
    const synth = window.speechSynthesis;
    const utter = new SpeechSynthesisUtterance(text);
    utter.voice = synth.getVoices().find(v => v.lang.startsWith("en"));
    utter.pitch = 1; utter.rate = 1;
    synth.speak(utter);
  }

  // STT
  const recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recog;
  if (recognition) {
    recog = new recognition();
    recog.lang = "en-US";
    recog.onresult = (e) => {
      input.value = e.results[0][0].transcript;
    };
  }
  speakBtn.onclick = () => recog && recog.start();

  // Send to API
  async function ask(prompt) {
    addMessage(prompt, "user");
    const systemPrompt = `
U-CORE:v1
MODE=UNPOLARIZED
BIND=${portalId}
OUTPUT=PHASED
RESUME_RULE=DAY1
END
    `;
    const q = `${systemPrompt}\n\n${prompt}`;
    const res = await fetch(askEndpoint, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ question: q })
    });
    const data = await res.json();
    const answer = data.answer || "No response.";
    addMessage(answer, "bot");
    speak(answer);

    // Image limit
    const today = new Date().toISOString().slice(0,10);
    const last = localStorage.getItem(imgDateKey);
    if (last !== today) {
      localStorage.setItem(imgDateKey, today);
      const imgPrompt = `Generate an image that represents this response: ${answer}`;
      const imgRes = await fetch(askEndpoint, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ question: imgPrompt })
      });
      const imgData = await imgRes.json();
      const imgUrl = imgData.answer.match(/https?:[^\s]+/i)?.[0];
      if (imgUrl) revealImage(imgUrl);
    }
  }

  sendBtn.onclick = () => {
    if (input.value.trim()) {
      ask(input.value.trim());
      input.value = "";
    }
  };
  ttsBtn.onclick = () => speak(chatBox.lastChild?.textContent || "");
  
  // Initial question
  if (!localStorage.getItem(`${storageKey}.started`)) {
    ask(defaultPrompt);
    localStorage.setItem(`${storageKey}.started`, "1");
  }
}
