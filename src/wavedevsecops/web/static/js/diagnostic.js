// Page Diagnostic et pastille de l'en-tête. Le front ne calcule rien (AD-2) : textes, décomptes,
// groupes et synthèse viennent du serveur (GET /api/diagnostic, POST /api/diagnostic/run).
import { bindAction, setActionDisabled } from "./actions.js";

export const ICONS = { ok: "✓", missing: "✗", too_old: "⚠", mismatch: "⚠", warn: "⚠", info: "ℹ" };
const STATE_CLASS = {
  ok: "state-ok",
  missing: "state-fail",
  too_old: "state-warn",
  mismatch: "state-warn",
  warn: "state-warn",
  info: "state-info",
};
const SEARCHING_REASON = "La recherche est en cours.";
const FAILED_FALLBACK = "Le diagnostic n'a pas pu se charger. Rechargez la page.";

/** Découpe un texte du serveur en segments ; ce qui est entre accents graves est du code. */
export function splitCode(text) {
  return String(text)
    .split("`")
    .map((part, index) => ({ text: part, code: index % 2 === 1 }))
    .filter((segment) => segment.text !== "");
}

function h(tag, props = {}, ...children) {
  const element = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === "text") element.textContent = value;
    else if (key === "class") element.className = value;
    else element.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child) element.append(child);
  }
  return element;
}

function rich(tag, text) {
  const element = h(tag);
  for (const segment of splitCode(text)) {
    element.append(segment.code ? h("code", { text: segment.text }) : segment.text);
  }
  return element;
}

async function getJson(url, init, fetchImpl) {
  const response = await fetchImpl(url, { cache: "no-store", credentials: "same-origin", ...init });
  const body = await response.json();
  if (!response.ok) throw Object.assign(new Error(body.error_text || url), { server: Boolean(body.error_text) });
  return body;
}

export const loadState = (fetchImpl = (...a) => fetch(...a)) =>
  getJson("/api/diagnostic", {}, fetchImpl);
export const runChecks = (fetchImpl = (...a) => fetch(...a)) =>
  getJson("/api/diagnostic/run", { method: "POST" }, fetchImpl);

/** Pastille « Diagnostic » : le décompte seul, lu en entier par le nom du lien. */
export function renderBadge(link, report) {
  const existing = link.querySelector(".diagnostic-badge");
  if (existing) existing.remove();
  link.removeAttribute("aria-label");
  if (!report || !report.badge_text) return;
  link.setAttribute("aria-label", report.badge_text);
  link.append(h("span", { class: "diagnostic-badge", "aria-hidden": "true", text: String(report.problem_count) }));
}

/** Pastille de l'en-tête sur une page autre que le Diagnostic : rapport connu, sinon une recherche. */
export async function refreshBadge(link, fetchImpl) {
  try {
    const state = await loadState(fetchImpl);
    renderBadge(link, state.report || (await runChecks(fetchImpl)));
  } catch (err) {
    // La pastille est facultative : sans réponse, l'en-tête reste sans pastille.
  }
}

function stateCell(status, text) {
  return h(
    "span",
    { class: `state ${STATE_CLASS[status] || "state-info"}` },
    h("span", { "aria-hidden": "true", text: ICONS[status] || "" }),
    h("span", { text }),
  );
}

function headerRow(columns) {
  return h("thead", {}, h("tr", {}, columns.map((name) => h("th", { scope: "col", text: name }))));
}

function toolRow(plan, check, ui) {
  const row = h("tr", { "data-check": plan.check_id });
  const running = !check;
  row.append(
    h("th", { scope: "row", text: plan.label_text }),
    h("td", { text: plan.usage_text }),
    h("td", { class: "mono", text: running ? "…" : check.version || ui.not_found }),
    h("td", { class: "mono", text: plan.required_version }),
    h("td", {}, running ? stateCell("info", ui.running) : stateCell(check.status, check.status_text)),
  );
  const todo = h("td");
  if (!running && check.what_to_do_text) {
    const details = h("details", {}, h("summary", { text: ui.todo_summary }), rich("p", check.what_to_do_text));
    if (check.blocking) details.setAttribute("open", "");
    todo.append(details);
  } else {
    todo.textContent = ui.nothing_to_do;
  }
  const scenarios = h("td", { class: "num" });
  if (running) {
    scenarios.textContent = ui.nothing_to_do;
  } else {
    scenarios.append(String(check.unavailable_scenarios.length));
    if (check.unavailable_scenarios.length > 0) {
      scenarios.append(h("span", { class: "sub", text: check.unavailable_scenarios.join(" ; ") }));
    }
  }
  row.append(todo, scenarios);
  return row;
}

