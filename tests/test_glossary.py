# ruff: noqa: E501
"""Vocabulaire de la chaîne (Story 9.4) : contenu, serveur, page et termes des explications."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from test_catalogue import call, cookie, instance  # noqa: F401  (fixtures)
from test_shell_js import NODE, _run
from test_workspace_dom import MINIDOM

from wavedevsecops.config import Settings
from wavedevsecops.web.explanations import load_explanations
from wavedevsecops.web.glossary import glossary_body, load_glossary

CONTENT = Path(__file__).resolve().parent.parent / "content"
TERMS = [
    "secrets-scanning",
    "sast",
    "sca",
    "sbom",
    "quality-gate",
    "four-eyes",
    "branch-protection",
    "traceability",
    "dast",
]


def _barriers() -> set[str]:
    chain = yaml.safe_load((CONTENT / "chain.yaml").read_text("utf-8"))
    return {b["id"] for s in chain["stations"] for b in s.get("barriers", [])}


def test_les_neuf_termes_et_leurs_barrieres_existent() -> None:
    glossary = load_glossary(Settings(content_dir=CONTENT))
    assert glossary is not None
    assert [t.id for t in glossary.terms] == TERMS
    for term in glossary.terms:
        assert term.barrier_id == "" or term.barrier_id in _barriers(), term.id
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", term.definition_text.strip()) if s]
        assert len(sentences) == 2, f"{term.id} : {len(sentences)} phrases"
        assert not re.search(r"\b(tu|ton|ta|tes|toi|te)\b", term.definition_text.lower())
        assert "http" not in term.definition_text
    dast = next(t for t in glossary.terms if t.id == "dast")
    assert dast.named_only and not dast.barrier_id and not dast.scenario_id


def test_les_termes_cites_dans_les_explications_existent() -> None:
    glossary = load_glossary(Settings(content_dir=CONTENT))
    explanations = load_explanations(Settings(content_dir=CONTENT))
    assert glossary is not None and explanations is not None
    known = {t.id for t in glossary.terms}
    cited = {
        match
        for entry in explanations.entries.values()
        for match in re.findall(r"\[\[([a-z0-9-]+)\|[^\]]+\]\]", entry.body_text)
    }
    assert cited and cited <= known
    # Une marque mal formée (majuscule, espace, sans `|`) s'afficherait telle quelle.
    for key, entry in explanations.entries.items():
        stripped = re.sub(r"\[\[([a-z0-9-]+)\|[^\]]+\]\]", "", entry.body_text)
        assert "[[" not in stripped and "]]" not in stripped, key


def test_chaque_scenario_du_vocabulaire_existe_au_catalogue() -> None:
    from wavedevsecops.web.catalogue import load_catalogue

    glossary = load_glossary(Settings(content_dir=CONTENT))
    assert glossary is not None
    catalogue = {
        loaded.scenario.scenario_id
        for loaded in load_catalogue(Settings(content_dir=CONTENT))
        if loaded.scenario.catalogue
    }
    cited = {t.scenario_id for t in glossary.terms if t.scenario_id}
    assert cited and cited <= catalogue, cited - catalogue


def test_barrieres_livrees_ont_un_scenario_les_autres_se_degradent() -> None:
    body = glossary_body(Settings(content_dir=CONTENT))
    by_id = {t["id"]: t for t in body["terms"]}
    assert list(by_id) == TERMS
    secrets = by_id["secrets-scanning"]
    assert secrets["barrier"]["id"] == "secret-scan"
    assert secrets["barrier"]["station_text"] == "Station 1 · Poste local"
    assert secrets["scenario"]["id"] == "secret-dans-un-commit"
    assert secrets["scenario"]["play_text"].startswith("La voir jouer : scénario ")
    # Barrière pas encore jouable (Epic 8) : le terme et la barrière restent, le scénario manque.
    # (`dast` n'a pas de barrière ; `sast` attend que 8.1 renseigne son `scenario_id`.)
    assert by_id["sast"]["barrier"]["id"] == "static-analysis" and by_id["sast"]["scenario"] is None
    # Livrée par la story 8.3 : SCA et SBOM renvoient au scénario « dépendance vulnérable ».
    assert by_id["sca"]["barrier"]["id"] == "dependencies"
    assert by_id["sca"]["scenario"]["id"] == "dependance-vulnerable"
    assert by_id["sbom"]["scenario"]["id"] == "dependance-vulnerable"
    assert by_id["dast"]["barrier"] is None and by_id["dast"]["scenario"] is None
    assert by_id["traceability"]["barrier"] is None and by_id["traceability"]["trace_text"]
    assert body["ui"]["soon_text"] == "Scénario à venir"


def test_fichier_absent_ou_invalide_donne_un_vocabulaire_vide(tmp_path: Path) -> None:
    assert glossary_body(Settings(content_dir=tmp_path)) == {
        "schema_version": 1,
        "ui": None,
        "terms": [],
    }
    (tmp_path / "glossary.yaml").write_text("schema_version: 1\nterms: 3\n", "utf-8")
    assert load_glossary(Settings(content_dir=tmp_path)) is None


def test_un_terme_nomme_seulement_ne_mene_a_rien(tmp_path: Path) -> None:
    text = (CONTENT / "glossary.yaml").read_text("utf-8").replace(
        "    named_only: true", "    named_only: true\n    barrier_id: lint"
    )
    (tmp_path / "glossary.yaml").write_text(text, "utf-8")
    assert load_glossary(Settings(content_dir=tmp_path)) is None


def test_get_glossary_sert_le_vocabulaire(instance, cookie) -> None:  # noqa: F811
    status, body = call(instance, "GET", "/api/glossary", cookie)
    assert status == 200 and [t["id"] for t in body["terms"]] == TERMS


pytestmark_node = pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")

GLOSSARY = {
    "ui": {
        "see_text": "Voir la barrière",
        "barrier_title": "Barrière",
        "play_text": "La voir jouer : scénario {name}",
        "soon_text": "Scénario à venir",
        "named_only_text": "Nommé seulement",
        "none_text": "Le vocabulaire n'est pas disponible pour le moment.",
        "close_text": "Fermer",
    },
    "terms": [
        {
            "id": "secrets-scanning",
            "term_text": "Secrets scanning",
            "definition_text": "Définition.",
            "named_only": False,
            "trace_text": "",
            "barrier": {"id": "secret-scan", "label": "Pas de secret", "station": 1, "station_text": "Station 1 · Poste local", "delivered": True},
            "scenario": {"id": "s1", "title_text": "Un secret", "play_text": "La voir jouer : scénario Un secret"},
        },
        {
            "id": "sast",
            "term_text": "SAST",
            "definition_text": "Définition SAST.",
            "named_only": False,
            "trace_text": "",
            "barrier": {"id": "static-analysis", "label": "Analyse statique", "station": 3, "station_text": "Station 3 · Sécurité", "delivered": True},
            "scenario": None,
        },
        {"id": "traceability", "term_text": "Traçabilité", "definition_text": "D.", "named_only": False, "trace_text": "Dans les PR et les checks.", "barrier": None, "scenario": None},
        {"id": "dast", "term_text": "DAST", "definition_text": "D.", "named_only": True, "trace_text": "", "barrier": None, "scenario": None},
    ],
}

PRELUDE = f"""
import {{ installDom }} from "{MINIDOM}";
const {{ document, main }} = installDom({{ width: 1280, height: 800 }});
const {{ renderVocabulary, termText, showBarrier, registerBarrierShower, loadGlossary }} = await import("@JS@/glossary.js");
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const glossary = {json.dumps(GLOSSARY)};
"""


def _js(tmp_path: Path, body: str) -> dict:
    return json.loads(_run(tmp_path, f"{PRELUDE}\n{body}"))


@pytestmark_node
def test_page_vocabulaire_termes_barrieres_et_nomme_seulement(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
renderVocabulary(main, glossary);
const entries = $$(".glossary-entry").map((e) => ({
  term: e.dataset.term,
  name: e.querySelector(".glossary-name").textContent,
  see: e.querySelector(".glossary-see") ? e.querySelector(".glossary-see").textContent : null,
  tag: e.querySelector(".named-only-tag") ? e.querySelector(".named-only-tag").textContent : null,
  trace: e.querySelector(".glossary-trace") ? e.querySelector(".glossary-trace").textContent : null,
}));
const see = $('[data-term="secrets-scanning"] .glossary-see');
const before = { expanded: see.getAttribute("aria-expanded"), controls: see.getAttribute("aria-controls"), detail: $$(".glossary-barrier").length };
see.click();
const played = { expanded: see.getAttribute("aria-expanded"), title: $(".glossary-barrier-title").textContent, link: $(".glossary-scenario-link").textContent };
see.click();
const closed = $$(".glossary-barrier").length;
$('[data-term="sast"] .glossary-see').click();
const soon = $('[data-term="sast"] .glossary-barrier-play').textContent;
console.log(JSON.stringify({ entries, before, played, closed, soon, controlsExist: Boolean(document.getElementById(before.controls)) }));
""",
    )
    assert [e["term"] for e in out["entries"]] == ["secrets-scanning", "sast", "traceability", "dast"]
    assert out["entries"][0]["see"] == "Voir la barrière" and out["entries"][1]["see"] == "Voir la barrière"
    # DAST : « Nommé seulement », aucune barrière ; traçabilité : renvoi aux PR et aux checks, sans bouton.
    assert out["entries"][3] == {"term": "dast", "name": "DAST Nommé seulement", "see": None, "tag": "Nommé seulement", "trace": None}
    assert out["entries"][2]["see"] is None and out["entries"][2]["trace"] == "Dans les PR et les checks."
    assert out["before"] == {"expanded": "false", "controls": "glossary-barrier-secrets-scanning", "detail": 0}
    assert out["controlsExist"] is True
    assert out["played"] == {
        "expanded": "true",
        "title": "Barrière : Pas de secret (Station 1 · Poste local)",
        "link": "La voir jouer : scénario Un secret",
    }
    assert out["closed"] == 0
    assert out["soon"] == "Scénario à venir"


