# Brainstorm amélioré — OIDA Code Verify

## Verdict rapide

Oui, les trois sources aident réellement :
- **Image 1 / repo `measurable-explore-exploit`** : utile immédiatement, car il apporte une **métrique opérationnelle** et du **code MIT** pour scorer des trajectoires d'agents.
- **Image 2 / LongCoT** : utile comme **stress test long-horizon** pour le verifier, mais secondaire pour un MVP code.
- **Image 3 / paper Explore/Exploit** : la plus précieuse des trois pour ton cas, car elle apporte une manière **policy-agnostic** de séparer “l’agent n’a pas trouvé” de “l’agent a trouvé mais n’a pas exploité”.

Le bon cadrage n’est pas “anti-slop” au sens cosmétique. Le bon cadrage est :

> **mesurer l’écart entre compétence apparente et intégrité opérationnelle du code généré par IA**.

---

## Ce qu’il faut garder du brainstorming initial

1. **Le lien OIDA ↔ explore/exploit est bon.**
   OIDA mesure déjà la dette cachée derrière un succès apparent. Explore/Exploit ajoute une mesure comportementale utile sur la trajectoire.

2. **LongCoT est pertinent, mais pas au bon étage.**
   Ce n’est pas un dataset d’entraînement central pour le code. C’est un **benchmark externe de robustesse long-horizon**.

3. **AgentV-RL reste la bonne couche de vérification.**
   Le verifier forward/backward + outils est une très bonne brique pour la phase “audit / verdict / repair”.

---

## Ce qu’il faut corriger

### 1. Ne pas dire que Explore/Exploit “s’adapte tel quel”

Le transfert **grid → codebase** est prometteur, mais pas automatique.
Dans le papier, les cibles et événements de progrès sont propres, observables, et bien définis.
Dans le code, tu dois d’abord définir **ta propre observation model**.

Sans ça, tu n’as pas encore une métrique ; tu as une intuition.

### 2. LongCoT ne doit pas entrer dans le cœur du MVP

LongCoT sert à répondre à la question :

> “Mon verifier reste-t-il lucide quand l’horizon devient long ?”

Pas à la question :

> “Mon système comprend-il une PR Python de 12 fichiers ?”

Donc LongCoT = **évaluation secondaire**, pas dépendance centrale.

### 3. Il manque une brique avant le scorer

Avant de scorer exploration/exploitation, il faut construire :

- une **trace d’agent sur repo**,
- un **graphe d’obligations**,
- une définition de **progrès**,
- une définition de **cible productive**.

C’est la vraie pièce manquante.

---

## Architecture révisée

```text
OIDA                      -> ontologie de la dette et score final
Trace schema              -> normalisation des actions repo/PR/CLI/test/LLM
Obligation graph          -> invariants, préconditions, dépendances, risques
Explore/Exploit metric    -> mesure des segments sans progrès et des erreurs
Static/dynamic verifiers  -> mypy, Semgrep, CodeQL, Hypothesis, mutmut
AgentV-style verifier     -> planification, forward/backward validation, verdict
Repair planner            -> prompts ciblés + propagation de correction
LongCoT                   -> benchmark externe de robustesse long-horizon
```

---

## Le mapping propre : grid → code

| Explore/Exploit paper | OIDA-for-code |
|---|---|
| cellule observée | fichier / symbole / test / endpoint déjà inspecté |
| cellule non observée | zone pertinente non explorée |
| task DAG node | obligation logicielle (invariant, précondition, migration, contrat d’API, règle métier) |
| pending task | obligation connue mais non satisfaite |
| progress event | invariant prouvé, bug localisé, contre-exemple trouvé, test manquant ajouté, dépendance propagée |
| no-progress segment | suite d’actions qui ne réduit ni inconnues critiques ni obligations pendantes |
| exploration error | l’agent fouille au mauvais endroit ou répète une inspection stérile |
| exploitation error | l’agent connaît déjà une obligation / un indice / un failing path mais ne l’utilise pas |

---

## Observation model minimal pour le MVP

Chaque action du système doit être normalisée sous une forme de ce type :

```json
{
  "t": 17,
  "kind": "tool_call",
  "tool": "pytest",
  "scope": ["payments/refund.py", "tests/test_refund.py"],
  "intent": "validate_refund_idempotency",
  "result": "failed",
  "new_facts": ["duplicate_refund_possible"],
  "closed_obligations": [],
  "opened_obligations": ["ensure_idempotency"],
  "evidence": ["AssertionError: refund called twice"]
}
```

