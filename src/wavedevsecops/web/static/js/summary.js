// Bilan de fin de scénario (UX-DR12) : le `score-summary` et ses trois actions. Les textes du
// score et des indices viennent du serveur (AD-2, AD-14) : ce module n'en calcule aucun. Il ne
// pose que les libellés fixes des boutons et la navigation.
import { el } from "./dom.js";

export const DONE_TITLE = "Scénario terminé";
export const NEXT_LABEL = "Scénario suivant";
export const CATALOGUE_LABEL = "Catalogue";
export const RESTART_LABEL = "Recommencer";
export const OPEN_FAILED_TEXT = "Le scénario suivant n'a pas pu s'ouvrir. Revenez au catalogue.";

let counter = 0;

/** Ouvre l'espace du scénario suivant (même parcours) puis y navigue. */
export async function openNext(next, { fetchImpl = (...a) => fetch(...a), assign } = {}) {
  const go = assign || ((path) => window.location.assign(path));
  const response = await fetchImpl("/api/open", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_id: next.scenario_id, mode: next.mode, track: next.track }),
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.reason_text || OPEN_FAILED_TEXT);
  go(`/espace/${encodeURIComponent(body.workspace_id)}`);
}

/**
 * `score-summary` : « 3 sur 4 du premier coup · 1 indice » puis « Scénario suivant »,
 * « Catalogue » et « Recommencer ». Sans scénario suivant, le premier bouton est inactif et dit
 * pourquoi (texte visible et relié).
 */
export function scoreSummary(summary, { onNext, onCatalogue, onRestart }) {
  const uid = ++counter;
  const root = el("section", "score-summary", {
    "data-zone": "score-summary",
    "aria-labelledby": `score-summary-title-${uid}`,
  });
  const title = el("h3", "score-summary-title", {
    id: `score-summary-title-${uid}`,
    tabindex: "-1",
  });
  title.textContent = DONE_TITLE;
  const score = el("p", "score-summary-score");
  score.textContent = summary.score_text;
  const hints = el("p", "score-summary-hints");
  hints.textContent = summary.hints_text;
  const actions = el("div", "score-summary-actions");

  const next = el("button", "btn btn-primary", { type: "button", "data-action": "next" });
  next.textContent = NEXT_LABEL;
  actions.append(next);
  let why = null;
  if (summary.next) {
    next.addEventListener("click", () => onNext && onNext(summary.next));
  } else {
    why = el("p", "score-summary-why", { id: `score-summary-why-${uid}` });
    why.textContent = summary.next_none_text || "";
    next.setAttribute("aria-disabled", "true");
    next.setAttribute("aria-describedby", why.id);
  }
  const catalogue = el("button", "btn btn-secondary", {
    type: "button",
    "data-action": "catalogue",
  });
  catalogue.textContent = CATALOGUE_LABEL;
  catalogue.addEventListener("click", () => onCatalogue && onCatalogue());
  const restart = el("button", "btn btn-secondary", { type: "button", "data-action": "restart" });
  restart.textContent = RESTART_LABEL;
  restart.addEventListener("click", () => onRestart && onRestart());
  actions.append(catalogue, restart);

  root.append(title, score, hints, actions);
  if (why) root.append(why);
  return root;
}

/** Texte annoncé par la région `role="status"` quand le bilan apparaît. */
export function summaryStatus(summary) {
  return `${DONE_TITLE}. ${summary.text}.`;
}
