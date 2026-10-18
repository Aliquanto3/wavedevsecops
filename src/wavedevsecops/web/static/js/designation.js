// Désignation dans les vues (story 5.3, UX-DR26) : le mode « Désigner dans les vues », la case
// `answer-slot`, le champ SHA et « Valider ma réponse ». Le serveur dit quels éléments sont
// désignables (`designable` dans les vues, AD-2) et corrige la réponse ; ce module ne garde que ce
// que l'apprenant a choisi et le mode armé. Une vue s'ouvre à la désignation en posant sur ses
// éléments `data-designable="true"` et `data-element-id` (ou `data-designate-id`).
import { bindAction } from "./actions.js";
import { el, richText } from "./dom.js";

export const DESIGNATE_LABEL = "Désigner dans les vues";
export const ARMED_LABEL = "Désignation active · Échap pour quitter";
export const ARMED_ANNOUNCE = "Désignation active. Choisissez un élément des vues, Échap pour quitter.";
export const DISARMED_ANNOUNCE = "Désignation désactivée.";
export const EMPTY_SLOT_TEXT = "Aucun élément choisi. Armez la désignation puis cliquez un élément des vues.";
export const SHA_LABEL = "Ou saisir un SHA";
export const SHA_HELP = "7 caractères au moins, résolus dans le bac à sable.";
export const SUBMIT_LABEL = "Valider ma réponse";
export const ONCE_TEXT = "1 seul essai";
export const NOTHING_CHOSEN = "Choisissez d'abord un élément.";
export const BUSY_TEXT = "Une action est en cours.";
export const SHA_FAILED_TEXT = "Le SHA n'a pas pu être résolu. Réessayez.";

const registry = new WeakMap();

/** Libellé d'une case d'après l'`element_id` : la forme courte d'un commit (7 caractères). */
export function shortId(elementId) {
  const [kind, ...rest] = String(elementId).split(":");
  const value = rest.join(":");
  return kind === "commit" ? value.slice(0, 7) : value || String(elementId);
}

/**
 * État de la désignation d'un espace : mode armé, choix par case (`slot_id` → `{id, label}`) et
 * étape concernée. Partagé par le panneau Scénario et les vues, comme la sélection.
 */
