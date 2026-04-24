---
title: "Modèle V4.2"
subtitle: "Version cohérente, simulation-ready, export formalisé"
author: "Synthèse structurée à partir des itérations V4.0 à V4.2"
date: "5 avril 2026"
lang: fr-FR
toc: true
toc-depth: 3
numbersections: true
fontsize: 11pt
geometry:
  - top=2.2cm
  - bottom=2.2cm
  - left=2.4cm
  - right=2.4cm
mainfont: "TeXGyrePagella"
mathfont: "DejaVu Math TeX Gyre"
sansfont: "TeXGyreHeros"
monofont: "DejaVu Sans Mono"
colorlinks: true
linkcolor: blue
urlcolor: blue
header-includes:
  - |
    ```{=latex}
    \usepackage{microtype}
    \usepackage{booktabs,longtable,array}
    \usepackage{enumitem}
    \usepackage{fancyhdr}
    \setlength{\parindent}{0pt}
    \setlength{\parskip}{0.45em}
    \setlist{leftmargin=*,itemsep=0.15em,topsep=0.2em}
    \pagestyle{fancy}
    \fancyhf{}
    \fancyfoot[C]{\thepage}
    \renewcommand{\headrulewidth}{0pt}
    ```
---

# Résumé

La version V4.2 corrige trois ambiguïtés structurelles de V4.1.

1. Le **domaine sémantique** et la **dépendance entre expériences** sont séparés.
   Le domaine est représenté par un treillis conceptuel $L_D$ ; l'empilement historique
   des expériences est représenté par un graphe orienté acyclique $G_N^D$.
2. La frontière technologique dentelée est déplacée du **niveau domaine** au
   **niveau tâche** : la variable d'absorption devient $\mu(\tau, T)$.
3. Les sorties sont dissociées :
   - $Q_{obs}$ : qualité observable à court terme ;
   - $V_{IA}$ : valeur productive durable ;
   - $H_{sys}$ : nuisance systémique ;
   - $V_{net}$ : valeur nette.

V4.2 conserve le noyau théorique le plus original des versions précédentes :

- $N$ comme **tissu cicatriciel professionnel** ;
- $uN_i$ comme **hypothèse obligatoire associée à chaque expérience** ;
- $uDN_i$ comme **trace cross-domaine** ;
- $N_{eff}$ comme **stock net signé**, pouvant devenir négatif ;
- la possibilité d'une **dette d'apprentissage** et d'un **expert atrophié**.

Le modèle est désormais prêt pour deux usages :

- un **usage analytique** au niveau des hypothèses falsifiables ;
- un **usage de simulation** au moyen d'un ABM Python combinant Mesa et NetworkX.

# Conventions de notation

- $I$ : individu.
- $D$ : domaine.
- $\tau \in \mathcal{T}(D)$ : tâche appartenant au domaine $D$.
- $T$ : temps d'observation.
- $\sigma(z)=\dfrac{1}{1+e^{-z}}$ : fonction logistique.
- $sim(D_j,D) \in [0,1]$ : similarité sémantique entre domaine adjacent et domaine cible.

## Tableau synthétique des variables

| Symbole | Interprétation | Type / borne |
|---|---|---|
| $L_D$ | Treillis conceptuel du domaine | objet structurel |
| $G_N^D$ | DAG de dépendance des expériences dans $D$ | objet structurel |
| $N^D(T)$ | Stock brut d'expériences qualifiantes | $\mathbb{N}$ |
| $uN_i(T)$ | État et valeur de l'hypothèse issue de $N_i$ | $(s_i,v_i,a_i)$ |
| $uDN_i$ | Domaines co-mobilisés lors de $N_i$ | ensemble |
| $N_{stock}^D(T)$ | Stock positif disponible | $\mathbb{R}_{\ge 0}$ |
| $B_{load}^D(T)$ | Charge négative cumulée | $\mathbb{R}_{\ge 0}$ |
| $N_{eff}^D(T)$ | Stock net signé | $\mathbb{R}$ |
| $Debt^D(T)$ | Dette d'apprentissage | $\mathbb{R}_{\ge 0}$ |
| $C_{stock}(T)$ | Variété liée accumulée | $[0,1]$ |
| $C_{flow}(T)$ | Plasticité cross-domaine actuelle | $[0,1]$ |
| $M_{IA}(I,T)$ | Maîtrise opérationnelle des outils IA | $[0,1)$ |
| $SIA_{brut}(T)$ | Capacité brute des solutions IA disponibles | $[0,1]$ |
| $SIA_{eff}(I,T)$ | Effet réel de l'IA pour l'individu | $[0,1]$ |
| $\mu(\tau,T)$ | Compatibilité de la tâche avec la frontière IA | $[0,1]$ |
| $G_D(I,\tau,T)$ | Ancrage humain net dans la tâche | $[0,1]$ |
| $Q_{obs}$ | Qualité visible à court terme | $[0,1]$ |
| $V_{IA}$ | Valeur productive durable | $\mathbb{R}_{\ge 0}$ |
| $H_{sys}$ | Nuisance systémique | $\mathbb{R}_{\ge 0}$ |
| $V_{net}$ | Valeur nette | $\mathbb{R}$ |