@pytestmark_node
def test_vocabulaire_indisponible_message(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
renderVocabulary(main, { ui: null, terms: [] });
const failed = await loadGlossary(async () => ({ ok: false }));
console.log(JSON.stringify({ text: $(".empty").textContent, role: $(".empty").getAttribute("role"), failed }));
""",
    )
    assert out["role"] == "alert" and "pas disponible" in out["text"]
    assert out["failed"] == {"ui": None, "terms": []}


@pytestmark_node
def test_terme_dans_une_explication_et_voir_la_barriere(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const byId = new Map(glossary.terms.map((t) => [t.id, t]));
const clicked = [];
const body = document.createElement("p");
main.append(body);
termText(body, "Un `check` lance le [[sast|SAST]], puis [[inconnu|autre]] chose.", byId, (term) => clicked.push(term.id));
const terms = $$(".glossary-term").map((t) => [t.textContent, t.tagName, t.dataset.term]);
$(".glossary-term").click();
const none = showBarrier("static-analysis");
const seen = [];
const off = registerBarrierShower((id) => { seen.push(id); return id === "static-analysis"; });
const handled = showBarrier("static-analysis");
const missed = showBarrier("secret-scan");
off();
console.log(JSON.stringify({ text: body.textContent, terms, clicked, code: $$("code").length, none, handled, missed, seen, after: showBarrier("static-analysis") }));
""",
    )
    assert out["text"] == "Un check lance le SAST, puis autre chose."
    assert out["terms"] == [["SAST", "BUTTON", "sast"]]  # terme inconnu : texte simple
    assert out["clicked"] == ["sast"] and out["code"] == 1
    assert out["none"] is False and out["handled"] is True and out["missed"] is False
    assert out["seen"] == ["static-analysis", "secret-scan"] and out["after"] is False


