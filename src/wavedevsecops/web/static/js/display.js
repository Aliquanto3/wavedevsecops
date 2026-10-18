// Menu « Affichage ▾ » : thème (Système, Clair, Sombre) et « Réduire les animations ».
// Le choix s'applique tout de suite et se garde dans le navigateur (localStorage).

const KEY = "wds.display";
const THEMES = ["system", "light", "dark"];

export function loadDisplay() {
  try {
    const prefs = JSON.parse(window.localStorage.getItem(KEY) || "{}");
    return {
      theme: THEMES.includes(prefs.theme) ? prefs.theme : "system",
      reduceMotion: prefs.reduceMotion === true,
    };
  } catch (err) {
    return { theme: "system", reduceMotion: false };
  }
}

function saveDisplay(prefs) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch (err) {
    // Le choix s'applique à cette page même si le navigateur refuse de le garder.
  }
}

export function applyDisplay(prefs, root = document.documentElement) {
  if (prefs.theme === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", prefs.theme);
  }
  if (prefs.reduceMotion) {
    root.setAttribute("data-motion", "reduced");
  } else {
    root.removeAttribute("data-motion");
  }
}

export function initDisplayMenu() {
  const trigger = document.getElementById("display-trigger");
  const popup = document.getElementById("display-popup");
  const menu = document.getElementById("display-menu");
  const picker = document.getElementById("theme-picker");
  const motion = document.getElementById("reduce-motion");

  let prefs = loadDisplay();
  picker.value = prefs.theme;
  motion.checked = prefs.reduceMotion;
  applyDisplay(prefs);

  function setOpen(open, returnFocus) {
    popup.hidden = !open;
    trigger.setAttribute("aria-expanded", String(open));
    if (!open && returnFocus) trigger.focus();
  }

  trigger.addEventListener("click", () => setOpen(popup.hidden, false));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !popup.hidden) {
      event.stopPropagation();
      setOpen(false, true);
    }
  });
  document.addEventListener("click", (event) => {
    if (!popup.hidden && !menu.contains(event.target)) setOpen(false, false);
  });

  picker.addEventListener("change", () => {
    prefs = { ...prefs, theme: picker.value };
    applyDisplay(prefs);
    saveDisplay(prefs);
  });
  motion.addEventListener("change", () => {
    prefs = { ...prefs, reduceMotion: motion.checked };
    applyDisplay(prefs);
    saveDisplay(prefs);
  });
}
