// Contenu du panneau Scénario (UX-DR8, UX-DR11) : mode, progression, consigne, explication de
// l'étape et encart « État inattendu ». Le serveur écrit tous les textes (AD-2) : ce module n'en
// invente aucun hors des libellés fixes de l'interface, et ne calcule aucun verdict. Il ne garde
// que des choix d'affichage : l'étape rouverte par un segment, l'encart écarté par « Continuer ».
import { el, richText } from "./dom.js";
import { alteredExplanation, quizChoices, restoreFailedNotice } from "./quiz.js";

export const UNEXPECTED_TITLE = "État inattendu";
export const CONTINUE_LABEL = "Continuer";
export const PASSED_TEXT = "Étape réussie.";
export const SEES_LABEL = "Ce que l'étape voit :";

let counter = 0;

/** L'état du moteur ne redessine le panneau que s'il montre un quiz (bouton « Exécuter »). */
function quizEngine(state) {
  const panel = state.stepPanel;
  return panel && panel.steps.some((step) => step.quiz) ? state.engineState : null;
}

/** « Étape n sur N » : n suit l'étape courante (la dernière quand toutes sont réussies). */
export function progressLabel(panel) {
  const total = panel.steps.length;
  const index = panel.steps.findIndex((step) => step.step_id === panel.current_step_id);
  return `Étape ${index < 0 ? total : index + 1} sur ${total}`;
}

/**
 * Texte de la région `role="status"` du panneau : l'étape en cours, puis le dernier verdict.
 * Rend "" quand le scénario n'a pas d'étape (le panneau garde alors son message d'ouverture).
 */
export function statusFor(state) {
  const panel = state.stepPanel;
  if (!panel) return "";
  const verdict = state.verdict;
  const current = panel.steps.find((step) => step.step_id === panel.current_step_id);
  const parts = [];
  if (verdict && verdict.status === "passed") parts.push(PASSED_TEXT);
  else if (verdict && verdict.status === "failed" && verdict.reason_text) {
    parts.push(verdict.reason_text.replaceAll("`", ""));
  } else if (verdict && verdict.status === "unexpected") parts.push(`${UNEXPECTED_TITLE}.`);
  if (current) parts.push(`${progressLabel(panel)} : ${current.title_text}.`);
  return parts.join(" ");
}

