// Explication attachée aux éléments (story 2.10, NFR-13, UX `explain-popover`).
//
// Le « i » suit un commit, une ref, un fichier, une PR, un check, une revue ou une sortie d'outil.
// Il s'ouvre au clic, à Entrée ou à Espace, jamais au seul survol ; Échap le ferme et rend le focus
// au « i ». Le texte vient de `content/explanations.yaml` (`GET /api/explanations`), par la clé
// `explain_ref` que la projection porte : le front n'écrit aucune explication.
//
// Les « i » sont posés après coup à côté des éléments déjà dessinés (un bouton ne contient pas un
// autre bouton) ; ils ne sont pas dans la tabulation, les flèches de la vue les atteignent.
import { el, richText } from "./dom.js";

export const UNAVAILABLE_TITLE = "Explication indisponible";
export const UNAVAILABLE_TEXT = "L'explication de cet élément n'est pas disponible pour le moment.";
export const LINKS_LABEL = "Voir les éléments liés";
export const CLOSE_LABEL = "Fermer";
export const NO_LINKS_TEXT = "Aucun élément lié pour l'instant.";
export const triggerLabel = (name) => `Expliquer ${name}`;
const EXPLAINABLE_CLASSES = ["diff-file-header", "tool-output"];
let counter = 0;

function explainable(node) {
  if (node.classList.contains("explain-trigger") || node.classList.contains("terminal-link")) return false;
  return node.tagName === "BUTTON" || EXPLAINABLE_CLASSES.some((name) => node.classList.contains(name));
}