# Architecture formelle

## Domaine : treillis conceptuel $L_D$

Le domaine n'est plus traité comme une simple étiquette sémantique. Il est défini par un
**contexte formel** :

$$
K_D=(O_D,A_D,R_D)
$$

avec :

- $O_D$ : objets ;
- $A_D$ : attributs ;
- $R_D \subseteq O_D \times A_D$ : relation binaire objet-attribut.

Le treillis conceptuel induit est :

$$
L_D=\mathfrak{B}(K_D)=(\mathcal{C}_D, \preceq)
$$

ou $\mathcal{C}_D$ est l'ensemble des concepts formels et $\preceq$ l'ordre partiel
induit par inclusion.

Ainsi, V4.2 distingue explicitement :

- le **contexte formel** $K_D$ ;
- le **treillis de concepts** $L_D$ ;
- le **graphe historique des expériences** $G_N^D$.

Cette séparation évite de confondre la hiérarchie sémantique du domaine avec la logique
historique de réutilisation des hypothèses.

## Tâches du domaine

Chaque domaine $D$ contient un ensemble fini ou au moins discrétisable de tâches :

$$
\mathcal{T}(D)=\{\tau_1,\tau_2,\dots,\tau_q\}
$$

La frontière technologique est supposée **dentelée** au niveau des tâches et non au
niveau du domaine agrégé. Une même profession peut donc contenir :

- des tâches très compatibles avec l'IA ;
- des tâches partiellement compatibles ;
- des tâches résistantes, tacites ou fortement contextuelles.

## Graphe de dépendance des expériences $G_N^D$

Le modèle introduit un deuxième objet structurel distinct du treillis :

$$
G_N^D(T)=\big(V_D(T),E_c(T),E_s(T)\big)
$$

avec :

- $V_D(T)$ : ensemble des expériences $N_i$ accumulées jusqu'au temps $T$ ;
- $E_c(T)$ : arêtes **constitutives** ;
- $E_s(T)$ : arêtes **supportives**.

Une arête $i \to j$ existe si l'expérience $N_j$ s'est appuyée sur l'hypothèse générée
par $N_i$.

La distinction entre deux types d'arêtes est centrale :

- une arête constitutive signifie que $N_i$ est nécessaire à la structure de $N_j$ ;
- une arête supportive signifie que $N_i$ a aidé $N_j$ sans être son unique fondement.

Comme les réutilisations sont temporelles, $G_N^D$ est construit comme un **DAG
historique**.

## Liaison structurelle par dominance

La notion vague de "structurellement liée" est remplacée par une relation de dominance
sur le sous-graphe constitutif $G_c^D=(V_D,E_c)$.

On ajoute un super-root $r_D$ relié à tous les nœuds sans parent constitutif, puis on
pose :

$$
dom_D(i,j)=1 \iff i \text{ domine } j \text{ dans } (G_c^D,r_D)
$$

Interprétation : $i$ domine $j$ si **tout chemin constitutif** menant à $j$ passe par
$i$.

Cette relation fonde la propagation des corrections de type double-loop. Elle remplace
une cascade naïve sur "tous les enfants".

# Variables fondamentales

## Variable $N$ : tissu cicatriciel professionnel

