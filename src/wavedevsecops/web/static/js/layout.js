// Disposition des volets : logique pure, sans DOM (testée sous Node). Le front ne mémorise que
// la disposition (AD-2) : volets masqués, proportions, volet agrandi. Rien de ce qui dépend d'un
// scénario n'y entre, donc la configuration survit au changement de scénario et au rechargement.
//
// Les volets viennent du registre (panes.js) : { id, row, rowShare, share, foldRank }.
//   - row      : rangée du volet (1 = haute) ; les volets d'une même rangée sont côte à côte ;
//   - rowShare : part de hauteur de la rangée (lue sur le premier volet de la rangée) ;
//   - share    : part de largeur du volet dans sa rangée ;
//   - foldRank : ordre de repli sous la taille nominale (plus petit = replié d'abord) ;
//                absent : jamais replié avant le mode « une vue ».

export const MIN_WIDTH = 240;
export const MIN_HEIGHT = 160;
export const STEP = 16;
export const GUTTER = 8;
export const COMPACT_BELOW = 1280;
export const STORAGE_KEY = "wds.layout";

const num = (value, fallback) => (Number.isFinite(value) && value > 0 ? value : fallback);

/** Rangées du registre, dans l'ordre de lecture : [{ row, share, panes: [pane…] }]. */
export function rowsOf(panes, only = null) {
  const rows = new Map();
  const shares = new Map(); // part de la rangée : premier volet qui la déclare, même masqué
  for (const pane of [...panes].sort((a, b) => a.step - b.step)) {
    const key = pane.row ?? 1;
    if (!shares.has(key) && pane.rowShare != null) shares.set(key, num(pane.rowShare, 1));
  }
  for (const pane of [...panes].sort((a, b) => a.step - b.step)) {
    if (only && !only.has(pane.id)) continue;
    const key = pane.row ?? 1;
    if (!rows.has(key)) rows.set(key, { row: key, share: shares.get(key) ?? 1, panes: [] });
    rows.get(key).panes.push(pane);
  }
  return [...rows.values()].sort((a, b) => a.row - b.row);
}

export function defaultConfig() {
  return { hidden: [], rows: {}, widths: {}, maximized: null };
}

/** Nettoie une configuration lue du navigateur : ids inconnus ignorés, au moins une vue visible. */
export function sanitize(raw, panes) {
  const ids = new Set(panes.map((pane) => pane.id));
  const config = defaultConfig();
  if (!raw || typeof raw !== "object") return config;
  if (Array.isArray(raw.hidden)) {
    config.hidden = [...new Set(raw.hidden.filter((id) => ids.has(id)))];
  }
  if (config.hidden.length >= ids.size) config.hidden = [];
  for (const field of ["rows", "widths"]) {
    const source = raw[field];
    if (!source || typeof source !== "object") continue;
    for (const [key, value] of Object.entries(source)) {
      const known = field === "widths" ? ids.has(key) : panes.some((p) => String(p.row ?? 1) === key);
      if (known && Number.isFinite(value) && value > 0) config[field][key] = value;
    }
  }
  return config;
}

export function visibleIds(config, panes) {
  const hidden = new Set(config.hidden);
  return new Set(panes.filter((pane) => !hidden.has(pane.id)).map((pane) => pane.id));
}

/** Masque un volet ; refusé (null) s'il est le dernier visible. */
export function hidePane(config, panes, id) {
  if (config.hidden.includes(id)) return config;
  if (visibleIds(config, panes).size <= 1) return null;
  return {
    ...config,
    hidden: [...config.hidden, id],
    maximized: config.maximized === id ? null : config.maximized,
  };
}

export function showPane(config, id) {
  return { ...config, hidden: config.hidden.filter((other) => other !== id) };
}

export function toggleMaximized(config, id) {
  return { ...config, maximized: config.maximized === id ? null : id };
}

/** Parts de largeur (volets d'une rangée) ou de hauteur (rangées), valeurs par défaut comprises. */
export function paneWeight(config, pane) {
  return num(config.widths[pane.id], num(pane.share, 1));
}

