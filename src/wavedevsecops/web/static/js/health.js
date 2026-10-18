// Point de vie : GET /api/health à intervalle régulier. Le flux SSE (Story 2.2) s'y ajoutera.

export const HEALTH_INTERVAL_MS = 5000;
export const STOPPED_MESSAGE =
  "WaveDevSecOps ne répond plus. Relancez-le ; votre progression est enregistrée.";

async function ping(fetchImpl) {
  try {
    const response = await fetchImpl("/api/health", {
      cache: "no-store",
      credentials: "same-origin",
    });
    return response.ok;
  } catch (err) {
    return false;
  }
}

/** Interroge le serveur ; `onChange(alive)` est appelé au premier résultat puis à chaque bascule. */
export function watchHealth(onChange, { interval = HEALTH_INTERVAL_MS, fetchImpl = fetch } = {}) {
  let last = null;
  let stopped = false;
  async function tick() {
    const alive = await ping(fetchImpl);
    if (stopped) return;
    if (alive !== last) {
      last = alive;
      onChange(alive);
    }
  }
  tick();
  const timer = setInterval(tick, interval);
  return () => {
    stopped = true;
    clearInterval(timer);
  };
}
