/* Dark/light mod — tercih localStorage'da tutulur, iki sayfada da geçerli.
   Tema değişince "themechange" olayı yayınlanır (Chart.js yeniden çizimi için). */
(function () {
  const KEY = "tusmec-theme";
  const root = document.documentElement;

  function apply(theme) {
    root.setAttribute("data-theme", theme);
    const btn = document.getElementById("theme-toggle");
    if (btn) btn.textContent = theme === "light" ? "🌙 Koyu" : "☀️ Açık";
    window.dispatchEvent(new CustomEvent("themechange", { detail: theme }));
  }

  window.toggleTheme = function () {
    const next = root.getAttribute("data-theme") === "light" ? "dark" : "light";
    localStorage.setItem(KEY, next);
    apply(next);
  };

  document.addEventListener("DOMContentLoaded", () => {
    apply(localStorage.getItem(KEY) || "dark");
    const btn = document.getElementById("theme-toggle");
    if (btn) btn.addEventListener("click", window.toggleTheme);
  });
})();
