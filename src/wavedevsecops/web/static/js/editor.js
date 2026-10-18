// Composant d'édition de la vue Code (AD-13, story 2.8) : un <textarea> natif et une gouttière de
// numéros de ligne. Aucune dépendance, aucun CDN, aucun build à l'exécution : le fichier est le
// composant. Choisi pour son accessibilité (clavier, lecteur d'écran, zoom, correcteur du système
// désactivé) et sa taille ; la coloration syntaxique n'est pas un besoin de la pédagogie (FR-3).
// Les marqueurs de conflit (<<<<<<<, =======, >>>>>>>) restent du texte éditable ; la gouttière les
// repère par une marque ⚠ et un trait, jamais par la seule couleur (UX-DR18).
import { el } from "./dom.js";

export const CONFLICT_LINE = /^(<<<<<<<|>>>>>>>)( |$)|^=======$/;
export const CONFLICT_MARK = "⚠";

/** Numéros (1…) des lignes de `text` qui sont un marqueur de conflit. */
export function conflictLines(text) {
  const found = [];
  text.split("\n").forEach((line, index) => {
    if (CONFLICT_LINE.test(line)) found.push(index + 1);
  });
  return found;
}

/**
 * Éditeur de texte. `onChange(value)` est appelé à chaque frappe, `onSave()` pour Ctrl+S / Cmd+S.
 * Rend `{ root, area, getValue, setValue, setReadOnly, focus }`.
 */
export function createEditor({ onChange = () => {}, onSave = () => {}, label = "Contenu du fichier" } = {}) {
  const root = el("div", "editor");
  const gutter = el("div", "editor-gutter", { "aria-hidden": "true" });
  const area = el("textarea", "editor-area", {
    spellcheck: "false",
    autocapitalize: "off",
    autocomplete: "off",
    autocorrect: "off",
    wrap: "off",
    "aria-label": label,
  });
  root.append(gutter, area);

  let drawn = -1;
  let drawnConflicts = "";

  function drawGutter() {
    const lines = area.value.split("\n");
    const conflicts = conflictLines(area.value);
    const key = conflicts.join(",");
    if (lines.length === drawn && key === drawnConflicts) return;
    drawn = lines.length;
    drawnConflicts = key;
    const marked = new Set(conflicts);
    gutter.replaceChildren(
      ...lines.map((_, index) => {
        const row = el("div", marked.has(index + 1) ? "editor-no is-conflict" : "editor-no");
        row.textContent = marked.has(index + 1) ? `${CONFLICT_MARK} ${index + 1}` : String(index + 1);
        return row;
      }),
    );
  }

  area.addEventListener("input", () => {
    drawGutter();
    onChange(area.value);
  });
  area.addEventListener("scroll", () => {
    gutter.scrollTop = area.scrollTop;
  });
  area.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && !event.altKey && String(event.key).toLowerCase() === "s") {
      event.preventDefault(); // pas la boîte « Enregistrer sous » du navigateur
      onSave();
    }
  });

  return {
    root,
    area,
    getValue: () => area.value,
    setValue(text) {
      area.value = text;
      drawGutter();
    },
    setReadOnly(on) {
      if (on) area.setAttribute("readonly", "");
      else area.removeAttribute("readonly");
    },
    focus: () => area.focus(),
  };
}
