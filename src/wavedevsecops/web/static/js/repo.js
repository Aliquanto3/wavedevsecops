// Vue « Dépôt local » : graphe des commits (SVG), liste des commits (alternative texte) et index.
// Le front dessine ce que le serveur projette (AD-2) : placement (colonne, rang), noms accessibles,
// marques « Nouveau », commits perdus, HEAD et refs viennent de `state_projected.views`. Ici, seules
// des coordonnées d'écran se calculent à partir des cases du serveur (une rangée de 28 px par commit).
import { el, svg } from "./dom.js";
import { selectionFor } from "./selection.js";

export const ROW = 28; // rangée du graphe (graph-row-height)
export const LANE = 28; // largeur d'une colonne de graphe
const RADIUS = 7; // disque de 14 px (graph-node-size)

export const LOST_TEXT = "perdu · visible par reflog";
export const NEW_TEXT = "Nouveau";
export const RESTORED_TEXT = "Rétabli";
export const ACTOR_TEXT = { colleague: "Collègue", agent: "Agent" };
export const GRAPH_LABEL = "Graphe des commits";
export const LIST_CAPTION = "Commits, dans l'ordre de git log --all --graph";
export const CLEAN_TEXT = "Arbre de travail propre : rien à indexer.";
export const LIST_COLUMNS = ["SHA", "Message", "Auteur", "Parents", "Refs", "État"];
export const STAGING_GROUPS = [
  ["staged", "Indexé", "is-staged"],
  ["unstaged", "Modifié, non indexé", "is-modified"],
  ["untracked", "Non suivi", "is-untracked"],
];
// Lettres d'état de `git status --short`, dites en toutes lettres pour le nom accessible.
export const LETTER_TEXT = {
  M: "modifié",
  A: "ajouté",
  D: "supprimé",
  R: "renommé",
  C: "copié",
  T: "type changé",
  U: "en conflit",
  "?": "non suivi",
};

const ICONS = {
  // poste : écran et pied
  poste: [
    ["rect", { x: 1.5, y: 2, width: 9, height: 6, rx: 1 }],
    ["path", { d: "M4 10.5h4" }],
  ],
  // serveur : deux baies empilées
  serveur: [
    ["rect", { x: 1.5, y: 1.5, width: 9, height: 4, rx: 1 }],
    ["rect", { x: 1.5, y: 6.5, width: 9, height: 4, rx: 1 }],
    ["path", { d: "M3.5 3.5h1M3.5 8.5h1" }],
  ],
  // tag : rectangle à encoche
  tag: [["path", { d: "M1.5 2.5h9v7h-9l2-3.5z" }]],
};

function icon(name) {
  const node = svg("svg", {
    class: "ico",
    viewBox: "0 0 12 12",
    width: 12,
    height: 12,
    "aria-hidden": "true",
    fill: "none",
    stroke: "currentColor",
    "stroke-width": 1.5,
  });
  for (const [tag, attrs] of ICONS[name]) node.append(svg(tag, attrs));
  return node;
}

function text(tag, className, value) {
  const node = el(tag, className);
  node.textContent = value;
  return node;
}

function newMark(restored = false) {
  return text("span", "new-mark", restored ? RESTORED_TEXT : NEW_TEXT);
}

/** Étiquette d'une ref : `graph-head`, `graph-branch`, `graph-remote-ref` ou `graph-tag`. */
function refPill(label) {
  const shape = { head: "graph-head", branch: "graph-branch", remote: "graph-remote-ref", tag: "graph-tag" };
  const pill = el("span", `${shape[label.kind] || "graph-tag"}${label.current ? " is-current" : ""}`, {
    "data-ref": label.element_id,
  });
  if (label.kind === "branch") pill.append(icon("poste"));
  else if (label.kind === "remote") pill.append(icon("serveur"));
  else if (label.kind === "tag") pill.append(icon("tag"));
  pill.append(text("span", "ref-name", label.name_text));
  return pill;
}

function actorBadge(actor) {
  return ACTOR_TEXT[actor] ? text("span", `graph-actor is-${actor}`, ACTOR_TEXT[actor]) : null;
}

/** Marque ● d'un élément sélectionné (visible seulement quand il l'est, CSS) : décorative. */
function dot() {
  const node = text("span", "sel-dot", "●");
  node.setAttribute("aria-hidden", "true");
  return node;
}

// --- graphe ----------------------------------------------------------------------------------

/** Tracé d'une arête (AD-2 : colonne et cases fournies par le serveur). */
export function edgePath(edge, at) {
  const child = at.get(edge.child);
  const parent = at.get(edge.parent);
  if (!child || !parent) return null;
  const column = LANE / 2 + edge.column * LANE;
  if (parent.y - child.y <= ROW) return `M${child.x} ${child.y}L${parent.x} ${parent.y}`;
  return (
    `M${child.x} ${child.y}L${column} ${child.y + ROW}` +
    `L${column} ${parent.y - ROW}L${parent.x} ${parent.y}`
  );
}

