// Export du rapport de progression (Story 6.5). En pied du catalogue : « Exporter mon rapport »
// ouvre `report-preview`, qui liste ce que le serveur a calculé (scores, indices, remises à zéro,
// horodatages) et propose « Exporter en HTML » et « Exporter en CSV ». Le front n'affiche et
// n'enregistre que ce que dit le serveur (AD-2) ; rien n'est envoyé : l'apprenant enregistre le
// fichier, puis choisit à qui le transmettre.
import { el } from "./dom.js";

export const PRIVACY_TEXT = "Rien n'est envoyé : vous choisissez à qui transmettre le fichier.";
export const OPEN_TEXT = "Exporter mon rapport";
export const FORMATS = [
  { key: "html", label: "Exporter en HTML" },
  { key: "csv", label: "Exporter en CSV" },
];
export const SAVE_FAILED = "Le fichier n'a pas pu être enregistré";
export const RETRY_TEXT = "Réessayer";
const LOAD_FAILED = "Le rapport n'a pas pu être lu. Rechargez la page.";

/** « Le fichier n'a pas pu être enregistré : <cause>. » (la cause se termine par un point). */
export function failureText(cause) {
  const text = String(cause || "cause inconnue").trim();
  return `${SAVE_FAILED} : ${/[.!?]$/.test(text) ? text : `${text}.`}`;
}

async function reasonOf(response, fallback) {
  try {
    return (await response.json()).reason_text || fallback;
  } catch (err) {
    return fallback;
  }
}

/** Récupère le rapport du serveur ; lève une erreur en français si la lecture échoue. */
export async function loadReport({ fetchImpl = (...a) => fetch(...a) } = {}) {
  let response;
  try {
    response = await fetchImpl("/api/report", { cache: "no-store", credentials: "same-origin" });
  } catch (err) {
    throw new Error(LOAD_FAILED);
  }
  if (!response.ok) throw new Error(await reasonOf(response, LOAD_FAILED));
  return response.json();
}

/**
 * Enregistre `blob` : boîte d'enregistrement du système si le navigateur ou la fenêtre
 * pywebview la fournit, sinon téléchargement. Rend `false` si l'apprenant annule.
 */
export async function saveBlob(blob, filename, { win = window, doc = document } = {}) {
  if (typeof win.showSaveFilePicker === "function") {
    let handle;
    try {
      handle = await win.showSaveFilePicker({ suggestedName: filename });
    } catch (err) {
      if (err && err.name === "AbortError") return false;
      throw err;
    }
    const writable = await handle.createWritable();
    await writable.write(blob);
    await writable.close();
    return true;
  }
  const url = win.URL.createObjectURL(blob);
  const link = doc.createElement("a");
  link.href = url;
  link.download = filename;
  doc.body.append(link);
  link.click();
  link.remove();
  win.URL.revokeObjectURL(url);
  return true;
}

/** Demande le fichier au serveur puis l'enregistre ; lève une erreur dont le message est la cause. */
export async function exportReport(
  format,
  { fetchImpl = (...a) => fetch(...a), save = saveBlob } = {},
) {
  let response;
  try {
    response = await fetchImpl(`/api/report/export?format=${encodeURIComponent(format)}`, {
      cache: "no-store",
      credentials: "same-origin",
    });
  } catch (err) {
    throw new Error("l'application ne répond pas");
  }
  if (!response.ok) throw new Error(await reasonOf(response, `réponse ${response.status}`));
  const disposition = response.headers && response.headers.get("Content-Disposition");
  const named = /filename="([^"]+)"/.exec(disposition || "");
  const filename = named ? named[1] : `rapport-wavedevsecops.${format}`;
  return save(await response.blob(), filename);
}

function row(label, value) {
  const item = el("li", "report-row");
  item.textContent = `${label} ${value}`;
  return item;
}

/** `report-preview` : le contenu du rapport, la phrase de confidentialité, les deux exports. */
export function renderPreview(container, report, { fetchImpl, save } = {}) {
  container.replaceChildren();
  const panel = el("section", "report-preview", { "aria-labelledby": "report-title" });
  const title = el("h2", "report-title", { id: "report-title" });
  title.textContent = OPEN_TEXT;
  const privacy = el("p", "report-privacy");
  privacy.textContent = report.privacy_text || PRIVACY_TEXT;
  const dates = el("ul", "report-dates");
  dates.append(
    row("Installation :", report.installed_text),
    row("Premier lancement :", report.first_launch_text),
  );
  panel.append(title, privacy, dates);
  if (report.empty) {
    const empty = el("p", "report-empty");
    empty.textContent = report.empty_text;
    panel.append(empty);
  }
  for (const track of report.tracks) {
    const block = el("div", "report-track", { "data-track": track.track });
    const heading = el("h3", "report-track-title");
    heading.textContent = track.label;
    const list = el("ul", "report-rows");
    for (const r of track.rows) {
      const item = el("li", "report-row", { "data-scenario": r.scenario_id });
      const parts = [`${r.title} (mode ${r.mode})`, r.state_text, r.score_text, r.hints_text, r.resets_text];
      if (r.completed_text) parts.push(`terminé le ${r.completed_text}`);
      item.textContent = parts.join(" · ");
      list.append(item);
    }
    block.append(heading, list);
    panel.append(block);
  }
  const notice = el("div", "report-notice");
  const actions = el("div", "report-actions");
  let last = null;
  const run = async (format) => {
    last = format;
    notice.replaceChildren();
    try {
      await exportReport(format, { fetchImpl, save });
    } catch (err) {
      const card = el("div", "notice-card notice-error", { role: "alert" });
      const text = el("p", "notice-text");
      text.textContent = failureText(err && err.message);
      const retry = el("button", "btn btn-secondary", { type: "button" });
      retry.textContent = RETRY_TEXT;
      retry.addEventListener("click", () => run(last));
      card.append(text, retry);
      notice.replaceChildren(card);
      retry.focus();
    }
  };
  for (const format of FORMATS) {
    const button = el("button", "btn btn-secondary", { type: "button", "data-format": format.key });
    button.textContent = format.label;
    button.addEventListener("click", () => run(format.key));
    actions.append(button);
  }
  panel.append(actions, notice);
  container.append(panel);
  return panel;
}

/**
 * Pied du catalogue : bouton « Exporter mon rapport » et phrase de confidentialité. Le clic lit
 * le rapport et ouvre `report-preview` sous le bouton.
 */
export function renderReportEntry(container, { fetchImpl, save } = {}) {
  const footer = el("footer", "report-entry");
  const button = el("button", "btn btn-secondary", { type: "button", "aria-expanded": "false" });
  button.textContent = OPEN_TEXT;
  const privacy = el("p", "report-privacy");
  privacy.textContent = PRIVACY_TEXT;
  const preview = el("div", "report-preview-slot");
  const alert = el("p", "scenario-card-alert", { role: "alert" });
  button.addEventListener("click", async () => {
    alert.textContent = "";
    try {
      const report = await loadReport({ fetchImpl });
      renderPreview(preview, report, { fetchImpl, save });
      button.setAttribute("aria-expanded", "true");
    } catch (err) {
      alert.textContent = err.message;
    }
  });
  footer.append(button, privacy, alert, preview);
  container.append(footer);
  return footer;
}
