// Contenu du panneau Scénario (UX-DR8, UX-DR11) : mode, progression, consigne, explication de
// l'étape et encart « État inattendu ». Le serveur écrit tous les textes (AD-2) : ce module n'en
// invente aucun hors des libellés fixes de l'interface, et ne calcule aucun verdict. Il ne garde
// que des choix d'affichage : l'étape rouverte par un segment, l'encart écarté par « Continuer ».
import { bindAction } from "./actions.js";
import { correctionBlock } from "./correction.js";
import { createDesignateBlock } from "./designation.js";
import { el, richText } from "./dom.js";
import { OPEN_HINT_LABEL, defaultTier, hintTabs, nextTier } from "./hints.js";
import { alteredExplanation, quizChoices, restoreFailedNotice } from "./quiz.js";
import { RESTARTED_TEXT, RESTART_LABEL, contentChangedNotice, restartFoot } from "./restart.js";
import { openNext, scoreSummary, summaryStatus } from "./summary.js";

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
  if (state.restarted) parts.push(RESTARTED_TEXT);
  const corrected = verdict && panel.steps.find((step) => step.step_id === verdict.step_id);
  if (verdict && verdict.status === "passed" && corrected && corrected.correction) {
    parts.push(corrected.correction.summary_text || PASSED_TEXT); // une désignation fausse ferme aussi l'étape
  } else if (verdict && verdict.status === "passed") parts.push(PASSED_TEXT);
  else if (verdict && verdict.status === "failed" && verdict.reason_text) {
    parts.push(verdict.reason_text.replaceAll("`", ""));
  } else if (verdict && verdict.status === "unexpected") parts.push(`${UNEXPECTED_TITLE}.`);
  if (current) parts.push(`${progressLabel(panel)} : ${current.title_text}.`);
  if (panel.summary) parts.push(summaryStatus(panel.summary));
  if (state.hintNotice) parts.push(state.hintNotice);
  return parts.join(" ");
}

