// Volet Terminal (UX-DR13, UX-DR37) : saisie de vraies commandes git et affichage verbatim de
// leur sortie. Le front ne l'analyse jamais (AD-2) : il dessine ce que le serveur publie
// (`terminal_output`) dans l'ordre d'arrivée, et envoie les intentions `terminal_line` et
// `interrupt` (AD-17). Les refus et les textes viennent du serveur.
import { el, richText } from "./dom.js";
import { selectionFor } from "./selection.js";

export const MAX_LINES = 5000; // au-delà, les plus anciennes sont masquées avec leur nombre
export const SLOW_AFTER_S = 1; // « En cours… n s » s'affiche après cette durée
export const HISTORY_MAX = 200;
export const OFFLINE_TEXT = "WaveDevSecOps ne répond pas. Rechargez la page.";
export const SEND_FAILED_TEXT = "La commande n'a pas pu être envoyée. Réessayez.";
export const EMPTY = {
  title: "Tapez une commande git.",
  text: "Par exemple `git status`, puis Entrée. Ctrl+C arrête une commande trop longue.",
};

const IDLE_STATES = new Set(["idle", "quiz_altered"]);

/** « En cours… 3 s » : affiché hors de toute région live (UX-DR37). */
export function runningText(seconds) {
  return `En cours… ${seconds} s`;
}

export function hiddenText(count) {
  return count === 1
    ? "1 ligne plus ancienne est masquée."
    : `${count} lignes plus anciennes sont masquées.`;
}

/** Lignes qu'une entrée occupe (une entrée en occupe au moins une). */
export function countLines(text) {
  let lines = 0;
  for (const char of text) if (char === "\n") lines += 1;
  return text === "" || text.endsWith("\n") ? Math.max(lines, 1) : lines + 1;
}

export function promptText(state) {
  const branch = state.views?.prompt?.text || "";
  return branch ? `${branch} $` : "$";
}

export const TOOL_OUTPUT_LABEL = (tool) => `Sortie de ${tool}`;

/**
 * Découpe `text` selon les `spans` du serveur (positions UTF-16 de `slice`) : des textes et des
 * liens `{text, elementId}`. Un passage hors bornes ou qui en chevauche un autre est ignoré.
 */
export function splitSpans(text, spans) {
  const parts = [];
  let at = 0;
  for (const span of [...(spans || [])].sort((a, b) => a.start - b.start)) {
    if (span.start < at || span.end > text.length || span.end <= span.start) continue;
    if (span.start > at) parts.push({ text: text.slice(at, span.start) });
    parts.push({ text: text.slice(span.start, span.end), elementId: span.element_id });
    at = span.end;
  }
  if (at < text.length) parts.push({ text: text.slice(at) });
  return parts;
}

/** Note sur un nœud les éléments que ses passages liables citent (`terminal-lit`, story 2.10). */
function markSpans(node, spans) {
  const ids = [...new Set((spans || []).map((span) => span.element_id))];
  if (ids.length) node.setAttribute("data-span-ids", ids.join(" "));
}

/** Ajoute le texte de `entry` à `parent`, ses passages `spans` en liens vers la sélection partagée. */
function appendWithLinks(parent, entry, selection) {
  for (const part of splitSpans(entry.text, entry.spans)) {
    if (!part.elementId) {
      parent.append(document.createTextNode(part.text));
      continue;
    }
    const link = el("button", "terminal-link", { type: "button", "data-element-id": part.elementId });
    link.textContent = part.text;
    link.addEventListener("click", (event) => {
      event.stopPropagation();
      selection.toggle(part.elementId);
    });
    parent.append(link);
  }
}

/** Bloc `tool-output` (UX-DR20) : sortie verbatim, étiquette au nom de l'outil, désignable. */
function toolOutputNode(entry, selection) {
  const block = el("div", "tool-output", {
    role: "group",
    tabindex: "0",
    "aria-label": TOOL_OUTPUT_LABEL(entry.tool),
    "data-tool": entry.tool,
  });
  const outputId = entry.opId ? `output:${entry.opId}` : "";
  if (outputId) block.setAttribute("data-element-id", outputId);
  if (entry.explain) block.setAttribute("data-explain-ref", entry.explain);
  markSpans(block, entry.spans);
  const label = el("span", "tool-output-label", { "aria-hidden": "true" });
  label.textContent = entry.tool;
  const body = el("pre", "tool-output-text");
  if (entry.lang === "en") body.setAttribute("lang", "en");
  appendWithLinks(body, entry, selection);
  block.append(label, body);
  if (outputId) {
    const designate = () => selection.toggle(outputId);
    block.addEventListener("click", (event) => {
      if (!String(globalThis.getSelection?.() ?? "")) designate();
      event.stopPropagation();
    });
    block.addEventListener("keydown", (event) => {
      if (event.target === block && (event.key === "Enter" || event.key === " ")) {
        event.preventDefault();
        designate();
      }
    });
  }
  return block;
}