export function buildGraph(graph) {
  const nodes = graph.nodes;
  const columns = Math.max(graph.columns || 0, ...nodes.map((node) => node.column + 1));
  const width = columns * LANE;
  const wrap = el("div", "graph", { role: "group", "aria-label": GRAPH_LABEL });
  const at = new Map();
  nodes.forEach((node, index) => {
    at.set(node.element_id, { x: LANE / 2 + node.column * LANE, y: index * ROW + ROW / 2 });
  });
  const lanes = svg("svg", {
    class: "graph-lanes",
    width,
    height: nodes.length * ROW,
    viewBox: `0 0 ${width} ${nodes.length * ROW}`,
    "aria-hidden": "true",
    focusable: "false",
  });
  for (const edge of graph.edges) {
    const d = edgePath(edge, at);
    if (!d) continue;
    lanes.append(
      svg("path", { class: `graph-edge${edge.lost ? " is-lost" : ""}`, d, "data-kind": edge.kind }),
    );
  }
  for (const node of nodes) {
    const { x, y } = at.get(node.element_id);
    lanes.append(
      svg("circle", {
        class: `graph-commit${node.lost ? " is-lost" : ""}`,
        cx: x,
        cy: y,
        r: RADIUS,
        "data-element-id": node.element_id,
      }),
    );
  }
  const list = el("ul", "graph-rows");
  for (const node of nodes) {
    const row = el("li", "graph-row");
    const button = el("button", `graph-node${node.lost ? " is-lost" : ""}`, {
      type: "button",
      "data-select": true,
      "data-element-id": node.element_id,
      "aria-label": node.a11y_name_text,
      "aria-pressed": "false",
    });
    button.style.paddingLeft = `${width + 8}px`;
    button.append(
      dot(),
      text("code", "graph-sha", node.short_sha),
      text("span", "graph-subject", node.subject),
    );
    const badge = actorBadge(node.actor);
    if (badge) button.append(badge);
    if (node.lost) button.append(text("span", "graph-lost", LOST_TEXT));
    for (const label of node.refs) {
      button.append(refPill(label));
      if (label.new) button.append(newMark());
    }
    if (node.new) button.append(newMark());
    if (node.restored) button.append(newMark(true));
    row.append(button);
    list.append(row);
  }
  wrap.append(lanes, list);
  return wrap;
}

// --- liste des commits -----------------------------------------------------------------------

export function buildCommitList(graph, repo) {
  const byId = new Map(graph.nodes.map((node) => [node.element_id, node]));
  const authors = new Map(((repo && repo.commits) || []).map((c) => [c.sha, c.author_name]));
  const table = el("table", "commit-list");
  table.append(text("caption", "visually-hidden", LIST_CAPTION));
  const head = el("tr");
  for (const name of LIST_COLUMNS) head.append(text("th", "", name));
  for (const th of head.children) th.setAttribute("scope", "col");
  const thead = el("thead");
  thead.append(head);
  const body = el("tbody");
  for (const node of graph.nodes) {
    const row = el("tr", node.lost ? "is-lost" : "", {
      "data-select": true,
      "data-element-id": node.element_id,
    });
    const button = el("button", "commit-pick", {
      type: "button",
      "data-element-id": node.element_id,
      "aria-label": node.a11y_name_text,
      "aria-pressed": "false",
    });
    button.append(dot(), text("code", "graph-sha", node.short_sha));
    const sha = el("td");
    sha.append(button);
    const parents = node.parents.map((id) => (byId.get(id) ? byId.get(id).short_sha : id));
    const state = [
      node.lost && "perdu",
      node.new && NEW_TEXT.toLowerCase(),
      node.restored && RESTORED_TEXT.toLowerCase(),
      node.head && "HEAD",
    ].filter(Boolean);
    const author = el("td");
    author.append(authors.get(node.sha) || "");
    const badge = actorBadge(node.actor);
    if (badge) author.append(" ", badge);
    const refs = el("td");
    node.refs.forEach((label, i) => {
      if (i > 0) refs.append(" ");
      refs.append(refPill(label));
    });
    row.append(
      sha,
      text("td", "", node.subject),
      author,
      text("td", "commit-parents", parents.length ? parents.join(", ") : "—"),
      refs,
      text("td", "", state.length ? state.join(" · ") : "—"),
    );
    body.append(row);
  }
  table.append(thead, body);
  return table;
}

// --- index -----------------------------------------------------------------------------------

