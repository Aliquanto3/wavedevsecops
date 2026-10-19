// Vue « Code » (story 2.8) : fichiers du bac à sable, éditeur et diff.
// Le serveur lit et projette (AD-2) : liste des fichiers, contenu avec son empreinte (`base_hash`),
// diff avec les `element_id`, numéros et noms accessibles de chaque ligne. Le front met en forme et
// garde l'état d'édition (tampons non enregistrés). Toute écriture est l'intention `save_file` : elle
// passe par la file d'opérations, et un disque qui a changé la refuse (409), d'où le choix
// « Garder ma version » / « Recharger ».
import { markCorrection } from "./correction.js";
import { designationFor, markDesignated } from "./designation.js";
import { el } from "./dom.js";
import { conflictLines, createEditor, CONFLICT_MARK } from "./editor.js";
import { diffSource, linkingFor } from "./linking.js";
import { pipelineFocusFor } from "./pipeline-focus.js";
import { selectionFor } from "./selection.js";

export const PIPELINE_MODE_TEXT = "Pipeline";
export const PIPELINE_TABS_LABEL = "Écritures du pipeline";
export const PIPELINE_JOBS_LABEL = "Tâches du pipeline";
export const PIPELINE_MISSING_TEXT = "tâche non repérée";
export const PIPELINE_ABSENT_TEXT = "Ce fichier n'existe pas à ce commit.";
export const PIPELINE_ERROR_TEXT = "Le pipeline n'a pas pu être lu.";
export const MARKER = { added: "+", removed: "−", context: " " };
export const KIND_CLASS = { added: "is-added", removed: "is-removed", context: "is-context" };
export const UNSAVED_TEXT = "non enregistré";
export const SAVED_TEXT = "Enregistré";
export const CONFLICT_TEXT = "Le fichier a changé sur le disque.";
export const EXTERNAL_TEXT = "Modifié hors de l'application";
export const KEEP_TEXT = "Garder ma version";
export const RELOAD_TEXT = "Recharger";
export const SAVE_TEXT = "Enregistrer";
export const OPEN_EXTERNAL_TEXT = "Ouvrir dans mon éditeur";
export const OFFLINE_TEXT = "WaveDevSecOps ne répond pas. Rechargez la page.";
export const NO_FILE = {
  title: "Aucun fichier ouvert.",
  text: "Choisissez un fichier dans la liste pour le modifier.",
};
export const WORKTREE = "worktree";
const SETTLE_TRIES = 20;

function text(tag, className, value) {
  const node = el(tag, className);
  node.textContent = value;
  return node;
}

function button(label, className, onClick) {
  const node = el("button", className, { type: "button" });
  node.textContent = label;
  node.addEventListener("click", onClick);
  return node;
}

/** « Commit a1b2c3d » pour une sélection `commit:<sha>`, sinon l'arbre de travail. */
export function diffTarget(selected) {
  return selected && selected.startsWith("commit:") ? selected.slice("commit:".length) : WORKTREE;
}

/** Corps d'un diff (en-têtes de fichier, blocs, lignes) : chacun focalisable, 24 px de haut. */
export function buildDiff(diff) {
  const wrap = el("div", "diff-view", { role: "group", "aria-label": diff.target_text });
  if (!diff.files.length) {
    wrap.append(text("p", "empty", diff.empty_text));
    return wrap;
  }
  for (const file of diff.files) {
    const group = el("div", "diff-file");
    const head = el("div", "diff-file-header", {
      role: "heading",
      "aria-level": "3",
      tabindex: "-1",
      "data-roving": true,
      "data-element-id": file.element_id,
      "aria-label": file.a11y_name_text,
    });
    head.append(text("code", "diff-path", file.path), text("span", "diff-meta", file.summary_text));
    group.append(head);
    for (const hunk of file.hunks) {
      group.append(text("div", "diff-hunk", hunk.header_text));
      for (const line of hunk.lines) {
        const row = el("div", `diff-line ${KIND_CLASS[line.kind]}${line.conflict ? " is-conflict" : ""}`, {
          role: "group",
          tabindex: "-1",
          "data-roving": true,
          "data-element-id": line.element_id,
          "aria-label": line.a11y_name_text,
        });
        const numbers = text("span", "diff-no", String(line.new_no ?? line.old_no ?? ""));
        numbers.setAttribute("aria-hidden", "true");
        const marker = text("span", "diff-marker", MARKER[line.kind]);
        marker.setAttribute("aria-hidden", "true");
        const body = text("span", "diff-text", line.text);
        row.append(numbers, marker, body);
        if (line.conflict) row.append(text("span", "diff-conflict-mark", `${CONFLICT_MARK} conflit`));
        group.append(row);
      }
    }
    wrap.append(group);
  }
  if (diff.truncated) wrap.append(text("p", "empty", diff.truncated_text));
  return wrap;
}

