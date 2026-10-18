// Point d'entrée : coquille d'interface. Le front ne calcule rien (AD-2) : il affiche ce que dit le serveur.
import { setOffline } from "./actions.js";
import { renderBadge, refreshBadge, renderDiagnosticPage } from "./diagnostic.js";
import { initDisplayMenu } from "./display.js";
import { STOPPED_MESSAGE, watchHealth } from "./health.js";
import { currentSurface, renderNav } from "./nav.js";
import { renderPanes } from "./panes.js";

const EMPTY_TEXT = "Aucune vue n'est encore disponible dans cette version.";

async function loadShell() {
  const response = await fetch("/api/shell", { cache: "no-store", credentials: "same-origin" });
  if (!response.ok) throw new Error(`/api/shell : ${response.status}`);
  return response.json();
}

function showAlive(alive) {
  document.getElementById("app-alert").textContent = alive ? "" : STOPPED_MESSAGE;
  setOffline(!alive);
}

async function start() {
  initDisplayMenu();
  let current = null;
  watchHealth(showAlive);
  try {
    const shell = await loadShell();
    current = currentSurface(shell.surfaces, window.location.pathname);
    renderNav(document.getElementById("surfaces"), shell.surfaces, current);
    if (current) {
      document.getElementById("page-title").textContent = current.label;
      document.getElementById("page-subtitle").textContent = current.subtitle;
      document.title = `${current.label} · WaveDevSecOps`;
    }
  } catch (err) {
    // Le point de vie signale l'arrêt du serveur ; l'en-tête reste vide en attendant.
  }
  const panes = document.getElementById("panes");
  const badgeLink = document.querySelector('#surfaces a[href="/diagnostic"]');
  if (current && current.key === "diagnostic") {
    await renderDiagnosticPage(panes, {
      onReport: (report) => badgeLink && renderBadge(badgeLink, report),
    });
  } else {
    if (badgeLink) refreshBadge(badgeLink);
    renderPanes(panes, EMPTY_TEXT);
  }
}

start();
