document.querySelectorAll("nav button").forEach(btn =>
  btn.addEventListener("click", () => {
    const page = btn.dataset.page;
    if (page === "dashboard") renderDashboard();
    // Later: router for languages/journal
  })
);