$N$ ne mesure ni la connaissance brute ni l'efficacité instantanée. Il mesure le
**tissu cicatriciel professionnel**, c'est-à-dire le stock brut d'expériences au cours
desquelles la connaissance a été mobilisée sous contrainte d'adaptation non procédurale.

$$
N^D(T)=\sum_i \mathbf{1}\Big[
 id\_inconnu(i)
 \land pert\_sys(i)
 \land vision(i)
 \land t_i \le T
\Big]
$$

avec :

- $id\_inconnu$ : identification de la structure réelle du problème ;
- $pert\_sys$ : viabilité systémique ;
- $vision$ : discernement prospectif.

$N^D(T)$ reste un **comptage brut**. La qualité de ce stock sera traitée plus loin par
$N_{eff}^D(T)$.

## Variable $uN_i$ : hypothèse obligatoire issue de $N_i$

Chaque expérience $N_i$ génère une hypothèse obligatoire :

$$
uN_i(T)=\big(s_i(T),v_i(T),a_i(T)\big)
$$

avec :

- $s_i(T) \in \{H,C+,E,B\}$ ;
- $v_i(T) \in [-1,1]$ ;
- $a_i(T) \in \{0,1\}$ : drapeau d'audit ou de revue.

### États

- $H$ : hypothèse active non encore confirmée ;
- $C+$ : hypothèse confirmée ;
- $E$ : hypothèse éliminée ;
- $B$ : hypothèse devenue pseudo-savoir biaisé.

### Déclin naturel en état $H$

Pour une hypothèse non réutilisée mais non biaisée :

$$
v_i(T)=v_i(t_i)e^{-\delta (T-t_i)}, \qquad s_i(T)=H
$$

Le déclin est donc interprété comme une disparition propre, non comme une corruption.

### Dommage en état $B$

Quand une hypothèse est traitée comme savoir sans validation, elle alimente une charge
négative :

$$
damage_i(T)=|v_i|\,usage_i(T)\,\log\!\left(1+\frac{T-t_{B,i}}{\tau_{ref}}\right)
$$

Le dommage augmente avec :

- l'intensité du biais ;
- la fréquence de réutilisation ;
- la durée d'installation du schéma biaisé.

## Opérateurs de transition des états

### Risque de transition $H \to B$

V4.2 modélise explicitement le risque de conversion d'une hypothèse en pseudo-savoir
biaisé sous assistance IA :

$$
\lambda_{H\to B,i}(T)=
\alpha_B\,
SIA_{eff}(I,T)\,
\big(1-\mu(\tau_i,T)\big)\,
\big(1-G_D(I,\tau_i,T)\big)\,
usage_i(T)
$$

Cette écriture implique :

- plus l'effet réel de l'IA est fort, plus la dépendance potentielle est forte ;
- plus la tâche est hors-frontière, plus le risque est élevé ;
- plus l'ancrage humain dans la tâche est faible, plus la bascule est probable ;
- plus le schéma est réutilisé, plus la bascule se consolide.

### Single-loop

Une correction **single-loop** modifie une réponse locale, une procédure ou un
paramétrage sans remettre en cause la structure gouvernante du graphe des hypothèses.

Conséquence formelle :

- le nœud corrigé peut passer de $H$ à $E$ ou rester $H$ ;
- ni la dominance ni la structure de dépendance ne sont modifiées.

### Double-loop

Une correction **double-loop** agit sur un nœud gouvernant $i$ puis propage la révision
dans le graphe historique.

La règle de propagation est :

$$
\forall j \neq i,
\begin{cases}
 s_j \leftarrow H,\ a_j \leftarrow 1 & \text{si } dom_D(i,j)=1 \\
 a_j \leftarrow 1 & \text{si } j \in Desc(i) \text{ sans domination}
\end{cases}
$$

Autrement dit :

- les descendants **dominés** sont rouverts automatiquement ;
- les descendants **influencés mais non dominés** sont marqués pour revue.

Cette distinction évite la cascade totale injustifiée.

## Variable $uDN_i$ : trace cross-domaine

Chaque expérience $N_i$ peut mobiliser des domaines autres que le domaine cible $D$ :

$$
uDN_i=\{D_j : D_j \neq D,\ D_j \text{ mobilisé pendant } N_i\}
$$

$uDN_i$ ne mesure pas un portefeuille abstrait de compétences. Il mesure une
**co-activation réelle** de domaines dans une situation incertaine.

