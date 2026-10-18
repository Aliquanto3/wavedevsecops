"""Comportement des modules du front (point de vie, actions inactives), exécutés avec Node.

Node n'est pas une dépendance du projet : sans lui, ces tests sont sautés (les runners de la CI
GitHub l'embarquent). Le DOM est une doublure minimale, limitée à ce qu'utilise `actions.js`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "src" / "wavedevsecops" / "web" / "static" / "js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="Node absent : comportement JS non exécuté")


def _run(tmp_path: Path, script: str) -> str:
    path = tmp_path / "check.mjs"
    path.write_text(script.replace("@JS@", JS.as_uri()), encoding="utf-8")
    result = subprocess.run(
        [NODE, str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_point_de_vie_bascule_apres_echecs_et_delai(tmp_path: Path) -> None:
    out = _run(
        tmp_path,
        """
import { watchHealth } from "@JS@/health.js";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// Scénario : ok, un raté isolé, ok, puis le serveur se fige (aucune réponse) : délai dépassé.
const plan = ["ok", "fail", "ok", "hang", "hang", "hang", "ok"];
let calls = 0, inflight = 0, maxInflight = 0;
function fakeFetch(url, opts) {
  const step = plan[Math.min(calls++, plan.length - 1)];
  inflight++; maxInflight = Math.max(maxInflight, inflight);
  const done = (v) => { inflight--; return v; };
  if (step === "ok") return Promise.resolve(done({ ok: true }));
  if (step === "fail") { inflight--; return Promise.reject(new Error("refused")); }
  return new Promise((_, reject) => {
    opts.signal.addEventListener("abort", () => { inflight--; reject(new Error("abort")); });
  });
}
const states = [];
const opts = { interval: 20, timeout: 15, fetchImpl: fakeFetch };
const stop = watchHealth((a) => states.push(a), opts);
await sleep(400);
stop();
console.log(JSON.stringify({ states, maxInflight, url: "/api/health" }));
""",
    )

    data = json.loads(out)
    # Vivant au départ ; le raté isolé ne bascule pas ; le gel est détecté ; le retour aussi.
    assert data["states"] == [True, False, True]
    assert data["maxInflight"] == 1


def test_actions_inactives_hors_ligne_avec_raison_reliee(tmp_path: Path) -> None:
    out = _run(
        tmp_path,
        """
class El {
  constructor(tag) { this.tag = tag; this.attrs = {}; this.parent = null; this.listeners = [];
    this.className = ""; this.id = ""; this.textContent = ""; }
  get classList() { return { contains: (c) => this.className.split(" ").includes(c) }; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  removeAttribute(k) { delete this.attrs[k]; }
  addEventListener(t, f) { this.listeners.push(f); }
  get nextElementSibling() {
    const s = this.parent.children; return s[s.indexOf(this) + 1] || null;
  }
  after(el) {
    const s = this.parent.children; s.splice(s.indexOf(this) + 1, 0, el); el.parent = this.parent;
  }
  remove() { const s = this.parent.children; s.splice(s.indexOf(this), 1); }
  click() { const ev = { prevented: false, preventDefault() { this.prevented = true; },
    stopImmediatePropagation() {} }; this.listeners.forEach((f) => f(ev)); return ev.prevented; }
}
globalThis.document = { createElement: (t) => new El(t) };
const { bindAction, setActionDisabled, setOffline, OFFLINE_REASON } =
  await import("@JS@/actions.js");
const parent = { children: [] };
const a = new El("button"); a.parent = parent; parent.children.push(a);
const b = new El("button"); b.parent = parent; parent.children.push(b);
bindAction(a);
setActionDisabled(b, "Choisissez d'abord un scénario.");
const r = {};
r.aActive = a.getAttribute("aria-disabled") === null && !a.click();
r.bReason = b.nextElementSibling.textContent;
r.bLinked = b.getAttribute("aria-describedby") === b.nextElementSibling.id;
r.bBlocked = b.click();
setOffline(true);
r.aOff = a.getAttribute("aria-disabled") === "true"
  && a.nextElementSibling.textContent === OFFLINE_REASON
  && a.getAttribute("aria-describedby") === a.nextElementSibling.id && a.click();
setOffline(false);
r.aBack = a.getAttribute("aria-disabled") === null && a.nextElementSibling === b;
r.bKeeps = b.nextElementSibling.textContent === "Choisissez d'abord un scénario.";
r.count = parent.children.length;
console.log(JSON.stringify(r));
""",
    )

    r = json.loads(out)
    assert r == {
        "aActive": True,
        "bReason": "Choisissez d'abord un scénario.",
        "bLinked": True,
        "bBlocked": True,
        "aOff": True,
        "aBack": True,
        "bKeeps": True,
        "count": 3,
    }
