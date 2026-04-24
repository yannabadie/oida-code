# Réponse technique à `CONSULTATION_OIDA.md` — revue OIDA-code v0.4.1

Date : 2026-04-24  
Objet : guider Claude Code sur les blocages de Phase 3 / Phase 4 et répondre à Q1–Q6.

## Verdict global

Le projet est sur une bonne trajectoire, mais il y a un point critique : **le scorer Explore/Exploit a été adapté trop vite au domaine code**. La partie synthétique est saine, mais le signal réel est confondu par la longueur des sessions, par le plafond artificiel de `U(t)`, et par le fait que les obligations ne sont pas encore reliées aux actions de trace.

Le correctif n’est pas de jeter Explore/Exploit. Il faut le repositionner :

- **OIDA** mesure la dette opérationnelle et le corrupt success.
- **Explore/Exploit** mesure la qualité de trajectoire de l’agent.
- **AgentV-style verifier** produit des jugements forward/backward outillés.
- **Les outils déterministes** fournissent les preuves primaires.

Donc : le mariage tient, mais il faut empêcher Explore/Exploit de devenir une métrique de verdict produit avant validation réelle.

---

## Q1 — Adaptation fidelity : `U(t) = changed_files` est-il correct ?

### Réponse courte

Non, `changed_files` seul est trop étroit. La bonne adaptation est :

```text
AuditSurface = ChangedFiles ∪ ImpactCone(ChangedFiles)
```

avec deux sous-surfaces :

```text
MustInspectSurface   = fichiers/symboles indispensables pour conclure
AllowedContextSurface = dépendances utiles, non pénalisées si explorées
OutOfScopeSurface     = le reste, pénalisable si exploration prolongée sans gain
```

`changed_files` est seulement un **point de départ**. Un auditeur compétent doit souvent lire les imports, les callers, les tests, les migrations, les settings, les contrats API et parfois les schemas. Punir ces lectures comme du wandering fausse `exploration_error`.

### Q1.1 — Faut-il inclure les imports reachable ?

Oui, mais pas en transitive closure illimitée.

Implémente un **impact cone borné** :

```text
U0 = changed_files
U1 = direct imports + direct callers + direct tests + touched config/schema/migration files
U2 = optional, seulement si un outil ou une obligation le justifie
```

Règle simple pour Phase 4 :

```python
audit_surface = changed_files 
              ∪ direct_imports(changed_files)
              ∪ direct_callers(changed_symbols)
              ∪ tests_touching(changed_files)
              ∪ config_or_schema_neighbors(changed_files)
```

Puis :

```text
exploring U0/U1 = normal
exploring U2    = normal seulement si gain/evidence
exploring hors surface = suspect si no-progress
```

### Q1.2 — Case 3 est-il atteignable en code ?

Oui, mais seulement si `U(t)` représente une **frontière de découverte finie**, pas “tous les fichiers non lus”.

Dans un repo, lire tous les fichiers pertinents n’est pas l’objectif. L’objectif est de réduire suffisamment l’incertitude pour fermer ou invalider les obligations.

Nouvelle définition recommandée :

```text
U(t) = unresolved_discovery_obligations(t)
```

Exemples :

```text
need_read_changed_file: src/foo.py
need_find_tests: tests/test_foo.py
need_check_callers: src/api.py callers of foo()
need_check_migration: migrations/2026_x.py
need_check_security_rule: auth boundary for endpoint /x
```

Une fois ces obligations de découverte closes, `U(t)=∅` même si le repo contient encore 20 000 fichiers non lus. À ce moment-là, Case 3 devient naturellement atteignable : il n’y a plus rien d’utile à explorer, mais il reste des obligations connues à exploiter.

### Q1.3 — Le `Gain()` actuel est-il récupérable ?

Oui, mais il doit devenir **evidence-based**, pas seulement set-membership.

Le `Gain()` recommandé :

```text
Gain(action) =
    action closes a discovery obligation
 OR action closes a behavioral obligation
 OR action produces new executable evidence
 OR action reduces a critical unknown
 OR action increases verified coverage of an obligation
```

Exemples de gain valides :

```text
Read file in MustInspectSurface for the first time
Run relevant tests and obtain pass/fail signal
Add a failing test that reproduces the bug
Mutation killed
Property test generated and passed
Static finding localized to changed symbol
Dependency edge discovered
Counterexample found
Obligation moved open → closed / violated
```

Exemples de non-gain :

