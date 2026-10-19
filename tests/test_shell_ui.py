"""Story 1.3 : coquille d'interface servie par l'application (AD-13, AD-19, convention Front).

Tests côté serveur : routes, en-têtes, fichiers servis, jetons de DESIGN.md, absence d'URL
externe. Pas de navigateur réel : le comportement du front (thème, bandeau) est vérifié par
la présence des fichiers et des textes attendus.
"""

from __future__ import annotations

import http.client
import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from static_rules import STATIC, static_url_violations

from wavedevsecops import cli
from wavedevsecops.config import Settings
from wavedevsecops.web.shell import delivered_surfaces

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "_bmad-output/planning-artifacts/ux-designs/ux-wavedevsecops-2026-10-18/DESIGN.md"
CSS = STATIC / "css"
JS = STATIC / "js"


@pytest.fixture
def instance(tmp_path: Path) -> Iterator[cli.Instance]:
    inst = cli.start_instance(Settings(data_dir=tmp_path / "data"))
    try:
        yield inst
    finally:
        inst.stop()


def get(
    inst: cli.Instance, path: str, headers: dict[str, str] | None = None
) -> tuple[http.client.HTTPResponse, bytes]:
    conn = http.client.HTTPConnection(cli.HOST, inst.port, timeout=5)
    conn.request("GET", path, headers=headers or {})
    resp = conn.getresponse()
    return resp, resp.read()


@pytest.fixture
def cookie(instance: cli.Instance) -> dict[str, str]:
    resp, _ = get(instance, f"/?t={instance.token}")
    return {"Cookie": resp.getheader("Set-Cookie", "").split(";")[0]}


def design_colors() -> dict[str, str]:
    front = DESIGN.read_text(encoding="utf-8").split("---")[1]
    return yaml.safe_load(front)["colors"]


# --- pages et API ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/", "/diagnostic"])
def test_surfaces_livrees_servent_la_coquille(
    instance: cli.Instance, cookie: dict[str, str], path: str
) -> None:
    get(instance, "/diagnostic", cookie)  # fin du premier lancement : « / » sert alors l'accueil
    resp, body = get(instance, path, cookie)
    assert resp.status == 200
    assert resp.getheader("Content-Type", "").startswith("text/html")
    html = body.decode("utf-8")
    assert '<html lang="fr">' in html
    assert 'id="app-alert"' in html and 'role="alert"' in html
    assert 'id="surfaces"' in html
    assert "Réduire les animations" in html


def test_surface_non_livree_absente(instance: cli.Instance, cookie: dict[str, str]) -> None:
    for path in ("/fiche",):
        resp, _ = get(instance, path, cookie)
        assert resp.status == 404


def test_surfaces_declarees_par_le_serveur(instance: cli.Instance, cookie: dict[str, str]) -> None:
    resp, body = get(instance, "/api/shell", cookie)
    assert resp.status == 200
    data = json.loads(body)
    assert data["milestone"] == "v0.2"
    assert [(s["label"], s["path"]) for s in data["surfaces"]] == [
        ("Catalogue", "/"),
        ("Diagnostic", "/diagnostic"),
        ("Vocabulaire", "/vocabulaire"),
    ]


def test_surfaces_suivent_le_jalon() -> None:
    assert [s.key for s in delivered_surfaces("v0.1")] == ["catalogue", "diagnostic"]
    assert [s.key for s in delivered_surfaces("v0.2")][-1] == "vocabulaire"
    assert [s.key for s in delivered_surfaces("v0.10")][-1] == "fiche"


def test_point_de_vie_sous_cookie(instance: cli.Instance, cookie: dict[str, str]) -> None:
    resp, body = get(instance, "/api/health", cookie)
    assert resp.status == 200
    assert json.loads(body) == {"status": "ok"}
    assert resp.getheader("Cache-Control") == "no-store"
    for path in ("/api/health", "/api/shell"):
        refused, _ = get(instance, path)
        assert refused.status == 401


def test_fichiers_statiques_sous_cookie(instance: cli.Instance, cookie: dict[str, str]) -> None:
    paths = ("/static/css/tokens.css", "/static/js/main.js", "/static/fonts/fredoka-variable.woff2")
    for path in paths:
        refused, _ = get(instance, path)
        assert refused.status == 401
        resp, _ = get(instance, path, cookie)
        assert resp.status == 200


def test_en_tetes_de_securite(instance: cli.Instance, cookie: dict[str, str]) -> None:
    for headers in (cookie, {}):
        resp, _ = get(instance, "/", headers)
        csp = resp.getheader("Content-Security-Policy", "")
        assert "default-src 'none'" in csp and "connect-src 'self'" in csp
        assert not re.search(r"https?:|\*", csp)
        assert resp.getheader("X-Content-Type-Options") == "nosniff"
    resp, _ = get(instance, "/", cookie)
    assert not [n for n, _ in resp.getheaders() if n.lower().startswith("access-control")]