// --- pipeline-tabs (story 7.6) -----------------------------------------------------------------

/** Texte du rang d'une tâche dans un onglet : « lignes 12 à 18 », ou pourquoi il n'y en a pas. */
export function rangeText(tab, job) {
  if (!tab.available) return PIPELINE_ABSENT_TEXT;
  const found = job && tab.jobs[job];
  return found ? found.range_text : PIPELINE_MISSING_TEXT;
}

/** Pose `is-job` (tâche ouverte) et `is-lit` (check survolé) sur les lignes du panneau ouvert. */
export function paintPipeline(root, data, state) {
  const tab = data.tabs.find((item) => item.id === state.tab);
  if (!tab) return;
  const within = (range, number) => Boolean(range) && number >= range.first && number <= range.last;
  const opened = state.job && tab.jobs[state.job];
  const lit = state.hover && tab.jobs[state.hover];
  for (const line of root.querySelectorAll(".pipeline-line")) {
    const number = Number(line.getAttribute("data-line"));
    if (within(opened, number)) line.classList.add("is-job");
    else line.classList.remove("is-job");
    if (within(lit, number)) line.classList.add("is-lit");
    else line.classList.remove("is-lit");
  }
}

/** `pipeline-tabs` : GitHub Actions | Jenkins | GitLab CI, en lecture seule, tâche surlignée. */
export function buildPipeline(data, state) {
  const wrap = el("div", "pipeline-view");
  const head = el("div", "pipeline-head");
  head.append(text("p", "pipeline-title", data.title_text), text("span", "tag pipeline-readonly", data.read_only_text));
  wrap.append(head, text("p", "pipeline-not-run", data.not_executed_text));
  const jobs = el("ul", "pipeline-jobs", { "aria-label": PIPELINE_JOBS_LABEL });
  for (const item of data.jobs) {
    const row = el("li", "pipeline-job-item");
    const pick = el("button", "pipeline-job", {
      type: "button",
      "data-job": item.job_id,
      "aria-pressed": String(item.job_id === state.job),
    });
    pick.append(text("code", "pipeline-job-id", item.job_id), text("span", "pipeline-job-label", item.label_text));
    row.append(pick);
    jobs.append(row);
  }
  const tabs = el("div", "pipeline-tabs", { role: "tablist", "aria-label": PIPELINE_TABS_LABEL });
  for (const tab of data.tabs) {
    const on = tab.id === state.tab;
    const pick = el("button", "pipeline-tab", {
      type: "button",
      role: "tab",
      id: `pipeline-tab-${tab.id}`,
      "data-tab": tab.id,
      "aria-selected": String(on),
      "aria-controls": "pipeline-panel",
    });
    pick.append(text("span", "pipeline-tab-name", tab.label_text), text("span", "pipeline-tab-range", rangeText(tab, state.job)));
    tabs.append(pick);
  }
  const current = data.tabs.find((tab) => tab.id === state.tab) || data.tabs[0];
  const panel = el("div", "pipeline-panel", {
    role: "tabpanel",
    id: "pipeline-panel",
    "aria-labelledby": current ? `pipeline-tab-${current.id}` : false,
  });
  if (current) {
    panel.append(text("code", "pipeline-path", current.path));
    if (!current.available) {
      panel.append(text("p", "empty", PIPELINE_ABSENT_TEXT));
    } else {
      const lines = el("div", "pipeline-lines", {
        role: "region",
        tabindex: "0",
        "data-roving": true,
        "aria-label": `${current.path}, ${data.read_only_text.toLowerCase()}`,
      });
      const rows = current.content.split("\n");
      if (rows[rows.length - 1] === "") rows.pop();
      rows.forEach((value, index) => {
        const row = el("div", "pipeline-line", { "data-line": index + 1 });
        const no = text("span", "pipeline-no", String(index + 1));
        no.setAttribute("aria-hidden", "true");
        row.append(no, text("span", "pipeline-text", value));
        lines.append(row);
      });
      panel.append(lines);
    }
  }
  wrap.append(jobs, tabs, panel);
  if (data.notice_text) wrap.append(text("p", "pipeline-notice", data.notice_text));
  paintPipeline(wrap, data, state);
  return wrap;
}

