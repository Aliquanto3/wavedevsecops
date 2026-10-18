// Registre des volets : une vue = un module qui s'enregistre ici (convention Front du spine).
// La disposition lit ce registre et ne connaît aucune vue en particulier ; ajouter une vue
// (la carte, en v0.2) ne touche donc pas la disposition.
//
//   registerPane({
//     id: "repo",                  // identifiant stable
//     step: 1,                     // numéro de lecture (pane-step)
//     title: "Dépôt local",
//     subtitle: "Ce que dit git du dépôt",
//     elementTypes: ["commit"],    // types d'element_id que la vue émet (liaison entre vues)
//     render(body) { ... },        // remplit le corps de la vue
//   });

const panes = new Map();

export function registerPane(pane) {
  for (const field of ["id", "title", "render"]) {
    if (!pane[field]) throw new Error(`Volet invalide : « ${field} » manquant.`);
  }
  if (panes.has(pane.id)) throw new Error(`Volet déjà enregistré : ${pane.id}.`);
  panes.set(pane.id, { step: panes.size + 1, subtitle: "", elementTypes: [], ...pane });
}

export function listPanes() {
  return [...panes.values()].sort((a, b) => a.step - b.step);
}

/** Dessine les volets enregistrés dans `container`. */
export function renderPanes(container, emptyText) {
  container.replaceChildren();
  const registered = listPanes();
  if (registered.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = emptyText;
    container.append(empty);
    return;
  }
  for (const pane of registered) {
    const section = document.createElement("section");
    section.className = "pane";
    section.setAttribute("aria-labelledby", `pane-${pane.id}-title`);
    section.dataset.pane = pane.id;

    const header = document.createElement("header");
    header.className = "pane-header";
    const step = document.createElement("span");
    step.className = "pane-step";
    step.textContent = String(pane.step);
    const title = document.createElement("h2");
    title.className = "pane-title";
    title.id = `pane-${pane.id}-title`;
    title.textContent = pane.title;
    header.append(step, title);

    const body = document.createElement("div");
    body.className = "pane-body";
    section.append(header, body);
    container.append(section);
    pane.render(body);
  }
}