export function installExplain(root, { store, linking, selection, fetchImpl, grid, nodesOf, observeWith }) {
  const fetcher = fetchImpl || ((...args) => fetch(...args));
  let catalogue = null; // Promise du catalogue, relu une fois
  const decorated = new WeakSet();
  let current = null; // { trigger, popover, id }

  function entries() {
    if (!catalogue) {
      catalogue = (async () => {
        try {
          const response = await fetcher("/api/explanations", { credentials: "same-origin" });
          if (!response.ok) return {};
          return (await response.json()).entries || {};
        } catch (err) {
          return {};
        }
      })();
    }
    return catalogue;
  }

  function keyOf(node) {
    const id = node.getAttribute("data-element-id");
    return node.getAttribute("data-explain-ref") || (id && linking.explainOf(id)) || "";
  }

  function nameOf(node, id) {
    return linking.nameOf(id) || node.getAttribute("aria-label") || id;
  }

  /** Pose un « i » à côté de chaque élément expliqué qui n'en a pas encore. */
  function decorate() {
    if (current && !current.trigger.isConnected) close(false);
    for (const node of nodesOf()) {
      if (decorated.has(node) || !node.hasAttribute("data-element-id") || !explainable(node)) continue;
      const key = keyOf(node);
      if (!key) continue;
      decorated.add(node);
      const id = node.getAttribute("data-element-id");
      const button = el("button", "explain-trigger", {
        type: "button",
        tabindex: "-1",
        "aria-label": triggerLabel(nameOf(node, id)),
        "aria-haspopup": "dialog",
        "aria-expanded": "false",
        "data-explain-for": id,
        "data-explain-ref": key,
      });
      button.textContent = "i";
      button.addEventListener("click", (event) => {
        event.stopPropagation(); // le « i » n'est pas une sélection de l'élément
        if (current && current.trigger === button) close(true);
        else open(button);
      });
      if (node.classList.contains("tool-output")) {
        node.classList.add("explain-host");
        node.prepend(button);
      } else {
        if (node.parentNode) node.parentNode.classList.add("explain-host");
        node.after(button);
      }
    }
  }

  /** Éléments liés à `id` que l'apprenant peut nommer (le serveur, sinon l'étiquette de la vue). */
  function linkedItems(id) {
    const labels = new Map();
    for (const node of nodesOf()) {
      const other = node.getAttribute("data-element-id") || node.getAttribute("data-link");
      if (other && !labels.has(other)) labels.set(other, node.getAttribute("aria-label") || "");
    }
    const items = [];
    for (const other of linking.linksOf(id)) {
      const name = linking.nameOf(other) || labels.get(other);
      if (name && !items.some((item) => item.name === name)) items.push({ id: other, name });
    }
    return items;
  }

  function focusElement(id) {
    for (const node of nodesOf()) {
      if (node.getAttribute("data-element-id") === id && node.tagName === "BUTTON") {
        node.focus();
        return;
      }
    }
    for (const node of nodesOf()) {
      if (node.getAttribute("data-element-id") === id) {
        node.focus?.();
        return;
      }
    }
  }

  function place(popover, trigger) {
    const rect = trigger.getBoundingClientRect ? trigger.getBoundingClientRect() : {};
    const width = (globalThis.window && window.innerWidth) || 1280;
    const height = (globalThis.window && window.innerHeight) || 800;
    const left = Math.max(8, Math.min(rect.left || 8, width - 440));
    const top = Math.max(8, Math.min((rect.bottom || 0) + 6, height - 160));
    popover.style.left = `${left}px`;
    popover.style.top = `${top}px`;
  }

  async function open(button) {
    close(false);
    const id = button.getAttribute("data-explain-for");
    const key = button.getAttribute("data-explain-ref");
    counter += 1;
    const titleId = `explain-title-${counter}`;
    const popover = el("div", "explain-popover", {
      role: "dialog",
      "aria-labelledby": titleId,
      tabindex: "-1",
      "data-explain-ref": key,
    });
    const title = el("h3", "explain-title", { id: titleId });
    const body = el("p", "explain-body");
    popover.append(title, body);
    current = { trigger: button, popover, id };
    button.setAttribute("aria-expanded", "true");
    const all = await entries();
    if (!current || current.popover !== popover) return; // fermé ou remplacé pendant la lecture
    const entry = all[key];
    title.textContent = entry ? entry.title_text : UNAVAILABLE_TITLE;
    richText(body, entry ? entry.body_text : UNAVAILABLE_TEXT);

    const items = linkedItems(id);
    const toggle = el("button", "explain-links-toggle", {
      type: "button",
      "aria-expanded": "false",
    });
    toggle.textContent = LINKS_LABEL;
    const list = el("ul", "explain-links", { "aria-label": LINKS_LABEL });
    list.hidden = true;
    if (items.length === 0) {
      const none = el("li", "explain-links-none");
      none.textContent = NO_LINKS_TEXT;
      list.append(none);
    }
    for (const item of items) {
      const li = el("li");
      const pick = el("button", "explain-link", { type: "button", "data-link-id": item.id });
      pick.textContent = item.name;
      pick.addEventListener("click", () => {
        selection.set(item.id);
        close(false);
        focusElement(item.id);
      });
      li.append(pick);
      list.append(li);
    }
    toggle.addEventListener("click", () => {
      list.hidden = !list.hidden;
      toggle.setAttribute("aria-expanded", String(!list.hidden));
    });
    const closeButton = el("button", "explain-close", { type: "button" });
    closeButton.textContent = CLOSE_LABEL;
    closeButton.addEventListener("click", () => close(true));
    const actions = el("div", "explain-actions");
    actions.append(toggle, closeButton);
    popover.append(actions, list);

    popover.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation(); // Échap ne ferme que le popover (UX : d'abord le popover)
        close(true);
        return;
      }
      if (event.key !== "Tab") return;
      const stops = [...popover.querySelectorAll("button")].filter((b) => !b.closest?.("[hidden]"));
      const at = stops.indexOf(event.target);
      const leaving = event.shiftKey ? at <= 0 : at === stops.length - 1;
      if (leaving) {
        event.preventDefault();
        close(true);
      }
    });
    document.body.append(popover); // hors de la disposition, comme le résumé lu au focus
    place(popover, button);
    popover.focus();
  }

  /** Ferme le popover ; `returnFocus` rend le focus au « i » (Échap, bouton Fermer). */
  function close(returnFocus) {
    if (!current) return;
    const { trigger, popover } = current;
    current = null;
    popover.remove();
    trigger.setAttribute("aria-expanded", "false");
    if (returnFocus && trigger.isConnected) trigger.focus();
  }

  document.addEventListener("click", (event) => {
    if (!current) return;
    const target = event.target;
    if (current.popover.contains(target) || current.trigger.contains(target)) return;
    close(false);
  });

  const unsubscribe = linking.subscribe(() => observeWith());
  decorate();
  return {
    decorate,
    close,
    get open() {
      return current;
    },
    catalogue: entries,
    destroy() {
      unsubscribe();
      close(false);
    },
  };
}
