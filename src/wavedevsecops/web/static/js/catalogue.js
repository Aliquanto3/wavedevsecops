// Catalogue (Stories 2.3 et 6.1). Au premier passage, `path-picker` pose seul la question du
// parcours. Ensuite la section « Socle git » liste les scénarios dans l'ordre conseillé : un
// disque numéroté, une colonne par mode (Mode A, Mode B s'il existe), l'état du parcours choisi
// et, si un outil manque, « ⊘ Indisponible » avec un lien vers le diagnostic. Le front n'affiche
// que ce que dit le serveur (AD-2) : ordre, états, textes et disponibilité viennent de
// `GET /api/catalogue?track=…`.
import { el } from "./dom.js";

export const NO_SCENARIO_TEXT = "Aucun scénario n'est déclaré dans cette installation.";

export async function openMode(
  scenario,
  mode,
  { fetchImpl = (...a) => fetch(...a), track = null } = {},
) {
  const response = await fetchImpl("/api/open", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scenario_id: scenario.scenario_id,
      mode: mode.mode,
      ...(track || mode.track ? { track: track || mode.track } : {}),
    }),
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.reason_text || "Le scénario n'a pas pu s'ouvrir.");
  return body;
}

export function workspacePath(workspaceId) {
  return `/espace/${encodeURIComponent(workspaceId)}`;
}

/** `path-picker` : groupe radio de pilules ; `onPick(track)` mémorise le choix et recharge. */
export function renderPicker(container, catalogue, onPick) {
  container.replaceChildren();
  const group = el("div", "path-picker", { role: "radiogroup", "aria-labelledby": "picker-question" });
  const question = el("p", "path-picker-question", { id: "picker-question" });
  question.textContent = catalogue.picker.question;
  const options = el("div", "path-picker-options");
  for (const track of catalogue.tracks) {
    const checked = catalogue.track === track.key;
    const wrap = el("div", "path-picker-option");
    const button = el("button", "path-pill", {
      type: "button",
      role: "radio",
      "aria-checked": checked ? "true" : "false",
      "aria-describedby": `picker-text-${track.key}`,
      "data-track": track.key,
    });
    button.textContent = track.label;
    button.addEventListener("click", () => onPick(track.key));
    const text = el("p", "path-picker-text", { id: `picker-text-${track.key}` });
    text.textContent = track.text;
    wrap.append(button, text);
    options.append(wrap);
  }
  group.append(question, options);
  container.append(group);
  return group;
}

function modeColumn(scenario, mode, onOpen) {
  const column = el("div", "scenario-mode", {
    "data-mode": mode.mode,
    "data-state": mode.state,
  });
  const name = el("p", "scenario-mode-name");
  name.textContent = `Mode ${mode.mode}`;
  column.append(name);
  if (!mode.available) {
    column.classList.add("is-unavailable");
    const info = mode.unavailable;
    const status = el("p", "scenario-mode-state");
    status.textContent = info.text;
    const needs = el("p", "scenario-mode-detail");
    needs.append(`${info.needs_text} · `);
    const link = el("a", "scenario-mode-link", { href: info.diagnostic_path });
    link.textContent = info.diagnostic_text;
    needs.append(link);
    column.append(status, needs);
    return column;
  }
  const state = el("p", "scenario-mode-state");
  state.textContent = mode.state_text;
  column.append(state);
  if (mode.detail_text) {
    const detail = el("p", "scenario-mode-detail");
    detail.textContent = mode.detail_text;
    column.append(detail);
  }
  const alert = el("p", "scenario-card-alert", { role: "alert" });
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
  column.append(button, alert);
  return column;
}

function card(scenario, onOpen) {
  const article = el("article", "scenario-card", { "data-scenario": scenario.scenario_id });
  const head = el("div", "scenario-card-head");
  const disc = el("span", "scenario-disc", { "aria-hidden": "true" });
  disc.textContent = String(scenario.number);
  const title = el("h3", "scenario-card-title");
  title.textContent = scenario.title;
  title.setAttribute("aria-label", `${scenario.number}. ${scenario.title}`);
  head.append(disc, title);
  const modes = el("div", "scenario-modes");
  for (const mode of scenario.modes) modes.append(modeColumn(scenario, mode, onOpen));
  article.append(head, modes);
  return article;
}

/**
 * Dessine le catalogue dans `container`. Sans parcours choisi (`catalogue.track` nul), seul le
 * `path-picker` apparaît ; `onPick(track)` reçoit le choix. `onOpen(scenario, mode)` ouvre l'espace.
 */
export function renderCatalogue(container, catalogue, onOpen, onPick = () => {}) {
  container.replaceChildren();
  if (!catalogue.track) {
    renderPicker(container, catalogue, onPick);
    return;
  }
  const picker = el("div", "path-picker-bar");
  renderPicker(picker, catalogue, onPick);
  container.append(picker);
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

export async function loadCatalogue({ fetchImpl = (...a) => fetch(...a), track = null } = {}) {
  const query = track ? `?track=${encodeURIComponent(track)}` : "";
  const response = await fetchImpl(`/api/catalogue${query}`, {
    cache: "no-store",
    credentials: "same-origin",
  });
  if (!response.ok) {
    let reason = "";
    try {
      reason = (await response.json()).reason_text || "";
    } catch (err) {
      reason = "";
    }
    const error = new Error(reason || `/api/catalogue : ${response.status}`);
    error.status = response.status;
    error.reasonText = reason;
    throw error;
  }
  return response.json();
}