## Spillovers positifs et négatifs entre domaines

La propagation inter-domaines est approchée par :

$$
\rho_{ij}=\rho_0\,sim(D_j,D)\,\mathbf{1}[D_j \in uDN_i],
\qquad 0 \le \rho_0 \le 1
$$

Si $uN_i$ est confirmé :

$$
\Delta N_{stock}^{D_j}\big|_{i\in C+}=\rho_{ij}
$$

Si $uN_i$ est biaisé :

$$
\Delta B_{load}^{D_j}\big|_{i\in B}=\rho_{ij}\,damage_i(T)
$$

Une expérience valide enrichit donc les domaines corrélés, tandis qu'une expérience
biaisée peut les contaminer.

## Richesse cross-domaine : $C_{stock}$ et $C_{flow}$

V4.2 distingue la variété liée accumulée de la plasticité actuelle.

On définit d'abord un poids individuel de contribution :

$$
w_i(T)=
\begin{cases}
1 & \text{si } s_i=C+ \\
v_i(T) & \text{si } s_i=H \\
0 & \text{si } s_i \in \{E,B\}
\end{cases}
$$

### Distribution stock

$$
p_k^{stock}(T)=
\frac{\sum_i w_i(T)\,\mathbf{1}[k \in uDN_i]}
{\sum_i w_i(T)\,|uDN_i|}
$$

$$
C_{stock}(T)=
\begin{cases}
-\dfrac{1}{\log m(T)}\sum_{k=1}^{m(T)} p_k^{stock}(T)\log p_k^{stock}(T) & \text{si } m(T)\ge 2 \\
0 & \text{si } m(T)\le 1
\end{cases}
$$

### Distribution flux

$$
p_k^{flow}(T)=
\frac{\sum_i w_i(T)e^{-\eta (T-t_i)}\,\mathbf{1}[k \in uDN_i]}
{\sum_i w_i(T)e^{-\eta (T-t_i)}\,|uDN_i|}
$$

$$
C_{flow}(T)=
\begin{cases}
-\dfrac{1}{\log m_\eta(T)}\sum_k p_k^{flow}(T)\log p_k^{flow}(T) & \text{si } m_\eta(T)\ge 2 \\
0 & \text{si } m_\eta(T)\le 1
\end{cases}
$$

Interprétation :

- $C_{stock}$ mesure la **variété liée accumulée** ;
- $C_{flow}$ mesure la **plasticité récente**.

## Stock positif, charge négative et dette

Le modèle sépare désormais explicitement la partie positive et la partie négative du stock
expérientiel.

$$
N_{stock}^D(T)=\sum_{i:s_i=C+}1+\sum_{i:s_i=H}v_i(T)
$$

$$
B_{load}^D(T)=\sum_{i:s_i=B}damage_i(T)
$$

$$
N_{eff}^D(T)=N_{stock}^D(T)-B_{load}^D(T)
$$

$$
Debt^D(T)=\max\{0,-N_{eff}^D(T)\}
$$

La négativité de $N_{eff}^D(T)$ est donc conservée comme propriété théorique. Elle ne
signifie pas un stock matériel négatif, mais une **charge nette d'erreurs structurantes**.

On peut en déduire un temps de récupération :

$$
T_{rec}^D(T)=\inf\{t\ge T : N_{eff}^D(t)\ge 0\}
$$

## Expérience accumulée $x$

L'expérience accumulée reste une variable génératrice de trajectoire :

$$
x(I,T)=\int_0^T \gamma_I(t)\,dt
$$

avec :

$$
\gamma_I(t)=\alpha_I(t)\beta_I(t)+\varepsilon_I(t)
$$

- $\alpha_I(t)$ : intensité d'exposition au domaine ;
- $\beta_I(t)$ : capacité d'intégration ;
- $\varepsilon_I(t)$ : terme stochastique.

## Domaines adjacents

Le stock de domaines adjacents mobilisables reste défini par :

$$
D.N_{adjacent}(I,T)=
\{(D_j,N_{eff}^{D_j}(I,T),sim(D_j,D))\}_{j=1}^{m}
$$

Cette variable devient un déterminant direct de l'ancrage humain net dans une tâche.

## Maîtrise des outils IA

La maîtrise IA est définie comme une capacité asymptotique :