export function rowWeight(config, row) {
  return num(config.rows[String(row.row)], row.share);
}

/** Répartit `total` px entre `weights`, gouttières déduites ; chaque taille respecte `min`. */
export function sizesFromWeights(weights, total, min, gutter = GUTTER) {
  const room = Math.max(0, total - gutter * (weights.length - 1));
  const sum = weights.reduce((a, b) => a + b, 0) || 1;
  return clampSizes(
    weights.map((w) => (w / sum) * room),
    min,
  );
}

/** Ramène chaque taille à `min` au moins, en prenant l'excédent aux plus grandes. */
export function clampSizes(sizes, min) {
  const out = sizes.slice();
  let deficit = 0;
  for (let i = 0; i < out.length; i++) {
    if (out[i] < min) {
      deficit += min - out[i];
      out[i] = min;
    }
  }
  while (deficit > 0.5) {
    let widest = 0;
    for (let i = 1; i < out.length; i++) if (out[i] > out[widest]) widest = i;
    const give = Math.min(deficit, out[widest] - min);
    if (give <= 0) break;
    out[widest] -= give;
    deficit -= give;
  }
  return out;
}

/** Déplace la frontière après `index` de `delta` px ; les deux voisins gardent `min` au moins. */
export function resizeSizes(sizes, index, delta, min) {
  if (index < 0 || index >= sizes.length - 1) return sizes.slice();
  const out = sizes.slice();
  const pair = out[index] + out[index + 1];
  const next = Math.min(Math.max(out[index] + delta, min), Math.max(pair - min, min));
  out[index] = next;
  out[index + 1] = pair - next;
  return out;
}

/** Valeurs ARIA d'une poignée : taille du volet qui précède, bornes de son déplacement. */
export function separatorValues(sizes, index, min) {
  const pair = sizes[index] + sizes[index + 1];
  return {
    now: Math.round(sizes[index]),
    min: Math.round(min),
    max: Math.max(Math.round(pair - min), Math.round(min)),
  };
}

/** Écrit les tailles en px d'un groupe comme parts, sans fausser les parts des volets masqués. */
export function weightsFromSizes(sizes, previousWeights) {
  const sumWeights = previousWeights.reduce((a, b) => a + b, 0);
  const sumSizes = sizes.reduce((a, b) => a + b, 0) || 1;
  return sizes.map((size) => (size / sumSizes) * sumWeights);
}

export function setPaneWidths(config, ids, weights) {
  const widths = { ...config.widths };
  ids.forEach((id, i) => {
    widths[id] = weights[i];
  });
  return { ...config, widths };
}

export function setRowWeights(config, rowKeys, weights) {
  const rows = { ...config.rows };
  rowKeys.forEach((key, i) => {
    rows[String(key)] = weights[i];
  });
  return { ...config, rows };
}

/** Double-clic sur une poignée : proportions par défaut des volets (ou rangées) concernés. */
export function resetWeights(config, { paneIds = [], rowKeys = [] }) {
  const widths = { ...config.widths };
  const rows = { ...config.rows };
  for (const id of paneIds) delete widths[id];
  for (const key of rowKeys) delete rows[String(key)];
  return { ...config, widths, rows };
}

/**
 * Disposition effective pour une fenêtre `width` × `height` (zone des vues, panneau Scénario
 * exclu). Rend `{ mode, shown, hidden, rows }` :
 *   - "full"   : tous les volets visibles tiennent à 240 × 160 au moins ;
 *   - "fold"   : des volets sont repliés en puces (repli par masquage, `foldRank` croissant) ;
 *   - "single" : sous 1280 px de large, ou si rien ne tient : une seule vue, les autres en puces.
 * `pinned` : volets réaffichés par l'apprenant malgré le repli, replié en dernier.
 */
