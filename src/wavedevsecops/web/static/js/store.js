// Magasin de projection (AD-17) : l'état d'un espace tel que le serveur le publie. Le front n'en
// calcule rien (AD-2) : il garde le dernier état connu, applique les événements du flux dans
// l'ordre de `seq`, et se resynchronise sur `resync_required`.
import { assertElementType } from "./panes.js";

export const LOADING = "loading";

function initial() {
  return {
    workspaceId: null,
    bootId: null,
    seq: 0,
    epoch: 0,
    engineState: LOADING, // « loading » tant que le premier état n'est pas arrivé
    reasonText: "",
    fingerprint: "",
    views: {}, // projection par volet : views[pane_id]
    errorText: "", // dernier app_error ou échec de lecture
    problems: [], // projections refusées (type d'élément non déclaré)
  };
}

/** Garde les projections dont chaque `element` a un type déclaré par son volet. */
export function acceptViews(views, problems = []) {
  const accepted = {};
  for (const [paneId, view] of Object.entries(views || {})) {
    try {
      for (const element of (view && view.elements) || []) assertElementType(paneId, element.type);
      accepted[paneId] = view;
    } catch (err) {
      problems.push(err.message);
    }
  }
  return accepted;
}

export function createStore() {
  let state = initial();
  const listeners = new Set();

  function set(patch) {
    state = { ...state, ...patch };
    for (const listener of [...listeners]) listener(state);
  }

  return {
    get state() {
      return state;
    },
    subscribe(listener) {
      listeners.add(listener);
      listener(state);
      return () => listeners.delete(listener);
    },
    reset(workspaceId) {
      state = { ...initial(), workspaceId };
      for (const listener of [...listeners]) listener(state);
    },
    applySnapshot(snapshot) {
      const problems = [];
      const views = acceptViews(snapshot.views, problems);
      set({
        workspaceId: snapshot.workspace_id ?? state.workspaceId,
        bootId: snapshot.boot_id,
        seq: snapshot.seq,
        epoch: snapshot.epoch,
        engineState: snapshot.state,
        reasonText: snapshot.reason_text || "",
        fingerprint: snapshot.fingerprint || "",
        views,
        errorText: "",
        problems,
      });
    },
    fail(errorText) {
      set({ errorText });
    },
    /** Applique un événement ; rend "resync" quand il faut relire l'état, "stale" s'il est périmé. */
    applyEvent(envelope) {
      if (envelope.kind === "resync_required") return "resync";
      if (envelope.boot_id !== state.bootId) return "resync";
      if (envelope.seq <= state.seq) return "stale";
      const payload = envelope.payload || {};
      const patch = { seq: envelope.seq, epoch: envelope.epoch ?? state.epoch };
      if (envelope.kind === "engine_state") {
        patch.engineState = payload.state;
        patch.reasonText = payload.reason_text || "";
      } else if (envelope.kind === "state_projected") {
        const problems = [];
        patch.views = acceptViews(payload.views, problems);
        patch.fingerprint = payload.fingerprint || "";
        patch.problems = problems;
      } else if (envelope.kind === "app_error") {
        patch.errorText = `${payload.cause_text} ${payload.action_text}`.trim();
      }
      set(patch);
      return "applied";
    },
  };
}

/**
 * Branche le magasin sur un espace : état courant, puis flux SSE repris à `<boot_id>:<seq>`.
 * Rend une fonction d'arrêt.
 */
export function connectWorkspace(store, workspaceId, options = {}) {
  const fetchImpl = options.fetchImpl || ((...args) => fetch(...args));
  const Source = options.EventSourceImpl || globalThis.EventSource;
  let source = null;
  let stopped = false;

  async function sync() {
    if (source) source.close();
    source = null;
    let snapshot;
    try {
      const response = await fetchImpl(`/api/ws/${encodeURIComponent(workspaceId)}/state`, {
        cache: "no-store",
        credentials: "same-origin",
      });
      const body = await response.json();
      if (!response.ok) {
        store.fail(body.reason_text || "L'espace n'a pas pu être lu. Revenez au catalogue.");
        return;
      }
      snapshot = body;
    } catch (err) {
      store.fail("WaveDevSecOps ne répond pas. Rechargez la page.");
      return;
    }
    if (stopped) return;
    store.applySnapshot(snapshot);
    if (!Source) return;
    const last = encodeURIComponent(`${snapshot.boot_id}:${snapshot.seq}`);
    source = new Source(`/api/ws/${encodeURIComponent(workspaceId)}/events?last_event_id=${last}`);
    source.onmessage = (message) => {
      let envelope;
      try {
        envelope = JSON.parse(message.data);
      } catch (err) {
        return;
      }
      if (store.applyEvent(envelope) === "resync") sync();
    };
  }

  store.reset(workspaceId);
  sync();
  return () => {
    stopped = true;
    if (source) source.close();
  };
}
