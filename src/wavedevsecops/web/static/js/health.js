// Point de vie : GET /api/health à intervalle régulier. Le flux SSE (Story 2.2) s'y ajoutera.

export const HEALTH_INTERVAL_MS = 5000;
export const HEALTH_TIMEOUT_MS = 4000;
// Échecs consécutifs avant de déclarer l'arrêt : un raté isolé ne fait pas clignoter le bandeau.
export const HEALTH_FAILURES = 2;
export const STOPPED_MESSAGE =
  "WaveDevSecOps ne répond plus. Relancez-le ; votre progression est enregistrée.";

async function ping(fetchImpl, timeout) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetchImpl("/api/health", {
      cache: "no-store",
      credentials: "same-origin",
      signal: controller.signal,
    });
    return response.ok;
  } catch (err) {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

/** Interroge le serveur ; `onChange(alive)` est appelé au premier résultat puis à chaque bascule. */
export function watchHealth(
  onChange,
  {
    interval = HEALTH_INTERVAL_MS,
    timeout = HEALTH_TIMEOUT_MS,
    failures = HEALTH_FAILURES,
    fetchImpl = (...args) => fetch(...args),
  } = {},
) {
  let last = null;
  let misses = 0;
  let stopped = false;
  let inFlight = false;
  async function tick() {
    if (inFlight || stopped) return; // pas de requêtes empilées si le serveur traîne
    inFlight = true;
    try {
      const ok = await ping(fetchImpl, Math.min(timeout, interval));
      if (stopped) return;
      misses = ok ? 0 : misses + 1;
      const alive = ok || (misses < failures && last !== false);
      if (alive !== last) {
        last = alive;
        onChange(alive);
      }
    } finally {
      inFlight = false;
    }
  }
  tick();
  const timer = setInterval(tick, interval);
  return () => {
    stopped = true;
    clearInterval(timer);
  };
}
