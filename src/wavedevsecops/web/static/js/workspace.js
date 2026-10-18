// Espace de travail : panneau Scénario à gauche, vues du registre à droite. Ce module ne connaît
// aucune vue en particulier : il lit le registre (panes.js) et la logique de disposition pure
// (layout.js). Le front ne mémorise que la disposition (AD-2).
import { bindAction } from "./actions.js";
import { buildChainBand, mountChain } from "./chain.js";
import { el, richText } from "./dom.js";
import * as L from "./layout.js";
import { listPanes } from "./panes.js";
import { createScenarioView } from "./scenario.js";
import { LOADING } from "./store.js";

export { buildChainBand };
export const PREPARING_TEXT = "Préparation du bac à sable…";
export const READY_TEXT = "Le bac à sable est prêt. Les consignes du scénario s'afficheront ici.";
export const LAST_VIEW_TEXT = "Au moins une vue reste visible.";

const TOOL_HIDE = "—";
const TOOL_MAXIMIZE = "⛶";

/** Monte l'espace de travail dans `container` et rend `{ destroy }`. */
export function mountWorkspace(container, { title, store, storage, chain = null, onSelect }) {
  const panes = listPanes();
  const byId = new Map(panes.map((pane) => [pane.id, pane]));
  let config = L.loadConfig(panes, storage);
  const pinned = new Set(); // vues réaffichées malgré le repli
  let focusId = null; // vue montrée sous 1280 px
  let signature = "";
  let effective = null;

  // --- squelette -------------------------------------------------------------------------
  const workspace = el("div", "workspace");
  const panel = el("section", "scenario-panel", {
    "aria-labelledby": "scenario-panel-title",
    tabindex: "-1",
    "data-zone": "scenario",
  });
  const panelTitle = el("h2", "scenario-panel-title", { id: "scenario-panel-title" });
  panelTitle.textContent = title;
  const panelStatus = el("p", "scenario-status", { role: "status" });
  const panelError = el("p", "scenario-error", { role: "alert" });
  const scenarioView = createScenarioView({ onSelect });
  panel.append(panelTitle, scenarioView.root, panelStatus, panelError);

  const zone = el("div", "views");
  const chipBar = el("div", "chips", {
    role: "group",
    "aria-label": "Vues masquées",
    "data-zone": "chips",
  });
  const grid = el("div", "views-grid");
  const announce = el("p", "visually-hidden", { role: "status", id: "layout-status" });
  zone.append(chipBar, grid, announce);
  // Bandeau de la chaîne : première rangée de la grille ; seule la rangée des vues rétrécit.
  let chainView = null;
  if (chain) {
    workspace.classList.add("has-chain-band");
    chainView = mountChain(workspace, chain, { inertNodes: [panel, zone] });
    workspace.append(chainView.band);
  }
  workspace.append(panel, zone);
  container.replaceChildren(workspace);

  // --- panneau Scénario, alimenté par le magasin -----------------------------------------
  const unsubscribe = store.subscribe((state) => {
    const preparing = state.engineState === LOADING || state.engineState === "setup";
    const stepStatus = scenarioView.update(state);
    panelStatus.textContent = state.errorText
      ? ""
      : preparing
        ? PREPARING_TEXT
        : stepStatus || READY_TEXT;
    panelError.textContent = state.errorText;
  });

  // --- volets (créés une fois, déplacés ensuite) -----------------------------------------
  const elements = new Map();

  function paneElement(pane) {
    if (elements.has(pane.id)) return elements.get(pane.id);
    const section = el("section", "pane", {
      "aria-labelledby": `pane-${pane.id}-title`,
      "data-pane": pane.id,
      "data-zone": "pane",
      "data-scroll": pane.scroll || "y",
    });
    const header = el("header", "pane-header");
    const step = el("span", "pane-step", { "aria-hidden": "true" });
    step.textContent = String(pane.step);
    const heading = el("div", "pane-heading");
    const paneTitle = el("h2", "pane-title", { id: `pane-${pane.id}-title`, tabindex: "-1" });
    paneTitle.textContent = pane.title;
    heading.append(paneTitle);
    if (pane.subtitle) {
      const subtitle = el("p", "pane-subtitle");
      richText(subtitle, pane.subtitle);
      heading.append(subtitle);
    }
    const tools = el("div", "pane-tools");
    const hide = el("button", "pane-tool", {
      type: "button",
      "data-action": "hide",
      "aria-label": `Masquer ${pane.title}`,
      title: `Masquer ${pane.title}`,
    });
    hide.textContent = TOOL_HIDE;
    const maximize = el("button", "pane-tool", {
      type: "button",
      "data-action": "maximize",
      "aria-pressed": "false",
      "aria-label": `Agrandir ${pane.title}`,
      title: `Agrandir ${pane.title}`,
    });
    maximize.textContent = TOOL_MAXIMIZE;
    tools.append(hide, maximize);
    header.append(step, heading, tools);
    const body = el("div", "pane-body");
    section.append(header, body);
    pane.render(body, { pane, store });
    hide.addEventListener("click", () => hideById(pane.id));
    maximize.addEventListener("click", () => toggleMaximize(pane.id));
    elements.set(pane.id, section);
    bindAction(hide, null);
    return section;
  }

  // --- actions sur la disposition --------------------------------------------------------
  function commit(next, { rearrange = true } = {}) {
    config = next;
    L.saveConfig(config, storage);
    if (rearrange) arrange(true);
    renderMenuState();
  }

  function say(text) {
    announce.textContent = "";
    announce.textContent = text;
  }

  function hideById(id) {
    const next = L.hidePane(config, panes, id);
    if (!next) {
      say(LAST_VIEW_TEXT);
      return;
    }
    pinned.delete(id);
    if (focusId === id) focusId = null;
    commit(next);
    say(`${byId.get(id).title} masqué.`);
    focusChip(id);
  }

  function showById(id) {
    pinned.add(id);
    focusId = id;
    commit(L.showPane(config, id));
    say(`${byId.get(id).title} affiché.`);
    byId.has(id) && paneElement(byId.get(id)).querySelector(".pane-title").focus();
  }

  function toggleMaximize(id) {
    const next = L.toggleMaximized(config, id);
    commit(next);
    const button = paneElement(byId.get(id)).querySelector('[data-action="maximize"]');
    button.focus();
  }

  function focusChip(id) {
    const chip = chipBar.querySelector(`[data-pane="${id}"]`);
    if (chip) chip.focus();
    else grid.querySelector(".pane-title")?.focus();
  }

  // --- redimensionnement -----------------------------------------------------------------
  function groupOf(handle) {
    const kind = handle.dataset.kind;
    const key = handle.dataset.group;
    const nodes =
      kind === "pane"
        ? [...grid.querySelectorAll(`.view-row[data-row="${key}"] > .pane`)]
        : [...grid.querySelectorAll(":scope > .view-row")];
    return { kind, nodes };
  }

  function measure(nodes, kind) {
    return nodes.map((node) => {
      const rect = node.getBoundingClientRect();
      return kind === "pane" ? rect.width : rect.height;
    });
  }

  function applySizes(kind, nodes, sizes) {
    nodes.forEach((node, i) => {
      node.style.flex = `${sizes[i]} 1 0`;
    });
  }

  function persistSizes(kind, nodes, sizes) {
    if (kind === "pane") {
      const ids = nodes.map((node) => node.dataset.pane);
      const previous = ids.map((id) => L.paneWeight(config, byId.get(id)));
      commit(L.setPaneWidths(config, ids, L.weightsFromSizes(sizes, previous)), {
        rearrange: false,
      });
    } else {
      const keys = nodes.map((node) => node.dataset.row);
      const rows = L.rowsOf(panes);
      const previous = keys.map((key) => L.rowWeight(config, rows.find((r) => String(r.row) === key)));
      commit(L.setRowWeights(config, keys, L.weightsFromSizes(sizes, previous)), {
        rearrange: false,
      });
    }
  }

  function resizeHandle(handle, delta, base = null) {
    const { kind, nodes } = groupOf(handle);
    const index = Number(handle.dataset.index);
    const min = kind === "pane" ? L.MIN_WIDTH : L.MIN_HEIGHT;
    const sizes = L.resizeSizes(base || measure(nodes, kind), index, delta, min);
    applySizes(kind, nodes, sizes);
    refreshHandles();
    return { kind, nodes, sizes };
  }

  function refreshHandles() {
    for (const handle of grid.querySelectorAll(".pane-resize-handle")) {
      const { kind, nodes } = groupOf(handle);
      const min = kind === "pane" ? L.MIN_WIDTH : L.MIN_HEIGHT;
      const values = L.separatorValues(measure(nodes, kind), Number(handle.dataset.index), min);
      handle.setAttribute("aria-valuenow", String(values.now));
      handle.setAttribute("aria-valuemin", String(values.min));
      handle.setAttribute("aria-valuemax", String(values.max));
    }
  }

  function resetHandle(handle) {
    const { kind, nodes } = groupOf(handle);
    if (kind === "pane") {
      commit(L.resetWeights(config, { paneIds: nodes.map((n) => n.dataset.pane) }));
    } else {
      commit(L.resetWeights(config, { rowKeys: nodes.map((n) => n.dataset.row) }));
    }
    const again = grid.querySelector(
      `.pane-resize-handle[data-kind="${handle.dataset.kind}"][data-group="${handle.dataset.group}"][data-index="${handle.dataset.index}"]`,
    );
    if (again) again.focus();
  }

  function makeHandle(kind, group, index, orientation, label) {
    const handle = el("div", "pane-resize-handle", {
      role: "separator",
      tabindex: "0",
      "aria-orientation": orientation,
      "aria-label": label,
      "data-kind": kind,
      "data-group": group,
      "data-index": index,
      "data-orientation": orientation,
    });
    handle.addEventListener("keydown", (event) => {
      const delta = L.keyDelta(event.key, orientation);
      if (delta === null) return;
      event.preventDefault();
      const done = resizeHandle(handle, delta);
      persistSizes(done.kind, done.nodes, done.sizes);
    });
    handle.addEventListener("dblclick", () => resetHandle(handle));
    handle.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      handle.focus();
      const { kind: k, nodes } = groupOf(handle);
      const base = measure(nodes, k);
      const origin = orientation === "vertical" ? event.clientX : event.clientY;
      let last = null;
      handle.setPointerCapture?.(event.pointerId);
      const move = (moveEvent) => {
        const now = orientation === "vertical" ? moveEvent.clientX : moveEvent.clientY;
        last = resizeHandle(handle, now - origin, base);
      };
      const stop = () => {
        handle.removeEventListener("pointermove", move);
        handle.removeEventListener("pointerup", stop);
        handle.removeEventListener("pointercancel", stop);
        if (last) persistSizes(last.kind, last.nodes, last.sizes);
      };
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", stop);
      handle.addEventListener("pointercancel", stop);
    });
    return handle;
  }

  /** « Élargir » / « Réduire » du menu Volets : même effet que la poignée, sans glisser. */
  function resizeById(id, direction) {
    const section = paneElement(byId.get(id));
    if (!section.isConnected) return;
    const row = section.parentElement;
    const siblings = [...row.children].filter((node) => node.classList.contains("pane"));
    let handle;
    let delta = direction * L.STEP;
    if (siblings.length > 1) {
      const at = siblings.indexOf(section);
      const index = at < siblings.length - 1 ? at : at - 1;
      handle = row.querySelector(`.pane-resize-handle[data-index="${index}"]`);
      if (at > index) delta = -delta; // le dernier volet grandit en reculant la frontière
    } else {
      const rows = [...grid.querySelectorAll(":scope > .view-row")];
      const at = rows.indexOf(row);
      if (rows.length < 2) return;
      const index = at < rows.length - 1 ? at : at - 1;
      handle = grid.querySelector(`:scope > .pane-resize-handle[data-index="${index}"]`);
      if (at > index) delta = -delta;
    }
    if (!handle) return;
    const done = resizeHandle(handle, delta);
    persistSizes(done.kind, done.nodes, done.sizes);
  }

  // --- disposition -----------------------------------------------------------------------
  function zoneSize() {
    return {
      width: grid.clientWidth || window.innerWidth,
      height: grid.clientHeight || window.innerHeight,
      viewport: window.innerWidth,
    };
  }

  function arrange(force = false) {
    effective = L.effectiveLayout(panes, config, zoneSize(), pinned, focusId);
    const next = JSON.stringify([
      effective.mode,
      effective.shown,
      effective.maximized,
      effective.rows.map((row) => row.panes.length),
    ]);
    if (!force && next === signature) return;
    signature = next;
    workspace.dataset.mode = effective.mode;
    grid.replaceChildren();
    const single = effective.mode === "single";
    effective.rows.forEach((row, rowIndex) => {
      if (rowIndex > 0 && !single) {
        grid.append(
          makeHandle("row", "rows", rowIndex - 1, "horizontal", "Redimensionner la hauteur des rangées de vues"),
        );
      }
      const rowEl = el("div", "view-row", { "data-row": row.row });
      rowEl.style.flex = single ? "1 1 auto" : `${L.rowWeight(config, row)} 1 0`;
      row.panes.forEach((pane, i) => {
        if (i > 0 && !single) {
          const before = row.panes[i - 1];
          rowEl.append(
            makeHandle(
              "pane",
              row.row,
              i - 1,
              "vertical",
              `Redimensionner ${before.title} et ${pane.title}`,
            ),
          );
        }
        const section = paneElement(pane);
        section.style.flex = single ? "1 1 auto" : `${L.paneWeight(config, pane)} 1 0`;
        const maximize = section.querySelector('[data-action="maximize"]');
        const isMax = effective.maximized && config.maximized === pane.id;
        maximize.setAttribute("aria-pressed", String(Boolean(isMax)));
        const label = isMax ? `Revenir à la disposition (${pane.title})` : `Agrandir ${pane.title}`;
        maximize.setAttribute("aria-label", label);
        maximize.title = label;
        const lastVisible = L.visibleIds(config, panes).size <= 1;
        bindAction(
          section.querySelector('[data-action="hide"]'),
          lastVisible ? LAST_VIEW_TEXT : null,
        );
        rowEl.append(section);
      });
      grid.append(rowEl);
    });
    renderChips();
    refreshHandles();
    syncRoving();
  }

  function renderChips() {
    chipBar.replaceChildren();
    for (const pane of panes) {
      if (!effective.hidden.has(pane.id)) continue;
      const chip = el("button", "pane-chip", { type: "button", "data-pane": pane.id });
      chip.textContent = `+ ${pane.title}`;
      chip.addEventListener("click", () => showById(pane.id));
      chipBar.append(chip);
    }
    chipBar.hidden = chipBar.children.length === 0;
  }

  // --- focus itinérant : chaque vue est un seul arrêt de tabulation ----------------------
  function rovingItems(section) {
    return [...section.querySelectorAll("button:not([disabled]), [data-roving]")];
  }

  function syncRoving() {
    for (const section of grid.querySelectorAll(".pane")) {
      const items = rovingItems(section);
      const current = items.find((item) => item.getAttribute("tabindex") === "0") || items[0];
      for (const item of items) item.setAttribute("tabindex", item === current ? "0" : "-1");
    }
  }

  grid.addEventListener("focusin", (event) => {
    const section = event.target.closest?.(".pane");
    if (!section) return;
    const items = rovingItems(section);
    if (!items.includes(event.target)) return;
    for (const item of items) item.setAttribute("tabindex", item === event.target ? "0" : "-1");
  });

  grid.addEventListener("keydown", (event) => {
    const section = event.target.closest?.(".pane");
    if (!section || event.altKey || event.ctrlKey || event.metaKey) return;
    const items = rovingItems(section);
    const index = items.indexOf(event.target);
    if (index < 0) return;
    const next = L.rovingIndex(event.key, index, items.length);
    if (next === index) return;
    event.preventDefault();
    items[next].focus();
  });

  // --- Échap et F6 -----------------------------------------------------------------------
  const displayPopup = document.getElementById("display-popup");

  function onKeydown(event) {
    if (event.key === "Escape") {
      if (displayPopup && !displayPopup.hidden) return; // le menu Affichage se ferme d'abord
      if (chainView?.isOpen()) {
        event.preventDefault();
        chainView.close();
        return;
      }
      const inTerminal = event.target.closest?.('[data-pane][data-terminal="true"]');
      if (inTerminal) {
        // Dans le terminal, Échap rend seulement le focus au titre de la vue.
        event.preventDefault();
        inTerminal.querySelector(".pane-title").focus();
        return;
      }
      if (menuPopup && !menuPopup.hidden) {
        event.preventDefault();
        setMenuOpen(false, true);
      } else if (config.maximized) {
        event.preventDefault();
        toggleMaximize(config.maximized);
      }
    } else if (event.key === "F6") {
      event.preventDefault();
      const zones = [...document.querySelectorAll("[data-zone]")].filter(
        (node) => node.isConnected && !node.hidden,
      );
      const current = zones.findIndex((node) => node.contains(document.activeElement));
      const target = zones[L.nextZone(zones.length, current, event.shiftKey)];
      if (target) zoneTarget(target).focus();
    }
  }

  function zoneTarget(zoneNode) {
    return (
      zoneNode.querySelector('[tabindex="0"]') ||
      zoneNode.querySelector("a[aria-current], button") ||
      zoneNode
    );
  }

  document.addEventListener("keydown", onKeydown);

  // --- menu « Volets ▾ » -----------------------------------------------------------------
  let menuPopup = null;
  let menuTrigger = null;
  let menuList = null;

  function buildMenu() {
    const tools = document.querySelector(".site-nav-tools");
    if (!tools) return;
    const menu = el("div", "menu", { id: "pane-menu" });
    menuTrigger = el("button", "menu-trigger", {
      type: "button",
      id: "pane-menu-trigger",
      "aria-haspopup": "true",
      "aria-expanded": "false",
      "aria-controls": "pane-menu-popup",
    });
    menuTrigger.append("Volets ");
    const caret = el("span", "", { "aria-hidden": "true" });
    caret.textContent = "▾";
    menuTrigger.append(caret);
    menuPopup = el("div", "menu-popup pane-menu-popup", {
      id: "pane-menu-popup",
      role: "group",
      "aria-label": "Volets",
      hidden: true,
    });
    menuList = el("ul", "pane-menu-list");
    const hint = el("p", "btn-reason", { id: "pane-menu-hint" });
    hint.textContent = "Élargir et Réduire agissent sur les vues affichées côte à côte.";
    menuPopup.append(menuList, hint);
    menu.append(menuTrigger, menuPopup);
    tools.prepend(menu);
    menuTrigger.addEventListener("click", () => setMenuOpen(menuPopup.hidden, false));
    document.addEventListener("click", (event) => {
      if (!menuPopup.hidden && !menu.contains(event.target)) setMenuOpen(false, false);
    });
    for (const pane of panes) {
      const item = el("li", "pane-menu-item", { "data-pane": pane.id });
      const label = el("label", "check");
      const box = el("input", "", { type: "checkbox", "data-action": "visible" });
      label.append(box, pane.title);
      box.addEventListener("change", () => {
        if (box.checked) showById(pane.id);
        else hideById(pane.id);
        renderMenuState();
      });
      const wider = el("button", "btn btn-reset pane-menu-size", {
        type: "button",
        "aria-label": `Élargir ${pane.title}`,
      });
      wider.textContent = "Élargir";
      const narrower = el("button", "btn btn-reset pane-menu-size", {
        type: "button",
        "aria-label": `Réduire ${pane.title}`,
      });
      narrower.textContent = "Réduire";
      wider.addEventListener("click", () => resizeById(pane.id, 1));
      narrower.addEventListener("click", () => resizeById(pane.id, -1));
      item.append(label, wider, narrower);
      menuList.append(item);
    }
    renderMenuState();
  }

  function setMenuOpen(open, returnFocus) {
    menuPopup.hidden = !open;
    menuTrigger.setAttribute("aria-expanded", String(open));
    if (!open && returnFocus) menuTrigger.focus();
  }

  function renderMenuState() {
    if (!menuList) return;
    const visible = L.visibleIds(config, panes);
    const shown = effective ? new Set(effective.shown) : visible;
    for (const item of menuList.children) {
      const id = item.dataset.pane;
      const box = item.querySelector("input");
      box.checked = shown.has(id);
      box.setAttribute("aria-disabled", String(visible.size <= 1 && visible.has(id)));
      box.setAttribute("aria-describedby", "pane-menu-hint");
      for (const button of item.querySelectorAll("button")) {
        const resizable = shown.has(id) && effective && effective.mode !== "single";
        if (resizable) button.removeAttribute("aria-disabled");
        else button.setAttribute("aria-disabled", "true");
        button.setAttribute("aria-describedby", "pane-menu-hint");
      }
    }
  }

  buildMenu();
  document.querySelector(".site-nav")?.setAttribute("data-zone", "header");

  // --- démarrage et suivi de la fenêtre --------------------------------------------------
  for (const pane of panes) {
    const section = paneElement(pane);
    if (pane.terminal) section.dataset.terminal = "true";
  }
  arrange(true);
  renderMenuState();
  let observer = null;
  if (typeof ResizeObserver !== "undefined") {
    observer = new ResizeObserver(() => {
      arrange();
      refreshHandles();
      renderMenuState();
    });
    observer.observe(grid);
  }

  return {
    destroy() {
      unsubscribe();
      chainView?.close(false);
      document.removeEventListener("keydown", onKeydown);
      if (observer) observer.disconnect();
    },
  };
}
