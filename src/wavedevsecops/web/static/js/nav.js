// site-nav : les liens viennent du serveur (GET /api/shell), la page courante est soulignée.

export function currentSurface(surfaces, pathname) {
  return surfaces.find((surface) => surface.path === pathname) || surfaces[0] || null;
}

export function renderNav(list, surfaces, current) {
  list.replaceChildren();
  for (const surface of surfaces) {
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = surface.path;
    link.textContent = surface.label;
    if (current && surface.key === current.key) link.setAttribute("aria-current", "page");
    item.append(link);
    list.append(item);
  }
}
