// Sélection persistante et unique d'un élément (UX : « un clic pose une sélection, un nouveau clic
// l'efface »). Elle est partagée par toutes les vues d'un même magasin : le graphe, la liste des
// commits et l'index sélectionnent le même `element_id`. Sélectionner ne fait rien d'autre :
// jamais de `git add` (FR-5, UX-DR16).

const registry = new WeakMap();

// Types que la projection énumère en entier (`views.names`) : une sélection de ce type qui n'y
// figure plus est périmée. Les autres (ligne de diff, sortie d'outil, fichier) sont relus par la
// vue qui les montre : aucune autre vue ne les efface (story 2.10, report de la story 3.3).
const ENUMERATED = new Set(["commit", "ref", "tag", "pr", "check", "review"]);

/** Vrai si `id` n'existe plus dans la projection `views` et doit quitter la sélection. */
export function selectionIsStale(views, id) {
  if (!id || !ENUMERATED.has(String(id).split(":", 1)[0])) return false;
  return !(views && views.names && id in views.names);
}

export function selectionFor(store) {
  if (registry.has(store)) return registry.get(store);
  let current = null;
  const listeners = new Set();
  const selection = {
    get value() {
      return current;
    },
    set(id) {
      const next = id || null;
      if (next === current) return;
      current = next;
      for (const listener of [...listeners]) listener(current);
    },
    toggle(id) {
      selection.set(current === id ? null : id);
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
  registry.set(store, selection);
  return selection;
}
