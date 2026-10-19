// « Recommencer » (UX-DR40) : le bouton du pied du panneau, sa confirmation en ligne et l'encart
// « Scénario mis à jour ». Le serveur remet l'espace à zéro et garde le score du premier coup ;
// ce module ne pose que les libellés fixes et le déroulé de la confirmation.
import { el, richText } from "./dom.js";

export const RESTART_LABEL = "Recommencer";
export const CONFIRM_TEXT =
  "Remettre le scénario à son état initial ? Votre score du premier coup est conservé.";
export const CONFIRM_LABEL = "Remettre à zéro";
export const CANCEL_LABEL = "Annuler";
export const RESTARTED_TEXT = "Scénario remis à zéro.";
export const RESTARTING_TEXT = "Remise à zéro du scénario…";
export const UPDATED_TITLE = "Scénario mis à jour";
export const DIAGNOSTIC_LABEL = "Voir le diagnostic";
export const DIAGNOSTIC_PATH = "/diagnostic";

let counter = 0;

/** Pied du panneau : « Recommencer », ou sa confirmation en ligne une fois demandée. */
export function restartFoot({ confirming, onAsk, onConfirm, onCancel }) {
  const foot = el("div", "restart-foot", { "data-zone": "restart" });
  if (!confirming) {
    const ask = el("button", "btn btn-secondary", { type: "button", "data-action": "restart-ask" });
    ask.textContent = RESTART_LABEL;
    ask.addEventListener("click", onAsk);
    foot.append(ask);
    return foot;
  }
  const uid = ++counter;
  const group = el("div", "notice-card restart-confirm", {
    role: "group",
    "aria-labelledby": `restart-confirm-${uid}`,
  });
  const text = el("p", "restart-confirm-text", { id: `restart-confirm-${uid}` });
  text.textContent = CONFIRM_TEXT;
  const actions = el("div", "notice-actions");
  const cancel = el("button", "btn btn-secondary", { type: "button", "data-action": "restart-cancel" });
  cancel.textContent = CANCEL_LABEL;
  cancel.addEventListener("click", onCancel);
  const confirm = el("button", "btn btn-primary", { type: "button", "data-action": "restart-confirm" });
  confirm.textContent = CONFIRM_LABEL;
  confirm.addEventListener("click", onConfirm);
  actions.append(cancel, confirm);
  group.append(text, actions);
  foot.append(group);
  return foot;
}

/** Encart d'un contenu mis à jour de façon incompatible : le texte vient du serveur (AD-20). */
export function contentChangedNotice(changed, onAsk) {
  const uid = ++counter;
  const card = el("div", "notice-card notice-warning", {
    role: "group",
    "aria-labelledby": `content-changed-${uid}`,
  });
  const title = el("h3", "notice-title", { id: `content-changed-${uid}` });
  title.textContent = UPDATED_TITLE;
  const text = el("p", "notice-explanation");
  richText(text, changed.text);
  const actions = el("div", "notice-actions");
  const ask = el("button", "btn btn-primary", { type: "button", "data-action": "restart-ask" });
  ask.textContent = RESTART_LABEL;
  ask.addEventListener("click", onAsk);
  actions.append(ask);
  card.append(title, text, actions);
  return card;
}

/** Lien « Voir le diagnostic » sous une erreur de l'espace. */
export function diagnosticLink() {
  const link = el("a", "scenario-error-link", { href: DIAGNOSTIC_PATH });
  link.textContent = DIAGNOSTIC_LABEL;
  link.hidden = true;
  return link;
}
