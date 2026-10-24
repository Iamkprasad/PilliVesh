/* Set the saved theme before first paint; app.js keeps it in sync afterwards. */
(function () {
  try {
    if (localStorage.getItem("pv.theme.v1") === "dark") {
      document.documentElement.setAttribute("data-theme", "dark");
    }
  } catch (e) {}
})();