export function buildStaging(staging, hasCommits) {
  const items = STAGING_GROUPS.flatMap(([key]) => staging[key] || []);
  if (items.length === 0) {
    return hasCommits ? text("p", "staging-clean", CLEAN_TEXT) : null;
  }
  const section = el("section", "staging-index", { "aria-labelledby": "staging-index-title" });
  const heading = text("h3", "staging-title", "Index");
  heading.id = "staging-index-title";
  section.append(heading);
  for (const [key, label, className] of STAGING_GROUPS) {
    const group = staging[key] || [];
    if (group.length === 0) continue;
    const box = el("div", `staging-group ${className}`, { "data-group": key });
    const title = text("h4", "staging-group-title", `${label} (${group.length})`);
    const list = el("ul", "staging-items");
    for (const item of group) {
      const moved = item.orig_path ? `${item.orig_path} → ${item.path}` : item.path;
      const word = LETTER_TEXT[item.letter] || item.letter;
      const button = el("button", "staging-item", {
        type: "button",
        "data-select": true,
        "data-element-id": item.element_id,
        "aria-label": `${label} : ${moved}, ${word}`,
        "aria-pressed": "false",
      });
      button.append(
        dot(),
        text("code", "status-letter", item.letter),
        text("code", "staging-path", moved),
      );
      const li = el("li");
      li.append(button);
      list.append(li);
    }
    box.append(title, list);
    section.append(box);
  }
  return section;
}

// --- volet -----------------------------------------------------------------------------------

/**
 * Remplit le corps du volet « Dépôt local » et le tient à jour d'après le magasin.
 * `renderEmpty` (views.js) dessine l'état vide titré tant qu'il n'y a aucun commit.
 */
export function renderRepo(body, ctx, renderEmpty) {
  const { store, pane } = ctx;
  const selection = selectionFor(store);
  let mode = "graph"; // « graph » ou « list » : le bouton de l'en-tête bascule
  let drawn; // dernières vues dessinées
  const root = el("div", "repo-view");
  const zone = el("div", "repo-zone");
  const indexZone = el("div", "repo-index");
  root.append(zone, indexZone);
  body.replaceChildren(root);

  const toggle = el("button", "pane-tool pane-tool-text", { type: "button", "data-action": "view-toggle" });
  const tools = body.parentElement && body.parentElement.querySelector(".pane-tools");
  if (tools) tools.append(toggle);
  else root.prepend(toggle);

  function syncToggle() {
    const list = mode === "list";
    toggle.textContent = list ? "Graphe" : "Liste";
    const label = list ? "Afficher le graphe des commits" : "Afficher la liste des commits";
    toggle.setAttribute("aria-label", label);
    toggle.setAttribute("title", label);
  }

  function mark(node, on) {
    if (on) node.classList.add("is-selected");
    else node.classList.remove("is-selected");
  }

  function refreshSelection() {
    for (const node of root.querySelectorAll("[data-element-id]")) {
      const on = node.getAttribute("data-element-id") === selection.value;
      mark(node, on);
      if (node.tagName === "BUTTON") node.setAttribute("aria-pressed", String(on));
    }
  }

  /** Un seul arrêt de tabulation par vue (workspace.js) : le nôtre ne l'est que si nul autre ne l'est. */
  function settleRoving(preferred) {
    const mine = [...root.querySelectorAll("button")];
    for (const button of mine) button.setAttribute("tabindex", "-1");
    const section = body.parentElement;
    const others = section
      ? [...section.querySelectorAll("button, [data-roving]")].filter((node) => !root.contains(node))
      : [];
    if (others.some((node) => node.getAttribute("tabindex") === "0") || mine.length === 0) return;
    const chosen =
      mine.find((b) => b.getAttribute("data-element-id") === preferred) ||
      mine.find((b) => b.getAttribute("aria-pressed") === "true") ||
      mine[0];
    chosen.setAttribute("tabindex", "0");
  }

  function draw(state, force = false) {
    if (!force && state.views === drawn) return;
    drawn = state.views;
    const active = document.activeElement;
    const focusedId = active && root.contains(active) ? active.getAttribute("data-element-id") : null;
    const { graph, staging, repo } = state.views;
    const nodes = (graph && graph.nodes) || [];
    zone.replaceChildren();
    indexZone.replaceChildren();
    if (nodes.length === 0) {
      renderEmpty(zone, pane.empty);
    } else {
      if (graph.head_text) zone.append(text("p", "graph-head-text", graph.head_text));
      zone.append(mode === "list" ? buildCommitList(graph, repo) : buildGraph(graph));
    }
    const index = staging ? buildStaging(staging, nodes.length > 0) : null;
    if (index) indexZone.append(index);
    const ids = new Set(
      [...root.querySelectorAll("[data-element-id]")].map((n) => n.getAttribute("data-element-id")),
    );
    if (selection.value && !ids.has(selection.value)) selection.set(null);
    refreshSelection();
    settleRoving(focusedId);
    if (focusedId) {
      const again = [...root.querySelectorAll("button")].find(
        (b) => b.getAttribute("data-element-id") === focusedId,
      );
      if (again) again.focus();
    }
  }

  // Un clic (ou Entrée, Espace) sélectionne ; l'index n'est jamais modifié (UX-DR16).
  root.addEventListener("click", (event) => {
    const target = event.target.closest && event.target.closest("[data-select]");
    if (target) selection.toggle(target.getAttribute("data-element-id"));
  });
  toggle.addEventListener("click", () => {
    mode = mode === "list" ? "graph" : "list";
    syncToggle();
    draw(store.state, true);
  });
  selection.subscribe(refreshSelection);
  syncToggle();
  store.subscribe((state) => draw(state));
}