/** Monte le contenu du panneau ; `update(state)` le redessine depuis le magasin. */
export function createScenarioView({
  onSelect,
  onIntent,
  onError,
  navigate,
  fetchImpl,
  designation = null,
} = {}) {
  const root = el("div", "scenario-body", { "data-zone": "scenario-body" });
  root.hidden = true;
  let shownId = null; // étape rouverte par un segment terminé
  let dismissed = null; // verdict dont l'encart a été écarté par « Continuer »
  const doneCorrections = new Set(); // corrections dont « Continuer » a retiré les marques (5.5)
  let infoOpen = false;
  let chosen = null; // commande cochée du quiz en cours
  let hintTier = null; // palier d'indice affiché ; null : le plus avancé des paliers ouverts
  let hintStep = null; // étape à laquelle `hintTier` se rapporte
  let confirming = false; // confirmation de « Recommencer » ouverte dans le pied du panneau
  let focusTitle = false; // après une remise à zéro : le focus revient sur la consigne
  let restartPending = false; // POST `restart` en cours : un second clic est ignoré
  let lastState = null;
  const uid = ++counter;
  const designateBlock = designation ? createDesignateBlock({ designation, onIntent }) : null;

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

  /**
   * « Ce qui l'aurait bloqué » (story 5.9, UX-DR8) : une ligne par barrière. Tous les textes viennent
   * du serveur : station livrée, le scénario est un lien ; sinon, l'étiquette en tirets, sans lien.
   */
  function blockersBlock(blockers) {
    const block = el("section", "step-explanation is-blockers", { "data-blockers": "" });
    const title = el("h3", "step-explanation-title");
    title.textContent = blockers.title_text;
    const list = el("ul", "blocker-list");
    for (const item of blockers.items) {
      const row = el("li", "blocker-item", { "data-barrier": item.barrier_id });
      const name = el("p", "blocker-name");
      name.textContent = `${item.label} · ${item.station_text}`;
      const reason = el("p", "blocker-reason");
      richText(reason, item.reason_text);
      row.append(name, reason);
      if (item.scenario) {
        const link = el("a", "blocker-scenario", { href: "/", "data-scenario": item.scenario.id });
        link.textContent = item.scenario.title_text;
        row.append(link);
      } else if (item.soon_text) {
        const soon = el("span", "blocker-soon is-dashed");
        soon.textContent = item.soon_text;
        row.append(soon);
      }
      list.append(row);
    }
    block.append(title, list);
    return block;
  }

  /** Ouvre un palier : l'onglet s'affiche tout de suite, le serveur confirme (ou refuse). */
  async function openHint(tier) {
    hintTier = tier;
    const ok = onIntent ? await onIntent("hint_open", { tier }) : false;
    if (!ok) {
      hintTier = null;
      if (lastState) render(lastState);
    }
  }

  /** Ouvre la confirmation en ligne de « Recommencer » et y met le focus (bouton le moins grave). */
  function askRestart() {
    if (restartPending) return;
    confirming = true;
    render(lastState);
    const cancel = root.querySelector('[data-action="restart-cancel"]');
    if (cancel) cancel.focus();
  }

  function cancelRestart() {
    confirming = false;
    render(lastState);
    const ask = root.querySelector('[data-action="restart-ask"]');
    if (ask) ask.focus();
  }

  async function confirmRestart() {
    // Garde synchrone : un double clic pendant l'envoi ne poste qu'un seul `restart`.
    if (restartPending) return;
    restartPending = true;
    confirming = false;
    focusTitle = true;
    let ok = false;
    try {
      ok = onIntent ? await onIntent("restart", {}) : false;
    } finally {
      restartPending = false;
    }
    if (!ok) focusTitle = false;
    if (lastState) render(lastState);
  }

  function notice(verdict, current) {
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
    const again = el("button", "btn", { type: "button", "data-action": "restart-ask" });
    again.textContent = RESTART_LABEL;
    again.addEventListener("click", askRestart);
    actions.append(again);
    // « Ouvrir un indice » : le premier palier non encore ouvert (le serveur dit s'il l'est).
    const upcoming = current && current.hints ? nextTier(current.hints) : null;
    if (upcoming) {
      const hint = el("button", "btn", { type: "button", "data-action": "open-hint" });
      hint.textContent = OPEN_HINT_LABEL;
      hint.addEventListener("click", () => openHint(upcoming.tier));
      actions.append(hint);
      bindAction(hint, upcoming.state === "locked" ? upcoming.condition_text : null);
    }
    card.append(actions);
    return card;
  }

  /**
   * Étape de désignation dont la correction est à lire : celle qu'on a rouverte, sinon celle qui
   * précède l'étape courante tant que « Continuer » ne l'a pas fermée (aussi après un rechargement).
   */
  function correctionOf(panel, shown, current) {
    if (shown.state === "done" && shown.correction) return { step: shown, reopened: true };
    if (shown !== current) return null;
    const prev = panel.steps[panel.steps.indexOf(current) - 1];
    if (prev && prev.state === "done" && prev.correction && !doneCorrections.has(prev.step_id)) {
      return { step: prev, reopened: false };
    }
    return null;
  }

  function render(state) {
    lastState = state;
    const panel = state.stepPanel;
    if (!panel || !panel.steps.length) {
      root.hidden = true;
      root.replaceChildren();
      if (designation) designation.setCorrection(null);
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

    const children = [...modeRow(panel), progress(panel, view)];
    // Bilan : le score du premier coup et les indices, lus dans `progress.json` par le serveur.
    if (panel.summary) {
      children.push(
        scoreSummary(panel.summary, {
          onNext(next) {
            openNext(next, { fetchImpl, assign: navigate }).catch((err) => onError && onError(err.message));
          },
          onCatalogue() {
            (navigate || ((path) => window.location.assign(path)))("/");
          },
          onRestart: askRestart,
        }),
      );
    }
    if (panel.content_changed) children.push(contentChangedNotice(panel.content_changed, askRestart));
    children.push(instruction);
    // Désignation (story 5.3) : le bloc ne se montre que sur l'étape courante.
    if (designateBlock && shown === current && current.designate) children.push(designateBlock.root);
    else if (designation) designation.disarm();
    // Indices par paliers de l'étape courante (UX-DR28) ; aucun compteur.
    if (shown === current && current.hints) {
      if (hintStep !== current.step_id) {
        hintStep = current.step_id;
        hintTier = null;
      }
      children.push(
        hintTabs(current.hints, {
          selected: hintTier ?? defaultTier(current.hints),
          onSelect(tier) {
            hintTier = tier;
            render(lastState);
          },
          onOpen: openHint,
        }),
      );
    }
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
      children.push(notice(verdict, current));
    }
    // L'explication suit la consigne : celle d'une étape terminée rouverte, ou celle de l'étape
    // qui vient d'être réussie (publiée par le serveur après la mise à jour des vues).
    let explained = shown.state === "done" ? shown : null;
    if (!explained && shown === current && verdict && verdict.status === "passed") {
      explained = byId.get(verdict.step_id) || null;
    }
    // Correction d'une désignation (story 5.5) : la liste, puis l'explication ; les vues portent les marques.
    // « Recommencer » reste le seul bouton, au pied (4.4) : confirmation en ligne et garde anti-double envoi.
    for (const step of panel.steps) if (!step.correction) doneCorrections.delete(step.step_id);
    const corrected = correctionOf(panel, shown, current);
    if (corrected) {
      const step = corrected.step;
      children.push(
        correctionBlock(step, {
          onSelect,
          onContinue: corrected.reopened
            ? null
            : () => {
                doneCorrections.add(step.step_id);
                render(lastState);
                const title = root.querySelector(".step-title");
                if (title) title.focus();
              },
        }),
      );
      if (designation) designation.setCorrection(step.correction);
    } else {
      if (designation) designation.setCorrection(null);
      if (explained && explained.explanation_text) children.push(explanationBlock(explained));
    }
    // Fin d'un scénario B : l'encart des barrières suit la correction (5.9).
    if (panel.blockers && panel.blockers.items && panel.blockers.items.length) {
      children.push(blockersBlock(panel.blockers));
    }
    // Pied du panneau : « Recommencer » et, une fois demandée, sa confirmation en ligne.
    children.push(
      restartFoot({
        confirming,
        onAsk: askRestart,
        onConfirm: confirmRestart,
        onCancel: cancelRestart,
      }),
    );
    const focusKey = focusKeyOf(document.activeElement);
    root.replaceChildren(...children);
    if (focusTitle && !String(state.engineState).startsWith("restor")) {
      focusTitle = false;
      const title = root.querySelector(".step-title");
      if (title) title.focus();
    } else if (focusKey) restoreFocus(focusKey);
  }

  // Le redessin remplace les nœuds : le focus qui était dans le panneau revient sur l'élément
  // équivalent (même segment, même bouton), sinon sur le titre de la consigne, jamais sur `body`.
  function focusKeyOf(active) {
    if (!active || active === root || !root.contains(active)) return null;
    if (active.dataset && active.dataset.step && active.classList.contains("step-segment")) {
      return `.step-segment[data-step="${active.dataset.step}"]`;
    }
    if (active.classList.contains("mode-info")) return ".mode-info";
    if (active.dataset && active.dataset.action && active.closest(".score-summary")) {
      return `.score-summary [data-action="${active.dataset.action}"]`;
    }
    if (active.dataset && active.dataset.action && active.closest(".restart-foot")) {
      return `.restart-foot [data-action="${active.dataset.action}"]`;
    }
    if (active.classList.contains("hint-tab")) return `.hint-tab[data-tier="${active.dataset.tier}"]`;
    if (active.classList.contains("quiz-radio")) return `.quiz-radio[value="${active.getAttribute("value")}"]`;
    if (active.classList.contains("quiz-run")) return ".quiz-run";
    const part = active.getAttribute && active.getAttribute("data-designate-focus");
    if (part) return `[data-designate-focus="${part}"]`;
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
      if (designation) {
        const panel = state.stepPanel;
        const step = panel && panel.steps.find((s) => s.step_id === panel.current_step_id);
        const active = step && step.designate ? step : null;
        designation.sync(
          active
            ? { stepId: active.step_id, slots: active.designate.slots, accept: active.designate.accept }
            : null,
        );
        designateBlock.update(state, active);
      }
      const changed =
        !lastState ||
        state.stepPanel !== lastState.stepPanel ||
        state.verdict !== lastState.verdict ||
        quizEngine(state) !== quizEngine(lastState);
      if (lastState && state.verdict !== lastState.verdict) shownId = null;
      if (state.restarted && !(lastState && lastState.restarted)) {
        focusTitle = true;
        confirming = false;
      }
      const focusDue = focusTitle && !String(state.engineState).startsWith("restor");
      if (changed || focusDue) render(state);
      else lastState = state; // rien à redessiner : le focus du panneau reste en place
      return statusFor(state);
    },
  };
}
