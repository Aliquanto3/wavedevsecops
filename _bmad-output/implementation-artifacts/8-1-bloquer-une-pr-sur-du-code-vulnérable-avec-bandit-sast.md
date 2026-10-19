---
story: "8.1"
key: 8-1-bloquer-une-pr-sur-du-code-vulnérable-avec-bandit-sast
title: Bloquer une PR sur du code vulnérable avec bandit (SAST)
status: review
branch: story/8-1-bandit-sast
ad: [AD-8, AD-10, AD-14]
---

# Story 8.1 : Bloquer une PR sur du code vulnérable avec bandit (SAST)

Source : `_bmad-output/planning-artifacts/epics.md`, section « Story 8.1 » ; FR-24, FR-27, FR-33, UX-DR19. bandit 1.9.4 est déjà dans la table Stack, `tools.toml` et les gabarits : aucune dépendance ajoutée.

## Livré

- **Job `bandit`** dans `content/pipeline.yaml` (bloc isolé, en fin de fichier) : outil `bandit`, `required: true`, barrière `static-analysis`, sortie humaine `-r src -q` (verbatim), exécution machine `-r src -q -f json` lue par `bandit_json`, codes `success: [0]`, `failure: [1]` (tout autre code : erreur de l'outil). Les tests (`assert`) ne sont pas analysés.
- **Lecteur `bandit_json`** (`ci/findings.py`, valeur de `ci.Parse`) : un constat par résultat, règle `test_id`, fichier relatif à l'arbre, ligne. Texte illisible ou de forme inattendue : `ValueError` (le check passe en « constats indisponibles » comme les autres lecteurs).
- **Scénario `code-vulnerable.A.yaml`** (parcours sans IA, station 3, `pipeline: true`) : `main` exige le check `bandit` ; la branche `feature` porte un commit avec `eval` (règle B307, `src/inventory/alertes.py:6`). Étapes : pousser, ouvrir la PR, lire le blocage (check `bandit` en échec), corriger et pousser (check repassé au vert). Les deux dernières étapes sont jugées sur l'état réel du check, jamais sur une saisie.
- **Étape `pr_state`** : nouveau champ `checks` (`{job_id: success|failure}`), lu sur les SHA courants de la PR ; un check d'un ancien SHA ne valide rien.
- Empreinte `no_ai/code-vulnerable.A` ajoutée par `scripts/update_fingerprints.py`.
- Tests : `tests/test_code_vulnerable.py` (contrat du job, lecteur, scénario, vrai bandit qui refuse puis accepte, étape `pr_state`), `tests/test_pipeline.py` réaligné sur quatre jobs.

## Décisions

- Parcours sans IA seulement, comme demandé par les critères ; le parcours LLM aura son équivalent avec les barrières propres au code LLM.
- Preuve `evidence_seen` : déjà soumise par « Voir la sortie » (intention `check_output_seen`, 7.4) via la barrière du job ; rien d'ajouté.
- `-r src` plutôt que `.` : le défaut prévu est dans le code d'application et la sortie reste courte.

## Reports

- Scénario du parcours LLM (gabarit `llm` : même défaut sur son arbre) : Epic 8, story des barrières LLM.
- Aucun test E2E navigateur ajouté : la vue Distant + PR (7.4) affiche déjà détail et « Voir la sortie » pour tout job.

## À vérifier sur poste réel

1. Pousser `feature`, ouvrir la PR : le check bandit passe à « Échec · Obligatoire », la ligne de détail désigne `src/inventory/alertes.py:6` et B307, « Merger » est inactif.
2. Corriger (`ast.literal_eval`), committer, pousser : le check repasse au vert sans autre action.
