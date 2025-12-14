function saveProgress(portal, code) {
  localStorage.setItem(`portal.${portal}.resume`, code);
}
function loadProgress(portal) {
  return localStorage.getItem(`portal.${portal}.resume`);
}
function saveNotes(portal, text) {
  localStorage.setItem(`portal.${portal}.notes`, text);
}
function loadNotes(portal) {
  return localStorage.getItem(`portal.${portal}.notes`) || "";
}