function entryNode(entry, selection) {
  if (entry.tool) return toolOutputNode(entry, selection);
  if (entry.kind === "input") {
    const line = el("div", "terminal-line terminal-command");
    const prompt = el("span", "terminal-prompt");
    prompt.textContent = `${entry.prompt || "$"} `;
    const text = el("span", "terminal-typed");
    text.textContent = entry.text;
    line.append(prompt, text);
    return line;
  }
  if (entry.kind === "app") {
    const line = el("div", "terminal-line terminal-app-message");
    const mark = el("span", "terminal-app-mark", { "aria-hidden": "true" });
    mark.textContent = "› ";
    const text = el("span");
    richText(text, entry.text);
    line.append(mark, text);
    return line;
  }
  if (entry.kind === "refused") {
    const line = el("div", "terminal-line terminal-refused", { role: "alert" });
    // Refus d'un hook (story 7.3) : un lien vers la ligne du secret, fixé par le serveur.
    appendWithLinks(line, entry, selection);
    return line;
  }
  if (entry.kind === "exit") {
    const line = el("div", "terminal-line terminal-exit-error");
    line.textContent = entry.text;
    return line;
  }
  const chunk = el("span", `terminal-chunk terminal-${entry.kind === "stderr" ? "stderr" : "stdout"}`);
  if (entry.lang === "en") chunk.setAttribute("lang", "en");
  markSpans(chunk, entry.spans);
  if (entry.kind === "stderr") {
    const prefix = el("span", "visually-hidden");
    prefix.textContent = "erreur standard : ";
    chunk.append(prefix);
  }
  chunk.append(document.createTextNode(entry.text));
  return chunk;
}

/**
 * Monte le terminal dans `body`. Rend un contrôleur : `tick(maintenant)` met à jour le
 * chronomètre (testable sans attendre), `destroy()` arrête les écouteurs.
 */
