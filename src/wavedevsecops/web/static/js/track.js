// Parcours choisi (`path-picker` du catalogue et `path-menu` de l'en-tête, UX-DR4 et UX-DR29).
// Le navigateur ne mémorise que le choix (clé `wds.track`) ; les parcours, leurs libellés et la
// progression viennent du serveur (AD-2). Chaque parcours garde sa progression : la changer ne
// touche à aucun espace.

export const TRACK_KEY = "wds.track";
export const MENU_LABEL = "Parcours";
export const MENU_PLACEHOLDER = "Choisir un parcours";

function storageOf(storage) {
  if (storage) return storage;
  try {
    return window.localStorage;
  } catch (err) {
    return null;
  }
}

/** Parcours mémorisé, ou `null` au premier passage (ou si le navigateur refuse la lecture). */
export function getTrack(storage) {
  try {
    return storageOf(storage)?.getItem(TRACK_KEY) || null;
  } catch (err) {
    return null;
  }
}

export function setTrack(track, storage) {
  try {
    storageOf(storage)?.setItem(TRACK_KEY, track);
  } catch (err) {
    // Le choix vaut pour cette page même si le navigateur refuse de le garder.
  }
}

/**
 * `path-menu` : un sélecteur de l'en-tête, sur tous les écrans. Changer de parcours le mémorise,
 * puis `onChange(track)` ramène au catalogue du nouveau parcours.
 */
export function renderPathMenu(menu, tracks, current, onChange) {
  menu.replaceChildren();
  if (!current) {
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = MENU_PLACEHOLDER;
    placeholder.disabled = true;
    placeholder.selected = true;
    menu.append(placeholder);
  }
  for (const track of tracks) {
    const option = document.createElement("option");
    option.value = track.key;
    option.textContent = track.label;
    if (track.key === current) option.selected = true;
    menu.append(option);
  }
  if (current) menu.value = current;
  menu.hidden = false;
  menu.onchange = () => {
    if (menu.value && menu.value !== current) onChange(menu.value);
  };
}
