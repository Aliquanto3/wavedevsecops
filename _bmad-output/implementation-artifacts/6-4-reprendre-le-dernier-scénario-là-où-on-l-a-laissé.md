---
story: "6.4"
key: 6-4-reprendre-le-dernier-scénario-là-où-on-l-a-laissé
title: Reprendre le dernier scénario là où on l'a laissé
status: review
branch: story/6-4-reprendre-scenario
ad: [AD-5, AD-6, AD-14, AD-20]
---

# Story 6.4 : Reprendre le dernier scénario là où on l'a laissé

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 6.4 » ; FR-9, UX-DR29, décision « Reprendre rouvre le bac à sable conservé » ; spine AD-5, AD-6, AD-14, AD-20. S'appuie sur le catalogue de la 6.1 (report « Reprendre revient à 6.4 »), `run.json` (4.x) et `ProgressStore` (4.2).

## Livré

- **Dernier scénario ouvert (AD-14).** `ProgressStore.set_last_opened` / `last_opened` : clé de tête `last_opened{track, scenario_id, mode, at}` de `progress.json`, écrite par `progress` seul (même verrou). Ce n'est pas un fait du premier passage : elle se remplace à chaque ouverture, sans toucher `facts`, et n'est pas réécrite si elle ne change pas. `POST /api/open` la consigne après une ouverture réussie ; un échec de consignation est journalisé et n'empêche pas l'ouverture.
- **Contrôle de reprise.** `engine/resume.py::check_resume(layout, loaded, settings, git_path)` (lecture seule, ne rouvre ni ne recrée rien) rend `ResumeCheck{can_resume, step_number, step_total, reason}`. Refus, dans l'ordre : `workspace_missing` (dossier ou `repo/` absent), `run_unreadable` (`run.json` absent, illisible ou d'une version future), `content_changed` (`content_hash` de `run.json` ≠ celui du scénario actuel, AD-20), `step_unknown` (étape disparue du scénario), `broken` (`restore_failed` ou `restoring`), `fingerprint` (l'empreinte, recalculée à la reprise, AD-6, ne se calcule plus : dépôt illisible). Un scénario terminé (`step_id` vide) n'offre ni reprise ni encart (`reason: finished`, « Terminé » reste affiché).
- **Catalogue.** Le mode qui est le dernier ouvert du parcours choisi porte `resume` : `{can_resume, step_number, step_total, text: "Étape n sur N", button_text: "Reprendre"}`, ou `{can_resume: false, blocked_text: "Ce scénario ne peut pas reprendre là où vous l'aviez laissé.", restart_text: "Recommencer"}`. Un seul mode porte `resume` ; un mode indisponible (outil absent) n'en porte pas.
- **Ouverture.** `POST /api/open` accepte `resume: true` (revérifie `check_resume`, 409 « … Recommencez le scénario. » sinon, puis rouvre l'espace existant via `manager.get` : jamais de nouveau `setup`) et `restart: true` (reconstruit l'espace : `manager.create(..., replace=True)`).
- **Front.** `catalogue.js::modeColumn` : « Étape n sur N » puis « Reprendre » (bouton principal) à côté d'« Ouvrir en mode X ». Si la reprise est impossible : encart (`role="status"`, le texte du serveur) et « Recommencer » seul ; « Ouvrir » n'est plus proposé sur un espace inutilisable. `openMode` poste `resume` / `restart` ; `main.js` transmet les options (ajout de deux lignes). `catalogue.css` : `.scenario-mode-step`, `.scenario-mode-blocked`.
- Tests : `tests/test_reprise.py` (reprise possible, six motifs de refus, scénario terminé, `last_opened`, catalogue par parcours, API de bout en bout : reprise sans perte du travail en cours, refus après changement du contenu, « Recommencer » reconstruit), `tests/test_reprise_dom.py` (Node : étape, boutons, encart, corps de la demande).

## Décisions

- Le dernier ouvert vit dans `progress.json`, pas dans le navigateur (cf. 6.1) : « Reprendre » survit à un changement de navigateur. Seul le parcours choisi affiche « Reprendre » ; le dernier ouvert d'un autre parcours réapparaît quand on y revient.
- « Empreinte qui ne correspond plus à l'étape » : `run.json` ne mémorise pas d'empreinte par étape (le dépôt change légitimement entre deux séances). La vérification porte donc sur ce qui est contrôlable : étape connue du scénario, `content_hash`, espace non en échec de restauration, empreinte calculable. Un contrôle plus fort (empreinte de l'instantané de l'étape) demanderait d'enregistrer cette empreinte à chaque changement d'étape.
- « Recommencer » de l'encart passe par `POST /api/open` avec `restart: true` plutôt que par un nouveau point d'entrée, pour ne pas recouper la 4.4.

## Reports

- « Recommencer » depuis l'encart ne consigne pas de fait `scenario_reset` (rapport 6.5) : la remise à zéro en espace (4.4) en est propriétaire ; à aligner à l'intégration des deux stories (l'appel est `restart: true` de `/api/open`).
- Contrôles navigateur (Anaël) : rendu de l'encart et du bouton principal dans la colonne de mode, focus après « Reprendre », rendu sombre.
- Ouvrir un scénario terminé ne recrée pas l'espace (inchangé) ; aucun « Reprendre » n'y est proposé.
