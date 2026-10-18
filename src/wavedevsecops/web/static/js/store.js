// Magasin de projection (AD-17) : l'état d'un espace tel que le serveur le publie. Le front n'en
// calcule rien (AD-2) : il garde le dernier état connu, applique les événements du flux dans
// l'ordre de `seq`, et se resynchronise sur `resync_required`.
import { assertElementType } from "./panes.js";

export const LOADING = "loading";
export const STREAM_LOST_TEXT =
  "Le suivi de l'espace s'est interrompu. Rechargez la page pour le reprendre.";
const CLOSED = 2; // EventSource.CLOSED : le navigateur ne retentera plus

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
    terminal: { entries: [], cleared: 0, version: 0 }, // sorties du terminal, dans l'ordre d'arrivée
    stepPanel: null, // panneau Scénario écrit par le serveur (étapes, étape courante)
    verdict: null, // dernier step_verdict de l'espace ; null après un rechargement
  };
}

/** Ajoute une entrée au terminal sans copier le tableau (jusqu'à plusieurs milliers de lignes). */
function withEntry(terminal, entry) {
  terminal.entries.push(entry);
  return { ...terminal, version: terminal.version + 1 };
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

/** Marque `stepId` réussie et ouvre `nextId` : le serveur fournit les deux (AD-2). */
function passStep(panel, stepId, nextId) {
  if (!panel) return panel;
  const steps = panel.steps.map((step) => {
    if (step.step_id === stepId) return { ...step, state: "done" };
    if (nextId && step.step_id === nextId) return { ...step, state: "current" };
    return step;
  });
  return { ...panel, steps, current_step_id: nextId || "" };
}

/** Joint l'explication publiée par le serveur à son étape. */
function explainStep(panel, payload) {
  if (!panel) return panel;
  const steps = panel.steps.map((step) =>
    step.step_id === payload.step_id
      ? { ...step, explanation_text: payload.explanation_text, explain_ref: payload.explain_ref }
      : step,
  );
  return { ...panel, steps };
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
        stepPanel: snapshot.step_panel || null,
        verdict: null,
      });
    },
    fail(errorText) {
      set({ errorText });
    },
    /** Entrée locale du terminal (ligne tapée, refus venu du serveur en 409) : même ordre que le flux. */
    terminalAppend(entry) {
      set({ terminal: withEntry(state.terminal, entry) });
    },
    /** Ctrl+L : efface l'affichage, pas l'historique des commandes. */
    terminalClear() {
      const terminal = state.terminal;
      set({ terminal: { ...terminal, cleared: terminal.entries.length, version: terminal.version + 1 } });
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
      } else if (envelope.kind === "terminal_output") {
        // Verbatim : le front n'analyse jamais la sortie (AD-2).
        patch.terminal = withEntry(state.terminal, {
          kind: payload.stream,
          text: payload.text,
          lang: payload.lang || "",
        });
      } else if (envelope.kind === "step_verdict") {
        patch.verdict = payload;
        if (payload.status === "passed") {
          patch.stepPanel = passStep(state.stepPanel, payload.step_id, payload.next_step_id);
        }
      } else if (envelope.kind === "step_explanation") {
        patch.stepPanel = explainStep(state.stepPanel, payload);
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
    const current = new Source(
      `/api/ws/${encodeURIComponent(workspaceId)}/events?last_event_id=${last}`,
    );
    source = current;
    // Erreur passagère : le navigateur se reconnecte seul. Flux fermé : on le dit, sans figer.
    current.onerror = () => {
      if (!stopped && source === current && current.readyState === CLOSED) {
        store.fail(STREAM_LOST_TEXT);
      }
    };
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
