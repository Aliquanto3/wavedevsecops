// Doublure de DOM minimale pour exécuter les modules du front sous Node, sans dépendance :
// arbre d'éléments, attributs, `dataset`, `hidden`, sélecteurs simples (balise, classe,
// identifiant, attribut, `:not()`, `:scope`, combinateurs espace et `>`, listes à virgules), événements
// avec capture et propagation, focus (`activeElement`, `focusin`). La mise en page n'existe
// pas : `getBoundingClientRect` lit la part `flex` posée par le code (px après un
// redimensionnement), et `clientWidth` vaut 0 (le code se rabat sur la fenêtre).

const FOCUSABLE = new Set(["BUTTON", "INPUT", "A", "TEXTAREA", "SELECT"]);

class Node {
  constructor() {
    this.parentNode = null;
    this.childNodes = [];
  }
  get parentElement() {
    return this.parentNode instanceof Element ? this.parentNode : null;
  }
  get isConnected() {
    let node = this;
    while (node) {
      if (node === doc) return true;
      node = node.parentNode;
    }
    return false;
  }
  get textContent() {
    return this.childNodes.map((child) => child.textContent).join("");
  }
  set textContent(value) {
    this.replaceChildren(String(value ?? ""));
  }
  get children() {
    return this.childNodes.filter((child) => child instanceof Element);
  }
  _adopt(item) {
    const node = typeof item === "string" ? new Text(item) : item;
    if (node.parentNode) node.remove();
    node.parentNode = this;
    return node;
  }
  append(...items) {
    for (const item of items) this.childNodes.push(this._adopt(item));
  }
  prepend(...items) {
    this.childNodes.unshift(...items.map((item) => this._adopt(item)));
  }
  replaceChildren(...items) {
    for (const child of this.childNodes) child.parentNode = null;
    this.childNodes = [];
    this.append(...items);
  }
  remove() {
    const parent = this.parentNode;
    if (!parent) return;
    parent.childNodes.splice(parent.childNodes.indexOf(this), 1);
    this.parentNode = null;
    if (doc.activeElement && !doc.activeElement.isConnected) doc.activeElement = doc.body;
  }
  after(...items) {
    const parent = this.parentNode;
    const at = parent.childNodes.indexOf(this) + 1;
    parent.childNodes.splice(at, 0, ...items.map((item) => parent._adopt(item)));
  }
  contains(other) {
    let node = other;
    while (node) {
      if (node === this) return true;
      node = node.parentNode;
    }
    return false;
  }
  get nextElementSibling() {
    const siblings = this.parentNode ? this.parentNode.children : [];
    return siblings[siblings.indexOf(this) + 1] || null;
  }
  *_descendants() {
    for (const child of this.children) {
      yield child;
      yield* child._descendants();
    }
  }
  querySelectorAll(selector) {
    const groups = parseSelector(selector);
    return [...this._descendants()].filter((node) =>
      groups.some((group) => matchGroup(node, group, this)),
    );
  }
  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }
  // --- événements -------------------------------------------------------------------
  addEventListener(type, listener, options) {
    const capture = options === true || Boolean(options && options.capture);
    (this._listeners ||= []).push({ type, listener, capture });
  }
  removeEventListener(type, listener) {
    this._listeners = (this._listeners || []).filter(
      (entry) => !(entry.type === type && entry.listener === listener),
    );
  }
  dispatchEvent(event) {
    event.target = this;
    const path = [];
    for (let node = this; node; node = node.parentNode) path.push(node);
    const run = (node, phase) => {
      for (const entry of [...(node._listeners || [])]) {
        if (entry.type !== event.type || event._stopImmediate) continue;
        if (phase === "capture" && !entry.capture) continue;
        if (phase === "bubble" && entry.capture) continue;
        event.currentTarget = node;
        entry.listener.call(node, event);
      }
    };
    for (const node of path.slice(1).reverse()) {
      if (event._stop) break;
      run(node, "capture");
    }
    if (!event._stop) {
      run(this, "capture");
      if (!event._stopImmediate) run(this, "bubble");
    }
    if (event.bubbles) {
      for (const node of path.slice(1)) {
        if (event._stop) break;
        run(node, "bubble");
      }
    }
    return !event.defaultPrevented;
  }
}

