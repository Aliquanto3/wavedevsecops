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
- **Contrôle de reprise.** `engine/resume.py::check_resume(layout, loaded)` (lecture seule, sans lancer git, ne rouvre ni ne recrée rien) rend `ResumeCheck{can_resume, step_number, step_total, reason}`. Refus, dans l'ordre : `workspace_missing` (dossier ou `repo/` absent), `repo_broken` (`repo/.git` ou `origin.git/` absent, que le setup crée toujours), `run_unreadable` (`run.json` absent, illisible, d'une version future, ou sans clé `step_id`), `content_changed` (`content_hash` de `run.json` ≠ celui du scénario actuel, AD-20), `step_unknown` (étape disparue du scénario), `broken` (`restore_failed` ou `restoring`). Un scénario terminé (`step_id: null`) n'offre ni reprise ni encart (`reason: finished`, « Terminé » reste affiché). L'empreinte est recalculée à la réouverture par la projection d'ouverture du moteur (AD-6), pas par ce contrôle (voir Revue, H1).
- **Catalogue.** Le mode qui est le dernier ouvert du parcours choisi porte `resume` : `{can_resume, step_number, step_total, text: "Étape n sur N", button_text: "Reprendre"}`, ou `{can_resume: false, blocked_text: "Ce scénario ne peut pas reprendre là où vous l'aviez laissé.", restart_text: "Recommencer"}`. Un seul mode porte `resume` ; un mode indisponible (outil absent) n'en porte pas.
- **Ouverture.** `POST /api/open` accepte `resume: true` (revérifie `check_resume`, 409 « … Recommencez le scénario. » sinon, puis rouvre l'espace existant via `manager.get` : jamais de nouveau `setup`) et `restart: true` (espace existant : intention `restart` de la 4.4 soumise à sa file, avec remise à l'instantané 0 ou reconstruction vérifiée, fait `scenario_reset` et faits du premier passage gardés ; espace absent : `setup` ordinaire).
- **Front.** `catalogue.js::modeColumn` : « Étape n sur N » puis « Reprendre » (bouton principal) à côté d'« Ouvrir en mode X ». Si la reprise est impossible : encart (`role="status"`, le texte du serveur) et « Recommencer » seul, avec la confirmation en ligne de la 4.4 (`restart.js::restartFoot`) ; « Ouvrir » n'est plus proposé sur un espace inutilisable. `openMode` poste `resume` / `restart` ; `main.js` transmet les options (ajout de deux lignes). `catalogue.css` : `.scenario-mode-step`, `.scenario-mode-blocked`.
- Tests : `tests/test_reprise.py` (reprise possible, six motifs de refus, scénario terminé, `last_opened`, catalogue par parcours, API de bout en bout : reprise sans perte du travail en cours, refus après changement du contenu, « Recommencer » reconstruit), `tests/test_reprise_dom.py` (Node : étape, boutons, encart, corps de la demande).

## Décisions

- Le dernier ouvert vit dans `progress.json`, pas dans le navigateur (cf. 6.1) : « Reprendre » survit à un changement de navigateur. Seul le parcours choisi affiche « Reprendre » ; le dernier ouvert d'un autre parcours réapparaît quand on y revient.
- « Empreinte qui ne correspond plus à l'étape » : `run.json` ne mémorise pas d'empreinte par étape, et AD-6 traite un écart entre l'empreinte recalculée à la reprise et la dernière projection comme un « changement externe » (suivi par les vues, 2.9), pas comme un refus : l'apprenant peut travailler dans son dépôt hors de l'application entre deux séances. Le contrôle porte donc sur ce qui rend la reprise impossible : espace et dépôts présents, `run.json` lisible, étape connue, `content_hash`, pas d'échec de restauration. **Décision pour Anaël** : reformuler le critère en « un bac à sable disparu ou inutilisable (dépôt absent, restauration en échec), ou un `content_hash` incompatible », ou bien décider d'un refus sur écart d'empreinte (ce qui contredirait AD-6 et la 2.9).
- « Recommencer » de l'encart passe par `POST /api/open` avec `restart: true`, qui soumet l'intention `restart` de la 4.4 dans la file de l'espace : même remise, même fait `scenario_reset`, et une reprise de restauration au démarrage passe d'abord (file FIFO).

## Reports

- Contrôles navigateur (Anaël) : rendu de l'encart et du bouton principal dans la colonne de mode, focus après « Reprendre », rendu sombre.
- Ouvrir un scénario terminé ne recrée pas l'espace (inchangé) ; aucun « Reprendre » n'y est proposé.

## Revue

Revue Opus (une passe, après rebase sur `origin/main` avec 4.4, 6.5 et 2.9 ; aucun conflit).

- H1 · second avis · corrigé · `if not fingerprint(...)` ne comparait rien (sha256 toujours vrai). Contrôle retiré de `check_resume` : AD-6 recalcule l'empreinte à l'ouverture (projection d'ouverture) et traite l'écart comme un changement externe, pas comme un refus. Remplacé par un contrôle structurel sans git (`repo_broken`). Test : dépôt modifié hors de l'application → reprise possible. Critère à reformuler (décision Anaël, voir Décisions).
- H2 · second avis · corrigé · « Recommencer » de l'encart faisait un `setup` avec `replace=True` (ni `scenario_reset`, ni instantané 0, ni `restoring`). Il soumet maintenant `build_restart` (4.4) dans la file de l'espace ; test de bout en bout : fait `scenario_reset` consigné.
- M3 · second avis · corrigé · calcul d'empreinte à chaque affichage du catalogue et faux refus sur `index.lock` : plus aucun appel git dans `check_resume`.
- M4 · second avis · corrigé · `resolve_git` hors du `try` dans `catalogue_body` et `/api/open` : n'est plus appelé.
- L5 · second avis · corrigé · `run.json` sans clé `step_id` donnait « terminé » : maintenant `run_unreadable` (encart et Recommencer). Test ajouté.
- L6 · second avis · corrigé (avec H2) · la remise passe dans la file FIFO derrière une reprise de restauration soumise à l'ouverture.
- L7 · second avis · corrigé en partie · confirmation en ligne de la 4.4 (`restartFoot`) avant « Recommencer » ; focus déplacé sur la confirmation puis rendu au bouton. Focus après « Reprendre » écarté : la page change (`location.assign`), une erreur s'annonce dans le `role="alert"`.
- Complexité : 0 constat (aucune structure qui grossit ; `last_opened` est une clé remplacée).
- Report · navigateur (Anaël) : rendu de la confirmation dans la colonne de mode du catalogue.
