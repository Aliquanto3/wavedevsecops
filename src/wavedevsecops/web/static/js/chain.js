// Bandeau et carte de la chaîne (Stories 9.1 et 9.2). Tous les textes viennent du serveur
// (`content/chain.yaml`, AD-2) : le front n'invente aucun texte ni lien. La carte se pose par-
// dessus les vues, qui deviennent `inert` tant qu'elle est ouverte.
import { el } from "./dom.js";
import { registerBarrierShower } from "./glossary.js";

const MAP_ID = "chain-map";
const TOGGLE_ID = "chain-map-toggle";
const DETAIL_ID = "chain-detail";

function zoneId(number) {
  return `chain-zone-${number}-title`;
}

/** Bandeau : quatre stations, frontière « CI | CD ». Avec `onStation`, les stations sont des boutons. */
export function buildChainBand(chain, { onStation = null } = {}) {
  const band = el("section", "chain-band", { "aria-label": chain.label });
  const list = el("ol", "chain-stations");
  for (const station of chain.stations) {
    const current = station.number === chain.current;
    const afterBoundary = station.number === chain.boundary_after + 1;
    const item = el("li", current ? "chain-station is-current" : "chain-station", {
      "data-station": station.number,
      "aria-current": current ? "step" : false,
      "aria-describedby": afterBoundary ? "chain-boundary" : false,
    });
    if (onStation) {
      const open = el("button", "chain-station-open", { type: "button" });
      open.textContent = station.text;
      open.addEventListener("click", () => onStation(station.number));
      item.append(open);
    } else {
      item.append(station.text);
    }
    if (current) {
      const pill = el("span", "chain-here");
      pill.textContent = chain.here_text;
      item.append(" ", pill);
    }
    list.append(item);
    if (station.number === chain.boundary_after) {
      // Séparateur visuel, pas une station : masqué du décompte de la liste, lu comme
      // description de la station qui le suit.
      const boundary = el("li", "chain-boundary", { id: "chain-boundary", "aria-hidden": "true" });
      boundary.textContent = chain.boundary_text;
      list.append(boundary);
    }
  }
  band.append(list);
  return band;
}

function dashed(node, text) {
  node.classList.add("is-dashed");
  node.textContent = text;
  return node;
}

function buildZone(station, text) {
  const zone = el("li", "chain-zone", {
    "data-station": station.number,
    "aria-labelledby": zoneId(station.number),
  });
  if (!station.delivered) zone.classList.add("is-soon");
  const title = el("h3", "chain-zone-title", { id: zoneId(station.number), tabindex: "-1" });
  title.append(station.text);
  if (!station.delivered) {
    const soon = el("span", "chain-soon");
    dashed(soon, text.soon_text);
    title.append(" ", soon);
  }
  zone.append(title);
  if (station.description) {
    const description = el("p", "chain-zone-description");
    description.textContent = station.description;
    zone.append(description);
  }
  if (station.tools.length) {
    const tools = el("ul", "chain-nodes chain-tools", { "aria-label": text.tools_title });
    for (const tool of station.tools) {
      const node = el("li", "chain-node chain-tool", { "data-tool": tool.id });
      node.textContent = tool.label;
      if (!tool.available) {
        node.classList.add("is-dashed");
        node.append(" ", `(${text.unavailable_text})`);
      }
      tools.append(node);
    }
    zone.append(tools);
  }
  return zone;
}

/** Monte le bandeau (avec « Carte ▾ ») et la carte dans `workspace`, au rang du bandeau. */
export function mountChain(workspace, chain, { inertNodes = [] } = {}) {
  const text = chain.map;
  const band = buildChainBand(chain, text ? { onStation: (number) => open(number) } : {});
  if (!text) return { band, isOpen: () => false, close() {}, destroy() {} };

  const toggle = el("button", "chain-map-toggle", {
    type: "button",
    id: TOGGLE_ID,
    "aria-expanded": "false",
    "aria-controls": MAP_ID,
    "aria-label": text.button_label,
  });
  toggle.textContent = text.button_text;

  const map = el("section", "chain-map", {
    id: MAP_ID,
    "aria-label": text.title,
    hidden: true,
  });
  const heading = el("h2", "chain-map-title");
  heading.textContent = text.title;
  const zones = el("ol", "chain-zones");
  const detail = el("div", "chain-detail", { id: DETAIL_ID, "aria-live": "polite" });
  const hint = el("p", "chain-detail-hint");
  hint.textContent = text.none_selected;
  detail.append(hint);

  const buttons = [];
  const placed = []; // { button, barrier, station } : pour « Voir la barrière » du vocabulaire
  function select(button, barrier) {
    for (const other of buttons) other.setAttribute("aria-pressed", String(other === button));
    const title = el("p", "chain-detail-title");
    title.textContent = `${barrier.label} — ${text.links_title}`;
    const list = el("ul", "chain-links");
    for (const link of barrier.links) {
      const item = el("li", "chain-link", { "data-kind": link.kind });
      item.textContent = `${link.kind_text} : ${link.label}`;
      list.append(item);
    }
    detail.replaceChildren(title, list);
  }

  for (const station of chain.stations) {
    const zone = buildZone(station, text);
    if (station.barriers.length) {
      const barriers = el("ul", "chain-nodes chain-barriers", { "aria-label": text.barriers_title });
      for (const barrier of station.barriers) {
        const item = el("li", "chain-node chain-barrier");
        const button = el("button", "chain-barrier-btn", {
          type: "button",
          "aria-pressed": "false",
          "aria-controls": DETAIL_ID,
          "data-barrier": barrier.id,
        });
        button.textContent = barrier.label;
        button.addEventListener("click", () => select(button, barrier));
        button.addEventListener("mouseenter", () => select(button, barrier));
        buttons.push(button);
        placed.push({ button, barrier, station: station.number });
        item.append(button);
        barriers.append(item);
      }
      zone.append(barriers);
    }
    zones.append(zone);
  }
  map.append(heading, zones, detail);
  band.append(toggle, map);

  let opened = false;

  function setInert(on) {
    for (const node of inertNodes) {
      if (on) node.setAttribute("inert", "");
      else node.removeAttribute("inert");
    }
  }

  function open(number) {
    const target = number ?? chain.current;
    if (!opened) {
      opened = true;
      map.hidden = false;
      toggle.setAttribute("aria-expanded", "true");
      setInert(true);
    }
    document.getElementById(zoneId(target))?.focus();
  }

  function close(restoreFocus = true) {
    if (!opened) return;
    opened = false;
    map.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
    setInert(false);
    if (restoreFocus) toggle.focus();
  }

  toggle.addEventListener("click", () => (opened ? close() : open(null)));

  // « Voir la barrière » (vocabulaire, Story 9.4) : la carte s'ouvre et sélectionne la barrière.
  const unregister = registerBarrierShower((id) => {
    const found = placed.find((item) => item.barrier.id === id);
    if (!found) return false;
    open(found.station);
    select(found.button, found.barrier);
    found.button.focus();
    return true;
  });

  return {
    band,
    isOpen: () => opened,
    close,
    destroy() {
      unregister();
      close(false);
      band.remove();
    },
  };
}