```text
Repeated grep over same term with no new file
Read unrelated docs after obligations known
Edit without new test or tool evidence
Run same failing test repeatedly without narrowing failure
Create abstraction with no closed obligation
```

### Bug important à corriger dans `score_trajectory`

Le scorer semble calculer le cas `CaseLabel` avec l’état **après** l’action courante, pas avec l’état **avant** l’action. Dans le papier, le cas doit être déterminé à l’état `s_t`, avant l’action `a_t`.

Aujourd’hui, la logique fait essentiellement :

```python
visited = _visited_paths_up_to(events, t)       # inclut event[t]
closed_now = _closed_obligations_up_to(events, t)
unobserved = changed_files - visited
pending = pending_set(..., closed_now, visited)
case = attribute_case(unobserved, pending, goal)
```

Il faut passer à :

```python
visited_before = _visited_paths_up_to(events, t - 1) if t > 0 else set()
closed_before = _closed_obligations_up_to(events, t - 1) if t > 0 else set()
unobserved_before = U - visited_before
pending_before = pending_set(obligations, closed_before, visited_before)
case = attribute_case(unobserved_before, pending_before, goal)

# puis seulement après :
gain = compute_gain(action=events[t], state_before=..., state_after=...)
progress = compute_progress(action=events[t], state_before=..., state_after=...)
```

Deuxième bug probable : pour `t=0`, `closed_before` ne doit pas inclure `event[0]`. Il doit être `set()`. Sinon une fermeture d’obligation au premier événement n’est pas comptée comme progrès.

### Décision Q1

- `changed_files` seul : **non**.
- `changed_files ∪ impact cone borné` : **oui**.
- `Gain()` par simple entrée dans un fichier non lu : **insuffisant**.
- `Gain()` par fermeture d’obligation / production de preuve / réduction d’incertitude : **oui**.
- Le résultat empirique actuel doit être documenté comme **validation non concluante**, pas comme négatif définitif.

---

## Q2 — Obligation ↔ PreconditionSpec : isomorphes ou non ?

### Réponse courte

Non, ils ne sont pas isomorphes.

Une **obligation** est un engagement logiciel de haut niveau : “le changement doit satisfaire X”.

Une **precondition** OIDA est une prémisse vérifiable qui soutient l’ancrage de cet événement : “pour croire que X est satisfait, il faut que A/B/C soient vrais”.

Donc une obligation peut et doit souvent générer plusieurs `PreconditionSpec`.

### Problème actuel

La fonction actuelle :

```python
def _preconditions_for(obligation):
    return [PreconditionSpec(...)]
```

aplatit tout. Cela lisse artificiellement `grounding` : une obligation API partiellement vérifiée devient binaire au lieu de montrer que l’auth est vérifiée mais pas le format de sortie, ou que le happy path est testé mais pas les erreurs.

### Mapping recommandé par type

#### `precondition`

```text
- guard_exists
- failure_path_exercised
- positive_path_exercised
```

#### `api_contract`

```text
- route_or_method_exists
- input_schema_validated
- auth_or_permission_checked
- output_shape_verified
- error_modes_verified
- backward_compatibility_checked
- contract_tests_present
```

#### `migration`

```text
- forward_migration_defined
- rollback_or_reversibility_defined
- idempotency_or_safety_checked
- data_loss_risk_checked
- migration_test_present
- backup_or_recovery_path_documented
```

#### `invariant`

```text
- invariant_formalized
- property_test_present
- counterexample_search_run
```

#### `security_rule`

```text
- source_sink_identified
- taint_or_static_rule_run
- negative_test_present
- auth_boundary_verified
```

#### `observability`

```text
- metric_or_log_added
- alert_or_trace_surface_present
- failure_mode_observable
```

### Pondération recommandée

Ne laisse pas `weight=1` partout. Utilise une formule stable :

```text
weight = base_kind_weight
       × intent_multiplier
       × blast_multiplier
       × data_or_security_multiplier
       × external_surface_multiplier
```

Valeurs simples pour commencer :

```text
base_kind_weight:
  precondition    = 1.0
  api_contract    = 1.2
  invariant       = 1.4
  migration       = 1.6
  observability   = 1.0
  security_rule   = 2.0

intent_multiplier:
  source == intent = 1.5
  otherwise        = 1.0

blast_multiplier:
  1 + blast_radius

data_or_security_multiplier:
  data/security touched = 1.5
  otherwise             = 1.0

external_surface_multiplier:
  public API / endpoint = 1.3
  internal only         = 1.0
```

### Décision Q2

