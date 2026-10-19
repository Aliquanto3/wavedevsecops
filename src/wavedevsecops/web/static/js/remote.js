// Vue « Distant + PR » : refs de `origin`, PR courante, checks, `merge-blocked`, journal de revue.
// Le front dessine ce que le serveur projette (`state_projected.views.remote`, AD-2) : états en mots,
// durées, compteurs, disponibilité de « Merger » et raisons de blocage viennent du serveur. Seuls les
// glyphes et l'ordre des blocs d'une carte (DESIGN.md > pr-card) sont décidés ici.
//
// `element_id` sélectionnables (partagés avec les autres vues, 2.10) : `ref:refs/remotes/origin/<b>`
// (branche), `pr:<n>` (titre de la carte), `check:<n>:<job_id>:<sha>` (ligne de check) et
// `review:<n>:<review_id>` (entrée du journal). Les raisons de `merge-blocked` ne portent pas d'`element_id`
// propre : leur bouton porte `data-link` (l'élément en cause) et le sélectionne.
import { bindAction } from "./actions.js";
import { el } from "./dom.js";
import { postIntent } from "./quiz.js";
import { selectionFor } from "./selection.js";

export const REFS_TITLE = "Refs de origin";
export const NO_REFS_TEXT = "Rien n'a encore été poussé sur origin.";
export const OPEN_PR_LABEL = "Ouvrir une PR";
export const MERGE_LABEL = "Merger";
export const BUSY_TEXT = "Une action est en cours.";
export const NO_REVIEW_TEXT = "Aucune revue pour l'instant.";
export const REQUIRED_TEXT = "Obligatoire";
export const COLLEAGUE_TEXT = "Collègue";
export const AGENT_TEXT = "Agent";
export const BLOCKED_TITLE = "Pourquoi Merger est inactif";
export const REVIEW_TITLE = "Revue";
export const CHECKS_TITLE = "Checks";
export const GLYPHS = { success: "✓", failure: "✗", error: "⚠", queued: "○", running: "" };
export const REVIEW_MARKS = { approved: "✓", changes_requested: "✗", commented: "•" };

function text(tag, className, value) {
  const node = el(tag, className);
  node.textContent = value;
  return node;
}

/** Marque ● d'un élément sélectionné (visible seulement quand il l'est, CSS) : décorative. */
function dot() {
  const node = text("span", "sel-dot", "●");
  node.setAttribute("aria-hidden", "true");
  return node;
}

function selectable(tag, className, id, label) {
  return el(tag, className, {
    type: tag === "button" ? "button" : false,
    "data-select": true,
    "data-element-id": id,
    "data-key": id,
    "aria-label": label,
    "aria-pressed": "false",
  });
}

// --- refs de origin --------------------------------------------------------------------------

