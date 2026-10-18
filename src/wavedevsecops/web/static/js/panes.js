// Registre des volets : une vue = un module qui s'enregistre ici (convention Front du spine).
// La disposition (layout.js, workspace.js) lit ce registre et ne connaît aucune vue en
// particulier ; ajouter une vue (la carte, en v0.2) ne touche donc pas la disposition.
//
//   registerPane({
//     id: "repo",                  // identifiant stable
//     step: 1,                     // numéro de lecture (pane-step) ; par défaut, l'ordre d'enregistrement
//     title: "Dépôt local",
//     subtitle: "Ce que dit git du dépôt",
//     elementTypes: ["commit"],    // types d'element_id que la vue émet (liaison entre vues)
//     row: 1, rowShare: 40,        // rangée (1 = haute) et sa part de hauteur (premier volet de la rangée)
//     share: 55,                   // part de largeur dans la rangée
//     foldRank: 2,                 // ordre de repli sous la taille nominale (absent : jamais replié)
//     projection: { graph: (view) => [element_id, …] },  // vues de `state_projected` que ce volet
//                                  // affiche, avec leurs `element_id` (types contrôlés par le magasin)
//     scroll: "both",           // défilement dans les deux sens (graphe, diff, terminal) ; sinon vertical
//     terminal: false,           // vrai : Échap y rend le focus au titre
//     empty: { title, text },      // état vide titré (jamais un spinner muet)
//     render(body, ctx) { ... },   // remplit le corps ; ctx.store donne la projection (store.js)
//   });

const panes = new Map();

export function registerPane(pane) {
  for (const field of ["id", "title", "render"]) {
    if (!pane[field]) throw new Error(`Volet invalide : « ${field} » manquant.`);
  }
  if (panes.has(pane.id)) throw new Error(`Volet déjà enregistré : ${pane.id}.`);
  const types = pane.elementTypes ?? [];
  if (!Array.isArray(types) || types.some((type) => typeof type !== "string" || !type)) {
    throw new Error(`Volet invalide : « elementTypes » de ${pane.id} doit lister des textes.`);
  }
  panes.set(pane.id, {
    step: panes.size + 1,
    subtitle: "",
    row: 1,
    empty: null,
    terminal: false,
    ...pane,
    elementTypes: [...types],
    projection: { ...(pane.projection || {}) },
  });
}

export function listPanes() {
  return [...panes.values()].sort((a, b) => a.step - b.step);
}

export function getPane(id) {
  return panes.get(id) || null;
}

/**
 * Vérifie qu'un type d'`element_id` émis par une vue est bien déclaré à son enregistrement.
 * Lève une erreur sinon : une liaison entre vues ne repose jamais sur un type non déclaré.
 */
export function assertElementType(paneId, type) {
  const pane = panes.get(paneId);
  if (!pane) throw new Error(`Volet inconnu : ${paneId}.`);
  if (!pane.elementTypes.includes(type)) {
    throw new Error(`Le volet ${paneId} émet le type « ${type} » sans l'avoir déclaré.`);
  }
}