À partir de là, tu peux définir :

- **U_t** = obligations ou zones critiques encore non explorées,
- **P_t** = obligations connues mais non closes,
- **T_t** = cibles productives à l’instant *t*.

Une action est productive si elle :
- réduit `U_t`,
- réduit `P_t`,
- augmente la preuve,
- ou trouve un contre-exemple exécutable.

---

## Version plus juste de ta promesse produit

À éviter :

> “preuves mathématiques des failles du code”

À dire :

> **preuves localisées quand une propriété est formalisable, contre-exemples exécutables quand elle ne l’est pas, et score de dette opérationnelle dans tous les cas.**

C’est beaucoup plus solide.

---

## Score révisé

Le scorer Explore/Exploit ne remplace pas OIDA. Il l’alimente.

Proposition simple :

```text
stale_t      = cycles_t + edge_reuse_t + node_reuse_t
traj_error_t = a * explore_error_t + b * exploit_error_t + c * stale_t
proof_gain_t = d * verified_property_t + e * counterexample_t + f * coverage_gain_t

lambda_bias_t = g * unsupported_assumptions_t + h * repeated_no_progress_t
mu_t          = i * unresolved_obligations_t + j * blast_radius_t

V_net_t = Q_obs_t - mu_t - lambda_bias_t - traj_error_t + proof_gain_t
```

Intuition :
- Explore/Exploit mesure la **mauvaise dynamique** de la trajectoire.
- OIDA garde la mesure de la **dette intégrée** et de la **valeur réelle**.

---

## Ce qu’il faut réellement “prouver” dans le MVP

### Niveau 1 — prouvable automatiquement
- erreurs de types,
- violations de contrats simples,
- dataflow / taint,
- propriétés locales décidables,
- contre-exemples générés par tests / property-based tests.

### Niveau 2 — démontrable par exécution ciblée
- non-régression partielle,
- incohérences entre prompt/ticket et comportement,
- cas limites que les tests initiaux ne couvrent pas.

### Niveau 3 — non prouvable en général
- “ce code est globalement correct”
- “ce code est bon en production”
- “ce refactor est sémantiquement équivalent dans tous les contextes”

Donc ton produit doit rendre des verdicts du type :
- **verified**,
- **counterexample found**,
- **insufficient evidence**,
- **corrupt success**.

---

## Ce que je construirais maintenant

### Phase 0 — instrumentation
- Capturer les traces d’un agent code : lecture de fichiers, grep, tests, edits, reruns, prompts.
- Définir le schéma d’événements.

### Phase 1 — graphe d’obligations
- À partir d’un diff + tests + codebase, extraire :
  - invariants,
  - préconditions,
  - dépendances,
  - blast radius.

### Phase 2 — scorer trajectoriel
- Brancher Explore/Exploit sur la trace.
- Mesurer les segments sans progrès.

### Phase 3 — verifier hybride
- Mypy
- Semgrep
- CodeQL
- Hypothesis
- mutmut
- exécution ciblée des tests

### Phase 4 — verdict OIDA
- Combiner succès apparent, preuve, trajectoire, dette, et obligations restantes.

### Phase 5 — repair
- Générer des prompts correctifs ciblés par obligation non close.
- Réouvrir automatiquement les nœuds dépendants.

---

## Priorité réelle des trois sources

### Priorité A — Explore/Exploit
À intégrer vite. C’est la source la plus actionnable.

### Priorité B — AgentV-RL
À utiliser comme architecture du verifier.

### Priorité C — LongCoT
À garder pour les benchmarks et papiers, pas pour le premier build.

---

## La phrase produit que je retiendrais

> **OIDA Verify n’essaie pas de deviner si un code IA “semble bon”. Il mesure ce que le code garantit réellement, la dette cachée qu’il introduit, et la trajectoire qui a produit cette dette.**

---

## Prochaine action concrète

Prendre le repo `measurable-explore-exploit`, isoler la logique de :
- `gainful move`,
- `no-progress segment`,
- `staleness score`,
- attribution exploration vs exploitation,

puis écrire un document de mapping formel :

```text
grid state      -> repo state
task node       -> code obligation
progress event  -> verification event
stale segment   -> unproductive agent loop
```

Si ce mapping tient proprement sur 2 ou 3 cas réels de PR foireuses, tu as ton noyau MVP.
