Oui, tu peux lancer D1 paper sanity check en parallèle. C’est indépendant, read-only, et ça peut révéler des divergences de formule avant qu’on empile B/C dessus.

Je valide le Block A bug-fix : state-before-action, bug t=0, Case 3 atteignable, et tests de discipline structurelle. Le commit fa4e1a0 répond bien à la demande immédiate.

Mais je ne valide pas encore Block A complet au sens Phase 3.5, parce qu’il manque encore trois durcissements structurels avant Block B :

A2.1 — séparer gain et progress
A2.2 — traiter explicitement l’état terminal P=∅, U=∅
A2.3 — passer les stale nodes vers resource_id plutôt que (kind, path)

Le point le plus important : dans le papier, Gain() et progress event sont distincts. Un agent peut faire un mouvement qui va dans la bonne direction sans encore produire de progrès réel ; c’est précisément pour ça que le stale score existe. Dans notre code actuel, compute_gain() et is_progress_step() sont encore identiques, donc la branche “gain sans progress” est structurellement inatteignable. Il faut corriger ça avant d’attaquer le mapper B.

Je veux donc un petit patch A2 avant Block B :

1. test(score): add gain_without_progress fixture
2. refactor(score): split candidate_gain from progress_event
3. test(score): prove gain=True, progress=False is reachable
4. refactor(score): add terminal/no_target handling or trace trimming
5. test(score): post-terminal commit/report does not inflate exploitation_error
6. refactor(score): stale node = resource_id, not (kind, path)
7. test(score): Read/Edit/Grep on same file are same resource territory

Sur le terminal state : aujourd’hui P=∅ ∧ U=∅ est classé comme exploit_goal. C’est dangereux. Dans une trace de code, après que les fichiers ont été lus et les obligations fermées, il peut rester des actions normales : commit, résumé, rapport, cleanup. Ces actions ne doivent pas mécaniquement gonfler exploitation_error. Deux options acceptables :

Option A — ajouter CaseLabel "terminal" / "no_target"
- exclu des normalizers exploration/exploitation
- post-terminal commit/report = neutral overhead
- post-terminal code edit = suspicious tail / regression-risk

Option B — trim de la trace après terminal_success
- plus proche du papier, où l’épisode se termine quand le goal est atteint
- mais moins réaliste pour Claude Code transcripts

Je préfère Option A, parce que nos traces incluent naturellement des actions post-solution. Le papier raisonne sur un épisode dont la tâche s’arrête quand le goal est atteint ; nos sessions de dev ne s’arrêtent pas toujours exactement au même endroit.

Pour Gain() côté code, ne le limite plus à “fichier découvert” ou “obligation fermée”. Propose une séparation comme ceci :

progress_event =
  newly_observed_impact_node
  OR obligation_closed
  OR verifier_state_changed_to_passing
  OR counterexample_found

candidate_gain =
  progress_event
  OR touched_pending_obligation_resource
  OR ran_relevant_test_for_open_obligation
  OR inspected_direct_dependency_of_pending_obligation
  OR discovered_high_risk_edge

Donc :

progress_event => reset no-progress segment
candidate_gain without progress => may be okay unless stale_score increases
no candidate_gain => immediate error

C’est plus fidèle au papier : le papier ne pénalise pas tout mouvement qui ne termine pas une tâche ; il pénalise les mouvements qui ne vont pas vers une cible, puis utilise le stale score pour détecter l’oscillation ou la redondance quand le gain apparent ne produit toujours pas de progrès.

Pour resource_id, le node du stale graph ne doit plus être :

(kind, scope[0])

mais plutôt :

resource_id = file path | symbol id | test id | endpoint id | migration id

Sinon Read src/a.py, Edit src/a.py, Grep src/a.py deviennent artificiellement trois territoires différents, alors qu’ils représentent la même zone de travail. Il faut garder kind comme attribut d’action, mais pas comme identité primaire du nœud de graphe.

Pour D1, vas-y maintenant, mais dans une branche séparée ou un commit séparé :

D1 deliverables:
- scripts/paper_sanity_check.py
- reports/paper_sanity_report.md
- exact version / commit of jjj-madison repo used
- whether their tests pass locally
- whether our ct/et/nt/St/err match their metrics on at least one exported trajectory
- explicit list of mismatches, if any

Le repo des auteurs expose bien un framework déterministe avec environnement, métriques par trajectoire, agents de baseline, traces exportables et une suite d’évaluation 3 x 3; c’est exactement ce qu’il faut pour vérifier d’abord la fidélité mathématique hors domaine code.

Important : D1 ne valide pas notre mapping vers le code. Il valide seulement que notre implémentation ne trahit pas le papier dans son domaine d’origine. Le risque spécifique à OIDA-code reste le transfert grid/task DAG → repo/obligation graph.

Donc ordre de travail :

1. Lance D1 en parallèle.
2. Fais A2 micro-hardening sur scorer.
3. Stop court avec:
   - before/after fixture table
   - preuve gain=True/progress=False atteignable
   - preuve terminal tail neutralisée
   - preuve resource_id stale nodes
   - D1 paper sanity status
4. Ensuite seulement Block B mapper multiplicity.

Ne commence pas Block C graph avant d’avoir stabilisé impact_cone et resource_id, parce que le graphe dépend de ces deux choix.

Mon avis : le travail est bon, mais il faut être strict sur le vocabulaire. Block A-bugfix est validé. Block A-architecture ne l’est pas encore.

Le rapport Phase 3 disait déjà que la validation réelle n’était pas encore acquise : les closed_obligations restaient vides, U(t) était encore heuristique, et le signal empirique était confondu avec la longueur des sessions. Donc le bon move reste exactement celui-ci : on durcit le signal avant d’ajouter plus de modèle ou plus de mapper.