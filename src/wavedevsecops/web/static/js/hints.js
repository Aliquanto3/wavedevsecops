// Indices par paliers (UX-DR28) : `hint-tabs` (Piste | Commande partielle | Solution). Le serveur
// décide de la disponibilité de chaque palier et écrit ses conditions et ses textes (AD-2) : ce
// module affiche l'état reçu et poste `hint_open`. Il garde seulement l'onglet affiché et la
// minuterie qui relit le panneau quand la solution se débloque (aucun décompte visible).
import { el, richText } from "./dom.js";

export const LOCK_ICON = "\u{1F512}";
export const OPEN_LABEL = "Ouvrir";
export const HINTS_LABEL = "Indices";
export const OPEN_HINT_LABEL = "Ouvrir un indice";
export const CLOSED_TEXT = "Cet indice n'est pas ouvert.";

let counter = 0;

/** Palier affiché par défaut : le plus avancé des paliers ouverts, sinon la piste. */
export function defaultTier(hints) {
  const open = hints.tiers.filter((t) => t.state === "open");
  return open.length ? open[open.length - 1].tier : 1;
}

/** Premier palier non encore ouvert, ou null quand les trois le sont. */
export function nextTier(hints) {
  return hints.tiers.find((t) => t.state !== "open") || null;
}

/**
 * `hint-tabs` : `role="tablist"` de trois onglets, un `tabpanel` pour le palier affiché.
 * Un onglet verrouillé montre un cadenas et sa condition, porte `aria-disabled="true"` et reste
 * focalisable ; un onglet disponible mais fermé s'ouvre au clic ; un onglet ouvert s'affiche.
 */
export function hintTabs(hints, { selected, onSelect, onOpen }) {
  const uid = ++counter;
  const root = el("section", "hint-tabs", { "aria-label": HINTS_LABEL, "data-zone": "hints" });
  const list = el("div", "hint-tablist", { role: "tablist", "aria-label": HINTS_LABEL });
  const tabs = [];
  for (const tier of hints.tiers) {
    const locked = tier.state === "locked";
    const tab = el("button", "hint-tab", {
      type: "button",
      role: "tab",
      id: `hint-tab-${uid}-${tier.tier}`,
      "data-tier": tier.tier,
      "data-state": tier.state,
      "aria-selected": String(tier.tier === selected),
      "aria-controls": `hint-panel-${uid}`,
      "aria-disabled": locked ? "true" : false,
      tabindex: tier.tier === selected ? "0" : "-1",
    });
    const label = el("span", "hint-tab-label");
    if (locked) {
      const lock = el("span", "hint-lock", { "aria-hidden": "true" });
      lock.textContent = LOCK_ICON;
      label.append(lock);
    }
    label.append(tier.label_text);
    tab.append(label);
    const sub = el("span", "hint-tab-sub");
    if (locked) sub.textContent = tier.condition_text;
    else if (tier.state === "available") sub.textContent = OPEN_LABEL;
    if (sub.textContent) tab.append(sub);
    tab.addEventListener("click", () => {
      if (locked) return;
      if (tier.state === "available") onOpen(tier.tier);
      else onSelect(tier.tier);
    });
    tab.addEventListener("keydown", (event) => {
      const at = tabs.indexOf(tab);
      let to = null;
      if (event.key === "ArrowRight") to = (at + 1) % tabs.length;
      else if (event.key === "ArrowLeft") to = (at - 1 + tabs.length) % tabs.length;
      else if (event.key === "Home") to = 0;
      else if (event.key === "End") to = tabs.length - 1;
      if (to === null) return;
      event.preventDefault();
      tabs[to].focus();
    });
    tabs.push(tab);
    list.append(tab);
  }
  const shown = hints.tiers.find((t) => t.tier === selected) || hints.tiers[0];
  const panel = el("div", "hint-panel", {
    role: "tabpanel",
    id: `hint-panel-${uid}`,
    "aria-labelledby": `hint-tab-${uid}-${shown.tier}`,
    tabindex: "0",
  });
  const text = el("p", `hint-text hint-text-${shown.tier}`);
  if (shown.state === "open") richText(text, shown.text || "");
  else text.textContent = CLOSED_TEXT;
  panel.append(text);
  root.append(list, panel);
  return root;
}