export function createTerminal(body, { store, timers = globalThis }) {
  const root = el("div", "terminal");
  const empty = el("div", "terminal-empty");
  const emptyTitle = el("p", "empty-title");
  richText(emptyTitle, EMPTY.title);
  const emptyText = el("p", "empty");
  richText(emptyText, EMPTY.text);
  empty.append(emptyTitle, emptyText);
  const note = el("p", "terminal-hidden-note");
  note.hidden = true;
  const log = el("div", "terminal-log", { role: "log", "aria-label": "Sortie du terminal" });
  const running = el("p", "terminal-running");
  running.hidden = true;
  const form = el("div", "terminal-form");
  const prompt = el("span", "terminal-prompt", { "aria-hidden": "true" });
  const input = el("input", "terminal-input", {
    type: "text",
    autocomplete: "off",
    autocapitalize: "off",
    spellcheck: "false",
    "aria-label": "Commande git",
  });
  form.append(prompt, input);
  root.append(empty, note, log, running, form);
  body.replaceChildren(root);

  const selection = selectionFor(store);
  const history = [];
  let historyIndex = null;
  let draft = "";
  let rendered = 0;
  let cleared = 0;
  let nodes = []; // { node, lines }
  let total = 0;
  let hidden = 0;
  let since = null;
  let timer = null;

  function post(intent, payload) {
    const id = encodeURIComponent(store.state.workspaceId);
    const send = globalThis.fetch;
    return send(`/api/ws/${id}/${intent}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(payload),
    });
  }

  async function refusal(response) {
    let text = SEND_FAILED_TEXT;
    try {
      text = (await response.json()).reason_text || text;
    } catch (err) {
      // Corps illisible : le texte par défaut suffit.
    }
    store.terminalAppend({ kind: "refused", text });
  }

  async function submit(line) {
    const text = line.trim();
    if (!text) return;
    if (history[history.length - 1] !== text) history.push(text);
    if (history.length > HISTORY_MAX) history.shift();
    historyIndex = null;
    input.value = "";
    if (text === "clear") {
      store.terminalClear(); // comme Ctrl+L : l'affichage seul est effacé, pas l'historique
      return;
    }
    store.terminalAppend({ kind: "input", text, prompt: promptText(store.state) });
    try {
      const response = await post("terminal_line", { line: text });
      if (!response.ok) await refusal(response);
    } catch (err) {
      store.terminalAppend({ kind: "refused", text: OFFLINE_TEXT });
    }
  }

  async function interrupt() {
    try {
      await post("interrupt", {});
    } catch (err) {
      store.terminalAppend({ kind: "refused", text: OFFLINE_TEXT });
    }
  }

  function isBusy(state) {
    return !IDLE_STATES.has(state.engineState);
  }

  function selectedText() {
    try {
      return String(globalThis.getSelection?.() ?? "");
    } catch (err) {
      return "";
    }
  }

  input.addEventListener("keydown", (event) => {
    const busy = isBusy(store.state);
    if (event.ctrlKey && !event.altKey && !event.metaKey && /^[cC]$/.test(event.key)) {
      if (busy) {
        event.preventDefault();
        interrupt();
      } else if (!selectedText()) {
        event.preventDefault(); // comme un shell : abandonne la ligne en cours de saisie
        input.value = "";
        historyIndex = null;
      }
      return;
    }
    if (event.ctrlKey && !event.altKey && !event.metaKey && /^[lL]$/.test(event.key)) {
      event.preventDefault();
      store.terminalClear();
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      if (!busy) submit(input.value);
    } else if (event.key === "ArrowUp" || event.key === "ArrowDown") {
      event.preventDefault();
      if (busy || history.length === 0) return;
      if (historyIndex === null) {
        if (event.key === "ArrowDown") return;
        draft = input.value;
        historyIndex = history.length - 1;
      } else if (event.key === "ArrowUp") {
        historyIndex = Math.max(historyIndex - 1, 0);
      } else if (historyIndex >= history.length - 1) {
        historyIndex = null;
      } else {
        historyIndex += 1;
      }
      input.value = historyIndex === null ? draft : history[historyIndex];
    }
  });

  // Un clic dans la sortie rend la saisie, sauf pour sélectionner du texte à copier.
  log.addEventListener("click", () => {
    if (!selectedText()) input.focus();
  });

  function refreshSelection() {
    for (const block of log.querySelectorAll?.("[data-element-id]") ?? []) {
      const on = block.getAttribute("data-element-id") === selection.value;
      if (on) block.classList.add("is-selected");
      else block.classList.remove("is-selected");
      if (block.tagName === "BUTTON") block.setAttribute("aria-pressed", String(on));
    }
  }
  const unselect = selection.subscribe(refreshSelection);

  function reset() {
    for (const { node } of nodes) node.remove();
    nodes = [];
    total = 0;
    hidden = 0;
  }

  function draw(terminal) {
    if (terminal.cleared !== cleared) {
      cleared = terminal.cleared;
      reset();
      rendered = cleared;
    }
    let added = false;
    for (let index = Math.max(rendered, cleared); index < terminal.entries.length; index += 1) {
      const entry = terminal.entries[index];
      const node = entryNode(entry, selection);
      const lines = countLines(entry.text);
      log.append(node);
      nodes.push({ node, lines });
      total += lines;
      added = true;
    }
    rendered = terminal.entries.length;
    while (total > MAX_LINES && nodes.length > 1) {
      const oldest = nodes.shift();
      oldest.node.remove();
      total -= oldest.lines;
      hidden += oldest.lines;
    }
    note.hidden = hidden === 0;
    if (hidden > 0) note.textContent = hiddenText(hidden);
    empty.hidden = nodes.length > 0;
    if (added) log.scrollTop = log.scrollHeight;
  }

  function tick(now = Date.now()) {
    if (since === null) {
      running.hidden = true;
      return;
    }
    const seconds = Math.floor((now - since) / 1000);
    running.hidden = seconds < SLOW_AFTER_S;
    if (seconds >= SLOW_AFTER_S) running.textContent = runningText(seconds);
  }

  let version = -1;
  let wasTiming = false;
  const unsubscribe = store.subscribe((state) => {
    prompt.textContent = `${promptText(state)} `;
    const busy = isBusy(state);
    if (busy) {
      // Saisie inactive mais focalisée : Ctrl+C doit rester reçu pendant la commande.
      input.setAttribute("readonly", "");
      input.setAttribute("aria-readonly", "true");
    } else {
      input.removeAttribute("readonly");
      input.removeAttribute("aria-readonly");
    }
    // Le chronomètre ne suit que l'état « commande » (pas le chargement ni la préparation).
    const timing = state.engineState === "command";
    if (timing && !wasTiming) {
      since = Date.now();
      timer = timers.setInterval?.(() => tick(Date.now()), 250) ?? null;
      timer?.unref?.();
    } else if (!timing && wasTiming) {
      since = null;
      if (timer !== null) timers.clearInterval?.(timer);
      timer = null;
      tick();
    }
    wasTiming = timing;
    if (state.terminal.version !== version) {
      version = state.terminal.version;
      draw(state.terminal);
    }
  });

  return {
    tick,
    input,
    destroy() {
      unsubscribe();
      unselect();
      if (timer !== null) timers.clearInterval?.(timer);
    },
  };
}

export function renderTerminal(body, ctx) {
  return createTerminal(body, { store: ctx.store });
}
