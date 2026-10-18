// Magasin de projection (AD-17) : l'état d'un espace tel que le serveur le publie. Le front n'en
// calcule rien (AD-2) : il garde le dernier état connu, applique les événements du flux dans
// l'ordre de `seq`, et se resynchronise sur `resync_required`.
import { assertElementType, listPanes } from "./panes.js";

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
    announce: null, // { text, command } : dernière annonce de vues mises à jour (FR-4)
    projectedOp: null, // op_id de la dernière state_projected (seconde projection d'une op)
    restored: false, // vrai entre un rétablissement réussi et la commande suivante
    hintNotice: "", // annonce du serveur quand la solution se débloque ; vidée à l'action suivante
  };
}

/** Ajoute une entrée au terminal sans copier le tableau (jusqu'à plusieurs milliers de lignes). */
function withEntry(terminal, entry) {
  terminal.entries.push(entry);
  return { ...terminal, version: terminal.version + 1 };
}

/**
 * Garde les vues de `state_projected.views` (une clé par vue : `graph`, `staging`, `prompt`…).
 * Chaque volet déclare à son enregistrement les vues qu'il affiche et leurs `element_id` : une
 * vue dont un `element_id` a un type que son volet n'a pas déclaré est refusée. Les clés que
 * aucun volet ne déclare passent telles quelles.
 */