Il faut réécrire `_preconditions_for`. Une obligation doit devenir un **paquet de preuves pondérées**, pas un booléen déguisé.

---

## Q2.5 — V_net avec graphe vide : acceptable ?

### Réponse courte

Non pour un rapport produit. Oui seulement pour un debug local explicitement marqué.

Avec :

```text
constitutive_parents = []
supportive_parents = []
```

OIDA perd une partie essentielle : la propagation de dette et la cascade de dépendances. Le modèle devient une somme d’événements isolés. Ce n’est pas faux mathématiquement, mais c’est incomplet opérationnellement.

### Règle recommandée

Ajoute :

```json
"graph_completeness": {
  "has_dependency_graph": false,
  "edge_count": 0,
  "coverage": 0.0,
  "fusion_allowed": false
}
```

Et bloque :

```text
if edge_count == 0 and event_count > 1:
    total_v_net = null
    debt_final = null
    corrupt_success_ratio = null
    emit local_event_scores_only = true
```

Autorise seulement :

```text
local_q_obs
local_grounding
local_risk_flags
```

### Graphe minimal à construire avant fusion

Pour Python, Phase 4 doit au minimum extraire :

```text
import edges:        module A imports module B
call edges:          function A calls function B
test edges:          test file exercises production file
route edges:         route handler → service → repo/db
migration edges:     model/schema → migration → storage
config edges:        config/env → runtime path
```

Typage des edges :

```text
constitutive = le parent est nécessaire pour que l’enfant soit correct
supportive   = le parent améliore la confiance mais n’est pas strictement nécessaire
```

### Décision Q2.5

Un graphe vide doit empêcher l’émission de `V_net` global et de `debt_final`. Il peut rester un mode `debug_local`.

---

## Q3 — V_net avant fusion : `null` ou estimation partielle ?

### Réponse courte

`null` est le bon protocole pour le rapport principal.

Quand `capability`, `observability` et `benefit` valent 0.5 par défaut, le score n’est pas “neutre”. C’est un mélange d’inconnues. Sortir `V_net = 0.0` ou une dette faible induirait le lecteur en erreur.

### Recommandation de schéma

Ajoute un bloc explicite :

```json
"fusion_status": {
  "status": "not_computed",
  "reason": "missing_identifiability",
  "missing_fields": ["capability", "observability", "benefit", "dependency_graph"],
  "safe_to_compare": false
}
```

Puis garde :

```json
"summary": {
  "mean_q_obs": null,
  "mean_grounding": null,
  "total_v_net": null,
  "debt_final": null,
  "corrupt_success_ratio": null
}
```

Pour les devs, tu peux ajouter un bloc optionnel séparé :

```json
"debug_estimates": {
  "enabled": false,
  "warning": "computed with default priors; not an OIDA measurement"
}
```

### Option avancée : intervalles au lieu d’un scalaire

Si tu veux pousser plus loin sans mentir :

```text
V_net_bounds = [min over unknown fields, max over unknown fields]
```

Mais ne l’appelle pas `V_net`. Appelle-le :

```text
v_net_identifiability_bounds
```

C’est utile pour dire :

```text
même en hypothèse optimiste, cette PR reste risquée
```

ou :

```text
le score est indécidable avec les preuves actuelles
```

### Différence “non calculé” vs “vraiment zéro”

Utilise un état, pas seulement une valeur :

```json
"debt_final": {
  "value": null,
  "status": "not_computed",
  "blocked_by": ["missing_dependency_graph", "missing_observability"]
}
```

Quand la dette est vraiment zéro :

```json
"debt_final": {
  "value": 0.0,
  "status": "computed",
  "blocked_by": []
}
```

### Décision Q3

`null` est correct. Une convention de confiance peut être ajoutée, mais seulement sous forme d’identifiability/bounds, pas comme score OIDA officiel.

---

## Q4 — Seuil `corrupt_success`

### Réponse courte

Ne déclenche pas `corrupt_success` sur un seul événement `B`. Utilise deux niveaux :

```text
suspected_corrupt_success
confirmed_corrupt_success
```

### Niveau 1 — suspicion

Un événement peut être suspect si :

```text
q_obs >= 0.70
AND grounding < 0.60
AND lambda_bias >= bias_threshold
```

C’est l’équivalent local de l’entrée B-state.

### Niveau 2 — confirmation produit

Pour émettre le verdict global `corrupt_success`, exige au moins une condition forte :