export function designationFor(store) {
  if (registry.has(store)) return registry.get(store);
  let armed = false;
  let stepId = null;
  let slots = []; // [{slot_id, label_text}] de l'étape courante
  let picks = new Map();
  let last = null; // dernière case remplie : un nouveau choix la remplace quand toutes sont pleines
  let button = null;
  const listeners = new Set();
  const notify = () => {
    for (const listener of [...listeners]) listener();
  };
  const designation = {
    get armed() {
      return armed;
    },
    get stepId() {
      return stepId;
    },
    get slots() {
      return slots;
    },
    pickOf(slotId) {
      return picks.get(slotId) || null;
    },
    pickedIds() {
      return new Set([...picks.values()].map((pick) => pick.id));
    },
    /** Suit l'étape courante : un autre identifiant (ou aucune désignation) remet tout à zéro. */
    sync(next) {
      const nextId = next ? next.stepId : null;
      if (nextId === stepId) return;
      stepId = nextId;
      slots = next ? next.slots : [];
      picks = new Map();
      last = null;
      armed = false;
      notify();
    },
    setButton(node) {
      button = node;
    },
    focusButton() {
      if (button) button.focus();
    },
    arm() {
      if (armed || !stepId) return;
      armed = true;
      notify();
    },
    disarm() {
      if (!armed) return;
      armed = false;
      notify();
    },
    toggle() {
      if (armed) designation.disarm();
      else designation.arm();
    },
    /** Place un élément dans la première case vide, sinon remplace la dernière remplie. */
    pick(id, label) {
      if (!stepId || !slots.length || !id) return;
      const target =
        slots.find((slot) => !picks.has(slot.slot_id)) ||
        slots.find((slot) => slot.slot_id === last) ||
        slots[0];
      picks.set(target.slot_id, { id, label: label || shortId(id) });
      last = target.slot_id;
      notify();
    },
    clear(slotId) {
      if (!picks.delete(slotId)) return;
      notify();
    },
    complete() {
      return slots.length > 0 && slots.every((slot) => picks.has(slot.slot_id));
    },
    body() {
      return { step_id: stepId, slots: slots.map((slot) => picks.get(slot.slot_id).id) };
    },
    /** Résout un SHA abrégé (lecture seule : ne consomme pas l'essai). Rend `{ok, ...}`. */
    async resolveSha(prefix) {
      try {
        const response = await globalThis.fetch(
          `/api/ws/${encodeURIComponent(store.state.workspaceId)}/resolve_sha?prefix=${encodeURIComponent(prefix)}`,
          { credentials: "same-origin", cache: "no-store" },
        );
        const data = await response.json();
        return { ok: response.ok, ...data };
      } catch (err) {
        return { ok: false, reason_text: SHA_FAILED_TEXT };
      }
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
  registry.set(store, designation);
  return designation;
}

/** Texte du choix : le nom accessible écrit par le serveur, sinon le contenu de l'élément. */
function labelOf(node) {
  return (
    node.getAttribute("data-designate-label") ||
    node.getAttribute("aria-label") ||
    (node.textContent || "").trim()
  );
}

/**
 * Branche la désignation sur la racine de l'espace : en mode armé, un clic (ou Entrée, qui en
 * produit un) sur un élément désignable le place dans la case sans rien sélectionner ; Échap
 * désarme sans vider la case et rend le focus à `designate-button`. Désarmé, rien n'est capté :
 * le clic ne sert qu'aux correspondances.
 */
export function installDesignation(root, designation) {
  const sync = () => {
    if (designation.armed) root.classList.add("is-designating");
    else root.classList.remove("is-designating");
  };
  designation.subscribe(sync);
  sync();
  root.addEventListener(
    "click",
    (event) => {
      if (!designation.armed || !event.target.closest) return;
      const node = event.target.closest('[data-designable="true"]');
      if (!node) return;
      const id = node.getAttribute("data-designate-id") || node.getAttribute("data-element-id");
      if (!id) return;
      event.preventDefault();
      event.stopPropagation();
      designation.pick(id, labelOf(node));
    },
    true,
  );
  root.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !designation.armed) return;
    event.preventDefault();
    event.stopPropagation(); // l'Échap du mode ne ferme ni ne replie rien d'autre
    designation.disarm();
    designation.focusButton();
  });
}

/** Marque d'un contour plein les éléments déjà choisis (à la place du pointillé). */
export function markDesignated(root, designation) {
  const chosen = designation.pickedIds();
  for (const node of root.querySelectorAll('[data-designable="true"]')) {
    const id = node.getAttribute("data-designate-id") || node.getAttribute("data-element-id");
    if (chosen.has(id)) node.classList.add("is-designated");
    else node.classList.remove("is-designated");
  }
}

let counter = 0;

/**
 * Bloc de désignation du panneau Scénario : question, bouton, cases, champ SHA, validation.
 * Le nœud est créé une fois et se met à jour seul (`update(state)`), pour que la saisie du SHA et
 * le focus survivent aux redessins du panneau.
 */