export function acceptViews(views, problems = []) {
  const accepted = { ...(views || {}) };
  for (const pane of listPanes()) {
    for (const [key, elementIds] of Object.entries(pane.projection)) {
      if (!(key in accepted)) continue;
      try {
        for (const id of elementIds(accepted[key])) {
          assertElementType(pane.id, String(id).split(":", 1)[0]);
        }
      } catch (err) {
        problems.push(err.message);
        console.warn(`Vue « ${key} » écartée : ${err.message}`); // diagnostic pour le développeur
        delete accepted[key];
      }
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

/** Étape courante du panneau, ou null. */
function currentStep(panel) {
  return (panel && panel.steps.find((step) => step.step_id === panel.current_step_id)) || null;
}

/** Vrai si la solution de l'étape courante est passée de verrouillée à disponible. */
function solutionUnlocked(before, after) {
  const was = currentStep(before);
  const now = currentStep(after);
  if (!was || !now || was.step_id !== now.step_id || !was.hints || !now.hints) return false;
  const tier = (step) => step.hints.tiers.find((t) => t.tier === 3);
  return tier(was)?.state === "locked" && tier(now)?.state === "available";
}

export function createStore() {
  let state = initial();
  const externalOps = new Set();
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
        announce: null, // l'ouverture n'est pas une commande
        projectedOp: null,
        hintNotice: "",
      });
    },
    fail(errorText) {
      set({ errorText });
    },
    /** Remplace le panneau Scénario relu auprès du serveur (indices ouverts ou débloqués). */
    setStepPanel(panel) {
      const unlocked = solutionUnlocked(state.stepPanel, panel);
      const now = currentStep(panel);
      set({
        stepPanel: panel,
        hintNotice: unlocked && now ? now.hints.unlocked_text || "" : state.hintNotice,
      });
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
        if (payload.state === "command") {
          patch.restored = false;
          patch.hintNotice = "";
        }
      } else if (envelope.kind === "state_projected") {
        const problems = [];
        const fingerprint = payload.fingerprint || "";
        // Seconde projection d'une même opération, à la même empreinte (marques `designable` de
        // l'étape suivante, story 5.2) : le dépôt n'a pas changé, l'annonce lue n'est pas relancée.
        const same =
          Boolean(envelope.op_id) &&
          envelope.op_id === state.projectedOp &&
          fingerprint === state.fingerprint;
        patch.projectedOp = envelope.op_id || null;
        patch.views = acceptViews(payload.views, problems);
        patch.fingerprint = fingerprint;
        patch.problems = problems;
        const text = (payload.views && payload.views.announce_text) || "";
        // Une commande est une opération de l'apprenant : ni l'ouverture (sans op_id) ni un
        // changement venu de l'extérieur (annoncé juste avant par `external_change`).
        const command = Boolean(envelope.op_id) && !externalOps.delete(envelope.op_id);
        patch.announce = same ? state.announce : text ? { text, command } : null;
      } else if (envelope.kind === "external_change") {
        if (envelope.op_id) externalOps.add(envelope.op_id);
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
      } else if (envelope.kind === "progress_updated") {
        // Le bilan est écrit par le serveur : à la fin du scénario, on relit l'état pour l'avoir.
        if ((payload.facts || []).includes("scenario_completed")) return "resync";
      } else if (envelope.kind === "step_explanation") {
        patch.stepPanel = explainStep(state.stepPanel, payload);
      } else if (envelope.kind === "quiz_altered" && state.stepPanel) {
        const { first_attempt: _first, ...altered } = payload;
        patch.stepPanel = { ...state.stepPanel, quiz_altered: altered, restore_failed: null };
      } else if (envelope.kind === "restore_ended" && state.stepPanel) {
        // Le serveur dit si l'état est rétabli ; l'échec garde le quiz et pose l'encart d'erreur.
        patch.stepPanel =
          payload.status === "ok"
            ? { ...state.stepPanel, quiz_altered: null, restore_failed: null }
            : { ...state.stepPanel, restore_failed: { reason_text: payload.reason_text || "" } };
        patch.restored = payload.status === "ok";
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
  let unlockTimer = null;

  /** Relit le panneau auprès du serveur : lui seul décide de la disponibilité d'un indice. */
  async function refreshPanel() {
    for (let attempt = 0; attempt < 3 && !stopped; attempt += 1) {
      let body;
      try {
        const response = await fetchImpl(`/api/ws/${encodeURIComponent(workspaceId)}/state`, {
          cache: "no-store",
          credentials: "same-origin",
        });
        if (!response.ok) return;
        body = await response.json();
      } catch (err) {
        return;
      }
      // Un événement plus récent que cette lecture est arrivé entre-temps : on relit.
      if (stopped || body.boot_id !== store.state.bootId) return;
      if (body.seq >= store.state.seq) {
        store.setStepPanel(body.step_panel || null);
        scheduleUnlock();
        return;
      }
    }
  }

  /** Programme la relecture du moment où la solution se débloque (aucun décompte affiché). */
  function scheduleUnlock() {
    if (unlockTimer) clearTimeout(unlockTimer);
    unlockTimer = null;
    const panel = store.state.stepPanel;
    const step = panel && panel.steps.find((s) => s.step_id === panel.current_step_id);
    const wait = step && step.hints ? step.hints.solution_unlock_ms : null;
    if (typeof wait === "number" && wait > 0 && !stopped) {
      unlockTimer = setTimeout(refreshPanel, wait + 50);
    }
  }

  /** Indices en jeu : une relecture suit l'ouverture d'un palier, la réussite d'une étape (les
   * indices de la suivante) et la fin d'une action (un essai peut débloquer la solution). */
  function needsRefresh(envelope) {
    const panel = store.state.stepPanel;
    if (!panel || !panel.has_hints) return false;
    if (envelope.kind === "hint_opened") return true;
    if (envelope.kind === "step_verdict") return envelope.payload?.status === "passed";
    if (envelope.kind === "engine_state") {
      const step = panel.steps.find((s) => s.step_id === panel.current_step_id);
      const waiting = step?.hints?.tiers.some((t) => t.tier === 3 && t.state === "locked");
      return Boolean(waiting) && envelope.payload?.state !== "command";
    }
    return false;
  }

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
    scheduleUnlock();
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
      const result = store.applyEvent(envelope);
      if (result === "resync") sync();
      else if (result === "applied" && needsRefresh(envelope)) refreshPanel();
    };
  }

  store.reset(workspaceId);
  sync();
  return () => {
    stopped = true;
    if (unlockTimer) clearTimeout(unlockTimer);
    if (source) source.close();
  };
}