```text
A. B-state sustained:
   même pattern en B sur ≥ 2 événements consécutifs

OR

B. B-load élevé:
   weighted_b_load >= 0.20

OR

C. événement critique:
   B-state sur obligation security/data/migration avec blast_radius >= 0.70

OR

D. succès apparent + preuve contraire:
   operator_accept/tests_pass élevés mais contre-exemple, mutation survivor critique,
   static finding critique ou invariant violé
```

Formule simple :

```text
weighted_b_load = Σ(weight_i × blast_i × is_B_i) / Σ(weight_i × blast_i)
```

Et décision :

```text
if any(critical_B_event): corrupt_success
elif weighted_b_load >= 0.20 and total_v_net < 0: corrupt_success
elif sustained_B_pattern: corrupt_success
else if any(B_event): suspected_corrupt_success
```

### Pourquoi ne pas utiliser `any(B)` directement ?

Parce qu’un seul B-event sur un petit scope peut être un vrai signal local mais pas un verdict global. `any(B)` doit remonter dans le rapport comme alerte, pas forcément comme label final.

### Décision Q4

- `any(B)` → alerte locale / suspicion.
- `sustained_B`, `weighted_b_load`, ou `critical_B` → verdict `corrupt_success`.

---

## Q5 — Validation empirique

### Réponse courte

Le signal “commit pendant la session” doit être abandonné comme outcome principal. Il est trop corrélé à la longueur et ne mesure pas la correction.

La bonne stratégie est un benchmark interne de type :

```text
prompt réel
+ base commit
+ patch produit
+ tests F2P/P2P pertinents
+ trace agent
+ résultat exécutable
```

### Signal recommandé

Priorité des signaux :

```text
1. F2P pass + P2P pass sur tests pertinents
2. Contre-exemple exécutable trouvé ou non
3. Mutation score sur changed surface
4. Static findings critiques corrigées ou non
5. Label humain sur échantillon stratifié
6. Revert/rollback post-merge, seulement comme signal retardé
```

### Protocole minimal Phase 4

Créer `datasets/traces_v1/` avec au moins 30 sessions, idéalement 100 :

```text
- 1 langage au début : Python
- 5 à 10 repos max
- chaque session a un request.json
- chaque session a une trace JSONL
- chaque session a base_sha / end_sha
- chaque session a changed_files réels via git diff
- chaque session a tests pertinents
- chaque session a outcome exécutable
```

Pour chaque tâche :

```text
pre-change tests:
  F2P doivent échouer avant patch
  P2P doivent passer avant patch

post-change tests:
  F2P doivent passer après patch
  P2P doivent rester verts
```

Exclure :

```text
flaky tests
non-testable prompts
documentation-only changes
prompts qui contiennent déjà la solution
sessions multi-humain non isolables
environnements non reproductibles
```

### Validation statistique

Ne fais plus une corrélation brute avec `total_steps` non contrôlé.

Utilise :

```text
- stratification par repo
- stratification par longueur de session
- régression logistique outcome ~ metrics + log(total_steps) + repo + task_type
- Spearman sur résidus après contrôle longueur
- bootstrap CI 95 %
- ablation : with/without impact cone, with/without obligation close detector
```

Critère de passage :

```text
metric must predict outcome after controlling for session length
and must improve over baseline length-only model
```

Exemple :

```text
baseline_auc = AUC(outcome ~ log(total_steps))
oida_auc     = AUC(outcome ~ log(total_steps) + trajectory_metrics + grounding)
ship if oida_auc - baseline_auc >= 0.05 on bootstrap median
```

### Paper sanity check obligatoire

Avant de continuer à discuter du transfert code, exécute :

```text
our ct/et/nt implementation on the authors' released 2D grid traces
```

Si les résultats divergent, il faut corriger l’implémentation. Si les résultats matchent, le problème est bien le mapping code, pas les formules.

### Décision Q5

La validation Phase 4 doit être exécutable, non tautologique, contrôlée par longueur, et fondée sur des tests pertinents. Le signal `commits > 0` doit être relégué à une métadonnée.

---

## Q6 — Public release timing

### Réponse courte

Ne publie pas encore une version PyPI “normale”. Publie seulement une preview de recherche si nécessaire.

### Bloquants avant release publique crédible

Minimum :

```text
- README aligné avec v0.4.1, pas “Phase 1 bootstrap”
- CI GitHub verte
- scorer state-before-action corrigé
- score-trace sans AuditRequest => not_computable, pas 0 silencieux
- dependency graph non vide ou fusion bloquée explicitement
- fusion fields null avec fusion_status
- paper-dataset sanity check exécuté
- 10-repo smoke ou dataset traces_v1 initial
```

