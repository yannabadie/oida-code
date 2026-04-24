Oui, tu peux commencer tout de suite par ADR-19 + les deux bugs.

Mais pour le Bloc D, je veux qu’on distingue clairement :

Phase 3.5 ship gate
obligatoire : paper sanity check sur jjj-madison/measurable-explore-exploit
obligatoire : mini sanity check code-domain sur quelques traces hermétiques F2P/P2P
non obligatoire : dataset complet de 30 traces labellisées
Phase 3.6 / pré-Phase 4 gate
obligatoire : 30 traces F2P/P2P ou équivalent
avec outcome non confondu par la longueur
idéalement automatisé, pas dépendant de labellisation manuelle par Yann

Donc : pas “paper sanity check only”, parce que ça validerait seulement que nos formules reproduisent le papier dans son domaine d’origine. Or notre vrai risque est le transfert vers le code. Mais je ne veux pas non plus bloquer Phase 3.5 sur 30 traces manuelles.

La décision :

Phase 3.5 ships when:
1. state-before-action bug fixed
2. t=0 edge case fixed
3. paper sanity check passes on the original metric/domain
4. U(t) is replaced by changed_files ∪ bounded impact_cone
5. Gain() is no longer only "file visited", but includes evidence/obligation gain
6. at least 6–10 hermetic code-domain traces pass expected classification
7. V_net/debt remain blocked/null if graph or fusion is incomplete

Les 30 traces F2P/P2P deviennent un gate de robustesse avant Phase 4 LLM, pas un prérequis pour corriger le scorer.

Pourquoi : le papier Explore/Exploit mesure exploration/exploitation à partir des seules actions observées, sans accès à la policy interne, mais son environnement est explicitement une grille 2D partiellement observable + task DAG symbolique. Le paper sanity check validera notre implémentation mathématique ; il ne validera pas notre mapping codebase/PR.

Pour la validation code, il faut s’aligner sur une logique type SWE-bench : le résultat doit être lié à des tests FAIL_TO_PASS et PASS_TO_PASS, pas à “commit présent” ni à “session longue”. Les F2P vérifient que le bug est corrigé ; les P2P vérifient que le comportement existant n’est pas cassé. C’est exactement le type de signal qui manque à notre Phase 3 actuelle.

Le rapport Phase 3 dit déjà que la vraie validation n’est pas encore acquise : progress_rate était mécaniquement confondu avec la longueur de session, closed_obligations est encore vide, et le bounded U(t) utilisé en validation était heuristique. Donc Phase 3.5 doit d’abord rendre le signal mesurable, avant d’ajouter du LLM.

Pour le Bloc A, commence dans cet ordre :

1. docs: add ADR-19 phase-3.5-measurement-before-llm
2. fix(score): compute case attribution from state_before_action
3. test(score): add t=0, first-action, and no-prior-progress fixtures
4. refactor(score): introduce explicit StateBefore / StateAfter structs if useful
5. test(score): prove Case 1/2/3/4 reachability on synthetic traces

Important : le fix ne doit pas simplement patcher events[:t+1] vers events[:t]. Je veux que le code rende impossible la confusion conceptuelle :

state_before = build_state(events[:t])
action       = events[t]
state_after  = apply_action(state_before, action)

case_label   = classify_case(state_before)
gain         = compute_gain(state_before, action, state_after)
error        = compute_error(case_label, gain, stale_before, stale_after)

Pour l’ImpactCone, ne pars pas sur “tout le repo”. Fais un cône borné, explicable, et auditable :

impact_cone =
  changed_files
  ∪ direct imports
  ∪ direct importers/callers when cheap
  ∪ related tests
  ∪ config/build files touched or referenced
  ∪ migrations/schema files when data path detected

Avec des limites explicites :

max_depth = 1 by default
max_files = configurable, default 50
every added file must carry a reason:
  changed | imported_by_changed | imports_changed | related_test | config | migration | caller

Pour Gain(), on doit sortir du simple “j’ai visité un fichier”. Un vrai gain doit être au moins l’un de ces cas :

discovery_gain:
  a new impact-cone node became observed

evidence_gain:
  a verifier result changed from unknown/failing to passing

obligation_gain:
  an obligation changed open -> closed

risk_gain:
  a high-risk edge or blast-radius dependency was discovered

counterexample_gain:
  a failing test, static finding, or repro was found

Et attention : lire un fichier déjà lu ou éditer sans fermer d’obligation ne doit pas être un gain.

Pour le Bloc D, je veux donc deux niveaux :

D1 — paper sanity check
- clone/read measurable-explore-exploit
- run or reproduce their ct/et/nt/S_t cases
- confirm our formulas match original expectations
- output: paper_sanity_report.md

D2 — code-domain mini sanity
- create 6–10 hermetic traces
- include:
  1 clean success
  1 exploration miss
  1 exploitation miss
  1 stale cycling
  1 corrupt plausible success
  1 counterexample found
- each trace has expected dominant label
- no LLM judge
- no commits>0 label

Les 30 traces F2P/P2P : on les fera, mais pas maintenant comme blocage de Phase 3.5. Prépare seulement le format :

datasets/code_traces_v1/
  trace.json
  issue.md
  before_sha
  after_sha
  f2p_tests
  p2p_tests
  expected_outcome
  notes.md

Je peux labelliser les cas ambigus plus tard, mais je ne veux pas être le chemin critique pour une semaine complète. Priorité : rendre le scorer correct et mesurable.

Stop après Bloc A complet avec :

ADR-19
diff résumé
tests ajoutés
avant/après sur les 5 fixtures existantes
preuve que Case 3 est atteignable ou explication si elle ne l’est pas encore

Ensuite seulement on valide B/C/D.