# --- hors ligne (AD-13) ---------------------------------------------------------------------


def test_aucune_url_externe_dans_static() -> None:
    assert static_url_violations() == []


def test_la_page_et_les_feuilles_ne_chargent_que_du_local(
    instance: cli.Instance, cookie: dict[str, str]
) -> None:
    _, body = get(instance, "/diagnostic", cookie)
    html = body.decode("utf-8")
    refs = re.findall(r'(?:href|src)="([^"#]+)"', html)
    assert refs
    for ref in refs:
        assert ref.startswith("/"), ref
        if ref.startswith("/static/"):
            assert (STATIC / ref.removeprefix("/static/")).is_file(), ref
    for css in CSS.glob("*.css"):
        for url in re.findall(r"url\(\s*[\"']?([^\"')]+)", css.read_text(encoding="utf-8")):
            assert not re.match(r"[a-z]+:|//", url), (css.name, url)
            assert (css.parent / url).resolve().is_file(), (css.name, url)


def test_polices_woff2_locales_et_licences(instance: cli.Instance, cookie: dict[str, str]) -> None:
    fonts = STATIC / "fonts"
    families = ("fredoka", "atkinson-hyperlegible", "jetbrains-mono")
    for family in families:
        files = list(fonts.glob(f"{family}-*.woff2"))
        assert files, family
        assert any(fonts.glob(f"OFL-{family}.txt")), f"licence OFL manquante : {family}"
    for font in fonts.glob("*.woff2"):
        resp, body = get(instance, f"/static/fonts/{font.name}", cookie)
        assert resp.status == 200
        assert body[:4] == b"wOF2"
        assert "font/woff2" in resp.getheader("Content-Type", "") or "woff2" in resp.getheader(
            "Content-Type", ""
        )
    face = (CSS / "fonts.css").read_text(encoding="utf-8")
    for name in ("Fredoka", "Atkinson Hyperlegible", "JetBrains Mono"):
        assert f'font-family: "{name}"' in face


# --- jetons de DESIGN.md --------------------------------------------------------------------


def _blocks(css: str) -> tuple[str, str, str]:
    start_media = css.index("@media (prefers-color-scheme: dark)")
    start_forced = css.index(':root[data-theme="dark"]')
    light = css[:start_media]
    media = css[start_media:start_forced]
    forced = css[start_forced:]
    return light, media, forced


def test_tous_les_jetons_de_couleur_sont_des_proprietes_css() -> None:
    light, media, forced = _blocks((CSS / "tokens.css").read_text(encoding="utf-8"))
    colors = design_colors()
    assert {"terminal-bg", "focus-on-ink", "terminal-lit-ring"} <= colors.keys()
    for name, value in colors.items():
        base = name.removesuffix("-dark")
        declaration = f"--color-{base}: {value};"
        if name.endswith("-dark"):
            assert declaration in media, name
            assert declaration in forced, name
        else:
            assert declaration in light, name


def test_theme_sombre_selon_le_systeme_ou_le_choix() -> None:
    css = (CSS / "tokens.css").read_text(encoding="utf-8")
    assert ':root:not([data-theme="light"])' in css
    assert ':root[data-theme="dark"]' in css


def test_typographie_espacements_arrondis_relief() -> None:
    front = yaml.safe_load(DESIGN.read_text(encoding="utf-8").split("---")[1])
    css = (CSS / "tokens.css").read_text(encoding="utf-8")
    for role, spec in front["typography"].items():
        assert f"--font-family-{role}: {spec['fontFamily']};" in css
        assert f"--font-size-{role}: {spec['fontSize']};" in css
        assert int(spec["fontSize"].removesuffix("px")) >= 12, role
    for name, value in front["rounded"].items():
        assert f"--radius-{name}: {value};" in css
    for name, value in front["spacing"].items():
        prop = f"--space-{name}" if name.isdigit() else f"--{name}"
        assert f"{prop}: {value};" in css, name
    assert "--scenario-panel-width: 440px;" in css
    for relief in ("--shadow-relief:", "--shadow-primary:", "--shadow-relief-overlay:"):
        assert relief in css


def test_aucun_texte_sous_12_px_et_aucune_opacite_sur_le_texte() -> None:
    for css in CSS.glob("*.css"):
        text = css.read_text(encoding="utf-8")
        for size in re.findall(r"font-size:\s*(\d+(?:\.\d+)?)px", text):
            assert float(size) >= 12, (css.name, size)
        assert "opacity" not in text.replace("dimmed-decor-opacity", ""), css.name


