// Catalogue, première version : la section « Socle git » liste les scénarios déclarés dans
// `content/scenarios/`, avec leurs modes. Un clic sur un mode ouvre son espace de travail, dans
// le parcours sans IA par défaut. La Story 6.1 étend cet écran (parcours, états, cartes
// indisponibles) sans le remplacer.
import { el } from "./dom.js";

export const NO_SCENARIO_TEXT = "Aucun scénario n'est déclaré dans cette installation.";

export async function openMode(scenario, mode, { fetchImpl = (...a) => fetch(...a) } = {}) {
  const response = await fetchImpl("/api/open", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_id: scenario.scenario_id, mode: mode.mode }),
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.reason_text || "Le scénario n'a pas pu s'ouvrir.");
  return body;
}

export function workspacePath(workspaceId) {
  return `/espace/${encodeURIComponent(workspaceId)}`;
}

function card(scenario, onOpen) {
  const article = el("article", "scenario-card");
  const title = el("h3", "scenario-card-title");
  title.textContent = scenario.title;
  const modes = el("div", "scenario-modes");
  const alert = el("p", "scenario-card-alert", { role: "alert" });
  for (const mode of scenario.modes) {
    const button = el("button", "btn btn-secondary", { type: "button", "data-mode": mode.mode });
    button.textContent = `Ouvrir en mode ${mode.mode}`;
    button.setAttribute("aria-label", `Ouvrir ${scenario.title} en mode ${mode.mode}`);
    button.addEventListener("click", async () => {
      alert.textContent = "";
      try {
        await onOpen(scenario, mode);
      } catch (err) {
        alert.textContent = err.message;
      }
    });
    modes.append(button);
  }
  article.append(title, modes, alert);
  return article;
}

/** Dessine le catalogue dans `container` ; `onOpen(scenario, mode)` ouvre l'espace. */
export function renderCatalogue(container, catalogue, onOpen) {
  container.replaceChildren();
  for (const section of catalogue.sections) {
    const block = el("section", "catalogue-section", {
      "aria-labelledby": `catalogue-${section.key}`,
    });
    const heading = el("h2", "catalogue-title", { id: `catalogue-${section.key}` });
    heading.textContent = section.title;
    const subtitle = el("p", "subtitle");
    subtitle.textContent = section.subtitle;
    const cards = el("div", "scenario-cards");
    if (section.scenarios.length === 0) {
      const empty = el("p", "empty");
      empty.textContent = NO_SCENARIO_TEXT;
      cards.append(empty);
    }
    for (const scenario of section.scenarios) cards.append(card(scenario, onOpen));
    block.append(heading, subtitle, cards);
    container.append(block);
  }
}

export async function loadCatalogue({ fetchImpl = (...a) => fetch(...a) } = {}) {
  const response = await fetchImpl("/api/catalogue", { cache: "no-store", credentials: "same-origin" });
  if (!response.ok) throw new Error(`/api/catalogue : ${response.status}`);
  return response.json();
}
