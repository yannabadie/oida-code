J'ai les métadonnées de la vidéo. Je récupère maintenant le détail des deux papiers cités.# Cognitive AI: The new Solution (w/o Mythos) — Discover AI, 23 avril 2026

Thèse de la vidéo : passage de la GenAI probabiliste (non-fiable par design) à des **systèmes de raisonnement agentique vérifiable** avec **trois passes de vérification**. La chaîne ne publie pas de transcript exploitable — je m'appuie sur la description officielle et les deux papiers cités.

## Core principles

1. **La vérification remplace la confiance.** Un LLM seul produit du plausible, pas du prouvé → il faut un *verifier* externe, non un meilleur générateur.
2. **Raisonnement bidirectionnel.** Un agent *forward* (prémisses → conclusion, vérifie la *suffisance*) + un agent *backward* (conclusion → prémisses, vérifie la *nécessité*). C'est le cœur d'AgentV-RL.
3. **Tool-augmented verification.** Le verifier n'est pas un juge verbal : il exécute du code (Python), ce qui le *ground* contre les hallucinations sur tâches calculatoires.
4. **Distillation multi-agent → mono-modèle.** Pipeline AgentV-RL : génération synthétique de trajectoires → Rejection SFT → GRPO. Le 4B qui en sort bat un ORM 70B de **+25,2 pts**.
5. **Insight avant preuve** (papier 1). Le goulot du *informal theorem proving* n'est pas la rédaction mais la **reconnaissance de la technique-clé** → SFT progressif multi-étapes, du sketch à la preuve.
6. **Test-Time Scaling des deux côtés.** Parallèle (Best-of-N) et séquentiel (critique-révision) bénéficient tous deux du verifier agentique.

## Papers