/** Monte le contenu du panneau ; `update(state)` le redessine depuis le magasin. */
export function createScenarioView({ onSelect, onIntent } = {}) {
  const root = el("div", "scenario-body", { "data-zone": "scenario-body" });
  root.hidden = true;
  let shownId = null; // étape rouverte par un segment terminé
  let dismissed = null; // verdict dont l'encart a été écarté par « Continuer »
  let infoOpen = false;
  let chosen = null; // commande cochée du quiz en cours
  let lastState = null;
  const uid = ++counter;

  function modeRow(panel) {
    const row = el("div", "mode-row");
    const badge = el("span", "mode-badge");
    badge.textContent = `Mode ${panel.mode}`;
    const textId = `mode-text-${uid}`;
    const info = el("button", "mode-info", {
      type: "button",
      "aria-label": `À propos du mode ${panel.mode}`,
      "aria-expanded": String(infoOpen),
      "aria-controls": textId,
    });
    info.textContent = "i";
    const text = el("p", "mode-text", { id: textId });
    text.hidden = !infoOpen;
    richText(text, panel.mode_text);
    info.addEventListener("click", () => {
      infoOpen = !infoOpen;
      info.setAttribute("aria-expanded", String(infoOpen));
      text.hidden = !infoOpen;
    });
    row.append(badge, info);
    return [row, text];
  }

  function progress(panel, state) {
    const nav = el("nav", "step-progress-nav", { "aria-label": "Progression du scénario" });
    const count = el("p", "step-count");
    count.textContent = progressLabel(panel);
    const list = el("ol", "step-progress");
    panel.steps.forEach((step, index) => {
      const item = el("li", "step-progress-item");
      const segment = el("button", "step-segment", {
        type: "button",
        "data-step": step.step_id,
        "data-state": step.state,
        "aria-label": `Étape ${index + 1} : ${step.title_text}`,
        "aria-current": step.step_id === state.shownId ? "step" : false,
      });
      segment.textContent = String(index + 1);
      if (step.state === "todo") {
        segment.setAttribute("aria-disabled", "true");
      } else {
        segment.addEventListener("click", () => {
          shownId = step.state === "current" ? null : step.step_id;
          render(lastState);
          const again = root.querySelector(`[data-step="${step.step_id}"]`);
          if (again) again.focus();
        });
      }
      item.append(segment);
      list.append(item);
    });
    nav.append(count, list);
    return nav;
  }

  function explanationBlock(step) {
    const block = el("section", "step-explanation", { "data-step": step.step_id });
    const title = el("h3", "step-explanation-title");
    title.textContent = "Explication";
    const text = el("p", "step-explanation-text");
    richText(text, step.explanation_text);
    block.append(title, text);
    return block;
  }

  function notice(verdict) {
    const id = `notice-${uid}`;
    const card = el("div", "notice-card notice-warning", {
      role: "group",
      "aria-labelledby": id,
    });
    const title = el("h3", "notice-title", { id });
    title.textContent = UNEXPECTED_TITLE;
    card.append(title);
    if (verdict.expected_text) {
      const expected = el("p", "notice-expected");
      richText(expected, verdict.expected_text);
      card.append(expected);
    }
    if (verdict.observed && verdict.observed.length) {
      const label = el("p", "notice-sees");
      label.textContent = SEES_LABEL;
      const list = el("ul", "notice-observed");
      for (const seen of verdict.observed) {
        const item = el("li", "notice-observed-item");
        if (seen.element_id) {
          const link = el("button", "element-link", {
            type: "button",
            "data-element-id": seen.element_id,
          });
          richText(link, seen.text);
          link.addEventListener("click", () => onSelect && onSelect(seen.element_id));
          item.append(link);
        } else {
          richText(item, seen.text);
        }
        list.append(item);
      }
      card.append(label, list);
    }
    if (verdict.reason_text) {
      const why = el("p", "notice-explanation");
      richText(why, verdict.reason_text);
      card.append(why);
    }
    const actions = el("div", "notice-actions");
    const next = el("button", "btn btn-primary", { type: "button", "data-action": "continue" });
    next.textContent = CONTINUE_LABEL;
    next.addEventListener("click", () => {
      dismissed = verdict;
      render(lastState);
    });
    actions.append(next);
    card.append(actions);
    return card;
  }

  function render(state) {
    lastState = state;
    const panel = state.stepPanel;
    if (!panel || !panel.steps.length) {
      root.hidden = true;
      root.replaceChildren();
      return;
    }
    root.hidden = false;
    const byId = new Map(panel.steps.map((step) => [step.step_id, step]));
    const current = byId.get(panel.current_step_id) || null;
    const shown = (shownId && byId.get(shownId)) || current || panel.steps.at(-1);
    const view = { ...state, shownId: shown.step_id };

    const instruction = el("section", "step-instruction", { "data-step": shown.step_id });
    const heading = el("h3", "step-title", { tabindex: "-1" });
    heading.textContent = shown.title_text;
    const chat = el("p", "step-chat");
    richText(chat, shown.instruction_text);
    instruction.append(heading, chat);

    const children = [...modeRow(panel), progress(panel, view), instruction];
    // Quiz : les commandes proposées, puis l'explication de la mauvaise réponse et, si le
    // rétablissement échoue, l'encart d'erreur (UX-DR9, UX-DR11).
    if (shown === current && current.quiz && !panel.restore_failed) {
      const known = current.quiz.choices.some((c) => c.choice_id === chosen);
      if (!known) chosen = null;
      children.push(
        quizChoices(current, {
          state,
          chosen,
          onChoose(choiceId) {
            chosen = choiceId;
            render(lastState);
            const again = root.querySelector(`.quiz-radio[value="${choiceId}"]`);
            if (again) again.focus();
          },
          onRun(choiceId) {
            if (choiceId && onIntent) onIntent("quiz_choice", { choice_id: choiceId });
          },
        }),
      );
    }
    if (shown === current && panel.quiz_altered) children.push(alteredExplanation(panel.quiz_altered));
    if (panel.restore_failed) {
      children.push(restoreFailedNotice(() => onIntent && onIntent("restart", {})));
    }
    const verdict = state.verdict;
    if (verdict && verdict.status === "unexpected" && verdict !== dismissed && shown === current) {
      children.push(notice(verdict));
    }
    // L'explication suit la consigne : celle d'une étape terminée rouverte, ou celle de l'étape
    // qui vient d'être réussie (publiée par le serveur après la mise à jour des vues).
    let explained = shown.state === "done" ? shown : null;
    if (!explained && shown === current && verdict && verdict.status === "passed") {
      explained = byId.get(verdict.step_id) || null;
    }
    if (explained && explained.explanation_text) children.push(explanationBlock(explained));
    const focusKey = focusKeyOf(document.activeElement);
    root.replaceChildren(...children);
    if (focusKey) restoreFocus(focusKey);
  }

  // Le redessin remplace les nœuds : le focus qui était dans le panneau revient sur l'élément
  // équivalent (même segment, même bouton), sinon sur le titre de la consigne, jamais sur `body`.
  function focusKeyOf(active) {
    if (!active || active === root || !root.contains(active)) return null;
    if (active.dataset && active.dataset.step && active.classList.contains("step-segment")) {
      return `.step-segment[data-step="${active.dataset.step}"]`;
    }
    if (active.classList.contains("mode-info")) return ".mode-info";
    if (active.classList.contains("quiz-radio")) return `.quiz-radio[value="${active.getAttribute("value")}"]`;
    if (active.classList.contains("quiz-run")) return ".quiz-run";
    if (active.dataset && active.dataset.elementId) {
      return `.element-link[data-element-id="${active.dataset.elementId}"]`;
    }
    return ".step-title";
  }

  function restoreFocus(selector) {
    const target = root.querySelector(selector) || root.querySelector(".step-title");
    if (target) target.focus();
  }

  return {
    root,
    update(state) {
      const changed =
        !lastState ||
        state.stepPanel !== lastState.stepPanel ||
        state.verdict !== lastState.verdict ||
        quizEngine(state) !== quizEngine(lastState);
      if (lastState && state.verdict !== lastState.verdict) shownId = null;
      if (changed) render(state);
      else lastState = state; // rien à redessiner : le focus du panneau reste en place
      return statusFor(state);
    },
  };
}