$$
M_{IA}(I,T)=1-\exp\big[-\lambda\,h_{int}(K_{IA}(I,T),R_{opt}(I,T))\big]
$$

ou :

- $K_{IA}$ est le stock pondéré de sous-compétences IA ;
- $R_{opt}$ est la capacité à sélectionner une stratégie utile sous bruit.

## Effet réel de la solution IA

V4.2 supprime la double comptabilisation de $M_{IA}$.

$$
SIA_{eff}(I,T)=
SIA_{brut}(T)\cdot
M_{IA}(I,T)\cdot
\exp\!\left(-\frac{v_{SIA}(T)}{1+C_{flow}(I,T)}\right)
$$

Interprétation :

- $SIA_{brut}$ capture la capacité brute des outils disponibles ;
- $M_{IA}$ borne l'opérationnalisation individuelle ;
- $v_{SIA}$ déprécie les routines validées ;
- $C_{flow}$ agit comme amortisseur adaptatif.

## Frontière technologique au niveau tâche

Le coefficient d'absorption est désormais défini au niveau de la tâche :

$$
\mu(\tau,T) \in [0,1]
$$

- $\mu(\tau,T)$ élevé : tâche très compatible avec l'IA ;
- $\mu(\tau,T)$ faible : tâche résistante, tacite, contextuelle ou pauvre en feedback.

Au niveau domaine, on peut former un agrégat :

$$
\bar{\mu}(D,T)=\sum_{\tau \in \mathcal{T}(D)} \pi_\tau\,\mu(\tau,T)
$$

avec $\pi_\tau$ poids d'exposition ou d'importance de la tâche dans le domaine.

## Ancrage humain net dans la tâche

V4.2 remplace l'ancien $D_{effectif}$ par une grandeur plus propre :

$$
G_D(I,\tau,T)=
\sigma\!\left(
\frac{
N_{eff}^D(I,T)
+\sum_{j=1}^{m} sim(D_j,D)\,N_{eff}^{D_j}(I,T)
-N_{min}(\tau)
}{s_D}
\right)
$$

- $N_{min}(\tau)$ est le seuil minimal de stock net pour traiter correctement la tâche ;
- $s_D>0$ est la pente logistique.

Le seuil domaine peut être défini comme un quantile des seuils de tâches :

$$
N_{min}(D)=Q_q\{N_{min}(\tau):\tau \in \mathcal{T}(D)\}
$$

# Sorties du modèle

## Qualité observable à court terme $Q_{obs}$

La première sortie n'est plus une valeur durable, mais une qualité immédiatement visible :

$$
Q_{obs}(I,\tau,T)=
SIA_{eff}(I,T)+\big(1-SIA_{eff}(I,T)\big)\,G_D(I,\tau,T)
$$

$Q_{obs}$ capte ce qu'un observateur voit au premier passage : cohérence, finition,
plausibilité, fluidité.

Le nivellement initial est désormais porté par $Q_{obs}$, et non par la valeur durable.

## Valeur productive durable $V_{IA}$

On introduit un facteur d'accélération lié à la variété accumulée :

$$
g(C_{stock},T)=1+\gamma\,C_{stock}(I,T)\log(1+T)
$$

La valeur durable est alors :

$$
V_{IA}(I,\tau,T)=
G_D(I,\tau,T)
\big[1+\mu(\tau,T)\,SIA_{eff}(I,T)\big]
\,g(C_{stock},T)
$$

Interprétation :

- sans ancrage humain net, l'outil n'engendre pas de valeur durable ;
- l'effet utile de l'IA est amplifié sur les tâches dans la frontière ;
- $C_{stock}$ accélère la montée en valeur sur terrain nouveau.

## Nuisance systémique $H_{sys}$

Pour formaliser l'expert atrophié, V4.2 ajoute une variable explicite de nuisance :

$$
\widetilde{B}^D(I,T)=1-e^{-B_{load}^D(I,T)}
$$

$$
H_{sys}(I,\tau,T)=
\psi(\tau)
\big(1-\mu(\tau,T)\big)
SIA_{eff}(I,T)
\widetilde{B}^D(I,T)
Q_{obs}(I,\tau,T)
$$

avec $\psi(\tau) \ge 0$ un coefficient de rayon d'impact systémique.

