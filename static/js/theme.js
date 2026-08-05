(function () {
  const STORAGE_KEY = "alice-theme";
  const DEFAULT = "default";

  function apply(name) {
    document.documentElement.setAttribute("data-theme", name);
    localStorage.setItem(STORAGE_KEY, name);
  }

  apply(localStorage.getItem(STORAGE_KEY) || DEFAULT);

  window.AliceTheme = {
    apply,
    current: () => document.documentElement.getAttribute("data-theme"),
  };
})();
