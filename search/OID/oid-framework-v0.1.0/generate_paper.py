#!/usr/bin/env python3
"""
Generate the OID paper as a formatted PDF.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    Image, KeepTogether, HRFlowable
)
from reportlab.lib import colors
import os

OUT = "/home/claude/paper.pdf"
FIG_DIR = "/home/claude/figures"

styles = getSampleStyleSheet()

# Custom styles
styles.add(ParagraphStyle(
    "PaperTitle", parent=styles["Title"], fontSize=16, leading=20,
    spaceAfter=6, alignment=TA_CENTER,
))
styles.add(ParagraphStyle(
    "Author", parent=styles["Normal"], fontSize=11, leading=14,
    alignment=TA_CENTER, spaceAfter=4,
))
styles.add(ParagraphStyle(
    "Abstract", parent=styles["Normal"], fontSize=10, leading=13,
    leftIndent=30, rightIndent=30, spaceAfter=12, alignment=TA_JUSTIFY,
    fontName="Helvetica-Oblique",
))
styles.add(ParagraphStyle(
    "SectionHead", parent=styles["Heading1"], fontSize=13, leading=16,
    spaceBefore=14, spaceAfter=6, textColor=HexColor("#1a1a1a"),
))
styles.add(ParagraphStyle(
    "SubHead", parent=styles["Heading2"], fontSize=11, leading=14,
    spaceBefore=10, spaceAfter=4, textColor=HexColor("#333333"),
))
styles.add(ParagraphStyle(
    "Body", parent=styles["Normal"], fontSize=10, leading=13,
    alignment=TA_JUSTIFY, spaceAfter=6,
))
styles.add(ParagraphStyle(
    "Formula", parent=styles["Normal"], fontSize=10, leading=14,
    alignment=TA_CENTER, spaceAfter=8, spaceBefore=6,
    fontName="Courier",
))
styles.add(ParagraphStyle(
    "Caption", parent=styles["Normal"], fontSize=9, leading=11,
    alignment=TA_CENTER, spaceAfter=10, fontName="Helvetica-Oblique",
))
styles.add(ParagraphStyle(
    "RefStyle", parent=styles["Normal"], fontSize=9, leading=11,
    leftIndent=20, firstLineIndent=-20, spaceAfter=3,
))


def S(text):
    return Paragraph(text, styles["SectionHead"])

def SS(text):
    return Paragraph(text, styles["SubHead"])

def P(text):
    return Paragraph(text, styles["Body"])

def F(text):
    return Paragraph(text, styles["Formula"])

def sp(h=6):
    return Spacer(1, h)

def fig(name, w=14*cm, caption=""):
    path = os.path.join(FIG_DIR, name)
    elems = []
    if os.path.exists(path):
        elems.append(Image(path, width=w, height=w*0.55))
    if caption:
        elems.append(Paragraph(caption, styles["Caption"]))
    return KeepTogether(elems)


def build():
    doc = SimpleDocTemplate(
        OUT, pagesize=A4,
        topMargin=2.2*cm, bottomMargin=2.2*cm,
        leftMargin=2.4*cm, rightMargin=2.4*cm,
    )
    story = []

    # ---- TITLE ----
    story.append(Paragraph(
        "Operational Integrity Dynamics for Autonomous AI Agents:<br/>"
        "A Formal Model of Competence Degradation and Systemic Harm",
        styles["PaperTitle"],
    ))
    story.append(Paragraph("Yann Abadie", styles["Author"]))
    story.append(Paragraph("Motherson Aerospace SAS &amp; Independent Researcher", styles["Author"]))
    story.append(Paragraph("April 2026", styles["Author"]))
    story.append(sp(10))

    # ---- ABSTRACT ----
    story.append(Paragraph("<b>Abstract</b>", styles["SubHead"]))
    story.append(Paragraph(
        "Autonomous AI agents are deployed in production environments where they execute "
        "multi-step tasks with minimal human oversight. Current safety frameworks address "
        "permissions, policy enforcement, and adversarial attacks, but lack a formal dynamic "
        "model of how an agent's accumulated operational patterns can silently degrade its "
        "capacity to produce net-positive outcomes. We introduce the Operational Integrity "
        "Dynamics (OID) framework, adapted from a formal model of professional competence "
        "under AI integration (Abadie, 2026). OID defines a four-state machine "
        "{H, C<super>+</super>, E, B} for action patterns, a dependency DAG with constitutive and supportive "
        "edges, and a triple output decomposition: observable quality (Q<sub>obs</sub>), durable "
        "productive value (V<sub>IA</sub>), and systemic harm (H<sub>sys</sub>). The framework formalises "
        "the 'atrophied agent' profile: an agent that passes all benchmarks while becoming "
        "net-destructive. We demonstrate through agent-based simulation that this profile "
        "emerges reliably under realistic conditions, particularly on irreversible, "
        "high-impact tasks. The OID framework provides computable risk scores derivable "
        "from existing observability traces, addressing a gap identified by OWASP, NIST, "
        "and recent industry frameworks.",
        styles["Abstract"],
    ))
    story.append(Paragraph(
        "<b>Keywords:</b> agent safety, operational integrity, competence degradation, "
        "autonomous agents, formal model, systemic harm, MLOps",
        ParagraphStyle("kw", parent=styles["Abstract"], fontName="Helvetica"),
    ))
    story.append(sp(8))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(sp(8))

    # ---- 1. INTRODUCTION ----
    story.append(S("1. Introduction"))
    story.append(P(
        "Autonomous AI agents have moved from experimental prototypes to production systems "
        "handling infrastructure tasks, customer interactions, and business-critical workflows. "
        "As of early 2026, the deployment landscape has shifted dramatically: Microsoft released "
        "the Agent Governance Toolkit addressing the OWASP Agentic AI Top 10; Proofpoint and "
        "Acuvity published the Agent Integrity Framework; NIST issued a formal Request for "
        "Information on agent security; and the OWASP GenAI Security Project released its "
        "inaugural Top 10 for Agentic Applications."
    ))
    story.append(P(
        "These frameworks share a common architectural focus: they address <b>who</b> can do "
        "<b>what</b> (permissions, identity, policy enforcement) and <b>how to detect</b> when "
        "something goes wrong (observability, audit trails, runtime monitoring). However, none "
        "of them formally model the <b>internal dynamics</b> by which an agent's accumulated "
        "operational patterns can silently degrade its capacity to produce net-positive outcomes."
    ))
    story.append(P(
        "The gap is structural. Sculley et al. (2015) established the concept of hidden "
        "technical debt in ML systems, but their framework is taxonomic and qualitative, "
        "offering no formal dynamics. The OWASP Agentic Top 10 identifies risk categories "
        "(goal hijacking, tool misuse, cascading failures, rogue agents) but does not model "
        "the accumulation mechanism. Microsoft's blog post on the OWASP Top 10 notes that "
        "'a system can be working as designed while still taking steps that a human would be "
        "unlikely to approve' - precisely the pattern we formalise."
    ))
    story.append(P(
        "This paper introduces the <b>Operational Integrity Dynamics (OID)</b> framework, a "
        "formal dynamic model adapted from a V4.2 theoretical model of professional competence "
        "under AI integration (Abadie, 2026). OID provides: (1) a four-state machine for action "
        "patterns; (2) a dependency DAG with dominance-based propagation; (3) a triple output "
        "decomposition that separates what benchmarks see from what matters; and (4) computable "
        "risk scores derivable from existing observability traces."
    ))

    # ---- 2. RELATED WORK ----
    story.append(S("2. Related Work"))

    story.append(SS("2.1 Agent Safety Frameworks"))
    story.append(P(
        "The OWASP Top 10 for Agentic Applications (December 2025) defines ten risk categories "
        "for autonomous agents, from goal hijacking (ASI01) to rogue agents (ASI10). The "
        "framework is operational and taxonomic, providing checklists and architectural "
        "blueprints rather than formal dynamics. Microsoft's Agent Governance Toolkit "
        "(April 2026) implements runtime policy enforcement with sub-millisecond latency "
        "across major agent frameworks. Proofpoint's Agent Integrity Framework (February 2026) "
        "defines five pillars: intent alignment, identity, behavioural consistency, auditability, "
        "and operational transparency. None of these model the temporal dynamics of pattern "
        "accumulation and degradation."
    ))

    story.append(SS("2.2 Technical Debt in ML Systems"))
    story.append(P(
        "Sculley et al. (2015) identified hidden feedback loops, boundary erosion, and "
        "entanglement as sources of technical debt in ML systems. Their framework remains "
        "the canonical reference, but it is qualitative: it describes <i>categories</i> of "
        "debt without providing a formal model of how debt accumulates, propagates, or "
        "creates systemic harm. The Databricks extension to GenAI systems (2026) extends "
        "the taxonomy but maintains the same qualitative approach."
    ))

    story.append(SS("2.3 The Competence Model (V4.2)"))
    story.append(P(
        "The formal model from which OID is adapted (Abadie, 2026) was developed in the "
        "context of labour economics and management science. It models how AI integration "
        "reshapes professional competence value, introducing concepts including: the 'scar "
        "tissue' stock of professional experience (N), a four-state hypothesis machine "
        "{H, C<super>+</super>, E, B}, cross-domain spillovers, a signed effective stock that can become "
        "negative, and the 'atrophied expert' profile. This paper demonstrates that the "
        "formal apparatus transfers to autonomous agent systems with specific adaptations."
    ))

    # ---- 3. THE OID FRAMEWORK ----
    story.append(S("3. The OID Framework"))

    story.append(SS("3.1 Action Patterns and State Machine"))
    story.append(P(
        "Each operational episode where an agent handles a non-trivial situation (error "
        "recovery, novel context, strategy revision) generates an <b>action pattern</b> - "
        "a learned heuristic that may be reused in future episodes. Each pattern carries "
        "a state, a confidence value, and an audit flag:"
    ))
    story.append(F("u<sub>i</sub>(T) = (s<sub>i</sub>(T), v<sub>i</sub>(T), a<sub>i</sub>(T))"))
    story.append(P(
        "where s<sub>i</sub> takes values in {H, C<super>+</super>, E, B}:"
    ))

    state_data = [
        ["State", "Meaning", "Agent interpretation"],
        ["H", "Active hypothesis", "Untested heuristic from a single episode"],
        ["C+", "Confirmed", "Validated across diverse conditions"],
        ["E", "Eliminated", "Invalidated by contradicting evidence"],
        ["B", "Biased pseudo-knowledge", "Falsely generalised; looks correct, causes harm"],
    ]
    state_table = Table(state_data, colWidths=[2*cm, 4*cm, 9*cm])
    state_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#e0e0e0")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(state_table)
    story.append(sp(6))

    story.append(SS("3.2 Transition Dynamics"))
    story.append(P(
        "The critical transition is H to B: an untested heuristic becomes biased pseudo-knowledge. "
        "The transition risk is:"
    ))
    story.append(F(
        "lambda<sub>H-&gt;B,i</sub> = alpha<sub>B</sub> . capability . (1 - mu(tau)) . (1 - G<sub>D</sub>) . usage<sub>i</sub>"
    ))
    story.append(P(
        "A pattern becomes biased when: the agent is highly capable (convincing outputs), "
        "the task is irreversible or opaque (low mu), the operational grounding is weak "
        "(low G<sub>D</sub>), and the pattern has been reused many times without validation. "
        "Patterns in state H also undergo natural decay (clean disappearance when unused), "
        "and patterns in state B generate cumulative damage:"
    ))
    story.append(F(
        "damage<sub>i</sub>(T) = |v<sub>i</sub>| . usage<sub>i</sub>(T) . log(1 + (T - t<sub>B,i</sub>) / tau<sub>ref</sub>)"
    ))

    story.append(SS("3.3 Dependency DAG and Dominance"))
    story.append(P(
        "Action patterns form a directed acyclic graph G<sub>N</sub><super>D</super> with two "
        "types of edges: <b>constitutive</b> (pattern i is necessary to pattern j) and "
        "<b>supportive</b> (pattern i aided j without being its sole foundation). "
        "Dominance is computed on the constitutive sub-graph: i dominates j if every "
        "constitutive path to j passes through i."
    ))
    story.append(P(
        "This distinction is critical for correction propagation. A <b>single-loop</b> "
        "correction fixes a local response without modifying the DAG structure. A "
        "<b>double-loop</b> correction eliminates a governing pattern and propagates "
        "revision: dominated descendants are reopened (state reset to H with audit flag); "
        "non-dominated descendants are flagged for review only."
    ))

    story.append(SS("3.4 Task Characterisation"))
    story.append(P(
        "Each task tau carries two characteristics: mu(tau) in [0,1] measuring "
        "reversibility times observability, and psi(tau) >= 0 measuring systemic impact "
        "radius. The 'jagged frontier' means that within a single operational domain, "
        "some tasks are safe (high mu, low psi: code generation, documentation) while "
        "others are dangerous (low mu, high psi: database migration, production "
        "configuration changes, incident response)."
    ))

    story.append(SS("3.5 Operational Grounding"))
    story.append(P(
        "Operational grounding G<sub>D</sub> measures the proportion of the operational "
        "environment that the agent has verified by direct observation (not inference). "
        "It is computed as a logistic function of the effective stock minus the task's "
        "minimum threshold:"
    ))
    story.append(F(
        "G<sub>D</sub>(I, tau, T) = sigma((N<sub>eff</sub> + adj - N<sub>min</sub>(tau)) / s<sub>D</sub>)"
    ))
    story.append(P(
        "An agent with low grounding on a high-impact task is the primary risk factor "
        "for the H to B transition."
    ))

    # ---- 4. OUTPUTS ----
    story.append(S("4. Triple Output Decomposition"))
    story.append(P(
        "The OID framework produces four outputs that separate what benchmarks see from "
        "what matters:"
    ))

    story.append(SS("4.1 Observable Quality (Q<sub>obs</sub>)"))
    story.append(F("Q<sub>obs</sub> = S<sub>eff</sub> + (1 - S<sub>eff</sub>) . G<sub>D</sub>"))
    story.append(P(
        "This is what benchmarks, test suites, and human reviewers see at first glance: "
        "coherence, fluency, plausibility. A capable agent always scores high on Q<sub>obs</sub> "
        "regardless of whether its outputs are actually safe."
    ))

    story.append(SS("4.2 Durable Productive Value (V<sub>IA</sub>)"))
    story.append(F("V<sub>IA</sub> = G<sub>D</sub> . [1 + mu . S<sub>eff</sub>] . g(C<sub>stock</sub>, T)"))
    story.append(P(
        "Without operational grounding, the agent generates no durable value. The AI "
        "capability multiplier only amplifies value on tasks within the frontier "
        "(high mu). Cross-domain experience accelerates value creation on novel terrain."
    ))

    story.append(SS("4.3 Systemic Harm (H<sub>sys</sub>)"))
    story.append(F("H<sub>sys</sub> = psi . (1 - mu) . S<sub>eff</sub> . B_tilde . Q<sub>obs</sub>"))
    story.append(P(
        "Systemic harm is maximal when: the task is irreversible (low mu), the agent is "
        "capable (high S<sub>eff</sub>), the bias load is high, and the output is convincing "
        "enough to be accepted (high Q<sub>obs</sub>). The last factor is crucial: harm "
        "requires that the output passes human review."
    ))

    story.append(SS("4.4 Net Value and the Atrophied Agent"))
    story.append(F("V<sub>net</sub> = V<sub>IA</sub> - H<sub>sys</sub>"))
    story.append(P(
        "The <b>atrophied agent</b> is characterised by: Q<sub>obs</sub> high, Debt > 0, "
        "H<sub>sys</sub> high, V<sub>net</sub> &lt; 0. This agent is not simply weak - it is "
        "net-destructive despite producing superficially credible outputs. This is the "
        "formal capture of the database deletion scenario and similar incidents."
    ))

    # ---- 5. SIMULATION ----
    story.append(S("5. Simulation Results"))
    story.append(P(
        "We implemented the OID framework as a Python package (oid-framework v0.1.0) and "
        "ran agent-based simulations across a standard task portfolio with six task types "
        "spanning the jagged frontier."
    ))

    story.append(SS("5.1 Database Deletion Scenario"))
    story.append(P(
        "We simulated an agent with high capability (0.9) and high mastery (0.85) but "
        "no prior grounding on database migration tasks (mu=0.1, psi=8.0, N<sub>min</sub>=10). "
        "The agent's V<sub>net</sub> becomes negative at T=3 and reaches -3.69 by T=50, "
        "while Q<sub>obs</sub> remains above 0.71. The agent accumulates a debt of 25.0 "
        "and is classified as 'atrophied'."
    ))
    story.append(fig("fig1_database_scenario.png", w=14*cm,
        caption="Figure 1. Database deletion scenario. Q_obs remains high while V_net "
                "diverges sharply negative. The agent becomes net-destructive at T=3."))

    story.append(SS("5.2 Comparative Trajectories"))
    story.append(P(
        "We compared four agent profiles across an 80-step simulation on the standard "
        "task portfolio (6 task types). The grounded expert (pre-seeded with 8 confirmed "
        "patterns on db_migration) maintains positive V<sub>net</sub> = 1.10. All ungrounded "
        "agents, regardless of capability, become atrophied on the critical path."
    ))
    story.append(fig("fig2_comparative_vnet.png", w=14*cm,
        caption="Figure 2. Net value trajectories. Only the grounded expert maintains "
                "positive V_net. Higher capability without grounding accelerates atrophy."))

    story.append(SS("5.3 Risk Surface"))
    story.append(P(
        "The H to B transition risk surface (Figure 3) confirms the intuition: the danger "
        "zone is characterised by low mu (irreversible tasks) and low G<sub>D</sub> "
        "(unverified environment). This maps directly to the operational conditions "
        "under which agents delete databases, misconfigure production systems, or "
        "escalate incidents."
    ))
    story.append(fig("fig6_risk_surface.png", w=12*cm,
        caption="Figure 3. H to B transition risk as a function of task reversibility "
                "and operational grounding. The danger zone (red) corresponds to "
                "irreversible tasks with unverified assumptions."))

    story.append(SS("5.4 Sensitivity Analysis"))
    story.append(P(
        "To verify that qualitative predictions are robust to parameter calibration, we "
        "swept five key parameters (alpha<sub>B</sub>, delta, mu, psi, capability) across "
        "their plausible ranges, with 8 random seeds per configuration. We tested three "
        "predictions: P1 (atrophied agent emerges on irreversible tasks), P2 (grounding "
        "advantage), P3 (higher capability accelerates atrophy when ungrounded)."
    ))

    sens_data = [
        ["Prediction", "Global robustness", "Interpretation"],
        ["P1: Atrophied emerges", "80.0%", "Drops correctly at high mu (safe tasks)"],
        ["P2: Grounding advantage", "91.8%", "Robust across all parameters"],
        ["P3: Cap. accelerates atrophy", "97.1%", "Extremely robust"],
    ]
    sens_table = Table(sens_data, colWidths=[4.5*cm, 3.5*cm, 7*cm])
    sens_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#e0e0e0")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(Paragraph("<b>Table 2.</b> Sensitivity analysis: global robustness of predictions.", styles["Caption"]))
    story.append(sens_table)
    story.append(sp(6))

    story.append(P(
        "P1's 80% rate is not a weakness: atrophy fails to emerge when mu is high (>0.5), "
        "which is the correct prediction — agents on reversible tasks do not accumulate "
        "destructive bias. P2 and P3 are robust across the full parameter space, confirming "
        "that grounding is the structural differentiator and that capability without "
        "grounding is counterproductive."
    ))
    story.append(fig("fig7_sensitivity.png", w=14*cm,
        caption="Figure 4. Sensitivity analysis across five parameters. "
                "Predictions P2 and P3 hold at >90% across the parameter space."))

    # ---- 6. MAPPING ----
    story.append(S("6. Mapping to Existing Frameworks"))

    map_data = [
        ["OID Concept", "OWASP ASI", "Agent Integrity Framework", "Sculley (2015)"],
        ["H->B transition", "ASI08 Cascading Failures", "Behavioral Consistency", "Hidden feedback loops"],
        ["Q_obs vs V_net gap", "ASI09 Trust Exploitation", "Intent Alignment", "Not addressed"],
        ["Dependency DAG", "ASI08 Cascading Failures", "Auditability", "Entanglement"],
        ["Double-loop correction", "Not addressed", "Not addressed", "Not addressed"],
        ["Atrophied agent", "ASI10 Rogue Agents (partial)", "Not addressed", "Not addressed"],
        ["mu(tau) task frontier", "Not addressed (implicit)", "Operational Transparency", "Not addressed"],
    ]
    map_table = Table(map_data, colWidths=[3.5*cm, 3.5*cm, 4*cm, 3.5*cm])
    map_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#e0e0e0")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(Paragraph(
        "<b>Table 1.</b> Mapping OID concepts to existing frameworks.",
        styles["Caption"],
    ))
    story.append(map_table)
    story.append(sp(8))

    story.append(P(
        "The key contribution of OID relative to existing frameworks is the formalisation "
        "of three concepts that are acknowledged but not modelled: (1) the dynamic "
        "accumulation of biased patterns; (2) the dominance-based propagation of "
        "corrections; and (3) the divergence between observable quality and net value."
    ))

    # ---- 7. IMPLEMENTATION ----
    story.append(S("7. Implementation and Integration"))
    story.append(P(
        "The OID framework is implemented as a Python package compatible with existing "
        "observability pipelines. The core data structures (ActionPattern, DependencyDAG, "
        "IntegrityScorer) can be populated from execution traces generated by any agent "
        "framework (LangChain, CrewAI, AutoGen). The key integration points are:"
    ))
    story.append(P(
        "(1) <b>Trace ingestion</b>: each tool call or decision in an agent trace maps to "
        "an OperationalEpisode. Dependencies between trace spans map to DAG edges. "
        "(2) <b>Pattern state tracking</b>: a supervisory process maintains the state "
        "register, tracking which patterns have been confirmed by feedback and which "
        "have been reused without validation. "
        "(3) <b>Risk scoring</b>: the IntegrityScorer computes Q<sub>obs</sub>, V<sub>IA</sub>, "
        "H<sub>sys</sub>, and V<sub>net</sub> at each step or on demand. "
        "(4) <b>Gating</b>: before executing an action with low mu and high psi, the "
        "H to B transition risk can be computed; if it exceeds a threshold, human "
        "approval is required."
    ))

    # ---- 8. LIMITATIONS ----
    story.append(S("8. Limitations and Open Questions"))
    story.append(P(
        "<b>Temporal dynamics.</b> The V4.2 model was designed for human professionals who "
        "accumulate experience over years. Agents accumulate patterns in minutes. The "
        "decay rate delta, bias intensity alpha<sub>B</sub>, and temporal reference tau<sub>ref</sub> "
        "require recalibration for agent timescales. The current simulation uses plausible "
        "but uncalibrated values."
    ))
    story.append(P(
        "<b>Empirical validation.</b> The framework produces testable predictions "
        "(H1-H5 in the original V4.2) but has not yet been validated against real agent "
        "execution logs. A credible validation protocol would require: (a) instrumented "
        "agent deployments with trace logging; (b) independent quality assessment by "
        "domain experts; (c) comparison of OID scores against actual incident rates."
    ))
    story.append(P(
        "<b>Parameter sensitivity.</b> The model contains 8-9 uncalibrated parameters "
        "(delta, tau<sub>ref</sub>, alpha<sub>B</sub>, rho<sub>0</sub>, eta, psi, s<sub>D</sub>, "
        "N<sub>min</sub>). A full sensitivity analysis is needed to verify that the "
        "qualitative results (atrophied agent emergence, grounding advantage) are "
        "robust to calibration choices."
    ))
    story.append(P(
        "<b>LLM belief representation.</b> Current LLM agents do not maintain persistent "
        "beliefs in the sense modelled by OID. The framework assumes an external state "
        "register that tracks patterns. This is an architectural requirement, not a "
        "property of existing agents. The contribution is normative: agents <i>should</i> "
        "track beliefs this way."
    ))

    # ---- 9. CONCLUSION ----
    story.append(S("9. Conclusion"))
    story.append(P(
        "The OID framework provides the first formal dynamic model of competence degradation "
        "in autonomous AI agents. It fills a gap between security-focused frameworks "
        "(OWASP, NIST, Proofpoint) that address what agents can access and observability "
        "frameworks that track what agents do. OID models what agents <i>become</i> over "
        "time: how their accumulated operational patterns can silently create systemic "
        "harm despite passing all quality checks."
    ))
    story.append(P(
        "The atrophied agent profile - high Q<sub>obs</sub>, negative V<sub>net</sub> - is "
        "the formal capture of a failure mode that the industry has experienced but not "
        "yet named or measured. By providing computable scores derivable from existing "
        "traces, OID offers a practical path toward detection and prevention."
    ))
    story.append(P(
        "The framework and simulation code are released as open-source (MIT licence) at "
        "oid-framework v0.1.0."
    ))

    # ---- REFERENCES ----
    story.append(S("References"))
    refs = [
        "[1] Abadie, Y. (2026). Modele V4.2: Version coherente, simulation-ready, export formalise. Working paper.",
        "[2] Sculley, D. et al. (2015). Hidden Technical Debt in Machine Learning Systems. NeurIPS.",
        "[3] OWASP (2025). Top 10 for Agentic Applications 2026. genai.owasp.org.",
        "[4] Microsoft (2026). Agent Governance Toolkit. opensource.microsoft.com.",
        "[5] Proofpoint/Acuvity (2026). The Agent Integrity Framework - 2026 Edition.",
        "[6] NIST (2026). Request for Information Regarding Security Considerations for AI Agents.",
        "[7] Dell'Acqua, F. et al. (2026). Navigating the Jagged Technological Frontier. Organization Science.",
        "[8] Brynjolfsson, E., Li, D., Raymond, L.R. (2023). Generative AI at Work. NBER WP 31161.",
        "[9] Cohen, W.M. &amp; Levinthal, D.A. (1990). Absorptive Capacity. Administrative Science Quarterly.",
        "[10] Frenken, K. et al. (2007). Related Variety and Regional Economic Growth. Regional Studies.",
        "[11] Ganter, B. &amp; Wille, R. (1999). Formal Concept Analysis. Springer.",
        "[12] Lee, H.P.H. et al. (2025). The Impact of GenAI on Critical Thinking. CHI.",
        "[13] Risko, E.F. &amp; Gilbert, S.J. (2016). Cognitive Offloading. Trends in Cognitive Sciences.",
        "[14] Partnership on AI (2025). Prioritizing Real-Time Failure Detection in AI Agents.",
        "[15] International AI Safety Report (2026). internationalaisafetyreport.org.",
    ]
    for r in refs:
        story.append(Paragraph(r, styles["RefStyle"]))

    doc.build(story)
    print(f"Paper generated: {OUT}")


if __name__ == "__main__":
    build()
