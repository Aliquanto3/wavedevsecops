// Correspondances entre vues (story 2.10, FR-5, UX « Correspondances entre vues »).
//
// Le serveur déclare les liens (AD-2) : `views.links` pour les éléments projetés, `links` des
// lignes et en-têtes du diff (lu à la demande par code.js). Le front ne déduit rien : il lit ces
// arêtes dans les deux sens, repère l'élément survolé, focalisé ou sélectionné, et marque ses
// correspondants dans toutes les vues (`is-linked`), pendant que le reste passe en retrait
// (`data-linking` sur l'espace : décors estompés, texte en `ink-soft`, jamais d'opacité sur le
// texte). Dans le terminal, les lignes qui citent un correspondant prennent `terminal-lit`.
//
// Préséance des marques (UX) : verdict, sélection, désignable, puis lié. Le CSS ne pose le lien
// que hors du mode Désigner (`.is-designating`) : armer la désignation n'est jamais gêné.
//
// Un correspondant dans une vue masquée change sa puce en « + Nom · lié » ; un clic réaffiche la
// vue et met l'élément en évidence. Un correspondant hors de la zone visible : la vue défile
// jusqu'à lui sur clic, jamais au survol.
import { installExplain } from "./explain.js";
import { getPane } from "./panes.js";
import { selectionFor } from "./selection.js";

export const SUMMARY_ID = "link-summary";
export const LINKED_CHIP_SUFFIX = " · lié";
const NAMED_MAX = 5;
const REVEAL_MS = 2400;
const ELEMENT = "[data-element-id], [data-link], [data-ref]";
const INTERACTIVE = `${ELEMENT}, [data-explain-for]`;

const registry = new WeakMap();

/** Texte du résumé lu au focus : « 3 éléments liés : ref origin/main, PR n°2, fichier a.py ». */
export function summaryText(names) {
  if (names.length === 0) return "";
  const shown = names.slice(0, NAMED_MAX);
  const more = names.length - shown.length;
  const plural = names.length > 1;
  const tail = more > 0 ? ` et ${more} autre${more > 1 ? "s" : ""}` : "";
  return `${names.length} élément${plural ? "s" : ""} lié${plural ? "s" : ""} : ${shown.join(", ")}${tail}`;
}

/** Sources de liens à ajouter pour un diff lu à la demande (fichiers et lignes). */
export function diffSource(diff) {
  const links = {};
  const explain = {};
  for (const file of (diff && diff.files) || []) {
    links[file.element_id] = file.links || [];
    if (file.explain_ref) explain[file.element_id] = file.explain_ref;
    for (const hunk of file.hunks || []) {
      for (const line of hunk.lines || []) links[line.element_id] = line.links || [];
    }
  }
  return { links, explain };
}

export function idOf(node) {
  if (!node) return null;
  return (
    node.getAttribute("data-explain-for") ||
    node.getAttribute("data-element-id") ||
    node.getAttribute("data-link") ||
    node.getAttribute("data-ref") ||
    null
  );
}

/**
 * Registre des liens d'un magasin : sources (projection, diff), arêtes lues dans les deux sens,
 * noms et clés d'explication. Partagé par tous les modules d'un même espace.
 */
