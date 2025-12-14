const tabs = document.querySelectorAll(".tab");
const frame = document.getElementById("portal-frame");

tabs.forEach(tab => {
  tab.addEventListener("click", () => {
    tabs.forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    const page = tab.getAttribute("data-page");
    
    // Smooth fade transition
    frame.style.opacity = 0;
    setTimeout(() => {
      frame.src = page;
      frame.onload = () => {
        frame.style.opacity = 1;
      };
    }, 300);
  });
});

// Optional: remember last open tab
const lastTab = localStorage.getItem("mufasa.lastTab");
if (lastTab) {
  const saved = [...tabs].find(t => t.getAttribute("data-page") === lastTab);
  if (saved) {
    saved.click();
  }
}
window.addEventListener("beforeunload", () => {
  const active = document.querySelector(".tab.active");
  if (active) localStorage.setItem("mufasa.lastTab", active.getAttribute("data-page"));
});