export function effectiveLayout(panes, config, { width, height, viewport = width }, pinned = new Set(), focus = null) {
  const userHidden = new Set(config.hidden);
  let visible = panes.filter((pane) => !userHidden.has(pane.id));
  if (visible.length === 0) visible = panes.slice(0, 1);
  const order = (list) => [...list].sort((a, b) => a.step - b.step);
  const result = (mode, shownPanes) => {
    const shown = new Set(shownPanes.map((pane) => pane.id));
    return {
      mode,
      shown: order(shownPanes).map((pane) => pane.id),
      hidden: new Set(panes.filter((pane) => !shown.has(pane.id)).map((pane) => pane.id)),
      rows: rowsOf(panes, shown),
    };
  };

  const maximized = config.maximized && visible.some((p) => p.id === config.maximized);
  if (maximized) return { ...result("single", visible.filter((p) => p.id === config.maximized)), maximized: true };

  const single = () => {
    const wanted = (focus && visible.find((pane) => pane.id === focus)) || order(visible)[0];
    return { ...result("single", [wanted]), maximized: false };
  };
  if (viewport < COMPACT_BELOW) return single();

  let current = visible;
  let folded = false;
  while (!fits(current, width, height)) {
    const candidates = current
      .filter((pane) => pane.foldRank != null)
      .sort((a, b) => Number(pinned.has(a.id)) - Number(pinned.has(b.id)) || a.foldRank - b.foldRank);
    if (candidates.length === 0 || current.length <= 1) return single();
    current = current.filter((pane) => pane.id !== candidates[0].id);
    folded = true;
  }
  return { ...result(folded ? "fold" : "full", current), maximized: false };
}

/** Vrai si les volets tiennent dans `width` × `height` à leur taille minimale. */
export function fits(visible, width, height) {
  const rows = rowsOf(visible);
  if (rows.length * MIN_HEIGHT + GUTTER * (rows.length - 1) > height) return false;
  return rows.every(
    (row) => row.panes.length * MIN_WIDTH + GUTTER * (row.panes.length - 1) <= width,
  );
}

/** Index du prochain élément d'une liste à focus itinérant (flèches, Début, Fin). */
export function rovingIndex(key, index, length) {
  if (length === 0) return -1;
  switch (key) {
    case "ArrowRight":
    case "ArrowDown":
      return Math.min(index + 1, length - 1);
    case "ArrowLeft":
    case "ArrowUp":
      return Math.max(index - 1, 0);
    case "Home":
      return 0;
    case "End":
      return length - 1;
    default:
      return index;
  }
}

/** Zone suivante (F6) ou précédente (Maj+F6) dans la boucle des zones. */
export function nextZone(count, index, backwards) {
  if (count === 0) return -1;
  if (index < 0) return backwards ? count - 1 : 0;
  return (index + (backwards ? count - 1 : 1)) % count;
}

/** Touche de redimensionnement d'une poignée → déplacement en px (null : touche ignorée). */
export function keyDelta(key, orientation) {
  const horizontal = orientation === "vertical"; // séparateur vertical : on déplace en largeur
  const grow = horizontal ? "ArrowRight" : "ArrowDown";
  const shrink = horizontal ? "ArrowLeft" : "ArrowUp";
  if (key === grow) return STEP;
  if (key === shrink) return -STEP;
  return null;
}

// --- mémorisation (try/catch : le navigateur peut la refuser) ---------------------------------

function defaultStorage() {
  try {
    return globalThis.localStorage || null;
  } catch (err) {
    return null;
  }
}

export function loadConfig(panes, storage = defaultStorage()) {
  try {
    return sanitize(JSON.parse(storage.getItem(STORAGE_KEY) || "null"), panes);
  } catch (err) {
    return defaultConfig();
  }
}

export function saveConfig(config, storage = defaultStorage()) {
  try {
    const { hidden, rows, widths } = config; // le volet agrandi ne se mémorise pas
    storage.setItem(STORAGE_KEY, JSON.stringify({ hidden, rows, widths }));
    return true;
  } catch (err) {
    return false; // la disposition s'applique à cette page même si elle ne se garde pas
  }
}