export function linkingFor(store) {
  if (registry.has(store)) return registry.get(store);
  const sources = new Map(); // nom → { links, names, explain }
  const listeners = new Set();
  let edges = new Map();
  let drawnViews;

  function rebuild() {
    edges = new Map();
    const join = (a, b) => {
      if (!a || !b || a === b) return;
      if (!edges.has(a)) edges.set(a, new Set());
      edges.get(a).add(b);
    };
    for (const source of sources.values()) {
      for (const [from, targets] of Object.entries(source.links || {})) {
        for (const to of targets) {
          join(from, to);
          join(to, from);
        }
      }
    }
    for (const listener of [...listeners]) listener();
  }

  const linking = {
    setSource(name, source) {
      if (source) sources.set(name, source);
      else sources.delete(name);
      rebuild();
    },
    linksOf(id) {
      return [...(edges.get(id) || [])];
    },
    nameOf(id) {
      for (const source of sources.values()) if (source.names && source.names[id]) return source.names[id];
      return "";
    },
    explainOf(id) {
      for (const source of sources.values()) if (source.explain && source.explain[id]) return source.explain[id];
      return "";
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
  store.subscribe((state) => {
    const views = state.views || {};
    if (views === drawnViews) return;
    drawnViews = views;
    linking.setSource("views", {
      links: views.links || {},
      names: views.names || {},
      explain: views.explain || {},
    });
  });
  registry.set(store, linking);
  return linking;
}

/** Les identifiants d'élément qu'un volet affiche d'après `views` (sa `projection` déclarée). */
function projectedIds(pane, views) {
  const ids = new Set();
  for (const [key, listIds] of Object.entries(pane.projection || {})) {
    if (!views || !(key in views)) continue;
    try {
      for (const id of listIds(views[key])) ids.add(String(id));
    } catch (err) {
      // Une vue mal formée est déjà refusée par le magasin ; ici, on n'y trouve simplement rien.
    }
  }
  return ids;
}

function reducedMotion() {
  try {
    return Boolean(globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches);
  } catch (err) {
    return false;
  }
}

/**
 * Branche les correspondances sur l'espace de travail `root` (grille `.views-grid`, barre de
 * puces `chipBar`). Rend `{ linking, syncChips, anchor, reveal, refresh, explain, destroy }`.
 */
export function mountLinking(root, { store, chipBar = null, fetchImpl, timers = globalThis }) {
  const selection = selectionFor(store);
  const linking = linkingFor(store);
  const grid = root.querySelector(".views-grid") || root;
  let hover = null;
  let focus = null;
  let held = null; // ancre gardée pendant qu'on atteint une puce
  let applied = "";
  let clickedPane = null;
  const summary = document.createElement("p");
  summary.className = "visually-hidden";
  summary.id = SUMMARY_ID;
  document.body.append(summary); // hors de l'espace : sa disposition reste celle que les vues attendent
  let described = null;
  let revealTimer = null;

  function active() {
    return hover || focus || held || selection.value || null;
  }

  function nodes() {
    return grid.querySelectorAll(ELEMENT);
  }

  /**
   * Correspondants de `id` : les arêtes déclarées, plus, pour un bloc de sortie d'outil, les
   * éléments que ses passages citent (`spans` du serveur, notés en `data-span-ids`). Ainsi le
   * bloc allume le fichier cité comme le fichier allume le bloc.
   */
  function related(id) {
    const out = linking.linksOf(id);
    if (!String(id).startsWith("output:")) return out;
    for (const node of grid.querySelectorAll("[data-span-ids]")) {
      if (node.getAttribute("data-element-id") !== id) continue;
      for (const span of (node.getAttribute("data-span-ids") || "").split(" ")) {
        if (span && !out.includes(span)) out.push(span);
      }
    }
    return out;
  }

  function setClass(node, name, on) {
    if (on) node.classList.add(name);
    else node.classList.remove(name);
  }

  /** Marque les correspondants de l'élément actif dans toutes les vues. */
  function apply() {
    const id = active();
    const lit = new Set(id ? [id, ...related(id)] : []);
    let others = 0;
    for (const node of nodes()) {
      const nid = idOf(node);
      const on = lit.has(nid);
      setClass(node, "is-linked", on);
      if (on) others += 1;
      // La vue Code ne marque pas elle-même sa sélection (lignes et en-têtes du diff).
      if (node.closest(".diff-view")) {
        const chosen = nid === selection.value;
        setClass(node, "is-selected", chosen);
        if (chosen) node.setAttribute("aria-current", "true");
        else node.removeAttribute("aria-current");
      }
    }
    let spanned = 0;
    for (const node of grid.querySelectorAll("[data-span-ids]")) {
      const on = (node.getAttribute("data-span-ids") || "").split(" ").some((span) => lit.has(span));
      setClass(node, "terminal-lit", on);
      if (on) spanned += 1;
    }
    // Un seul élément lié (lui-même) : rien à mettre en regard, les autres ne se retirent pas.
    if (id && others + spanned > 1) root.setAttribute("data-linking", "on");
    else root.removeAttribute("data-linking");
    applied = `${id}|${others}|${spanned}`;
    syncChips();
  }

  function set(patch) {
    const before = `${hover}|${focus}|${held}`;
    if ("hover" in patch) hover = patch.hover;
    if ("focus" in patch) focus = patch.focus;
    if ("held" in patch) held = patch.held;
    // Le survol passe d'un nœud à l'autre du même élément : rien ne change, rien à reparcourir.
    if (`${hover}|${focus}|${held}` !== before) apply();
  }

  const inChips = (node) => Boolean(chipBar && node && chipBar.contains(node));

  // --- survol et focus --------------------------------------------------------------------
  root.addEventListener("pointerover", (event) => {
    if (event.pointerType === "touch") return;
    if (inChips(event.target)) {
      set({ held: active(), hover: null });
      return;
    }
    const node = event.target.closest?.(INTERACTIVE);
    const inView = node && grid.contains(node);
    set({ hover: inView ? idOf(node) : null, held: null });
  });
  root.addEventListener("pointerleave", () => set({ hover: null }));
  root.addEventListener("focusin", (event) => {
    if (inChips(event.target)) {
      set({ held: active(), hover: null, focus: null });
      return;
    }
    const node = event.target.closest?.(INTERACTIVE);
    const inView = node && grid.contains(node);
    set({ focus: inView ? idOf(node) : null, held: null });
    describe(inView ? node : null);
  });
  root.addEventListener("focusout", (event) => {
    if (!inChips(event.target)) {
      set({ focus: null });
      describe(null);
    }
  });

  /** Relie le résumé « n éléments liés : … » à l'élément qui a le focus (lu sur demande). */
  function describe(node) {
    if (described) {
      described.removeAttribute("aria-describedby");
      described = null;
    }
    summary.textContent = "";
    const id = node && node.getAttribute("data-element-id");
    if (!id) return;
    const names = namesLinkedTo(id);
    if (names.length === 0) return;
    summary.textContent = summaryText(names);
    node.setAttribute("aria-describedby", SUMMARY_ID);
    described = node;
  }

  /** Noms des éléments liés qu'un lecteur peut trouver : le serveur les nomme, sinon la vue. */
  function namesLinkedTo(id) {
    const labels = new Map();
    for (const node of nodes()) {
      const other = idOf(node);
      if (other && !labels.has(other)) labels.set(other, node.getAttribute("aria-label") || "");
    }
    const out = [];
    for (const other of related(id)) {
      const name = linking.nameOf(other) || labels.get(other);
      if (name && !out.includes(name)) out.push(name);
    }
    return out;
  }

  // --- sélection : clic, Entrée, Espace ----------------------------------------------------
  // Les éléments qui ne sont pas des boutons (lignes et en-têtes du diff) se sélectionnent
  // comme les autres ; le clic synthétique d'Entrée et d'Espace passe par la désignation armée.
  grid.addEventListener(
    "click",
    (event) => {
      clickedPane = event.target.closest?.(".pane") || null;
      queueMicrotask(() => {
        clickedPane = null;
      });
    },
    true,
  );
  // Un événement déjà traité par sa vue (`preventDefault`, ex. sortie de check) n'est pas rejoué.
  grid.addEventListener("click", (event) => {
    if (event.defaultPrevented) return;
    const node = event.target.closest?.("[data-roving][data-element-id]");
    if (!node || node.tagName === "BUTTON" || event.target.closest?.("button")) return;
    if (String(globalThis.getSelection?.() ?? "")) return; // copier du texte n'est pas sélectionner
    selection.toggle(node.getAttribute("data-element-id"));
  });
  grid.addEventListener("keydown", (event) => {
    if (event.defaultPrevented || (event.key !== "Enter" && event.key !== " ")) return;
    const node = event.target;
    if (!node.hasAttribute || node.tagName === "BUTTON") return;
    if (!node.hasAttribute("data-roving") || !node.hasAttribute("data-element-id")) return;
    event.preventDefault();
    node.click();
  });

  /** Fait défiler chaque autre vue jusqu'à son premier correspondant (sur clic seulement). */
  function scrollToLinked() {
    const behavior = reducedMotion() ? "auto" : "smooth";
    for (const section of grid.querySelectorAll(".pane")) {
      if (section === clickedPane) continue;
      const target = section.querySelector(".is-linked, .terminal-lit");
      if (target && target.scrollIntoView) target.scrollIntoView({ block: "nearest", inline: "nearest", behavior });
    }
  }

  const unselect = selection.subscribe((value) => {
    apply();
    if (value && clickedPane) scrollToLinked();
  });
  const unlink = linking.subscribe(() => apply());

  // --- puces des vues masquées -------------------------------------------------------------
  let cache = { views: null, held: new Map() };

  function holds(pane, id) {
    const views = store.state.views;
    if (cache.views !== views) cache = { views, held: new Map() };
    if (!cache.held.has(pane.id)) cache.held.set(pane.id, projectedIds(pane, views));
    const ids = cache.held.get(pane.id);
    if (Object.keys(pane.projection || {}).length > 0) return ids.has(id);
    return pane.elementTypes.includes(String(id).split(":", 1)[0]);
  }

  /** Les puces des vues masquées qui contiennent un correspondant deviennent « + Nom · lié ». */
  function syncChips() {
    if (!chipBar) return;
    const id = active();
    const lit = id ? [id, ...related(id)] : [];
    for (const chip of chipBar.querySelectorAll("[data-pane]")) {
      const pane = getPane(chip.getAttribute("data-pane"));
      if (!pane) continue;
      const linked = lit.some((other) => holds(pane, other));
      chip.textContent = `+ ${pane.title}${linked ? LINKED_CHIP_SUFFIX : ""}`;
      setClass(chip, "is-linked", linked);
      if (linked) chip.setAttribute("data-linked", "true");
      else chip.removeAttribute("data-linked");
    }
  }

  /** Élément dont les correspondants comptent pour une puce cliquée : celui d'avant le clic. */
  function anchor() {
    return active();
  }

  /** Après le réaffichage d'une vue : met en évidence son premier correspondant et y défile. */
  function reveal(paneId, anchorId = active()) {
    const section = grid.querySelector(`[data-pane="${paneId}"]`);
    if (!section || !anchorId) return null;
    const lit = new Set([anchorId, ...related(anchorId)]);
    apply();
    let target = null;
    for (const node of section.querySelectorAll(ELEMENT)) {
      if (lit.has(idOf(node))) {
        target = node;
        break;
      }
    }
    if (!target) return null;
    target.classList.add("is-revealed");
    target.scrollIntoView?.({ block: "nearest", inline: "nearest", behavior: reducedMotion() ? "auto" : "smooth" });
    if (revealTimer) timers.clearTimeout(revealTimer);
    revealTimer = timers.setTimeout(() => target.classList.remove("is-revealed"), REVEAL_MS);
    return target;
  }

  // --- redessins : les vues remplacent leurs nœuds, les marques se reposent -----------------
  let pending = false;
  function schedule() {
    if (pending) return;
    pending = true;
    queueMicrotask(() => {
      pending = false;
      explain.decorate(); // les « i » des éléments qui viennent d'être dessinés
      apply();
    });
  }
  const unsubscribe = store.subscribe(schedule);
  let observer = null;
  if (typeof MutationObserver !== "undefined") {
    observer = new MutationObserver(schedule);
    observer.observe(grid, { childList: true, subtree: true });
  }

  const explain = installExplain(root, { store, linking, selection, fetchImpl, grid, nodesOf: nodes, observeWith: schedule, relatedOf: related });

  apply();
  return {
    linking,
    explain,
    syncChips,
    anchor,
    reveal,
    refresh: apply,
    get applied() {
      return applied;
    },
    destroy() {
      unselect();
      unlink();
      unsubscribe();
      explain.destroy();
      summary.remove();
      if (observer) observer.disconnect();
      if (revealTimer) timers.clearTimeout(revealTimer);
    },
  };
}