La nuisance est maximale lorsque :

- la tâche est hors-frontière ;
- l'outil produit une sortie convaincante ;
- la charge de biais est élevée ;
- la sortie est assez cohérente pour être acceptée.

## Valeur nette et valeur relative

La valeur nette est définie par :

$$
V_{net}(I,\tau,T)=V_{IA}(I,\tau,T)-H_{sys}(I,\tau,T)
$$

La valeur relative agrégée devient :

$$
V_{relative}(I,T)=
\frac{\sum_{\tau} \pi_\tau V_{net}(I,\tau,T)}
{E\big[\sum_{\tau} \pi_\tau V_{net}(march\acute{e},\tau,T)\big]}
$$

Cette grandeur est volontairement reportée à un second niveau de modélisation, car elle
nécessite un modèle de diffusion de l'usage de l'IA dans la population.

# Profils-types et propriétés émergentes

## Spécialiste

Profil caractérisé par :

- $N_{eff}^D$ élevé ;
- forte capacité d'ancrage dans le domaine cible ;
- sensibilité aux tâches à faible $\mu$ ;
- risque d'atrophie si une fraction croissante des $uN_i$ bascule vers $B$.

## Novice

Profil caractérisé par :

- faible ancrage humain net ;
- forte dépendance à $Q_{obs}$ ;
- montée rapide de la qualité visible ;
- valeur durable faible tant que $G_D$ reste sous le seuil.

## Profil adjacent

Profil caractérisé par :

- forte contribution de $D.N_{adjacent}$ ;
- $C_{stock}$ et $C_{flow}$ élevés ;
- bonne résilience aux changements rapides de l'écosystème IA ;
- forte vitesse de montée sur terrain nouveau.

## Expert atrophié

Le cas le plus distinctif du modèle apparaît lorsque :

- $Q_{obs}$ reste élevé ;
- $Debt^D(T)>0$ ;
- $H_{sys}$ devient élevé ;
- $V_{net}<0$.

Ce profil n'est pas simplement "faible" : il devient **destructeur de valeur** malgré une
production superficiellement crédible.

# Hypothèses empiriques minimales

Le modèle produit les hypothèses ordinales suivantes.

## H1. Nivellement initial observable

À très court terme, une hausse de $SIA_{brut}$ augmente $Q_{obs}$ chez tous les profils,
avec un effet relativement plus fort chez les individus à faible expérience domainale.

## H2. Divergence durable

À horizon plus long, $V_{IA}$ diverge selon :

- l'ancrage humain net $G_D$ ;
- la structure des domaines adjacents ;
- la dynamique de transition des $uN_i$.

## H3. Risque hors-frontière

Pour les tâches à faible $\mu(\tau,T)$, une hausse de $SIA_{eff}$ accroît la probabilité
de transition $H \to B$ si $G_D$ est faible.

## H4. Avantage du profil adjacent

À difficulté comparable, le profil adjacent surpasse le spécialiste pur sur terrain
nouveau dès lors que :

$$
C_{stock} \text{ élevé}, \qquad C_{flow} \text{ élevé}, \qquad M_{IA} \ge M_{min}
$$

## H5. Apparition d'une nuisance systémique

Pour certaines tâches hors-frontière à fort rayon d'impact, un individu peut présenter :

$$
Q_{obs} \text{ élevé}, \qquad V_{IA} \text{ modeste}, \qquad H_{sys} \text{ élevé}
$$

Cette configuration caractérise l'expert atrophié.

# Stratégie de falsifiabilité

## Ce que les datasets généralistes peuvent faire

Des bases comme O*NET peuvent aider à :

- décrire les tâches ;
- approximer des proxys de similarité sémantique ;
- préparer une stratification des métiers et sous-tâches.

En revanche, elles n'observent pas directement :

- les états $H,C+,E,B$ ;
- la charge $B_{load}$ ;
- la structure de dominance dans $G_N^D$.

## Ce qu'il faut effectivement tester

Le protocole minimal crédible est un essai randomisé par tâches avec au moins trois
conditions :

1. sans IA ;
2. IA standard ;
3. IA avec forcing de vérification.

Une quatrième condition peut être ajoutée dans un environnement simulé à risque minimal :

4. IA perturbée ou volontairement incomplète sur certaines tâches hors-frontière.