function toolsSection(plan, report) {
  const ui = plan.ui;
  const byId = new Map((report ? report.checks : []).map((check) => [check.check_id, check]));
  const rows = new Map(plan.rows.map((row) => [row.check_id, row]));
  const body = h("tbody");
  for (const group of plan.groups) {
    body.append(
      h("tr", { class: "group-row" }, h("th", { scope: "colgroup", colspan: "7", text: group.title_text })),
    );
    for (const id of group.check_ids) body.append(toolRow(rows.get(id), byId.get(id), ui));
  }
  return h(
    "section",
    { class: "diag-section", "aria-labelledby": "diag-tools" },
    h("h2", { id: "diag-tools", text: ui.tools_title }),
    h("p", { class: "diag-note", text: ui.tools_subtitle }),
    h("p", { class: "diag-note", text: ui.tools_note }),
    h("div", { class: "diag-scroll" }, h("table", { class: "diag-table" }, headerRow(ui.columns), body)),
  );
}

function proxySection(plan, report) {
  const proxy = report && report.checks.find((check) => check.group === "proxy");
  if (!proxy) return null;
  const ui = plan.ui;
  const body = h("tbody");
  for (const part of proxy.parts) {
    const todo = h("td");
    if (part.what_to_do_text) {
      const details = h("details", {}, h("summary", { text: ui.todo_summary }), rich("p", part.what_to_do_text));
      if (part.status === "warn") details.setAttribute("open", "");
      todo.append(details);
    } else {
      todo.textContent = ui.nothing_to_do;
    }
    body.append(
      h(
        "tr",
        {},
        h("th", { scope: "row", class: "mono", text: part.label_text }),
        h("td", { class: "mono", text: part.value_text || ui.nothing_to_do }),
        h("td", {}, stateCell(part.status, part.status_text)),
        todo,
      ),
    );
  }
  return h(
    "section",
    { class: "diag-section", "aria-labelledby": "diag-proxy" },
    h("h2", { id: "diag-proxy", text: ui.proxy_title }),
    h("p", { class: "diag-note", text: ui.proxy_subtitle }),
    h("div", { class: "diag-scroll" }, h("table", { class: "diag-table" }, headerRow(ui.proxy_columns), body)),
  );
}

function gitNotice(report) {
  if (!report || !report.git_notice) return null;
  const notice = report.git_notice;
  return h(
    "section",
    { class: "notice-card notice-error", "aria-labelledby": "diag-git" },
    h("h2", { id: "diag-git" }, h("span", { "aria-hidden": "true", text: "✗ " }), notice.title_text),
    h("p", { text: notice.cause_text }),
    rich("p", notice.action_text),
  );
}

/** Dessine la page Diagnostic dans `root` et lance la recherche. */
export async function renderDiagnosticPage(root, { onReport, fetchImpl = (...a) => fetch(...a) } = {}) {
  let plan;
  try {
    plan = await loadState(fetchImpl);
  } catch (err) {
    root.replaceChildren(h("p", { role: "status", text: err.server ? err.message : FAILED_FALLBACK }));
    return;
  }
  const ui = plan.ui;
  const summary = h("p", { class: "diag-summary", role: "status", text: ui.searching });
  const rerun = h("button", { type: "button", class: "btn btn-secondary", text: ui.rerun });
  const content = h("div");
  const foot = h(
    "div",
    { class: "diag-foot" },
    h("a", { class: "btn btn-primary", href: "/", text: ui.continue }),
    h("p", { class: "diag-note", text: ui.continue_hint }),
  );
  root.replaceChildren(
    h(
      "div",
      { class: "annex" },
      h("div", { class: "diag-head" }, rerun),
      summary,
      content,
      foot,
    ),
  );
  bindAction(rerun);

  async function search() {
    setActionDisabled(rerun, SEARCHING_REASON);
    summary.textContent = ui.searching;
    content.replaceChildren(toolsSection(plan, null));
    try {
      const report = await runChecks(fetchImpl);
      summary.textContent = report.summary_text;
      content.replaceChildren(
        ...[gitNotice(report), toolsSection(plan, report), proxySection(plan, report)].filter(Boolean),
      );
      if (onReport) onReport(report);
    } catch (err) {
      summary.textContent = err.server ? err.message : ui.failed;
      content.replaceChildren();
    } finally {
      setActionDisabled(rerun, null);
    }
  }
  rerun.addEventListener("click", search);
  await search();
}
