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
export const NOT_ACCEPTED_TEXT = "Cette question n'attend pas de commit.";
export const SENDING_TEXT = "Réponse en cours d'envoi.";

export const LIST_LABEL = "Choisir dans la liste";
export const FILTER_LABEL = "Filtrer par nom, SHA ou chemin";
export const CHOSEN_TEXT = "choisi";
export const NO_MATCH_TEXT = "Aucun élément ne correspond à ce filtre.";
export const NO_DESIGNABLE_TEXT = "Aucun élément désignable pour l'instant.";
export const SHA_MIN = 7;
const ACTOR_NAMES = { agent: "Agent", colleague: "Collègue", learner: "Vous" };
const KIND_ICONS = { commit: "●", ref: "⑂", file: "▤", branch: "⑂", pr: "⇄", check: "✓", review: "✎" };
const GROUP_TITLES = { graph: "Graphe", staging: "Index", remote: "Distant" };

const registry = new WeakMap();

/**
 * Éléments désignables des vues, groupés par vue : `[{key, title, items: [{id, kind, label,
 * sha, search}]}]`. Le front ne décide de rien : il liste ce que la projection marque
 * `designable` (AD-2), dans l'ordre du dessin.
 */
export function collectDesignables(views) {
  const groups = [];
  const seen = new Set();
  const add = (key, item) => {
    if (!item || item.designable !== true || !item.element_id || seen.has(`${key}|${item.element_id}`)) return;
    seen.add(`${key}|${item.element_id}`);
    let group = groups.find((g) => g.key === key);
    if (!group) {
      group = { key, title: GROUP_TITLES[key] || key, items: [] };
      groups.push(group);
    }
    const id = String(item.element_id);
    const kind = id.split(":")[0];
    const sha = kind === "commit" ? String(item.sha || id.slice(7)) : "";
    const label =
      kind === "commit"
        ? `${item.short_sha || sha.slice(0, 7)} · ${item.subject || ""}`.trim()
        : item.name_text || item.path || item.title_text || item.a11y_name_text || shortId(id);
    group.items.push({ id, kind, label, sha, search: `${label} ${id} ${sha}`.toLowerCase() });
  };
  const v = views || {};
  const graph = v.graph || {};
  for (const node of graph.nodes || []) add("graph", node);
  for (const node of graph.nodes || []) for (const ref of node.refs || []) add("graph", ref);
  const staging = v.staging || {};
  for (const name of ["staged", "unstaged", "untracked"]) for (const item of staging[name] || []) add("staging", item);
  const remote = v.remote || {};
  for (const branch of remote.branches || []) add("remote", branch);
  for (const card of remote.pulls || []) {
    add("remote", card);
    for (const check of card.checks || []) add("remote", check);
    for (const entry of (card.review || {}).entries || []) add("remote", entry);
  }
  return groups;
}

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
  let accept = null; // types d'element_id acceptés par l'étape, null : inconnus
  let picks = new Map();
  let last = null; // dernière case remplie : un nouveau choix la remplace quand toutes sont pleines
  let button = null;
  let correction = null; // correction active (story 5.5) : le serveur l'a écrite, les vues la marquent
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
    /** Le type d'`element_id` (« commit », « ref »…) est-il attendu par l'étape ? */
    accepts(kind) {
      return !accept || accept.includes(kind);
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
      accept = next && Array.isArray(next.accept) ? next.accept : null;
      picks = new Map();
      last = null;
      armed = false;
      notify();
    },
    /** Correction dont les vues portent les marques ; null : aucune (story 5.5). */
    get correction() {
      return correction;
    },
    setCorrection(next) {
      const value = next || null;
      if (JSON.stringify(value) === JSON.stringify(correction)) return;
      correction = value;
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
  const shaPreview = el("p", "sha-preview", { role: "status" });
  const shaPlace = el("button", "btn btn-secondary sha-place", { type: "button", "data-designate-focus": "sha-place" });
  shaPlace.textContent = "Placer dans la case";
  shaPlace.hidden = true;
  shaRow.append(shaLabel, sha, shaHelp, shaPreview, shaPlace, shaError);

  // Liste filtrable (« Choisir dans la liste ▾ ») : tous les désignables des vues, au clavier.
  const listId = `designate-list-${uid}`;
  const listToggle = el("button", "btn btn-secondary designate-list-toggle", {
    type: "button",
    "aria-expanded": "false",
    "aria-controls": listId,
    "data-designate-focus": "list-toggle",
  });
  const listBox = el("div", "designate-list-box", { id: listId });
  listBox.hidden = true;
  const filterId = `designate-filter-${uid}`;
  const filterLabel = el("label", "designate-filter-label", { for: filterId });
  filterLabel.textContent = FILTER_LABEL;
  const filter = el("input", "designate-filter", {
    type: "text",
    id: filterId,
    autocomplete: "off",
    spellcheck: "false",
    "data-designate-focus": "filter",
  });
  const list = el("div", "designate-list", { "data-testid": "designate-list" });
  listBox.append(filterLabel, filter, list);
  let listOpen = false;
  function drawList() {
    listToggle.textContent = `${LIST_LABEL} ${listOpen ? "▴" : "▾"}`;
    listToggle.setAttribute("aria-expanded", String(listOpen));
    listBox.hidden = !listOpen;
    if (!listOpen) return;
    const needle = String(filter.value || "").trim().toLowerCase();
    const chosen = designation.pickedIds();
    const groups = collectDesignables(state ? state.views : null);
    const active = document.activeElement;
    const focusId = active && list.contains(active) ? active.getAttribute("data-element-id") : null;
    list.replaceChildren();
    let total = 0;
    let shown = 0;
    for (const group of groups) {
      const items = group.items.filter((item) => !needle || item.search.includes(needle));
      total += group.items.length;
      if (!items.length) continue;
      shown += items.length;
      const section = el("div", "designate-group", { "data-group": group.key });
      const heading = el("p", "designate-group-title");
      heading.textContent = group.title;
      const ul = el("ul", "designate-items");
      for (const item of items) {
        const isChosen = chosen.has(item.id);
        const button = el("button", `designate-item${isChosen ? " is-chosen" : ""}`, {
          type: "button",
          "data-element-id": item.id,
          "aria-pressed": String(isChosen),
        });
        const icon = el("span", "designate-item-icon", { "aria-hidden": "true" });
        icon.textContent = KIND_ICONS[item.kind] || "•";
        const name = el("span", "designate-item-label");
        name.textContent = item.label;
        button.append(icon, name);
        if (isChosen) {
          const mark = el("span", "designate-item-chosen");
          mark.textContent = CHOSEN_TEXT;
          button.append(mark);
        }
        button.addEventListener("click", () => {
          if (!designation.accepts(item.kind)) return;
          if (designation.pickedIds().has(item.id)) return;
          designation.pick(item.id, item.label);
          live.textContent = `${item.label} : choisi.`;
        });
        const li = el("li");
        li.append(button);
        ul.append(li);
      }
      section.append(heading, ul);
      list.append(section);
    }
    if (!shown) {
      const empty = el("p", "designate-list-empty");
      empty.textContent = total ? NO_MATCH_TEXT : NO_DESIGNABLE_TEXT;
      list.append(empty);
    }
    if (focusId) {
      const again = [...list.querySelectorAll("button")].find((b) => b.getAttribute("data-element-id") === focusId);
      if (again) again.focus();
    }
  }
  listToggle.addEventListener("click", () => {
    listOpen = !listOpen;
    drawList();
    if (listOpen) filter.focus();
  });
  filter.addEventListener("input", drawList);
  filter.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !listOpen || designation.armed) return;
    event.preventDefault();
    event.stopPropagation();
    listOpen = false;
    drawList();
    listToggle.focus();
  });
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

  let previewed = null; // {prefix, found} : dernier commit résolu pour le texte du champ
  let lookupSeq = 0;
  let debounce = null;
  const actorText = (actor) => (ACTOR_NAMES[actor] ? ` · ${ACTOR_NAMES[actor]}` : "");

  function clearFeedback() {
    shaError.textContent = "";
    shaPreview.textContent = "";
    shaPlace.hidden = true;
    previewed = null;
    sha.removeAttribute("aria-invalid");
    sha.setAttribute("aria-describedby", helpId);
  }

  /** Résout le texte du champ ; rend le commit (aperçu posé) ou null (erreur posée). */
  async function lookup(prefix) {
    const askedFor = designation.stepId;
    const seq = ++lookupSeq;
    const found = await designation.resolveSha(prefix);
    if (designation.stepId !== askedFor || seq !== lookupSeq || sha.value.trim() !== prefix) return null;
    if (found.ok && found.element_id && !designation.accepts(String(found.element_id).split(":")[0])) {
      found.ok = false;
      found.reason_text = NOT_ACCEPTED_TEXT;
    }
    clearFeedback();
    if (found.ok && found.element_id) {
      previewed = { prefix, found };
      shaPreview.textContent = `${found.short_sha} · ${found.subject}${actorText(found.actor)}`;
      shaPlace.hidden = false;
      return found;
    }
    sha.setAttribute("aria-invalid", "true");
    sha.setAttribute("aria-describedby", `${helpId} ${errId}`);
    shaError.textContent = found.reason_text || SHA_FAILED_TEXT;
    return null;
  }

  async function resolve() {
    const prefix = sha.value.trim();
    if (!prefix) return;
    const found = previewed && previewed.prefix === prefix ? previewed.found : await lookup(prefix);
    if (!found) return;
    designation.pick(found.element_id, `${found.short_sha} · ${found.subject}`);
    clearFeedback();
    sha.value = "";
  }
  shaPlace.addEventListener("click", resolve);
  sha.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    resolve();
  });
  sha.addEventListener("input", () => {
    clearFeedback();
    lookupSeq++;
    clearTimeout(debounce);
    const prefix = sha.value.trim();
    if (prefix.length < SHA_MIN) return; // en dessous de 7 caractères, pas de requête
    debounce = setTimeout(() => lookup(prefix), 250);
  });
  // Garde d'envoi : posée au clic, avant tout redessin, pour qu'un double clic n'envoie pas une
  // seconde réponse (refusée en 409). Elle tombe si l'envoi échoue ; acceptée, elle dure jusqu'au
  // changement d'étape ou au retour du moteur au repos après l'opération.
  let sending = null; // null, ou {step, sawBusy}

  submit.addEventListener("click", () => {
    if (sending || submit.getAttribute("aria-disabled") === "true" || !designation.complete()) return;
    const guard = { step: designation.stepId, sawBusy: false };
    sending = guard;
    refresh();
    Promise.resolve(onIntent && onIntent("answer_submit", designation.body())).then(
      (ok) => {
        if (ok === false && sending === guard) {
          sending = null;
          refresh();
        }
      },
      () => {
        if (sending === guard) {
          sending = null;
          refresh();
        }
      },
    );
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
    drawList();
    if (focusKey) {
      const again = root.querySelector(`[data-designate-focus="${focusKey}"]`);
      (again || button).focus();
    }
    let reason = null;
    if (sending) reason = SENDING_TEXT;
    else if (state && state.engineState !== "idle") reason = BUSY_TEXT;
    else if (!designation.complete()) reason = NOTHING_CHOSEN;
    bindAction(submit, reason);
  }

  root.append(question, button, listToggle, listBox, slotsBox, shaRow, submit, once, live);
  designation.subscribe(refresh);

  return {
    root,
    /** `step` : l'étape courante portant `designate`, ou null. */
    update(next, step) {
      state = next;
      if (sending) {
        if (!step || sending.step !== step.step_id) sending = null;
        else if (next.engineState !== "idle") sending.sawBusy = true;
        else if (sending.sawBusy) sending = null;
      }
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
