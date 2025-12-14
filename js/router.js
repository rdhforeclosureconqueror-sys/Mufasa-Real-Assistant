const views = document.querySelectorAll(".view");
const tabs = document.querySelectorAll(".top-nav button");

function showView(id) {
  views.forEach(v => v.classList.remove("active"));
  tabs.forEach(t => t.classList.remove("active"));
  const view = document.getElementById("view-" + id);
  const tab = document.querySelector(`[data-route="${id}"]`);
  if (view) view.classList.add("active");
  if (tab) tab.classList.add("active");
  history.replaceState(null, "", "#" + id);
}

tabs.forEach(btn =>
  btn.addEventListener("click", () => showView(btn.dataset.route))
);

window.addEventListener("load", () => {
  const hash = location.hash.replace("#", "") || "ask";
  showView(hash);
});