# --- thème, mouvement, bandeau d'arrêt, boutons ---------------------------------------------


def test_menu_affichage_theme_et_mouvement() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "Affichage" in html and 'id="theme-picker"' in html
    assert [o for o in re.findall(r"<option value=\"(\w+)\">(\w+)", html)] == [
        ("system", "Système"),
        ("light", "Clair"),
        ("dark", "Sombre"),
    ]
    display = (JS / "display.js").read_text(encoding="utf-8")
    assert "localStorage" in display and '"wds.display"' in display
    assert "data-motion" in display
    assert "wds.display" in (JS / "theme-init.js").read_text(encoding="utf-8")
    shell = (CSS / "shell.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion: reduce" in shell
    assert ':root[data-motion="reduced"]' in shell


def test_bandeau_d_arret_et_point_de_vie() -> None:
    health = (JS / "health.js").read_text(encoding="utf-8")
    assert (
        "WaveDevSecOps ne répond plus. Relancez-le ; votre progression est enregistrée." in health
    )
    assert "/api/health" in health
    main = (JS / "main.js").read_text(encoding="utf-8")
    assert "setOffline" in main and "app-alert" in main


def test_boutons_inactifs_avec_raison_visible_et_reliee() -> None:
    actions = (JS / "actions.js").read_text(encoding="utf-8")
    assert "aria-disabled" in actions and "aria-describedby" in actions
    css = (CSS / "shell.css").read_text(encoding="utf-8")
    for variant in ("btn-primary", "btn-secondary", "btn-reset", "btn-danger"):
        assert f".{variant}" in css
    assert '.btn[aria-disabled="true"]' in css and ".btn-reason" in css


def test_registre_des_volets_extensible() -> None:
    panes = (JS / "panes.js").read_text(encoding="utf-8")
    assert "export function registerPane" in panes and "export function listPanes" in panes
    assert "elementTypes" in panes


# --- contrastes WCAG des paires texte / fond employées par la coquille ----------------------

# (texte, fond, seuil) : paires de shell.css, puis celles du tableau « Contrastes des
# combinaisons ajoutées » de DESIGN.md, recalculées depuis les valeurs servies.
CONTRAST_PAIRS = (
    ("ink", "surface", 4.5),
    ("ink", "surface-raised", 4.5),
    ("ink", "danger-soft", 4.5),
    ("on-ink", "ink-fill", 4.5),
    ("primary-deep", "surface-raised", 4.5),
    ("primary", "surface-raised", 4.5),
    ("on-primary", "primary", 4.5),
    ("ink-soft", "surface", 4.5),
    ("ink-soft", "surface-raised", 4.5),
    ("ink-soft", "discipline-neutral-soft", 4.5),
    ("terminal-fg", "terminal-bg", 4.5),
    ("terminal-fg-soft", "terminal-bg", 4.5),
    ("terminal-accent", "terminal-bg", 4.5),
    ("terminal-danger", "terminal-bg", 4.5),
    ("terminal-rule", "terminal-bg", 3),
    ("focus-on-ink", "terminal-bg", 3),
    ("on-vivid", "danger", 4.5),
    ("primary-deep", "primary-soft", 4.5),
    ("muted", "surface-raised", 3),
    ("danger", "surface-raised", 3),
    ("discipline-context", "discipline-context-soft", 3),
    ("primary", "primary-soft", 4.5),
    ("primary", "surface", 3),
    ("ink", "primary-soft", 4.5),
    ("ink", "discipline-harness-soft", 4.5),
    ("discipline-harness", "surface-raised", 3),
    ("hosting-boundary", "surface-raised", 3),
)


def _luminance(hex_color: str) -> float:
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _ratio(fg: str, bg: str) -> float:
    high, low = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _palette(block: str) -> dict[str, str]:
    return dict(re.findall(r"--color-([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6});", block))


def test_formule_de_contraste_wcag() -> None:
    assert _ratio("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert _ratio("#777777", "#FFFFFF") == pytest.approx(4.48, abs=0.01)


@pytest.mark.parametrize("theme", ["clair", "sombre"])
def test_contrastes_des_paires_texte_fond(theme: str) -> None:
    light, _media, forced = _blocks((CSS / "tokens.css").read_text(encoding="utf-8"))
    palette = _palette(light)
    if theme == "sombre":
        palette |= _palette(forced)
    low = [
        f"{fg}/{bg} {_ratio(palette[fg], palette[bg]):.2f} < {minimum}"
        for fg, bg, minimum in CONTRAST_PAIRS
        if _ratio(palette[fg], palette[bg]) < minimum
    ]
    assert low == []