export function createDesignateBlock({ designation, onIntent }) {
  const uid = ++counter;
  const root = el("section", "designate-block", { "aria-label": "Désignation", "data-zone-part": "designate" });
  const question = el("p", "designate-question");
  const button = el("button", "btn btn-secondary designate-button", {
    type: "button",
    "aria-pressed": "false",
    "data-designate-focus": "button",
  });
  const slotsBox = el("div", "designate-slots");
  const shaId = `sha-field-${uid}`;
  const helpId = `sha-help-${uid}`;
  const errId = `sha-error-${uid}`;
  const onceId = `designate-once-${uid}`;
  const shaRow = el("div", "sha-row");
  const shaLabel = el("label", "sha-label", { for: shaId });
  shaLabel.textContent = SHA_LABEL;
  const sha = el("input", "sha-field", {
    type: "text",
    id: shaId,
    autocomplete: "off",
    spellcheck: "false",
    "aria-describedby": helpId,
    "data-designate-focus": "sha",
  });
  const shaHelp = el("p", "sha-help", { id: helpId });
  shaHelp.textContent = SHA_HELP;
  const shaError = el("p", "sha-error", { id: errId, role: "alert" });
  shaRow.append(shaLabel, sha, shaHelp, shaError);
  const submit = el("button", "btn btn-primary designate-submit", {
    type: "button",
    "aria-describedby": onceId,
    "data-designate-focus": "submit",
  });
  submit.textContent = SUBMIT_LABEL;
  const once = el("p", "designate-once", { id: onceId });
  once.textContent = ONCE_TEXT;
  const live = el("p", "visually-hidden designate-live", { role: "status" });
  button.addEventListener("click", () => {
    designation.toggle();
  });
  designation.setButton(button);

  async function resolve() {
    const prefix = sha.value.trim();
    if (!prefix) return;
    const found = await designation.resolveSha(prefix);
    if (found.ok && found.element_id) {
      shaError.textContent = "";
      sha.removeAttribute("aria-invalid");
      sha.removeAttribute("aria-describedby");
      sha.setAttribute("aria-describedby", helpId);
      designation.pick(found.element_id, `${found.short_sha} · ${found.subject}`);
      sha.value = "";
    } else {
      sha.setAttribute("aria-invalid", "true");
      sha.setAttribute("aria-describedby", `${helpId} ${errId}`);
      shaError.textContent = found.reason_text || SHA_FAILED_TEXT;
    }
  }
  sha.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    resolve();
  });
  sha.addEventListener("input", () => {
    shaError.textContent = "";
    sha.removeAttribute("aria-invalid");
    sha.setAttribute("aria-describedby", helpId);
  });
  submit.addEventListener("click", () => {
    if (submit.getAttribute("aria-disabled") === "true" || !designation.complete()) return;
    onIntent("answer_submit", designation.body());
  });

  let wasArmed = false;
  let drawnStep = null;
  let state = null;

  function drawSlots() {
    slotsBox.replaceChildren();
    for (const slot of designation.slots) {
      const pick = designation.pickOf(slot.slot_id);
      const box = el("div", `answer-slot${pick ? " is-filled" : ""}`, { "data-slot": slot.slot_id });
      const label = el("span", "answer-label");
      label.textContent = slot.label_text;
      box.append(label);
      if (pick) {
        const chip = el("span", "answer-chip");
        const code = el("code", "answer-id");
        code.textContent = shortId(pick.id);
        const text = el("span", "answer-text");
        text.textContent = pick.label;
        const clear = el("button", "answer-clear", {
          type: "button",
          "aria-label": `Vider la case ${slot.label_text}`,
          "data-designate-focus": `clear-${slot.slot_id}`,
        });
        clear.textContent = "✕";
        clear.addEventListener("click", () => {
          designation.clear(slot.slot_id);
          live.textContent = "Case vidée.";
        });
        chip.append(code, text, clear);
        box.append(chip);
      } else {
        const help = el("span", "answer-help");
        help.textContent = EMPTY_SLOT_TEXT;
        box.append(help);
      }
      slotsBox.append(box);
    }
  }

  function refresh() {
    const armed = designation.armed;
    if (armed !== wasArmed) {
      live.textContent = armed ? ARMED_ANNOUNCE : DISARMED_ANNOUNCE; // bouton, Échap ou changement d'étape
      wasArmed = armed;
    }
    button.textContent = armed ? ARMED_LABEL : DESIGNATE_LABEL;
    button.setAttribute("aria-pressed", String(armed));
    if (armed) button.classList.add("is-armed");
    else button.classList.remove("is-armed");
    const active = document.activeElement;
    const focusKey = active && root.contains(active) ? active.getAttribute("data-designate-focus") : null;
    drawSlots();
    if (focusKey) {
      const again = root.querySelector(`[data-designate-focus="${focusKey}"]`);
      (again || button).focus();
    }
    let reason = null;
    if (state && state.engineState !== "idle") reason = BUSY_TEXT;
    else if (!designation.complete()) reason = NOTHING_CHOSEN;
    bindAction(submit, reason);
  }

  root.append(question, button, slotsBox, shaRow, submit, once, live);
  designation.subscribe(refresh);

  return {
    root,
    /** `step` : l'étape courante portant `designate`, ou null. */
    update(next, step) {
      state = next;
      const sameStep = step && drawnStep === step.step_id;
      if (step && !sameStep) {
        richText(question, step.designate.question_text);
        drawnStep = step.step_id;
      }
      if (!step) drawnStep = null;
      refresh();
    },
  };
}
