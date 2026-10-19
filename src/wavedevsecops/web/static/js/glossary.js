// Vocabulaire de la chaîne (Story 9.4). Les termes, leurs définitions, leurs barrières et le scénario
// qui les fait jouer viennent du serveur (`GET /api/glossary`, `content/glossary.yaml`, AD-2) : le
// front n'invente aucun texte. Ce module sert la page Vocabulaire et les `glossary-term` des
// explications.
import { el, richText } from "./dom.js";

const TERM_MARK = /\[\[([a-z0-9-]+)\|([^\]]+)\]\]/g;

/** Vocabulaire du serveur ; `{ ui: null, terms: [] }` s'il manque (jamais d'exception). */
export async function loadGlossary(fetcher = (...args) => fetch(...args)) {
  try {
    const response = await fetcher("/api/glossary", { cache: "no-store", credentials: "same-origin" });
    if (!response.ok) return { ui: null, terms: [] };
    const body = await response.json();
    return { ui: body.ui || null, terms: Array.isArray(body.terms) ? body.terms : [] };
  } catch (err) {
    return { ui: null, terms: [] };
  }
}

// La carte de la chaîne d'un espace ouvert s'enregistre ici : « Voir la barrière » la sélectionne
// quand la barrière y figure (l'état courant), sinon l'appelant affiche le détail lui-même.
const showers = new Set();

export function registerBarrierShower(shower) {
  showers.add(shower);
  return () => showers.delete(shower);
}

/** Sélectionne la barrière dans la carte ouverte ; faux si aucune carte ne la porte. */
export function showBarrier(id) {
  for (const shower of showers) if (shower(id)) return true;
  return false;
}

/** Détail d'une barrière : son nom, sa station, puis le scénario qui la joue, ou « à venir ». */
export function barrierDetail(term, ui) {
  const box = el("div", "glossary-barrier", { "data-barrier": term.barrier.id });
  const title = el("p", "glossary-barrier-title");
  title.textContent = `${ui.barrier_title} : ${term.barrier.label} (${term.barrier.station_text})`;
  box.append(title);
  const play = el("p", "glossary-barrier-play");
  if (term.scenario) {
    const link = el("a", "glossary-scenario-link", { href: "/", "data-scenario": term.scenario.id });
    link.textContent = term.scenario.play_text;
    play.append(link);
  } else {
    play.classList.add("is-soon");
    play.textContent = ui.soon_text;
  }
  box.append(play);
  return box;
}

/** Écrit `text` dans `parent` : accents graves en `<code>`, `[[id|texte]]` en `glossary-term`. */
export function termText(parent, text, byId, onTerm) {
  const nodes = [];
  let last = 0;
  const plain = (segment) => {
    if (segment) nodes.push(...richText(el("span"), segment).childNodes);
  };
  for (const match of text.matchAll(TERM_MARK)) {
    plain(text.slice(last, match.index));
    const term = byId.get(match[1]);
    if (term) {
      const button = el("button", "glossary-term", {
        type: "button",
        "aria-haspopup": "dialog",
        "data-term": term.id,
      });
      button.textContent = match[2];
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        onTerm(term, button);
      });
      nodes.push(button);
    } else {
      nodes.push(document.createTextNode(match[2]));
    }
    last = match.index + match[0].length;
  }
  plain(text.slice(last));
  parent.replaceChildren(...nodes);
  return parent;
}

function buildEntry(term, ui) {
  const entry = el("li", "glossary-entry", { "data-term": term.id });
  const nameId = `glossary-name-${term.id}`;
  const heading = el("h2", "glossary-name", { id: nameId });
  heading.textContent = term.term_text;
  if (term.named_only) {
    const tag = el("span", "named-only-tag");
    tag.textContent = ui.named_only_text;
    heading.append(" ", tag);
  }
  const definition = el("p", "glossary-definition");
  definition.textContent = term.definition_text;
  entry.append(heading, definition);
  if (term.barrier && !term.named_only) {
    const detailId = `glossary-barrier-${term.id}`;
    const see = el("button", "glossary-see", {
      type: "button",
      "aria-expanded": "false",
      "aria-controls": detailId,
      "aria-describedby": nameId,
    });
    see.textContent = ui.see_text;
    const region = el("div", "glossary-detail", { id: detailId, "aria-live": "polite" });
    see.addEventListener("click", () => {
      const open = see.getAttribute("aria-expanded") === "true";
      see.setAttribute("aria-expanded", String(!open));
      region.replaceChildren(...(open ? [] : [barrierDetail(term, ui)]));
    });
    entry.append(see, region);
  } else if (term.trace_text) {
    const trace = el("p", "glossary-trace");
    trace.textContent = term.trace_text;
    entry.append(trace);
    // Avec un espace de station ouvert, le serveur donne le lien ; sans espace, une phrase et jamais
    // un lien mort (story 9.6).
    const target = term.trace && term.trace.link;
    if (target) {
      const link = el("a", "glossary-trace-link", { href: target.href });
      link.textContent = target.text;
      entry.append(link);
    } else if (term.trace && term.trace.none_text) {
      const none = el("p", "glossary-trace-none");
      none.textContent = term.trace.none_text;
      entry.append(none);
    }
  }
  return entry;
}

/** Page Vocabulaire : un terme par entrée, avec « Voir la barrière » quand il en a une. */
export function renderVocabulary(container, glossary) {
  if (!glossary.ui || glossary.terms.length === 0) {
    const empty = el("p", "empty", { role: "alert" });
    empty.textContent = (glossary.ui && glossary.ui.none_text) || "Le vocabulaire n'est pas disponible pour le moment.";
    container.replaceChildren(empty);
    return;
  }
  const list = el("ul", "glossary-list");
  for (const term of glossary.terms) list.append(buildEntry(term, glossary.ui));
  const section = el("section", "glossary");
  section.append(list);
  container.replaceChildren(section);
}