class Text extends Node {
  constructor(text) {
    super();
    this.data = String(text);
  }
  get textContent() {
    return this.data;
  }
  set textContent(value) {
    this.data = String(value);
  }
}

class Element extends Node {
  constructor(tag) {
    super();
    this.tagName = tag.toUpperCase();
    this.attributes = new Map();
    this.style = {};
    this.checked = false;
    const self = this;
    this.dataset = new Proxy(
      {},
      {
        get: (_, key) => self.getAttribute(dataName(key)) ?? undefined,
        set: (_, key, value) => {
          self.setAttribute(dataName(key), value);
          return true;
        },
      },
    );
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }
  hasAttribute(name) {
    return this.attributes.has(name);
  }
  removeAttribute(name) {
    this.attributes.delete(name);
  }
  get id() {
    return this.getAttribute("id") ?? "";
  }
  set id(value) {
    this.setAttribute("id", value);
  }
  get className() {
    return this.getAttribute("class") ?? "";
  }
  set className(value) {
    this.setAttribute("class", value);
  }
  get classList() {
    const names = () => this.className.split(/\s+/).filter(Boolean);
    return {
      contains: (name) => names().includes(name),
      add: (...more) => {
        this.className = [...new Set([...names(), ...more])].join(" ");
      },
      remove: (...less) => {
        this.className = names()
          .filter((name) => !less.includes(name))
          .join(" ");
      },
    };
  }
  get hidden() {
    return this.hasAttribute("hidden");
  }
  set hidden(value) {
    if (value) this.setAttribute("hidden", "");
    else this.removeAttribute("hidden");
  }
  get clientWidth() {
    return 0;
  }
  get clientHeight() {
    return 0;
  }
  getBoundingClientRect() {
    const size = parseFloat(this.style.flex) || 0;
    return { width: size, height: size };
  }
  closest(selector) {
    const groups = parseSelector(selector);
    for (let node = this; node instanceof Element; node = node.parentNode) {
      if (groups.some((group) => matchGroup(node, group, null))) return node;
    }
    return null;
  }
  get focusable() {
    return this.isConnected && (FOCUSABLE.has(this.tagName) || this.hasAttribute("tabindex"));
  }
  focus() {
    if (!this.focusable || doc.activeElement === this) return;
    doc.activeElement = this;
    this.dispatchEvent(makeEvent("focusin", { bubbles: true }));
  }
  click() {
    return this.dispatchEvent(makeEvent("click", { bubbles: true, button: 0 }));
  }
}

class Document extends Node {
  constructor() {
    super();
    this.body = null;
    this.activeElement = null;
  }
  createElement(tag) {
    return new Element(tag);
  }
  createTextNode(text) {
    return new Text(text);
  }
  createElementNS(_namespace, tag) {
    return new Element(tag);
  }
  getElementById(id) {
    return [...this._descendants()].find((node) => node.id === id) || null;
  }
}

