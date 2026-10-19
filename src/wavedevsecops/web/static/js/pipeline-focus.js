// Lien entre la vue « Distant + PR » et `pipeline-tabs` (vue Code, story 7.6) : « Voir dans le
// pipeline » demande l'ouverture des trois écritures sur une tâche d'une PR, et le survol d'un check
// éclaire les lignes de sa tâche. Ce n'est pas une sélection (UX : un clic pose une sélection) ni une
// intention : rien ne passe par la file, rien ne s'écrit, le front ne fait que montrer.
const registry = new WeakMap();

export function pipelineFocusFor(store) {
  if (registry.has(store)) return registry.get(store);
  let request = null; // { number, jobId, nonce } : dernière demande d'ouverture
  let hover = null; // job_id survolé ou focalisé
  let nonce = 0;
  const listeners = new Set();
  const emit = (kind) => {
    for (const listener of [...listeners]) listener(kind, focus);
  };
  const focus = {
    get request() {
      return request;
    },
    get hover() {
      return hover;
    },
    /** « Voir dans le pipeline » : ouvre `pipeline-tabs` sur la tâche `jobId` de la PR `number`. */
    open(number, jobId) {
      nonce += 1;
      request = { number: Number(number), jobId, nonce };
      emit("open");
    },
    /** Survol (ou focus) d'un check : `jobId`, ou `null` quand il le quitte. */
    setHover(jobId) {
      const next = jobId || null;
      if (next === hover) return;
      hover = next;
      emit("hover");
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
  registry.set(store, focus);
  return focus;
}
