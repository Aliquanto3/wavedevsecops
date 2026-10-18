// Boutons d'action. Un bouton inactif porte aria-disabled et sa raison, en texte visible et relié
// (aria-describedby). Il reste focalisable ; son clic est neutralisé. Quand l'application ne
// répond plus, toutes les actions deviennent inactives avec la même raison.

export const OFFLINE_REASON = "WaveDevSecOps ne répond plus.";

const actions = new Map(); // bouton -> raison propre (null : actif)
let offline = false;
let counter = 0;

function reasonElement(button) {
  let element = button.nextElementSibling;
  if (!element || !element.classList.contains("btn-reason")) {
    element = document.createElement("span");
    element.className = "btn-reason";
    element.id = `reason-${++counter}`;
    button.after(element);
  }
  return element;
}

function refresh(button) {
  const reason = offline ? OFFLINE_REASON : actions.get(button);
  if (reason) {
    const element = reasonElement(button);
    element.textContent = reason;
    button.setAttribute("aria-disabled", "true");
    button.setAttribute("aria-describedby", element.id);
  } else {
    button.removeAttribute("aria-disabled");
    button.removeAttribute("aria-describedby");
    const element = button.nextElementSibling;
    if (element && element.classList.contains("btn-reason")) element.remove();
  }
}

/** Enregistre un bouton d'action ; `reason` non vide : inactif, avec cette raison. */
export function bindAction(button, reason = null) {
  if (!actions.has(button)) {
    button.addEventListener(
      "click",
      (event) => {
        if (button.getAttribute("aria-disabled") === "true") {
          event.preventDefault();
          event.stopImmediatePropagation();
        }
      },
      true,
    );
  }
  actions.set(button, reason);
  refresh(button);
}

export function setActionDisabled(button, reason) {
  bindAction(button, reason || null);
}

export function setOffline(value) {
  offline = value;
  for (const button of actions.keys()) refresh(button);
}
