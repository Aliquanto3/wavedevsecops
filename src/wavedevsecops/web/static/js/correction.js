// Correction d'une désignation (story 5.5, UX-DR26, UX-DR8 variante correction). Le serveur corrige
// et écrit tous les textes (AD-2, AD-17 : `answer_corrected`, relue dans le panneau après un
// rechargement) ; ce module ne fait que poser des marques sur les éléments des vues et lister la
// correction dans le panneau. Il ne décide jamais si une réponse est juste.
import { shortId } from "./designation.js";
import { el, richText } from "./dom.js";

export const CHOICE_RIGHT_TEXT = "✓ Votre choix";
export const CHOICE_WRONG_TEXT = "✗ Votre choix";
export const EXPECTED_TEXT = "✓ Attendu";
export const EQUIVALENT_TEXT = "≡ Accepté aussi";
export const CORRECTION_TITLE = "Correction";
export const VALIDATED_SUFFIX = "validée";
export const SEE_IN_VIEWS_LABEL = "voir dans les vues";
export const CONTINUE_LABEL = "Continuer";

const KIND_TEXT = {
  "choice-right": CHOICE_RIGHT_TEXT,
  "choice-wrong": CHOICE_WRONG_TEXT,
  expected: EXPECTED_TEXT,
  equivalent: EQUIVALENT_TEXT,
};
const KIND_ORDER = ["choice-right", "choice-wrong", "expected", "equivalent"];

/** Marques par élément : `Map(element_id → [kind…])`, dans l'ordre choix, attendu, équivalent. */
export function marksOf(correction) {
  const marks = new Map();
  const add = (id, kind) => {
    if (!id) return;
    const kinds = marks.get(id) || [];
    if (!kinds.includes(kind)) kinds.push(kind);
    marks.set(id, kinds);
  };
  for (const slot of (correction && correction.slots) || []) {
    add(slot.element_id, slot.correct ? "choice-right" : "choice-wrong");
    add(slot.expected_element_id, "expected");
    for (const id of slot.accepted_element_ids || []) {
      if (id !== slot.expected_element_id) add(id, "equivalent");
    }
  }
  for (const kinds of marks.values()) kinds.sort((a, b) => KIND_ORDER.indexOf(a) - KIND_ORDER.indexOf(b));
  return marks;
}

function clearMarks(root) {
  for (const badge of [...root.querySelectorAll(".verdict-mark")]) badge.remove();
  for (const node of root.querySelectorAll(".has-verdict")) {
    node.classList.remove("has-verdict", "is-verdict-right", "is-verdict-wrong", "is-verdict-expected");
  }
  for (const node of root.querySelectorAll("[data-label-before]")) {
    node.setAttribute("aria-label", node.getAttribute("data-label-before"));
    node.removeAttribute("data-label-before");
  }
}

/**
 * Élément qui porte le nom accessible de `node` : lui-même s'il a un `aria-label`, sinon le bouton
 * nommé qui le contient (l'étiquette d'une ref dans un nœud du graphe), sinon aucun : le nom vient
 * alors du texte, qui contient déjà la marque.
 */
function namedOwner(node, root) {
  if (node.hasAttribute("aria-label")) return node;
  // Étiquette de ref du graphe : posée à côté du bouton de son commit (repo.js), elle est nommée
  // avec lui, comme quand elle était dedans.
  const refs = node.closest(".graph-refs");
  const commit = refs && refs.parentElement && refs.parentElement.querySelector("button[aria-label]");
  if (commit && root.contains(commit)) return commit; // le premier bouton de la rangée : le commit
  const owner = node.parentElement && node.parentElement.closest("button[aria-label]");
  return owner && root.contains(owner) ? owner : null;
}

/**
 * Pose les marques de la correction active sur les éléments désignables des vues (ceux qui portent
 * `data-designable` et `data-element-id` ou `data-designate-id`, comme `markDesignated`), et les
 * retire quand il n'y en a plus. Une vue l'appelle après chaque dessin. Le texte de la marque est
 * ajouté au nom accessible de l'élément : le lecteur d'écran lit le verdict avec l'élément.
 * Préséance : verdict > sélection > désignable > lié (CSS).
 */
