// Quiz à exécution réelle (UX-DR9, UX-DR10, UX-DR11, UX-DR37) : choix des commandes, bandeau
// « État modifié par le quiz », rétablissement et échec du rétablissement. Le serveur écrit les
// textes d'explication et juge la réponse (AD-2) : ce module ne garde que les libellés fixes de
// l'interface et ce que l'apprenant a coché.
import { bindAction } from "./actions.js";
import { el, richText } from "./dom.js";

export const CHOOSE_TEXT = "Choisissez une commande.";
export const RUN_LABEL = "Exécuter ma réponse";
export const BUSY_TEXT = "Une action est en cours.";
export const ALTERED_TEXT = "Rétablissez d'abord l'état.";
export const BANNER_LABEL = "État modifié par le quiz";
export const BANNER_PREFIX = "État modifié par le quiz — ";
export const UNDERSTOOD_LABEL = "J'ai compris, rétablir l'état";
export const RESTORING_TEXT = "Rétablissement de l'état…";
export const RESTORED_TEXT = "Rétabli.";
export const EXPLANATION_TITLE = "Ce que cette commande a fait";
export const FAILED_TITLE = "Rétablissement échoué";
export const FAILED_TEXT =
  "L'état n'a pas pu être rétabli. Pour ne pas vous laisser sur un état faux, recommencez le scénario. Votre score du premier coup est conservé.";
export const RESTART_LABEL = "Recommencer";
export const SEND_FAILED_TEXT = "L'action n'a pas pu être envoyée. Réessayez.";

/** Envoie une intention ; en cas de refus, le texte du serveur s'affiche dans la zone d'erreur. */
export async function postIntent(store, intent, body = {}) {
  try {
    const response = await globalThis.fetch(
      `/api/ws/${encodeURIComponent(store.state.workspaceId)}/${intent}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify(body),
      },
    );
    if (!response.ok) {
      let text = SEND_FAILED_TEXT;
      try {
        text = (await response.json()).reason_text || text;
      } catch (err) {
        // Corps illisible : le texte par défaut suffit.
      }
      store.fail(text);
    }
    return response.ok;
  } catch (err) {
    store.fail(SEND_FAILED_TEXT);
    return false;
  }
}

/** Raison pour laquelle « Exécuter ma réponse » est inactif, ou null. */
export function runReason(state, chosen) {
  const panel = state.stepPanel;
  if (panel && (panel.quiz_altered || panel.restore_failed)) return ALTERED_TEXT;
  if (state.engineState !== "idle") return BUSY_TEXT;
  return chosen ? null : CHOOSE_TEXT;
}

let counter = 0;

/** Groupe radio d'une carte par commande, puis « Exécuter ma réponse ». */
export function quizChoices(step, { state, chosen, onChoose, onRun }) {
  const uid = ++counter;
  const group = el("fieldset", "quiz-choice", { "data-step": step.step_id });
  const legend = el("legend", "quiz-legend");
  legend.textContent = "Commandes proposées";
  group.append(legend);
  const locked = Boolean(runReason(state, "x"));
  for (const choice of step.quiz.choices) {
    const card = el("label", "quiz-card");
    const input = el("input", "quiz-radio", {
      type: "radio",
      name: `quiz-${uid}`,
      value: choice.choice_id,
      "aria-disabled": locked ? "true" : false,
    });
    input.checked = chosen === choice.choice_id;
    input.addEventListener("change", () => {
      if (!locked) onChoose(choice.choice_id);
    });
    const command = el("code", "quiz-command");
    command.textContent = choice.command_text;
    card.append(input, command);
    group.append(card);
  }
  const run = el("button", "btn btn-primary quiz-run", { type: "button", "data-action": "run" });
  run.textContent = RUN_LABEL;
  run.addEventListener("click", () => onRun(chosen));
  group.append(run);
  bindAction(run, runReason(state, chosen));
  return group;
}

/** Explication de la mauvaise réponse, écrite par le serveur. */
export function alteredExplanation(altered) {
  const block = el("section", "quiz-explanation", { "data-step": altered.step_id });
  const title = el("h3", "step-explanation-title");
  title.textContent = EXPLANATION_TITLE;
  const text = el("p", "step-explanation-text");
  richText(text, altered.explanation_text || "");
  block.append(title, text);
  return block;
}

/** `notice-card` d'erreur d'un rétablissement échoué : seule action, « Recommencer ». */
export function restoreFailedNotice(onRestart) {
  const card = el("div", "notice-card notice-error", {
    role: "alert",
    "data-notice": "restore-failed",
  });
  const title = el("h3", "notice-title");
  title.textContent = FAILED_TITLE;
  const text = el("p", "notice-explanation");
  text.textContent = FAILED_TEXT;
  const actions = el("div", "notice-actions");
  const restart = el("button", "btn btn-primary", { type: "button", "data-action": "restart" });
  restart.textContent = RESTART_LABEL;
  restart.addEventListener("click", onRestart);
  actions.append(restart);
  card.append(title, text, actions);
  return card;
}

/** Texte de la région `role="status"` pour le quiz ; "" quand il n'y a rien à dire. */
export function quizStatus(state) {
  const altered = state.stepPanel && state.stepPanel.quiz_altered;
  if (state.engineState === "restoring") return RESTORING_TEXT;
  if (altered && !state.stepPanel.restore_failed) {
    return `${BANNER_PREFIX}${altered.command_text.replaceAll("`", "")}`;
  }
  return state.restored ? RESTORED_TEXT : "";
}

/**
 * Bandeau `quiz-banner` au-dessus des vues. Il prend le focus à son apparition ; pendant le
 * rétablissement les vues passées à `inertTargets` sont `inert`. Quand il disparaît après un
 * rétablissement réussi, `onRestored` ramène le focus sur le panneau.
 */
export function createQuizBanner({ store, inertTargets, onRestored }) {
  const root = el("section", "quiz-banner", {
    "aria-label": BANNER_LABEL,
    tabindex: "-1",
    "data-zone": "quiz-banner",
  });
  root.hidden = true;
  const text = el("p", "quiz-banner-text");
  const button = el("button", "btn btn-primary quiz-restore", {
    type: "button",
    "data-action": "restore",
  });
  button.textContent = UNDERSTOOD_LABEL;
  button.addEventListener("click", () => postIntent(store, "restore_state"));
  root.append(text, button);
  let shown = false;

  function setInert(on) {
    for (const node of inertTargets) {
      if (on) node.setAttribute("inert", "");
      else node.removeAttribute("inert");
    }
  }

  return {
    root,
    update(state) {
      const panel = state.stepPanel;
      const altered = panel && !panel.restore_failed ? panel.quiz_altered : null;
      const restoring = state.engineState === "restoring";
      const visible = Boolean(altered) || (restoring && shown);
      setInert(restoring);
      if (visible) {
        const command = altered ? altered.command_text : "";
        text.replaceChildren();
        if (restoring) text.textContent = RESTORING_TEXT;
        else {
          text.append(BANNER_PREFIX);
          const code = el("code", "quiz-command");
          code.textContent = command;
          text.append(code);
        }
        button.hidden = restoring;
      }
      root.hidden = !visible;
      if (visible && !shown) root.focus();
      if (!visible && shown && state.restored) onRestored();
      shown = visible;
    },
  };
}