export function buildRefs(remote, busy = false) {
  const section = el("section", "remote-refs", { "aria-labelledby": "remote-refs-title" });
  const heading = text("h3", "remote-title", REFS_TITLE);
  heading.id = "remote-refs-title";
  section.append(heading);
  if (remote.branches.length === 0) {
    section.append(text("p", "remote-none", NO_REFS_TEXT));
    return section;
  }
  const list = el("ul", "remote-branches");
  for (const branch of remote.branches) {
    const item = el("li", "remote-branch");
    const pick = selectable("button", "remote-ref graph-remote-ref", branch.element_id, branch.a11y_name_text);
    pick.append(dot(), text("code", "ref-name", branch.name_text), text("code", "graph-sha", branch.short_sha));
    if (branch.protection_text) pick.append(text("span", "tag tag-protected", branch.protection_text));
    if (branch.pr_number) pick.append(text("span", "tag tag-pr", `PR n°${branch.pr_number}`));
    item.append(pick);
    if (branch.can_open_pr) {
      const open = el("button", "btn btn-secondary btn-small", {
        type: "button",
        "data-action": "open-pr",
        "data-head": branch.name_text.replace(/^origin\//, ""),
        "data-key": `open:${branch.name_text}`,
        "aria-label": `${OPEN_PR_LABEL} pour ${branch.name_text}`,
      });
      open.textContent = OPEN_PR_LABEL;
      item.append(open); // dans le DOM d'abord, comme Merger : sa raison se place après lui
      bindAction(open, busy ? BUSY_TEXT : null);
    }
    list.append(item);
  }
  section.append(list);
  return section;
}

// --- checks ----------------------------------------------------------------------------------

export function buildCheck(check) {
  const row = selectable("button", `pr-check is-${check.state}${check.stale ? " is-stale" : ""}`, check.element_id, check.a11y_name_text);
  const glyph = el("span", check.state === "running" ? "check-glyph pending-dot" : "check-glyph");
  glyph.setAttribute("aria-hidden", "true");
  glyph.textContent = GLYPHS[check.state] || "";
  row.append(dot(), glyph, text("code", "check-job", check.job_id), text("span", "check-state", check.state_text));
  if (check.stale) row.append(text("span", "check-stale", "ancien commit"));
  if (check.required) row.append(text("span", "tag tag-required", REQUIRED_TEXT));
  row.append(text("span", "check-duration", check.duration_text));
  const item = el("li", "pr-check-item");
  item.append(row);
  return item;
}

function buildChecks(checks, wanted, className) {
  const rows = checks.filter(wanted);
  if (rows.length === 0) return null;
  const list = el("ul", `pr-checks ${className}`);
  for (const check of rows) list.append(buildCheck(check));
  return list;
}

// --- merge-blocked ---------------------------------------------------------------------------

function buildMerge(card, busy) {
  const zone = el("div", `merge-zone${card.merge.enabled ? "" : " merge-blocked"}`, { "data-zone": "merge" });
  if (card.state === "merged") {
    zone.append(text("p", "merge-done", card.merge.done_text));
    return zone;
  }
  const button = el("button", "btn btn-primary", {
    type: "button",
    "data-action": "merge",
    "data-number": card.number,
    "data-key": `merge:${card.number}`,
  });
  button.textContent = MERGE_LABEL;
  zone.append(button); // dans le DOM d'abord : la raison d'un bouton inactif se place après lui
  bindAction(button, card.merge.enabled ? (busy ? BUSY_TEXT : null) : card.merge.disabled_text);
  if (card.merge.reasons.length > 0) {
    const list = el("ul", "merge-reasons", { "aria-label": BLOCKED_TITLE });
    for (const reason of card.merge.reasons) {
      const item = el("li", "merge-reason");
      const pick = el("button", `merge-reason-link is-${reason.kind}`, {
        type: "button",
        "data-link": reason.element_id,
        "data-key": `reason:${card.number}:${reason.kind}:${reason.element_id}`,
        "aria-pressed": "false",
      });
      pick.append(dot(), text("span", "reason-text", reason.text));
      item.append(pick);
      list.append(item);
    }
    zone.append(list);
  }
  return zone;
}

// --- journal de revue ------------------------------------------------------------------------

export function buildReviewLog(card) {
  const log = card.review;
  const section = el("section", "review-log", { "aria-label": REVIEW_TITLE });
  const head = el("div", "review-head");
  head.append(text("h4", "review-title", REVIEW_TITLE));
  const counter = el("p", "review-counter");
  counter.append(text("span", "number", log.counter_text), " ", text("span", "review-required", log.required_text));
  head.append(counter);
  section.append(head);
  if (log.entries.length === 0) {
    section.append(text("p", "review-none", NO_REVIEW_TEXT));
    return section;
  }
  const list = el("ol", "review-entries");
  for (const entry of log.entries) {
    const item = el("li", `review-entry is-${entry.state}`);
    const pick = selectable("button", "review-pick", entry.element_id, entry.a11y_name_text);
    const mark = text("span", "review-mark", REVIEW_MARKS[entry.state] || "•");
    mark.setAttribute("aria-hidden", "true");
    pick.append(dot(), mark, text("span", "review-author", entry.author));
    const badge = entry.actor === "agent" ? AGENT_TEXT : COLLEAGUE_TEXT;
    pick.append(text("span", `graph-actor is-${entry.actor}`, badge), text("span", "review-action", entry.action_text));
    if (entry.time_text) pick.append(text("span", "review-time", entry.time_text));
    if (entry.stale) pick.append(text("span", "review-stale", entry.stale_text));
    if (entry.body_text) pick.append(text("span", "review-body", entry.body_text));
    item.append(pick);
    list.append(item);
  }
  section.append(list);
  return section;
}

// --- carte de PR -----------------------------------------------------------------------------

export function buildCard(card, busy) {
  const article = el("article", `pr-card${card.current ? " is-current" : ""} is-${card.state}`, {
    "data-pr": card.number,
  });
  const head = el("header", "pr-head");
  const title = el("h3", "pr-title");
  const pick = selectable("button", "pr-pick", card.element_id, card.a11y_name_text);
  pick.append(dot(), text("span", "pr-title-text", card.title_text));
  title.append(pick);
  head.append(title, text("span", `tag tag-state is-${card.state}`, card.state_text));
  const branches = el("p", "pr-branches");
  branches.append(text("code", "", card.branches_text));
  article.append(head, branches);
  const failing = buildChecks(card.checks, (c) => c.state === "failure" || c.state === "error", "is-failing");
  if (failing) article.append(failing);
  article.append(buildMerge(card, busy));
  const others = buildChecks(card.checks, (c) => c.state !== "failure" && c.state !== "error", "is-others");
  if (others) article.append(others);
  article.append(buildReviewLog(card));
  return article;
}

// --- volet -----------------------------------------------------------------------------------

/** Élément qui reçoit le focus quand un bouton d'action disparaît après son action. */
export function fallbackKey(key) {
  if (!key) return null;
  if (key.startsWith("merge:")) return `pr:${key.slice("merge:".length)}`;
  if (key.startsWith("open:origin/")) return `ref:refs/remotes/origin/${key.slice("open:origin/".length)}`;
  return null;
}

/** Remplit le corps du volet « Distant + PR » et le tient à jour d'après le magasin. */
export function renderRemote(body, ctx, renderEmpty) {
  const { store, pane } = ctx;
  const selection = selectionFor(store);
  const root = el("div", "remote-view");
  body.replaceChildren(root);
  let drawn; // dernière vue dessinée
  let drawnBusy;

  function refreshSelection() {
    for (const node of root.querySelectorAll("[data-element-id], [data-link]")) {
      const id = node.getAttribute("data-element-id") || node.getAttribute("data-link");
      const on = id === selection.value;
      if (on) node.classList.add("is-selected");
      else node.classList.remove("is-selected");
      if (node.tagName === "BUTTON") node.setAttribute("aria-pressed", String(on));
    }
  }

  /** Un seul arrêt de tabulation par vue (workspace.js) : le nôtre ne l'est que si nul autre ne l'est. */
  function settleRoving(preferred) {
    const mine = [...root.querySelectorAll("button")];
    for (const button of mine) button.setAttribute("tabindex", "-1");
    const section = body.parentElement;
    const others = section
      ? [...section.querySelectorAll("button, [data-roving]")].filter((node) => !root.contains(node))
      : [];
    if (others.some((node) => node.getAttribute("tabindex") === "0") || mine.length === 0) return;
    const chosen = mine.find((b) => b.getAttribute("data-key") === preferred) || mine[0];
    chosen.setAttribute("tabindex", "0");
  }

  function draw(state) {
    const remote = state.views.remote;
    const busy = state.engineState !== "idle";
    if (remote === drawn && busy === drawnBusy) return;
    drawn = remote;
    drawnBusy = busy;
    const active = document.activeElement;
    const focusedKey = active && root.contains(active) ? active.getAttribute("data-key") : null;
    root.replaceChildren();
    if (!remote) {
      renderEmpty(root, pane.empty);
      return;
    }
    if (remote.error_text) root.append(text("p", "remote-error", remote.error_text));
    if (remote.branches.length === 0 && remote.pulls.length === 0 && !remote.error_text) {
      renderEmpty(root, pane.empty);
    } else {
      root.append(buildRefs(remote, busy));
      if (remote.pulls.length === 0) {
        const none = el("div", "remote-empty");
        renderEmpty(none, pane.empty);
        root.append(none);
      }
      for (const card of remote.pulls) root.append(buildCard(card, busy));
    }
    refreshSelection();
    const buttons = [...root.querySelectorAll("button")];
    const byKey = (key) => key && buttons.find((b) => b.getAttribute("data-key") === key);
    // Merger (PR mergée) ou Ouvrir une PR (PR ouverte) disparaissent après leur action : le focus
    // passe au titre de la carte, ou à la branche, plutôt que de tomber sur la page.
    const again = byKey(focusedKey) || byKey(fallbackKey(focusedKey));
    settleRoving(again ? again.getAttribute("data-key") : focusedKey);
    if (again) again.focus();
  }

  // Un clic (ou Entrée, Espace) sélectionne ; Merger et Ouvrir une PR envoient leur intention.
  root.addEventListener("click", (event) => {
    const target = event.target.closest && event.target.closest("button");
    if (!target || target.getAttribute("aria-disabled") === "true") return;
    const action = target.getAttribute("data-action");
    if (action === "merge") {
      postIntent(store, "pr_merge", { number: Number(target.getAttribute("data-number")) });
    } else if (action === "open-pr") {
      postIntent(store, "pr_open", { head: target.getAttribute("data-head") });
    } else if (target.hasAttribute("data-link")) {
      selection.toggle(target.getAttribute("data-link"));
    } else if (target.hasAttribute("data-select")) {
      selection.toggle(target.getAttribute("data-element-id"));
    }
  });
  selection.subscribe(refreshSelection);
  store.subscribe((state) => draw(state));
}