export function renderCode(body, ctx, renderEmpty, options = {}) {
  const { store } = ctx;
  const selection = selectionFor(store);
  const designation = designationFor(store);
  const send = (...args) => (options.fetch || globalThis.fetch)(...args);
  const settleMs = options.settleMs ?? 150;
  const base = () => `/api/ws/${encodeURIComponent(store.state.workspaceId)}`;

  // État d'édition : un tampon par fichier ouvert, gardé tant que la vue vit.
  const buffers = new Map(); // chemin → { content, saved, hash, editable, note, conflict }
  let files = [];
  let truncated = false;
  let current = null; // chemin ouvert
  let mode = "file"; // « file » ou « diff »
  let drawnViews;
  let diffToken = 0;
  const linking = linkingFor(store);
  // Cible du diff affiché : un commit sélectionné, sinon l'arbre de travail. Une autre sélection
  // (ligne de diff, ref, PR) laisse le diff en place ; seul l'effacement ramène à l'arbre.
  let shownTarget = diffTarget(selection.value);
  let pruning = false;
  const focus = pipelineFocusFor(store);
  // `pipeline-tabs` : écritures lues au SHA de tête de la PR demandée ; la tâche et l'onglet ouverts
  // sont gardés quand on change d'onglet ou de tâche.
  const pipe = { data: null, number: 0, tab: "github", job: null, token: 0 };

  const root = el("div", "code-view");
  const nav = el("nav", "code-files", { "aria-label": "Fichiers du bac à sable" });
  const main = el("div", "code-main");
  root.append(nav, main);
  body.replaceChildren(root);

  const modes = el("div", "code-modes", { role: "group", "aria-label": "Affichage" });
  const fileTab = button("Fichier", "code-mode", () => setMode("file"));
  const diffTab = button("Diff", "code-mode", () => setMode("diff"));
  const pipelineTab = button(PIPELINE_MODE_TEXT, "code-mode", () => setMode("pipeline"));
  modes.append(fileTab, diffTab); // « Pipeline » s'ajoute au premier « Voir dans le pipeline »
  const filePanel = el("div", "code-panel code-file-panel");
  const diffPanel = el("div", "code-panel code-diff-panel");
  const status = el("p", "code-status", { "aria-live": "polite" });
  // `external-change-notice` : ligne en haut de l'éditeur après une modification venue d'ailleurs.
  const notice = el("p", "external-change-notice", { role: "status", hidden: true });
  notice.textContent = EXTERNAL_TEXT;
  const pipelinePanel = el("div", "code-panel code-pipeline-panel");
  pipelinePanel.hidden = true;
  main.append(notice, modes, status, filePanel, diffPanel, pipelinePanel);

  const editor = createEditor({ onChange: onEdit, onSave: save });
  const title = el("div", "code-file-title");
  const pathLabel = el("code", "code-path");
  const unsaved = text("span", "code-unsaved", "");
  title.append(pathLabel, unsaved);
  const saveButton = button(SAVE_TEXT, "code-save", () => save());
  const externalButton = button(OPEN_EXTERNAL_TEXT, "code-external", () => openExternal());
  const actions = el("div", "code-actions");
  actions.append(saveButton, externalButton);
  const conflictBar = el("div", "code-conflict", { role: "alert", hidden: true });
  const conflictMsg = el("p", "code-conflict-text");
  const keepButton = button(KEEP_TEXT, "code-keep", () => keepMine());
  const reloadButton = button(RELOAD_TEXT, "code-reload", () => reloadTheirs());
  conflictBar.append(conflictMsg, keepButton, reloadButton);
  const markers = el("p", "code-markers", { hidden: true });
  const note = el("p", "empty code-note", { hidden: true });
  const empty = el("div", "code-empty");
  renderEmpty(empty, NO_FILE);
  filePanel.append(empty, title, actions, conflictBar, markers, note, editor.root);

  function say(message) {
    status.textContent = message || "";
  }

  async function failure(response, fallback) {
    try {
      return (await response.json()).reason_text || fallback;
    } catch (err) {
      return fallback;
    }
  }

  function isDirty(path) {
    const buffer = buffers.get(path);
    return Boolean(buffer && buffer.editable && buffer.content !== buffer.saved);
  }

  // --- liste des fichiers ----------------------------------------------------------------
  function drawFiles() {
    const focusedPath = document.activeElement?.getAttribute?.("data-path");
    const list = el("ul", "code-file-list");
    for (const path of files) {
      const item = el("li", "code-file-item");
      const open = el("button", `code-file${path === current ? " is-open" : ""}`, {
        type: "button",
        "data-path": path,
        "aria-pressed": String(path === current),
      });
      open.append(text("code", "code-file-name", path));
      if (isDirty(path)) {
        const dot = text("span", "dirty-dot", "●");
        dot.setAttribute("aria-hidden", "true");
        open.append(dot, text("span", "visually-hidden", ` ${UNSAVED_TEXT}`));
      }
      item.append(open);
      list.append(item);
    }
    nav.replaceChildren(list);
    if (truncated) nav.append(text("p", "empty", "La liste est coupée : utilisez « ls » dans le terminal."));
    settleRoving(focusedPath);
  }

  nav.addEventListener("click", (event) => {
    const target = event.target.closest && event.target.closest("[data-path]");
    if (target) openFile(target.getAttribute("data-path"));
  });

  /** Un seul arrêt de tabulation par vue (workspace.js) : les nôtres ne le sont que si nul autre ne l'est. */
  function settleRoving(preferredPath) {
    const mine = [...root.querySelectorAll("button, [data-roving]")];
    for (const node of mine) node.setAttribute("tabindex", "-1");
    const section = body.parentElement;
    const others = section
      ? [...section.querySelectorAll("button, [data-roving]")].filter((node) => !root.contains(node))
      : [];
    if (others.some((node) => node.getAttribute("tabindex") === "0") || mine.length === 0) return;
    const chosen =
      mine.find((node) => node.getAttribute("data-path") === preferredPath) ||
      mine.find((node) => node.getAttribute("aria-pressed") === "true") ||
      mine[0];
    chosen.setAttribute("tabindex", "0");
  }

  async function loadTree() {
    try {
      const response = await send(`${base()}/code/tree`, { cache: "no-store", credentials: "same-origin" });
      if (!response.ok) return;
      const data = await response.json();
      files = data.files;
      truncated = Boolean(data.truncated);
      drawFiles();
    } catch (err) {
      say(OFFLINE_TEXT);
    }
  }

  // --- éditeur ---------------------------------------------------------------------------
  function drawFile() {
    const buffer = current && buffers.get(current);
    empty.hidden = Boolean(buffer);
    for (const node of [title, actions, editor.root]) node.hidden = !buffer;
    if (!buffer) {
      conflictBar.hidden = true;
      markers.hidden = true;
      note.hidden = true;
      return;
    }
    pathLabel.textContent = current;
    const dirty = isDirty(current);
    unsaved.textContent = dirty ? `● ${UNSAVED_TEXT}` : "";
    unsaved.className = dirty ? "code-unsaved is-dirty" : "code-unsaved";
    saveButton.hidden = !buffer.editable;
    editor.root.hidden = !buffer.editable;
    note.hidden = buffer.editable;
    note.textContent = buffer.note || "";
    conflictBar.hidden = !buffer.conflict;
    conflictMsg.textContent = buffer.conflict ? CONFLICT_TEXT : "";
    const lines = buffer.editable ? conflictLines(buffer.content) : [];
    markers.hidden = lines.length === 0;
    markers.textContent = lines.length
      ? `${CONFLICT_MARK} Marqueurs de conflit aux lignes ${lines.join(", ")} : modifiez le texte, puis enregistrez.`
      : "";
  }

  function onEdit(value) {
    const buffer = buffers.get(current);
    if (!buffer) return;
    buffer.content = value;
    say("");
    drawFile();
    drawFiles();
  }

  async function fetchFile(path) {
    const response = await send(`${base()}/code/file?path=${encodeURIComponent(path)}`, {
      cache: "no-store",
      credentials: "same-origin",
    });
    if (!response.ok) throw new Error(await failure(response, "Ce fichier n'a pas pu être lu."));
    return response.json();
  }

  async function openFile(path) {
    setMode("file");
    if (!buffers.has(path)) {
      try {
        const file = await fetchFile(path);
        buffers.set(path, {
          content: file.content,
          saved: file.content,
          hash: file.hash,
          editable: file.editable,
          note: file.note_text,
          conflict: null,
        });
      } catch (err) {
        say(err.message === "Failed to fetch" ? OFFLINE_TEXT : err.message);
        return;
      }
    }
    current = path;
    editor.setValue(buffers.get(path).content);
    editor.setReadOnly(!buffers.get(path).editable);
    say("");
    drawFile();
    drawFiles();
  }

  async function post(intent, payload) {
    return send(`${base()}/${intent}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(payload),
    });
  }

  /** Attend que le disque porte `content` (la file écrit après le 202), puis aligne l'empreinte. */
  async function settle(path, content) {
    for (let attempt = 0; attempt < SETTLE_TRIES; attempt += 1) {
      const file = await fetchFile(path);
      if (file.content === content) return file;
      await new Promise((resolve) => setTimeout(resolve, settleMs));
    }
    return null;
  }

  async function save() {
    const path = current;
    const buffer = path && buffers.get(path);
    if (!buffer || !buffer.editable) return;
    const sent = buffer.content;
    say("");
    try {
      const response = await post("save_file", { path, content: sent, base_hash: buffer.hash });
      if (response.status === 409) {
        const reason = await failure(response, CONFLICT_TEXT);
        const disk = await fetchFile(path).catch(() => null);
        if (disk && disk.hash !== buffer.hash) {
          buffer.conflict = { hash: disk.hash, content: disk.content };
          say("");
        } else {
          say(reason);
        }
        drawFile();
        return;
      }
      if (!response.ok) {
        say(await failure(response, "L'enregistrement a échoué. Réessayez."));
        return;
      }
      const written = await settle(path, sent.replace(/\r\n?/g, "\n"));
      if (!written) {
        // La file a refusé l'écriture (le disque a bougé entre-temps) : on relit l'état réel.
        const disk = await fetchFile(path).catch(() => null);
        if (disk && disk.hash !== buffer.hash) buffer.conflict = { hash: disk.hash, content: disk.content };
        else say("L'enregistrement n'a pas abouti. Réessayez.");
        drawFile();
        return;
      }
      buffer.hash = written.hash;
      buffer.saved = written.content;
      buffer.conflict = null;
      if (buffer.content === sent) buffer.content = written.content;
      say(`${SAVED_TEXT} : ${path}.`);
      notice.hidden = true; // la modification venue d'ailleurs est tranchée par l'enregistrement
      drawFile();
      drawFiles();
    } catch (err) {
      say(OFFLINE_TEXT);
    }
  }

  function keepMine() {
    const buffer = buffers.get(current);
    if (!buffer || !buffer.conflict) return;
    buffer.hash = buffer.conflict.hash; // j'écrase en connaissance de cause
    buffer.conflict = null;
    drawFile();
    save();
  }

  function reloadTheirs() {
    const buffer = buffers.get(current);
    if (!buffer || !buffer.conflict) return;
    buffer.hash = buffer.conflict.hash;
    buffer.content = buffer.conflict.content;
    buffer.saved = buffer.conflict.content;
    buffer.conflict = null;
    editor.setValue(buffer.content);
    say(`Fichier rechargé depuis le disque : ${current}.`);
    drawFile();
    drawFiles();
  }

  async function openExternal() {
    if (!current) return;
    try {
      const response = await post("open_external", { path: current });
      if (!response.ok) say(await failure(response, "Le fichier n'a pas pu être ouvert."));
    } catch (err) {
      say(OFFLINE_TEXT);
    }
  }

  /**
   * Après une modification venue d'ailleurs (terminal, éditeur externe) : relit un fichier propre ;
   * un fichier avec des changements non enregistrés garde sa version et propose le choix
   * « Garder ma version » / « Recharger » dès que le disque diffère (pas seulement à l'enregistrement).
   */
  async function refreshOpen() {
    const path = current;
    const buffer = path && buffers.get(path);
    if (!buffer) return;
    try {
      const file = await fetchFile(path);
      if (current !== path) return;
      if (isDirty(path)) {
        if (file.hash === buffer.hash) {
          // Le disque est revenu à la version ouverte : plus de conflit à trancher.
          if (buffer.conflict) {
            buffer.conflict = null;
            drawFile();
          }
        } else if (!(buffer.conflict && buffer.conflict.hash === file.hash)) {
          buffer.conflict = { hash: file.hash, content: file.content };
          drawFile();
        }
      } else if (file.hash !== buffer.hash || buffer.conflict) {
        // Tampon propre : la version du disque fait foi, un conflit d'avant n'a plus d'objet.
        Object.assign(buffer, { content: file.content, saved: file.content, hash: file.hash });
        buffer.conflict = null;
        editor.setValue(file.content);
        drawFile();
      }
    } catch (err) {
      // Fichier supprimé ou illisible : le tampon reste, l'enregistrement dira ce qui s'est passé.
    }
  }

  // --- diff ------------------------------------------------------------------------------
  async function loadDiff() {
    const token = (diffToken += 1);
    const target = shownTarget;
    try {
      const response = await send(`${base()}/code/diff?target=${encodeURIComponent(target)}`, {
        cache: "no-store",
        credentials: "same-origin",
      });
      if (token !== diffToken) return;
      if (!response.ok) {
        diffPanel.replaceChildren(text("p", "empty", await failure(response, "Le diff n'a pas pu être lu.")));
        return;
      }
      const diff = await response.json();
      if (token !== diffToken) return;
      const header = el("div", "diff-target");
      header.append(text("span", "diff-target-text", diff.target_text));
      if (target !== WORKTREE) {
        header.append(button("Arbre de travail", "diff-worktree", () => selection.set(null)));
      }
      diffPanel.replaceChildren(header, buildDiff(diff));
      flagDiff();
      linking.setSource("diff", diffSource(diff));
      // Une ligne de diff sélectionnée qui a disparu du diff relu ne reste pas sélectionnée.
      const picked = selection.value;
      if (
        picked &&
        picked.startsWith("diffline:") &&
        !diffPanel.querySelector(`[data-element-id="${picked}"]`)
      ) {
        pruning = true;
        selection.set(null);
        pruning = false;
      }
      settleRoving();
    } catch (err) {
      if (token === diffToken) say(OFFLINE_TEXT);
    }
  }

  // Fichiers et lignes du diff s'ouvrent à la désignation (story 5.6) selon les types que l'étape
  // accepte, comme les éléments que la projection marque `designable` dans les autres vues.
  function flagDiff() {
    for (const node of diffPanel.querySelectorAll("[data-element-id]")) {
      const kind = node.getAttribute("data-element-id").split(":")[0];
      node.setAttribute("data-designable", String(designation.accepts(kind)));
    }
    markDesignated(diffPanel, designation);
    markCorrection(diffPanel, designation);
  }
  designation.subscribe(flagDiff);

  // --- pipeline (trois écritures, lecture seule) ---------------------------------------------
  function drawPipeline(keepFocus = false) {
    if (mode !== "pipeline" || !pipe.data) return;
    const active = document.activeElement;
    const focused = keepFocus && active && pipelinePanel.contains(active) ? focusKey(active) : null;
    pipelinePanel.replaceChildren(buildPipeline(pipe.data, { ...pipe, hover: focus.hover }));
    settleRoving();
    const again = focused && [...pipelinePanel.querySelectorAll("button")].find((node) => focusKey(node) === focused);
    if (again) again.focus();
  }

  function focusKey(node) {
    return node.getAttribute("data-tab") || node.getAttribute("data-job") || "";
  }

  async function loadPipeline() {
    const token = (pipe.token += 1);
    try {
      const response = await send(`${base()}/code/pipeline?pr=${encodeURIComponent(pipe.number)}`, {
        cache: "no-store",
        credentials: "same-origin",
      });
      if (token !== pipe.token) return;
      if (!response.ok) {
        pipe.data = null;
        pipelinePanel.replaceChildren(text("p", "empty", await failure(response, PIPELINE_ERROR_TEXT)));
        return;
      }
      pipe.data = await response.json();
      if (token !== pipe.token) return;
      const tab = pipe.data.tabs.find((item) => item.id === pipe.tab);
      say(
        tab && pipe.job
          ? `Pipeline, ${pipe.job} : ${rangeText(tab, pipe.job)} dans ${tab.label_text}.`
          : "",
      );
      drawPipeline(true);
      pipelinePanel.querySelector(".pipeline-line.is-job")?.scrollIntoView?.({ block: "nearest" });
    } catch (err) {
      if (token === pipe.token) say(OFFLINE_TEXT);
    }
  }

  pipelinePanel.addEventListener("click", (event) => {
    const target = event.target.closest && event.target.closest("button");
    if (!target || !pipe.data) return;
    if (target.hasAttribute("data-tab")) pipe.tab = target.getAttribute("data-tab");
    else if (target.hasAttribute("data-job")) pipe.job = target.getAttribute("data-job");
    else return;
    drawPipeline(true);
  });

  focus.subscribe((kind) => {
    if (kind === "hover") {
      if (mode === "pipeline" && pipe.data) paintPipeline(pipelinePanel, pipe.data, { ...pipe, hover: focus.hover });
      return;
    }
    const request = focus.request;
    pipe.number = request.number;
    pipe.job = request.jobId;
    if (!pipelineTab.parentNode) modes.append(pipelineTab);
    setMode("pipeline");
  });

  function setMode(next) {
    mode = next;
    filePanel.hidden = mode !== "file";
    diffPanel.hidden = mode !== "diff";
    pipelinePanel.hidden = mode !== "pipeline";
    fileTab.setAttribute("aria-pressed", String(mode === "file"));
    diffTab.setAttribute("aria-pressed", String(mode === "diff"));
    pipelineTab.setAttribute("aria-pressed", String(mode === "pipeline"));
    if (mode === "diff") loadDiff();
    if (mode === "pipeline") loadPipeline();
    else pipelinePanel.replaceChildren(); // ses boutons ne restent pas dans l'ordre de tabulation
    settleRoving();
  }

  // Sélectionner un commit (graphe, liste) montre son diff ; effacer la sélection, l'arbre de travail.
  selection.subscribe((value) => {
    let target = shownTarget;
    if (value && value.startsWith("commit:")) target = diffTarget(value);
    else if (!value && !pruning) target = WORKTREE;
    const changed = target !== shownTarget;
    shownTarget = target;
    if (value && value.startsWith("commit:")) setMode("diff");
    else if (mode === "diff" && changed) loadDiff();
  });

  let seenExternal = store.state.externalChange || 0;
  store.subscribe((state) => {
    const external = state.externalChange || 0;
    // Le compteur repart de 0 au changement d'espace : la ligne ne vaut que pour l'espace vu.
    if (external > seenExternal) notice.hidden = false;
    else if (external < seenExternal) notice.hidden = true;
    seenExternal = external;
    if (state.views === drawnViews) return;
    drawnViews = state.views;
    if (!state.workspaceId) return;
    loadTree();
    refreshOpen();
    if (mode === "diff") loadDiff();
    if (mode === "pipeline") loadPipeline();
  });

  drawFile();
  setMode("file");
  return { openFile, save, setMode, buffers };
}
