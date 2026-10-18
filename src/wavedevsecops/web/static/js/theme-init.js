// Script classique, chargé dans <head> : applique le thème et le mouvement avant le premier rendu.
(function () {
  try {
    var raw = window.localStorage.getItem("wds.display");
    var prefs = raw ? JSON.parse(raw) : {};
    var root = document.documentElement;
    if (prefs.theme === "light" || prefs.theme === "dark") {
      root.setAttribute("data-theme", prefs.theme);
    }
    if (prefs.reduceMotion === true) {
      root.setAttribute("data-motion", "reduced");
    }
  } catch (err) {
    // Stockage indisponible ou illisible : le thème du système s'applique.
  }
})();