| # | Titre | arXiv | Équipes |
|---|---|---|---|
| 1 | Learning to Reason with Insight for Informal Theorem Proving | [2604.16278](https://arxiv.org/abs/2604.16278) | CityU Hong Kong, Tsinghua, Ke Holdings, SZ Univ. Adv. Tech., CUHK-Shenzhen |
| 2 | AgentV-RL: Scaling Reward Modeling with Agentic Verifier | [2604.16004](https://arxiv.org/abs/2604.16004) | Fudan, HUST, HKU, ByteDance Seed |

Les deux soumis le **17 avril 2026**.

## Dépôts code

- **AgentV-RL** → https://github.com/JiazhengZhang/AgentV-RL (explicite dans l'abstract)
- **DeepInsightTheorem / papier 1** → aucun lien GitHub trouvé à ce jour (papier < 1 semaine, release probable à suivre via la page arXiv)

## Datasets / benchmarks

**Papier 1 — DeepInsightTheorem** : dataset hiérarchique *introduit par le papier* (core techniques + proof sketches + proof final). Pas de lien HF/GitHub public identifié pour l'instant.

**Papier 2 — AgentV-RL** :
- *Entraînement* : curation sur **Polaris**, **DeepScaleR-40K**, **AReaL-boba-106k** (15k SFT + 50k GRPO, base Qwen3-4B)
- *Éval math* : GSM8K, MATH500, Gaokao2023, AIME24
- *Éval généralisation* : LiveCodeBench, HotpotQA

## Chiffre qui justifie le titre "w/o Mythos"

Sur MATH500 @ BoN-128, Agentic-Verifier-Qwen3-**4B** atteint **79,0 %** vs **55,4 %** pour INF-ORM-Llama3.1-**70B**. C'est l'argument empirique contre la mystique du scaling : un verifier agentique 17× plus petit écrase un ORM géant.

---

J'ai un nouveau projet tres simple: unslop.ai (vérifie que ca n'existe pas deja). L'idée est de fournir un saas ou un framwork capable transformer du slop en code structuré , logique, cohérent et fonctionnel. Si ce n'est pas possible. D'expliquer les failles, preuves mathémathiques a l'appui. Et pourquoi pas des prompt pour remetter le LLM coder sur la bonne voie. Pour cela je souhaite me base sur un modele du type Qwen3.6.  Voici ma configuration pour le MVP. Prends ton temps fais les recherches nécessaires. Nous sommes le  23 avril 2026  CPU
  - Intel Core i7-13850HX (13e gen, Raptor Lake HX)
  - 20 cœurs / 28 threads, base 2.1 GHz
  - Cache L2 28 MB · L3 30 MB
  - Charge actuelle : 24 %
  RAM
  - 32 GB DDR5 (1× 32 GB, SODIMM slot DIMM A)
  - Micron MTC20C2085S1TC56BD1, 5600 MHz (configuré 5200 MHz)
  - 3 slots libres → upgrade jusqu'à 128 GB possible
  - Utilisation : 25.3 / 31.7 GB (80 % — élevée, cohérent avec WSL + Docker actifs)
  GPU
  - NVIDIA RTX 3500 Ada Laptop (driver 32.0.15.8216, déc. 2025) — discret
  - Intel UHD (Raptor Lake-S Mobile) — intégré, pilote 1920×1080 @ 60 Hz
  - Affichage sur l'iGPU → vérifier bascule NVIDIA pour charges ML
  Stockage
  - 1 SSD NVMe Samsung PM9A1 512 GB (OEM PCIe 4.0), santé OK
  - C: 475 GB — 80 GB libres (16.9 %) ⚠️ critique
  - Un seul disque physique → 3 slots M.2 libres sur Precision 7780

  ----


Je vais faire les vérifications dans l'ordre : existence du nom/concept, réalité de Qwen3.6, VRAM exacte de ta RTX 3500 Ada, et état de l'art des outils qui font déjà ça. Ensuite je te donne une analyse franche.Recherches faites. Je te réponds en mode direct, sans emballage.

## 1. Nom : grillé

`unslop` est **saturé**. Non-exhaustif, tous actifs :

- **github.com/mshumer/unslop** — exactement ton concept (analyse de patterns slop, génération de skills anti-slop pour Claude Code), traction communautaire déjà bien installée
- **unslop.xyz** — "coordination layer humans/AI", projet *Noodles* de visualisation de code IA, interviewé par Heavybit il y a 2 semaines
- **unslop.design** — product planning IA
- **unslopsearch.com**, **theunslop.app**, **Unslop Code Cleaner** sur mcpmarket, skill **anti-slop** sur Smithery

Le `.ai` est peut-être encore libre techniquement, mais le brand est cramé : tu arriverais en SEO 6e sur ta propre catégorie. Et mshumer occupe déjà le créneau "analyse empirique des patterns slop" avec la bonne audience (Claude Code users). **Change de nom.** Quelques directions : quelque chose qui pointe vers la *preuve* ou la *vérification* (tu veux aller plus loin que le nettoyage cosmétique), pas vers l'absence de slop.

## 2. Qwen3.6 — oui, ça existe, mais attention à la taille

Tu avais raison, Qwen3.6 est sorti en avril 2026 :

| Variante | Params | VRAM Q4_K_M | Licence | Sortie |
|---|---|---|---|---|
| **Qwen3.6-35B-A3B** | 35B MoE, 3B actifs | ~20 GB | Apache 2.0 | 16 avril |
| **Qwen3.6-27B dense** | 27B | ~16 GB | Apache 2.0 | 22 avril |
| Qwen3.6-Plus | ? | API-only | fermé | 2 avril |
| Qwen3.6-Max-Preview | ? | API-only | fermé | 20 avril |
| **Qwen3-Coder-Next** | 80B MoE, 3B actifs | ~45 GB Q4 | Apache 2.0 | 3 fév |

## 3. Ton hardware vs. ta cible — chiffres durs

**RTX 3500 Ada Laptop = 12 GB VRAM ECC GDDR6, 432 GB/s, FP8 support** (4th-gen Tensor Cores).

Ce que ça signifie concrètement :
- **Qwen3.6-27B dense Q4_K_M (~16 GB)** → ne rentre PAS en full-GPU. Offload llama.cpp possible, mais débit chute à ~8-15 tok/s.
- **Qwen3.6-35B-A3B Q4_K_M (~20 GB)** → idem offload obligatoire. *Mais* comme seuls 3B sont actifs par token, llama.cpp avec `-ngl` partiel peut te sortir 20-30 tok/s en pratique. C'est **le meilleur candidat pour ton laptop**.
- **Modèles qui rentrent vraiment en VRAM 12 GB sans souffrir** : Qwen3.5-9B Q5, Qwen3-Coder 7B/14B Q4. Ordres de grandeur plus faibles pour un projet "corrige le slop".

**Ton vrai bottleneck, ce n'est pas le GPU : c'est le SSD.** 80 GB libres sur C:, un seul disque physique. Qwen3.6-35B-A3B GGUF Q4 fait ~20 GB, la version FP8 fait ~35 GB. Ajoute WSL + Docker + Dokploy + AUTOMIT qui tournent déjà (tu es à 80 % RAM). **Tu dois régler le stockage avant le reste** — un M.2 2 TB dans un des 3 slots libres du Precision 7780, c'est 120-180 € et ça débloque tout. Sans ça, ton MVP est mort-né au premier `git clone` sérieux.

## 4. Le concept — la partie qui va piquer

Tu dis "transformer du slop en code structuré, ou sinon donner des preuves mathématiques des failles."

Les deux moitiés ont un problème distinct :

**(a) "Transformer slop → code propre" est déjà le métier de :** Cursor Composer, aider, Claude Code, Continue, Qodo (ex-Codium), Sourcegraph Amp, CodeRabbit, Windsurf Cascade, et maintenant mshumer/unslop côté prompting. Tu n'as pas d'angle de différenciation si c'est juste "un LLM + critique → réécriture". C'est le cœur d'AgentV-RL du papier qu'on vient de décortiquer.

**(b) "Preuves mathématiques des failles" se heurte au théorème de Rice** — il est formellement indécidable de prouver une propriété sémantique non-triviale d'un programme arbitraire. Ce que tu *peux* prouver automatiquement :
- Erreurs de types (mypy, TypeScript, pyright — existe)
- Flux de données / taint (Semgrep, CodeQL — existe)
- Contrats formels (Dafny, Lean, F*, Creusot pour Rust — existe, demande une spec)
- Equivalence sémantique bornée (symbolic execution, KLEE — existe)

"Prouver qu'un code LLM est mauvais avec des maths" dans le cas général est **publicitairement attirant, techniquement faux**. Tu ne veux pas te mettre à défendre ça dans une démo technique. Tu te souviens du ton d'audit honnête qu'on a appliqué à YGN-SAGE et Meta-YGN — là tu risques exactement le piège inverse.

## 5. Là où il y a du jus — et c'est toi qui a l'angle

Ton IP personnelle est **OIDA** (Operational Integrity and Debt Analysis, V4.2 → NeurIPS SafeGenAI). OIDA c'est littéralement un cadre formel pour mesurer la dette opérationnelle et l'intégrité. **Le slop d'un code IA, c'est exactement de la dette opérationnelle cachée sous une compétence apparente.** Le papier que tu as produit sur OIDA parle d'effective competence négative et d'entropie de domaines — ce sont précisément les métriques qui distinguent le "ça compile et ça passe les tests heureux" du "ça tient en production."

Le vrai positionnement disruptif n'est pas "unslop" (défensif, esthétique), c'est **"OIDA-for-code : mesure formelle de la dette cachée dans le code IA"**. Concrètement :

1. **Entrée** : un diff ou un repo généré par un LLM
2. **Extraction de spec implicite** : le code tente de faire *quoi* ? (LLM + analyse statique)
3. **Score OIDA adapté au code** : competence apparente, competence effective (après mutation testing + exécution de cas adversariaux), entropie de couverture, dette — avec les vraies formules de ton papier, pas du storytelling
4. **Sortie** : un rapport "le code prétend X, couvre réellement Y, la dette masquée est Z, voici les 3 prompts de correction ciblés."

Tu as l'asset intellectuel (OIDA publié), l'asset technique (AUTOMIT + n8n + Qwen3.6-35B-A3B en local), et l'asset narratif (audit honnête, pas de mythos). Ça c'est défendable. "unslop.ai" tout seul, non.

## 6. Faisabilité MVP — tableau honnête

| Composant | Possible sur ton hardware ? | Note |
|---|---|---|
| Inférence Qwen3.6-35B-A3B Q4 + llama.cpp | Oui, après upgrade SSD | 15-25 tok/s attendus |
| Pipeline multi-agent (forward/backward type AgentV-RL) | Oui | latence 2-5 min/audit acceptable |
| Static analysis (ruff, mypy, semgrep, CodeQL local) | Oui | CPU/RAM, pas GPU |
| Mutation testing (mutmut, cosmic-ray) | Oui | lent mais déterministe |
| Fine-tuning un verifier 4B style AgentV-RL | **Non sur ce laptop** | 12 GB VRAM suffisant pour QLoRA d'un 4B mais tu veux un H100 loué à l'heure |
| API SaaS multi-utilisateur | **Non** | laptop ≠ prod, il te faut VPS ou Modal/Runpod |

## Ce que je te proposerais comme prochain pas

1. **Trancher le nom** — 48 h maxi. Je peux te sortir 10 propositions testées côté domaine + trademark si tu veux.
2. **Commander le M.2 2 TB** — c'est bloquant. Sans ça tu ne feras rien.
3. **Décider l'angle** : "énième anti-slop" ou "OIDA-for-code". Mon vote tu le devines.
4. **Télécharger Qwen3.6-35B-A3B-GGUF Q4_K_M** via unsloth ou bartowski sur HF, benchmarker sur 20 samples de code slop (tu en as sous la main avec tes audits YGN-SAGE précédents — le `runner.py` context window bug est un cas d'école).

Tu veux que je creuse laquelle de ces 4 étapes en premier ?