@pytestmark_node
def test_tracabilite_lien_avec_espace_et_phrase_sans_lien_mort(tmp_path: Path) -> None:
    out = _js(
        tmp_path,
        """
const base = glossary.terms.filter((t) => t.id === "traceability").map((t) => ({ ...t }));
const draw = (trace) => {
  renderVocabulary(main, { ui: glossary.ui, terms: [{ ...base[0], trace }] });
  const a = $(".glossary-trace-link");
  return {
    link: a ? { href: a.getAttribute("href"), text: a.textContent } : null,
    none: $(".glossary-trace-none") ? $(".glossary-trace-none").textContent : null,
    dead: $$("a").filter((x) => !x.getAttribute("href")).length,
  };
};
const open = draw({ link: { href: "/espace/sans-ia.x.A", text: "Voir les PR et les checks de votre espace" } });
const closed = draw({ link: null, none_text: "Ouvrez un scénario de station pour voir des PR et des checks." });
console.log(JSON.stringify({ open, closed }));
""",
    )
    assert out["open"] == {"link": {"href": "/espace/sans-ia.x.A", "text": "Voir les PR et les checks de votre espace"}, "none": None, "dead": 0}
    assert out["closed"] == {"link": None, "none": "Ouvrez un scénario de station pour voir des PR et des checks.", "dead": 0}
