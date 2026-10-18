// Exécution facultative du code d'exercice du parcours LLM (AD-13, UX-DR23). Le bouton ouvre une
// confirmation en ligne ; seule l'acceptation envoie l'intention `run_exercise_code` avec
// `confirmed: true`. Le serveur revérifie la confirmation (AD-19) : ce bloc ne décide de rien.
import { bindAction, setActionDisabled } from "./actions.js";
import { el } from "./dom.js";
import { LOADING } from "./store.js";

export const RUN_LABEL = "Exécuter le code (réseau possible)";
export const CONFIRM_TEXT = "Ce code peut appeler un service en ligne. Continuer ?";
export const BUSY_TEXT = "Une action est déjà en cours dans l'espace.";
export const LOADING_TEXT = "L'espace se charge.";
export const SEND_FAILED_TEXT = "WaveDevSecOps ne répond pas. Rechargez la page.";

/** Monte le bloc dans `parent` ; rend `{ destroy }`. */
export function mountNetworkRun(parent, { store, fetchImpl }) {
  const send = fetchImpl || ((...args) => fetch(...args));
  const block = el("div", "network-run", { "data-zone": "network-run" });
  const button = el("button", "btn btn-secondary", {
    type: "button",
    id: "network-run-button",
    "data-action": "network-run",
    "aria-expanded": "false",
  });
  button.textContent = RUN_LABEL;
  const confirm = el("div", "network-run-confirm", {
    role: "group",
    "aria-labelledby": "network-run-question",
  });
  confirm.hidden = true;
  const question = el("p", "network-run-question", { id: "network-run-question" });
  question.textContent = CONFIRM_TEXT;
  const accept = el("button", "btn btn-primary", {
    type: "button",
    "data-action": "network-run-accept",
  });
  accept.textContent = "Continuer";
  const cancel = el("button", "btn btn-reset", {
    type: "button",
    "data-action": "network-run-cancel",
  });
  cancel.textContent = "Annuler";
  const actions = el("div", "network-run-actions");
  actions.append(accept, cancel);
  confirm.append(question, actions);
  block.append(button, confirm);
  parent.append(block);

  function close(refocus) {
    confirm.hidden = true;
    button.setAttribute("aria-expanded", "false");
    if (refocus) button.focus();
  }

  function open() {
    confirm.hidden = false;
    button.setAttribute("aria-expanded", "true");
    cancel.focus(); // le choix prudent par défaut
  }

  button.addEventListener("click", () => {
    if (confirm.hidden) open();
    else close(true);
  });
  cancel.addEventListener("click", () => close(true));
  confirm.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      close(true);
    }
  });
  accept.addEventListener("click", async () => {
    const id = store.state.workspaceId;
    close(true);
    try {
      const response = await send(`/api/ws/${encodeURIComponent(id)}/run_exercise_code`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmed: true }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        store.fail(body.reason_text || SEND_FAILED_TEXT);
      }
    } catch (err) {
      store.fail(SEND_FAILED_TEXT);
    }
  });

  bindAction(button, null);
  const unsubscribe = store.subscribe((state) => {
    const loading = state.engineState === LOADING;
    const busy = loading || state.engineState !== "idle";
    const reason = loading ? LOADING_TEXT : state.reasonText || BUSY_TEXT;
    setActionDisabled(button, busy ? reason : null);
    if (busy && !confirm.hidden) close(false);
  });
  return {
    destroy() {
      unsubscribe();
      block.remove();
    },
  };
}
