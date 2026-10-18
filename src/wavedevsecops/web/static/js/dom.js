// Petits utilitaires de DOM partagés par les écrans.

/** Écrit `text` dans `parent` : les segments entre accents graves deviennent du `<code>`. */
export function richText(parent, text) {
  const nodes = [];
  text.split("`").forEach((part, index) => {
    if (part === "") return;
    if (index % 2 === 1) {
      const code = document.createElement("code");
      code.textContent = part;
      nodes.push(code);
    } else {
      nodes.push(document.createTextNode(part));
    }
  });
  parent.replaceChildren(...nodes);
  return parent;
}

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

/** Élément SVG ; `class` et les autres attributs passent par `setAttribute`. */
export function svg(tag, attrs = {}) {
  const node = document.createElementNS(SVG_NAMESPACE, tag);
  for (const [name, value] of Object.entries(attrs)) {
    if (value !== false && value != null) node.setAttribute(name, String(value));
  }
  return node;
}

export function el(tag, className = "", attrs = {}) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  for (const [name, value] of Object.entries(attrs)) {
    if (value === true) node.setAttribute(name, "");
    else if (value !== false && value != null) node.setAttribute(name, String(value));
  }
  return node;
}