function dataName(key) {
  return `data-${String(key).replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`)}`;
}

export function makeEvent(type, init = {}) {
  return {
    type,
    bubbles: true,
    key: "",
    shiftKey: false,
    altKey: false,
    ctrlKey: false,
    metaKey: false,
    defaultPrevented: false,
    ...init,
    preventDefault() {
      this.defaultPrevented = true;
    },
    stopPropagation() {
      this._stop = true;
    },
    stopImmediatePropagation() {
      this._stop = true;
      this._stopImmediate = true;
    },
  };
}

// --- sélecteurs -------------------------------------------------------------------------

function splitTop(text, separator) {
  const parts = [];
  let depth = 0;
  let quote = null;
  let current = "";
  for (const c of text) {
    if (quote) {
      if (c === quote) quote = null;
    } else if (c === '"' || c === "'") quote = c;
    else if (c === "(" || c === "[") depth++;
    else if (c === ")" || c === "]") depth--;
    else if (depth === 0 && separator(c)) {
      parts.push(current);
      current = "";
      continue;
    }
    current += c;
  }
  parts.push(current);
  return parts;
}

/** Liste de groupes ; un groupe : [{ compound, combinator }] de gauche à droite. */
function parseSelector(selector) {
  return splitTop(selector, (c) => c === ",").map((group) => {
    const tokens = splitTop(group.replace(/\s*>\s*/g, " > ").trim(), (c) => c === " ").filter(
      Boolean,
    );
    const steps = [];
    let combinator = " ";
    for (const token of tokens) {
      if (token === ">") {
        combinator = ">";
        continue;
      }
      steps.push({ compound: parseCompound(token), combinator });
      combinator = " ";
    }
    return steps;
  });
}

function parseCompound(token) {
  const parts = [];
  const pattern = /^(\*|[a-zA-Z][\w-]*)|\.([\w-]+)|#([\w-]+)|\[([\w-]+)(?:="([^"]*)")?\]|:not\(([^)]*)\)|:scope/g;
  let match;
  let consumed = 0;
  while ((match = pattern.exec(token)) !== null) {
    if (match.index !== consumed) throw new Error(`Sélecteur non pris en charge : ${token}`);
    consumed = pattern.lastIndex;
    if (match[1]) parts.push({ tag: match[1].toUpperCase() });
    else if (match[2]) parts.push({ cls: match[2] });
    else if (match[3]) parts.push({ attr: "id", value: match[3] });
    else if (match[4]) parts.push({ attr: match[4], value: match[5] });
    else if (match[6] !== undefined) parts.push({ not: parseCompound(match[6]) });
    else parts.push({ scope: true });
  }
  if (consumed !== token.length) throw new Error(`Sélecteur non pris en charge : ${token}`);
  return parts;
}

function matchCompound(node, parts, scope) {
  return parts.every((part) => {
    if (part.tag) return part.tag === "*" || node.tagName === part.tag;
    if (part.cls) return node.classList.contains(part.cls);
    if (part.attr) {
      if (!node.hasAttribute(part.attr)) return false;
      return part.value === undefined || node.getAttribute(part.attr) === part.value;
    }
    if (part.not) return !matchCompound(node, part.not, scope);
    if (part.scope) return node === scope;
    return false;
  });
}

function matchGroup(node, steps, scope) {
  const match = (element, index) => {
    if (!(element instanceof Element) && !(element === scope && steps[index].compound[0]?.scope)) {
      return false;
    }
    if (!matchCompound(element, steps[index].compound, scope)) return false;
    if (index === 0) return true;
    const combinator = steps[index].combinator;
    if (combinator === ">") return element.parentNode && match(element.parentNode, index - 1);
    for (let up = element.parentNode; up; up = up.parentNode) {
      if (match(up, index - 1)) return true;
    }
    return false;
  };
  return match(node, steps.length - 1);
}

// --- installation -----------------------------------------------------------------------

const doc = new Document();

/** Installe `document` et `window` globaux, avec une coquille `body > nav.site-nav`. */
export function installDom({ width = 1920, height = 1080 } = {}) {
  doc.body = new Element("body");
  doc.replaceChildren(doc.body);
  doc.activeElement = doc.body;
  const nav = new Element("nav");
  nav.className = "site-nav";
  const tools = new Element("div");
  tools.className = "site-nav-tools";
  nav.append(tools);
  const main = new Element("main");
  doc.body.append(nav, main);
  globalThis.document = doc;
  globalThis.window = { innerWidth: width, innerHeight: height };
  return { document: doc, main };
}

/** Frappe `key` sur l'élément qui a le focus (ou `target`), comme le ferait le navigateur. */
export function press(key, { target = doc.activeElement, shiftKey = false } = {}) {
  const event = makeEvent("keydown", { key, shiftKey });
  (target || doc.body).dispatchEvent(event);
  return event;
}

export function memoryStorage(initial = {}) {
  const data = new Map(Object.entries(initial));
  return {
    getItem: (key) => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => data.set(key, String(value)),
    data,
  };
}
