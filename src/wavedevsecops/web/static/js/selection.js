// Sélection persistante et unique d'un élément (UX : « un clic pose une sélection, un nouveau clic
// l'efface »). Elle est partagée par toutes les vues d'un même magasin : le graphe, la liste des
// commits et l'index sélectionnent le même `element_id`. Sélectionner ne fait rien d'autre :
// jamais de `git add` (FR-5, UX-DR16).

const registry = new WeakMap();

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
