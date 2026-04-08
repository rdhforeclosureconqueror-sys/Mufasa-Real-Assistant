// API + portal definitions
const fallbackApiBase = "https://mufasa-real-assistant-api.onrender.com";
const isLocalhost = ["localhost", "127.0.0.1"].includes(window.location.hostname);

window.MUFASA_CFG = {
  API_BASE: isLocalhost ? window.location.origin : (window.MUFASA_API_BASE || fallbackApiBase),
  PORTALS: [
    { id: "maat", title: "Order of Ma’at", start: "What is the Order of Ma’at?" },
    { id: "decolonize", title: "Decolonize the Mind", start: "How do I know if my mind has been decolonized?" },
    { id: "melanin", title: "Melanin the Superpower", start: "What is melanin and how is it powerful?" },
    { id: "swahili", title: "Learn Swahili", start: "Teach me today’s Swahili lesson." },
    { id: "yoruba", title: "Learn Yoruba", start: "Teach me today’s Yoruba lesson." },
  ],
};
