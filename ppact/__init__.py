"""
ppact - PPACT analysis for AI semiconductor technology planning

Semiconductor School course package for AI Semiconductor Technology Planning.

Two levels of analysis share one scoring framework:

    component level   compare DRAM technologies against each other
    system level      pick an application, assemble CPU + Compute + Memory,
                      and find out whether the product ships

Quick start
-----------
    from ppact import run_application, list_applications
    list_applications()
    run_application("drone")

    from ppact import compare_memories
    compare_memories(["LPDDR5", "GDDR6", "HBM3E"])

Module map
----------
    core         Anchor scoring, environment detection, figure helpers
    process      process nodes and the derating factors between them
    memory       MemorySpec, MEMORY_LIBRARY, wafer/yield, component PPACT
    compute      ComputeSpec, COMPUTE_LIBRARY
    accuracy     quantisation loss by model family and method
    revisions    why model parameters changed
    coefficients every number that was chosen rather than derived
    validation   the model against published products
    crossval     external cases split into calibration and holdout
    interpret    is this number ordinary for this kind of product
    gold         fixed scenarios, and what each can actually settle
    migration    what must be true when a design moves
    economics    the cost that does not depend on how many you build
    explain      why the number changed, not just what it is
    sensitivity  which conclusions survive their assumptions
    reproducibility  what ran, on what, and whether a rerun agrees
    evidence     how much weight each figure can carry
    industry     real company cases and what the model cannot express
    memory_sweep HBM3E against HBM4, with the effects kept apart
    preprocess   where each preprocessing function runs
    cpu          CPUSpec, CPU_LIBRARY
    application  Application, APPLICATION_LIBRARY (workload + budgets)
    system       roofline, constraint gate, system scoring
    report       all text output
    charts       all matplotlib output
    workflow     the run_* convenience functions
    game         the simplified guided flow students use
    runtime      Phase 3: many jobs, pipeline, utilisation, dashboard
    designs      starting points and design examples
    innovation   the Innovation Challenge: evidence, rubric, report

Adding a technology means adding one dataclass entry to the matching library.
No branching logic anywhere needs editing.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from .core import Anchor, in_notebook, in_colab, set_figure_scale, PALETTE
from .process import (ProcessNode, NODE_LIBRARY, PROFILES, REFERENCE_NODE,
                      COST_REFERENCE_NODE, get_node, print_node_table,
                      print_profiles)
from .memory import (
    MemorySpec, MEMORY_LIBRARY, PPACTResult, ANCHORS, AXIS_ORDER,
    evaluate, evaluate_wafer,
)
from .compute import ComputeSpec, COMPUTE_LIBRARY
from .accuracy import (QUANTISATION_LOSS_PP, quantisation_loss_pp,
                       canonical_precision, print_table as print_accuracy_table)
from .revisions import REVISIONS, print_revisions
from .coefficients import (COEFFICIENTS, Coefficient, print_coefficients,
                          provenance)
from .validation import REFERENCES, print_validation, run as run_validation
from .crossval import (CASES as CROSSVAL_CASES, TOLERANCE_PCT,
                       print_crossval, by_set)
from .interpret import (RANGES, DOMAINS, interpret, explain_metric,
                        from_measurement)
from .migration import (MIGRATIONS, check_migration,
                        check_all as check_migrations,
                        node_sweep, cheapest_node, design_type_nodes,
                        DESIGN_TYPES)
from .economics import (economics, break_even, print_economics,
                        print_break_even, node_decision, node_and_memory,
                        memory_options, host_options, allocation_sweep,
                        reduction_check, compare_proposal,
                        stack_marginal_utility, memory_choice,
                        context_sweep, quantisation_sweep, batch_sweep,
                        model_size_sweep, prompt_ratio_sweep,
                        moe_comparison, MODEL_SIZES,
                        QUANT_BYTES, QUANT_ACCURACY_COST_PP,
                        DESIGN_REUSE,
                        MIGRATION_DISTANCE, RESPIN_RISK, IP_PORTING)
from .reproducibility import (build_manifest, fingerprint,
                             write_package, verify,
                             coefficient_snapshot, GRADES,
                             package_hash, certified_run,
                             print_evidence_status,
                             EVIDENCE_STATUS,
                             CERTIFIED_RUN_CONDITIONS, grade_run,
                             CERTIFIED_SEED)
from .sensitivity import (run_sweep, run_all as run_sensitivity,
                          build_sweeps, ROBUST_PASS, ROBUST_FAIL,
                          CONDITIONAL, BOUNDARY_ADJACENT,
                          NO_INFLUENCE, handoff_break_even,
                          handoff_ranking, ranking_stability,
                          print_ranking, coefficient_liveness,
                          STABLE, RANK_FLIP, PARTIALLY_STABLE,
                          memory_energy_common_scale,
                          memory_energy_relative)
from .explain import (CHAINS, why, decision_explanation,
                      CONTEXT_BINDING_GATES, suggest_chain,
                      chain_contradicts)
from .gold import (SCENARIOS as GOLD_SCENARIOS, run_gold, run_all_gold,
                   LEVELS as VALIDATION_LEVELS, PROMOTION_CRITERIA,
                   print_promotion_queue)
from .evidence import (EVIDENCE, LEVELS as EVIDENCE_LEVELS,
                       print_evidence, level_of)
from .industry import (CASES as INDUSTRY_CASES, BENCHMARKS,
                      gap_report, print_case, run_case,
                      power_gap_report, LATENCY_BOUNDARIES,
                      revalidate, revalidate_all)
from .memory_sweep import (COMPARISONS, compare as compare_memory_generations,
                           sweep_memories as sweep_memory_generations)
from .preprocess import (PREPROCESS_FUNCTIONS, MODES as PREPROCESSING_MODES,
                         print_modes as print_preprocessing_modes)
from .cpu import CPUSpec, CPU_LIBRARY
from .application import (Application, APPLICATION_LIBRARY,
                          make_custom_application, print_provenance,
                          REQUIREMENT_PROVENANCE)
from .system import (
    gate_causes, print_gate_causes, show, rank, print_infeasible,
    METRIC_BOUNDARIES, PIPELINE_STAGES, SYSTEM_PARTS, FAMILY_SCOPE,
    check_metric_boundaries,
    print_metric_boundaries,
    OPS_PER_MAC, SystemConfig, SystemResult, evaluate_system, score_system,
    default_candidates, SYSTEM_ANCHORS, SYSTEM_AXES, AUTOMOTIVE_QUALIFIED_MEMORY,
)
from .report import (
    print_memory_report, print_comparison, print_anchor_table,
    print_gate, print_analysis,
)
from .charts import (
    render_spider, render_block_diagram, render_bars, render_system_spider,
)
from .runtime import (simulate, print_dashboard, compare_runs,
                      explain_latency_delta, print_secondary_activity,
                      print_work_split_analysis, explore_memory,
                      print_llm_traffic, serving_band,
                      RuntimeResult, ModuleState, STAGES)
from .designs import (DESIGNS, DesignOption, designs_for, reference_of,
                      print_designs, compare_with_examples)
from .innovation import (REFERENCE_DESIGNS, reference_design, describe_design,
                        evaluate_proposal, print_proposal, print_rubric,
                        print_innovation_report, system_score,
                        grading_weights,
                        reference_score, print_calibration, REFERENCE_BAND,
                        print_requirements,
                        REFERENCE_PLATFORMS, GRADING_WEIGHTS, RUBRIC)
from .game import (play, show_result, show_memory, compare_designs, score_design,
                   evaluate_with_precision, PRECISION_OPTIONS, AXES as GAME_AXES)
from .workflow import (
    run_application, compare_memories, list_applications, list_libraries,
    sweep,
)
from .workspace import remember, recent, export_csv, print_workspace
from .demo import DEMOS, print_demo, demo_violations
from .challenge import CHALLENGES, print_challenge, challenge_violations
from .framework import FRAMEWORK, print_framework, framework_violations
from .decide import (explain as explain_change, report_markdown,
                     BANNED_ALONE, headroom, design_review,
                     confidence_evidence, try_options, ceilings,
                     cost_effectiveness, whatif, print_handover)
from .progress import Progress, print_progress, print_score, print_certificate
from .lessons import LESSONS, print_lesson, lesson_violations
from .guided import (build_questions, key_takeaway,
                     guided_comparison)
from .about import (SECTIONS as ABOUT_SECTIONS, CORE_PRINCIPLES,
                    about_text, print_about, about_violations)
from .arch_classes import (ACCELERATOR_CLASSES, MEMORY_CLASSES,
                           print_registry, registry_violations,
                           coverage_metrics)
from .branding import (PRODUCT_NAME, PRODUCT_VERSION, RELEASE_LABEL,
                       banner, print_banner)
from .modes import MODES, print_main_menu, first_screen_violations
from .menu import main_menu

__version__ = "4.19.0"

__all__ = [
    "PRODUCT_NAME", "PRODUCT_VERSION", "RELEASE_LABEL",
    "banner", "print_banner",
    "ACCELERATOR_CLASSES", "MEMORY_CLASSES", "print_registry",
    "registry_violations", "coverage_metrics",
    "MODES", "print_main_menu", "first_screen_violations",
    "LESSONS", "print_lesson", "lesson_violations",
    "Progress", "print_progress", "print_score", "print_certificate",
    "explain_change", "report_markdown", "BANNED_ALONE",
    "headroom", "design_review", "confidence_evidence", "try_options",
    "ceilings", "cost_effectiveness", "whatif", "print_handover",
    "FRAMEWORK", "print_framework", "framework_violations",
    "CHALLENGES", "print_challenge", "challenge_violations",
    "DEMOS", "print_demo", "demo_violations",
    "remember", "recent", "export_csv", "print_workspace",
    "Anchor", "in_notebook", "in_colab", "set_figure_scale", "PALETTE",
    "ProcessNode", "NODE_LIBRARY", "PROFILES", "REFERENCE_NODE",
    "COST_REFERENCE_NODE", "get_node", "print_node_table", "print_profiles",
    "MemorySpec", "MEMORY_LIBRARY", "PPACTResult", "ANCHORS", "AXIS_ORDER",
    "evaluate", "evaluate_wafer",
    "ComputeSpec", "COMPUTE_LIBRARY", "CPUSpec", "CPU_LIBRARY",
    "QUANTISATION_LOSS_PP", "quantisation_loss_pp", "canonical_precision",
    "print_accuracy_table", "REVISIONS", "print_revisions",
    "COEFFICIENTS", "Coefficient", "print_coefficients", "provenance",
    "gate_causes", "print_gate_causes", "show", "rank", "print_infeasible",
    "METRIC_BOUNDARIES", "PIPELINE_STAGES", "SYSTEM_PARTS",
    "FAMILY_SCOPE", "check_metric_boundaries",
    "print_metric_boundaries",
    "REFERENCES", "print_validation", "run_validation",
    "CROSSVAL_CASES", "TOLERANCE_PCT", "print_crossval", "by_set",
    "RANGES", "DOMAINS", "interpret", "explain_metric", "from_measurement",
    "build_manifest", "fingerprint", "write_package", "verify",
    "coefficient_snapshot", "GRADES", "CERTIFIED_SEED",
    "package_hash", "certified_run", "print_evidence_status",
    "EVIDENCE_STATUS", "CERTIFIED_RUN_CONDITIONS", "grade_run",
    "run_sweep", "run_sensitivity", "build_sweeps",
    "ROBUST_PASS", "ROBUST_FAIL", "CONDITIONAL",
    "BOUNDARY_ADJACENT", "NO_INFLUENCE", "handoff_break_even",
    "handoff_ranking", "ranking_stability", "print_ranking",
    "coefficient_liveness", "STABLE", "RANK_FLIP",
    "PARTIALLY_STABLE", "memory_energy_common_scale",
    "memory_energy_relative",
    "CHAINS", "why", "decision_explanation", "CONTEXT_BINDING_GATES",
    "suggest_chain", "chain_contradicts",
    "MIGRATIONS", "check_migration", "check_migrations",
    "node_sweep", "cheapest_node", "design_type_nodes", "DESIGN_TYPES",
    "economics", "break_even", "print_economics", "print_break_even",
    "node_decision", "node_and_memory", "memory_options", "host_options", "allocation_sweep",
    "reduction_check", "compare_proposal", "stack_marginal_utility", "memory_choice",
    "context_sweep", "quantisation_sweep", "batch_sweep",
    "model_size_sweep", "prompt_ratio_sweep", "moe_comparison",
    "MODEL_SIZES",
    "QUANT_BYTES", "QUANT_ACCURACY_COST_PP",
    "DESIGN_REUSE", "MIGRATION_DISTANCE", "RESPIN_RISK", "IP_PORTING",
    "GOLD_SCENARIOS", "run_gold", "run_all_gold", "VALIDATION_LEVELS",
    "PROMOTION_CRITERIA", "print_promotion_queue",
    "EVIDENCE", "EVIDENCE_LEVELS", "print_evidence", "level_of",
    "INDUSTRY_CASES", "BENCHMARKS", "gap_report", "print_case", "run_case",
    "power_gap_report", "LATENCY_BOUNDARIES", "revalidate",
    "revalidate_all",
    "COMPARISONS", "compare_memory_generations", "sweep_memory_generations",
    "PREPROCESS_FUNCTIONS", "PREPROCESSING_MODES", "print_preprocessing_modes",
    "Application", "APPLICATION_LIBRARY", "make_custom_application",
    "print_provenance", "REQUIREMENT_PROVENANCE",
    "OPS_PER_MAC", "SystemConfig", "SystemResult", "evaluate_system", "score_system",
    "default_candidates", "SYSTEM_ANCHORS", "SYSTEM_AXES",
    "AUTOMOTIVE_QUALIFIED_MEMORY",
    "print_memory_report", "print_comparison", "print_anchor_table",
    "print_gate", "print_analysis",
    "render_spider", "render_block_diagram", "render_bars", "render_system_spider",
    "run_application", "compare_memories", "list_applications", "list_libraries",
    "sweep", "main_menu",
    "DESIGNS", "DesignOption", "designs_for", "reference_of",
    "print_designs", "compare_with_examples",
    "REFERENCE_DESIGNS", "reference_design", "describe_design",
    "evaluate_proposal", "print_proposal", "print_rubric",
    "print_innovation_report",
    "system_score", "grading_weights", "reference_score", "print_requirements",
    "print_calibration", "REFERENCE_BAND", "REFERENCE_PLATFORMS",
    "GRADING_WEIGHTS", "RUBRIC",
    "simulate", "print_dashboard", "compare_runs", "RuntimeResult",
    "explain_latency_delta", "print_secondary_activity",
    "print_work_split_analysis", "explore_memory", "print_llm_traffic",
    "serving_band",
    "ModuleState", "STAGES",
    "play", "show_result", "show_memory", "compare_designs", "score_design",
    "evaluate_with_precision", "PRECISION_OPTIONS", "GAME_AXES",
    "__version__",
]