export function markCorrection(root, designation) {
  clearMarks(root);
  const correction = designation.correction;
  if (!correction) return;
  // Une nouvelle désignation en cours (mode armé ou case remplie) l'emporte sur la correction de la
  // précédente : ses marques masqueraient la sélection et s'ajouteraient au nom de l'élément choisi.
  if (designation.armed || designation.pickedIds().size) return;
  const marks = marksOf(correction);
  const named = new Map(); // élément nommé → textes à ajouter à son nom accessible
  for (const node of root.querySelectorAll("[data-designable]")) {
    const id = node.getAttribute("data-designate-id") || node.getAttribute("data-element-id");
    const kinds = marks.get(id);
    if (!kinds) continue;
    node.classList.add("has-verdict");
    if (kinds.includes("choice-right")) node.classList.add("is-verdict-right");
    if (kinds.includes("choice-wrong")) node.classList.add("is-verdict-wrong");
    if (kinds.includes("expected") || kinds.includes("equivalent")) node.classList.add("is-verdict-expected");
    const texts = kinds.map((kind) => KIND_TEXT[kind]);
    const owner = namedOwner(node, root);
    if (owner) {
      const said = owner === node ? texts.join(", ") : `${(node.textContent || "").trim()} : ${texts.join(", ")}`;
      named.set(owner, [...(named.get(owner) || []), said]);
    }
    for (const kind of kinds) {
      const badge = el("span", `verdict-mark is-${kind}`, { "data-verdict": kind });
      badge.textContent = KIND_TEXT[kind];
      node.append(badge);
    }
  }
  for (const [owner, said] of named) {
    const before = owner.getAttribute("aria-label");
    owner.setAttribute("data-label-before", before);
    owner.setAttribute("aria-label", `${before} — ${said.join(" ; ")}`);
  }
}

function nameOf(slot, id) {
  return (slot.element_texts && slot.element_texts[id]) || shortId(id);
}

function seeInViews(slot, id, onSelect) {
  const button = el("button", "element-link correction-see", {
    type: "button",
    "data-element-id": id,
    "aria-label": `${SEE_IN_VIEWS_LABEL} : ${nameOf(slot, id)}`,
  });
  button.textContent = SEE_IN_VIEWS_LABEL;
  button.addEventListener("click", () => onSelect && onSelect(id));
  return button;
}

function listItem(slot, id, kind, onSelect) {
  const item = el("li", `correction-item is-${kind}`);
  const tag = el("span", `verdict-mark is-${kind}`, { "data-verdict": kind });
  tag.textContent = KIND_TEXT[kind];
  const code = el("code", "answer-id");
  code.textContent = shortId(id);
  const name = el("span", "answer-text");
  name.textContent = nameOf(slot, id);
  item.append(tag, code, name, seeInViews(slot, id, onSelect));
  return item;
}

/**
 * Case validée : « <intitulé> · validée », le choix de l'apprenant, sans ✕ (la réponse est
 * définitive), puis la phrase de correction écrite par le serveur.
 */
function validatedSlot(slot, onSelect) {
  const box = el("div", "answer-slot is-filled is-validated", { "data-slot": slot.slot_id });
  const label = el("span", "answer-label");
  label.textContent = `${slot.label_text || "Votre réponse"} · ${VALIDATED_SUFFIX}`;
  const chip = el("span", "answer-chip");
  const mark = el("span", `verdict-mark is-${slot.correct ? "choice-right" : "choice-wrong"}`);
  mark.textContent = slot.correct ? CHOICE_RIGHT_TEXT : CHOICE_WRONG_TEXT;
  const code = el("code", "answer-id");
  code.textContent = shortId(slot.element_id);
  const text = el("span", "answer-text");
  text.textContent = nameOf(slot, slot.element_id);
  chip.append(code, text, mark);
  const says = el("p", "correction-text");
  richText(says, slot.text);
  const list = el("ul", "correction-list");
  list.append(listItem(slot, slot.expected_element_id, "expected", onSelect));
  for (const id of slot.accepted_element_ids || []) {
    if (id !== slot.expected_element_id) list.append(listItem(slot, id, "equivalent", onSelect));
  }
  box.append(label, chip, says, list);
  return box;
}

/**
 * Bloc `step-explanation` (variante correction) : le résumé, chaque case validée avec l'attendu et
 * les équivalents (chacun « voir dans les vues », que la réponse soit juste ou non), puis
 * l'explication de l'étape (ordre fixe : correction puis explication, AD-1).
 * `onContinue` (nul si la correction est relue sur une étape rouverte) ferme les marques.
 * « Recommencer » n'est pas ici : c'est le bouton du pied du panneau (4.4), avec sa confirmation.
 */
export function correctionBlock(step, { onSelect, onContinue } = {}) {
  const correction = step.correction;
  const block = el("section", "step-explanation is-correction", {
    "data-step": step.step_id,
    "data-correct": String(Boolean(correction.correct)),
  });
  const title = el("h3", "step-explanation-title");
  title.textContent = CORRECTION_TITLE;
  block.append(title);
  if (correction.summary_text) {
    const summary = el("p", "correction-summary");
    richText(summary, correction.summary_text);
    block.append(summary);
  }
  for (const slot of correction.slots || []) block.append(validatedSlot(slot, onSelect));
  if (step.explanation_text) {
    const text = el("p", "step-explanation-text");
    richText(text, step.explanation_text);
    block.append(text);
  }
  if (onContinue) {
    const actions = el("div", "notice-actions");
    const next = el("button", "btn btn-primary", { type: "button", "data-action": "continue" });
    next.textContent = CONTINUE_LABEL;
    next.addEventListener("click", onContinue);
    actions.append(next);
    block.append(actions);
  }
  return block;
}
