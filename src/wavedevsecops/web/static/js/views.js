// Les quatre vues de la disposition principale. Chacune s'enregistre avec ses sous-titres, ses
// types d'`element_id`, sa place et son état vide titré ; leur contenu réel (graphe, PR, éditeur,
// terminal) arrive avec leurs stories ; la disposition ne connaît aucune de ces vues.
import { richText } from "./dom.js";
import { registerPane } from "./panes.js";
import { renderRepo } from "./repo.js";
import { EMPTY, renderTerminal } from "./terminal.js";

/** Corps d'un volet tant qu'il n'a rien à montrer : un titre et une phrase, jamais un spinner. */
export function renderEmpty(body, empty) {
  const title = document.createElement("p");
  title.className = "empty-title";
  richText(title, empty.title);
  const text = document.createElement("p");
  text.className = "empty";
  richText(text, empty.text);
  body.replaceChildren(title, text);
}

const render = (body, ctx) => renderEmpty(body, ctx.pane.empty);

registerPane({
  id: "repo",
  title: "Dépôt local",
  subtitle: "Graphe des commits et index, comme `git log --all` et `git status`",
  elementTypes: ["commit", "ref", "tag", "path"],
  // Vues de state_projected affichées ici, avec leurs element_id (le magasin en contrôle les types).
  projection: {
    graph: (graph) => graph.nodes.flatMap((n) => [n.element_id, ...n.refs.map((r) => r.element_id)]),
    staging: (staging) =>
      [...staging.staged, ...staging.unstaged, ...staging.untracked].map((i) => i.element_id),
  },
  row: 1,
  rowShare: 40,
  scroll: "both",
  share: 55,
  empty: {
    title: "Aucun commit pour l'instant.",
    text: "Créez un fichier puis tapez `git add` et `git commit`.",
  },
  render: (body, ctx) => renderRepo(body, ctx, renderEmpty),
});

registerPane({
  id: "remote",
  title: "Distant + PR",
  subtitle: "Refs de origin et PR du GitHub simulé",
  elementTypes: ["ref", "pr", "check"],
  row: 1,
  share: 45,
  foldRank: 1,
  empty: {
    title: "Aucune PR.",
    text: "Poussez une branche, puis ouvrez une PR.",
  },
  render,
});

registerPane({
  id: "code",
  title: "Code",
  subtitle: "Fichiers du bac à sable, diff et éditeur",
  elementTypes: ["path", "commit", "pr"],
  row: 2,
  rowShare: 33,
  scroll: "both",
  foldRank: 2,
  empty: {
    title: "Rien à afficher.",
    text: "Sélectionnez un fichier, un commit ou une PR pour voir son contenu.",
  },
  render,
});

registerPane({
  id: "terminal",
  title: "Terminal",
  subtitle: "Vrai git, dans le bac à sable",
  elementTypes: [],
  row: 3,
  rowShare: 27,
  scroll: "both",
  terminal: true,
  empty: EMPTY,
  render: renderTerminal,
});