### Variables mesurées

- correction réelle de la sortie ;
- qualité observable perçue ;
- confiance ;
- calibration de la confiance ;
- prompts, révisions et chaînes de dépendance ;
- transitions d'états des $uN_i$ ;
- propagation de la revue dans $G_N^D$.

# Niveau 2 : implémentation ABM

V4.2 est compatible avec un ABM Python en trois étages.

## Étape micro

Simulation des trajectoires individuelles :

- accumulation de $N$ ;
- transitions des $uN_i$ ;
- formation de $B_{load}$ ;
- évolution de $C_{stock}$ et $C_{flow}$ ;
- production de $Q_{obs}$, $V_{IA}$ et $H_{sys}$.

## Étape méso

Ajout des effets de diffusion locale :

- imitation ;
- propagation des routines ;
- apprentissage social ;
- contamination ou correction au niveau équipe.

## Étape marché

Seulement dans un troisième temps :

- diffusion de l'usage IA ;
- sélection ;
- redistribution relative de la valeur ;
- estimation de $V_{relative}$.

# Zones d'ombre restantes

V4.2 n'est plus contradictoire, mais reste ouverte sur plusieurs paramètres et
opérationnalisations.

| Zone | Statut | Commentaire |
|---|---|---|
| $\delta$ | non calibré | déclin des hypothèses non réutilisées |
| $\tau_{ref}$ | non calibré | inertie temporelle du dommage |
| $\alpha_B$ | non calibré | intensité de bascule vers $B$ |
| $\rho_0$ | non calibré | transfert inter-domaines |
| $\eta$ | non calibré | pondération de récence pour $C_{flow}$ |
| $\psi(\tau)$ | non calibré | rayon d'impact systémique |
| $s_D$ | non calibré | pente logistique de l'ancrage |
| $N_{min}(\tau)$ | non observé directement | nécessite un protocole expert |
| $sim(D_j,D)$ | proxy | embeddings, descripteurs ou taxonomies |
| $V_{relative}$ | niveau 3 | demande un modèle de diffusion marché |

# Conclusion de la version V4.2

Le point d'arrivée de V4.2 peut être résumé ainsi :

$$
\begin{aligned}
L_D &\text{ décrit ce que le domaine est,}\\
G_N^D &\text{ décrit comment l'expérience s'empile,}\\
(Q_{obs},V_{IA},H_{sys}) &\text{ distinguent apparence, valeur durable et nuisance.}
\end{aligned}
$$

La version V4.2 est donc la première version :

- **théoriquement cohérente** ;
- **compatible avec une implémentation** ;
- **prête pour une stratégie de falsifiabilité** ;
- **suffisamment séparée en plans** pour éviter les circularités les plus graves des versions antérieures.

# Références citées (sélection)

- Autor, D. H., Levy, F., & Murnane, R. J. (2003). *The Skill Content of Recent Technological Change: An Empirical Exploration*. Quarterly Journal of Economics.
- Brynjolfsson, E., Li, D., & Raymond, L. R. (2023). *Generative AI at Work*. NBER Working Paper 31161.
- Cohen, W. M., & Levinthal, D. A. (1990). *Absorptive Capacity: A New Perspective on Learning and Innovation*. Administrative Science Quarterly.
- Dell'Acqua, F., et al. (2026). *Navigating the Jagged Technological Frontier*. Organization Science. (Version publiée de la lignée de working papers 2023.)
- Frenken, K., Van Oort, F., & Verburg, T. (2007). *Related Variety, Unrelated Variety and Regional Economic Growth*. Regional Studies.
- Ganter, B., & Wille, R. (1999). *Formal Concept Analysis: Mathematical Foundations*. Springer.
- Lee, H. P. H., et al. (2025). *The Impact of Generative AI on Critical Thinking: Self-Reported Reductions in Cognitive Effort and Confidence Effects From a Survey of Knowledge Workers*.
- Mesa documentation. *Mesa: Agent-Based Modeling in Python*.
- NetworkX documentation. *Directed Acyclic Graphs* ; *Dominance* ; *immediate_dominators*.
- O*NET Resource Center. *O*NET Database*.
- Risko, E. F., & Gilbert, S. J. (2016). *Cognitive Offloading*. Trends in Cognitive Sciences.