### Version recommandée

```text
v0.4.x = internal/research preview
v0.5.0 = first public research preview
v1.0.0 = never before validated OIDA fusion + stable schema
```

Message PyPI possible seulement en preview :

```text
pip install oida-code --pre
```

avec bannière :

```text
Research preview. Deterministic audit and trajectory diagnostics only.
OIDA fusion and corrupt_success verdict are experimental / not yet validated.
```

### Décision Q6

Déférer une release PyPI stable. Une preview MIT est acceptable si les placeholders sont très visibles et si le README ne sur-promet pas.

---

## Guidance directe pour Claude Code — ordre de travail Phase 4

### Bloc A — Corriger le scorer avant tout LLM

1. Corriger la logique `state_before_action` dans `score_trajectory`.
2. Corriger `closed_before` pour `t=0`.
3. Si `request is None` ou `changed_files=[]`, retourner `trajectory_status="not_computable"` ou exiger `--request` pour `score-trace`.
4. Remplacer `U(t)=changed_files unread` par `DiscoveryObligation[]`.
5. Introduire `ImpactCone` borné.
6. Changer `Gain()` vers evidence/obligation gain.
7. Changer les nodes de stale-score : ne pas utiliser `(tool_kind, file)` comme nœud principal. Utiliser plutôt `resource_id = file/symbol/obligation`, avec `tool_kind` comme attribut d’action. Sinon `Read foo.py` et `Edit foo.py` ne sont pas reconnus comme revisite du même territoire.

### Bloc B — Corriger le mapper

1. Réécrire `_preconditions_for` avec multiplicité par `Obligation.kind`.
2. Ajouter des poids par type d’obligation.
3. Ajouter `field_provenance` ou `identifiability`.
4. Ajouter `fusion_status`.
5. Bloquer `V_net` global si `graph_completeness < threshold`.

### Bloc C — Graphe minimal

1. AST import graph.
2. AST call graph approximatif.
3. Test-to-source mapping.
4. Route/service/db mapping heuristique.
5. Migration/schema edges.

### Bloc D — Validation

1. Exécuter le sanity check sur le repo Explore/Exploit original.
2. Construire 30 traces Python avec tests F2P/P2P.
3. Recalculer métriques en contrôlant `log(total_steps)`.
4. Publier un `VALIDATION_PHASE4.md` avec résultats positifs ou négatifs.

### Bloc E — LLM verifier seulement après

Le verifier LLM Phase 4 doit venir après A+B+C partiels. Sinon il va seulement expliquer des métriques non validées.

Quand il arrive, son rôle doit être :

```text
forward verifier  = suffisance : le patch prouve-t-il l’intent ?
backward verifier = nécessité : quelles prémisses sont nécessaires mais absentes ?
aggregator        = fusionne preuves outillées + obligations + trajectoire
```

Il ne doit pas être la source primaire de vérité.

---

## Réponse synthétique Q1–Q6

| Question | Réponse |
|---|---|
| Q1 | Mapping récupérable, mais `changed_files` seul est faux. Utiliser impact cone + discovery obligations + evidence-based Gain. Corriger aussi state-before-action. |
| Q2 | Non, obligation et precondition ne sont pas isomorphes. Une obligation doit générer plusieurs preconditions pondérées. |
| Q2.5 | Graphe vide = pas de `V_net` global ni `debt_final`. Autoriser seulement scores locaux/debug. |
| Q3 | `null` est correct. Ajouter `fusion_status`, `blocked_by`, éventuellement des bounds, mais pas de score officiel avec defaults 0.5. |
| Q4 | `any(B)` = suspicion. Verdict `corrupt_success` seulement si B soutenu, B-load élevé, ou B critique high-blast. |
| Q5 | Abandonner `commits > 0`. Utiliser F2P/P2P, test relevance, non-flakiness, contrôle par longueur, et sanity check sur dataset papier. |
| Q6 | Pas de PyPI stable. Preview seulement après README/CI/corrections/scoring/fusion_status. |

---

## Message final à Claude Code

Tu as bien avancé, mais la prochaine étape n’est pas “plus de LLM”. La prochaine étape est de rendre le signal mesurable : état avant action, surface d’audit correcte, obligations de découverte, graphe minimal, et validation non tautologique. Une fois ça en place, AgentV-style forward/backward devient utile. Avant ça, il risque seulement de rationaliser des métriques confondues.
