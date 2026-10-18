// Point d'entrée : coquille d'interface. Le front ne calcule rien (AD-2) : il affiche ce que dit le serveur.
import { setOffline } from "./actions.js";
import { loadCatalogue, openMode, renderCatalogue, workspacePath } from "./catalogue.js";
import { renderBadge, refreshBadge, renderDiagnosticPage } from "./diagnostic.js";
import { initDisplayMenu } from "./display.js";
import { STOPPED_MESSAGE, watchHealth } from "./health.js";
import { currentSurface, renderNav } from "./nav.js";
import { connectWorkspace, createStore } from "./store.js";
import "./views.js";
import { mountWorkspace } from "./workspace.js";

const WORKSPACE_PATH = /^\/espace\/([^/]+)$/;
const TRACKS = { no_ai: "Parcours sans IA", llm: "Parcours LLM" };
const LOAD_FAILED = "Le catalogue n'a pas pu être lu. Rechargez la page.";
const WORKSPACE_MISSING = "Cet espace n'existe pas. Revenez au catalogue.";

async function loadShell() {
  const response = await fetch("/api/shell", { cache: "no-store", credentials: "same-origin" });
  if (!response.ok) throw new Error(`/api/shell : ${response.status}`);
  return response.json();
}

function showAlive(alive) {
  document.getElementById("app-alert").textContent = alive ? "" : STOPPED_MESSAGE;
  setOffline(!alive);
}

function message(container, text) {
  const paragraph = document.createElement("p");
  paragraph.className = "empty";
  paragraph.setAttribute("role", "alert");
  paragraph.textContent = text;
  container.replaceChildren(paragraph);
}

async function showWorkspace(container, workspaceId) {
  document.querySelector("main").classList.add("is-workspace");
  let info;
  try {
    const response = await fetch(`/api/workspaces/${encodeURIComponent(workspaceId)}`, {
      cache: "no-store",
      credentials: "same-origin",
    });
    const body = await response.json();
    if (!response.ok) return message(container, body.reason_text || WORKSPACE_MISSING);
    info = body;
  } catch (err) {
    return message(container, WORKSPACE_MISSING);
  }
  document.getElementById("page-title").textContent = info.title;
  document.getElementById("page-subtitle").textContent =
    `${TRACKS[info.track] || info.track} · Mode ${info.mode}`;
  document.title = `${info.title} · WaveDevSecOps`;
  const store = createStore();
  mountWorkspace(container, { title: info.title, store, chain: info.chain, track: info.track });
  connectWorkspace(store, workspaceId);
}

async function showCatalogue(container) {
  try {
    const catalogue = await loadCatalogue();
    renderCatalogue(container, catalogue, async (scenario, mode) => {
      const opened = await openMode(scenario, mode);
      window.location.assign(workspacePath(opened.workspace_id));
    });
  } catch (err) {
    message(container, LOAD_FAILED);
  }
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
  const container = document.getElementById("panes");
  const badgeLink = document.querySelector('#surfaces a[href="/diagnostic"]');
  const workspace = WORKSPACE_PATH.exec(window.location.pathname);
  if (workspace) {
    if (badgeLink) refreshBadge(badgeLink);
    await showWorkspace(container, decodeURIComponent(workspace[1]));
  } else if (current && current.key === "diagnostic") {
    await renderDiagnosticPage(container, {
      onReport: (report) => badgeLink && renderBadge(badgeLink, report),
    });
  } else {
    if (badgeLink) refreshBadge(badgeLink);
    await showCatalogue(container);
  }
}

start();
