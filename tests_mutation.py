"""
tests_mutation.py - does the suite actually catch anything?

A thousand passing tests prove nothing on their own. This harness breaks the
model on purpose, one edit at a time, and checks that at least one test
notices. A mutation that survives is a hole: some behaviour nobody is
watching.

CRITICAL mutations are the ones whose survival would matter most - double
counting, unit errors, a missing gate, peak confused with effective, work
attributed to the wrong module, an assumption leaking into a result. Those must
all be killed. The rest should mostly be.

Usage:  python tests_mutation.py [--quick]

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))


# ==============================================================================
# The mutations
# ==============================================================================
#
# Each is (name, file, find, replace, critical). The find string must appear
# exactly once, or the mutation is reported as INVALID rather than silently
# doing nothing - a mutation that fails to apply would look like a survivor.

MUTATIONS = [
    # --- units and conventions -------------------------------------------
    ("ops_per_mac_1", "ppact/system.py",
     "OPS_PER_MAC = 2", "OPS_PER_MAC = 1", True),
    ("bits_to_bytes_dropped", "ppact/memory.py",
     "return self.package_io_width * self.pin_speed_gbps / 8.0",
     "return self.package_io_width * self.pin_speed_gbps", True),
    ("memory_energy_bits_to_bytes", "ppact/system.py",
     "    e_memory = (dram_bytes * 8 * mem.energy_pj_per_bit * 1e-12",
     "    e_memory = (dram_bytes * mem.energy_pj_per_bit * 1e-12", True),

    # --- time accounting ---------------------------------------------------
    ("overlap_sign", "ppact/system.py",
     "    core_time = exposed_compute + exposed_memory + hidden_time\n\n    # What",
     "    core_time = exposed_compute + exposed_memory - hidden_time\n\n    # What",
     True),
    ("hidden_max_not_min", "ppact/system.py",
     "    hidden_time = overlap * min(compute_time, memory_time)\n    exposed_compute",
     "    hidden_time = overlap * max(compute_time, memory_time)\n    exposed_compute",
     True),
    ("handoff_counted_twice", "ppact/system.py",
     "offload_s = exposed_pre + npu_pre_overhead + handoff_s",
     "offload_s = exposed_pre + npu_pre_overhead + 2 * handoff_s", True),
    ("cpu_time_dropped", "ppact/system.py",
     "    latency_s = (cpu_active_s + offload_s + isp_exposed_s + core_time",
     "    latency_s = (offload_s + isp_exposed_s + core_time", True),
    ("wait_folded_into_active", "ppact/runtime.py",
     "active = min(active_per_job * jobs, total_time_ms)",
     "active = min((active_per_job + wait_per_job) * jobs, total_time_ms)", True),

    # --- pipeline ----------------------------------------------------------
    ("interval_min_not_max", "ppact/runtime.py",
     "interval_ms = max(stages.values())",
     "interval_ms = min(stages.values())", True),
    ("memory_not_a_stage_single", "ppact/runtime.py",
     '    "Memory": "Stage memory (ms)",\n}\n\n# With two engines',
     '}\n\n# With two engines', True),
    ("memory_not_a_stage_dual", "ppact/runtime.py",
     '    "Accelerator 2": "Stage accelerator 2 (ms)",\n'
     '    "Memory": "Stage memory (ms)",\n}',
     '    "Accelerator 2": "Stage accelerator 2 (ms)",\n}', True),
    ("accel_stage_includes_memory", "ppact/system.py",
     '        "Stage accelerator (ms)": (compute_time + exposed_pre\n'
     "                                   + offload_dispatch_s\n"
     "                                   + handoff_s) * 1e3,",
     '        "Stage accelerator (ms)": (core_time + offload_s) * 1e3,', True),
    ("transfer_in_two_stations", "ppact/system.py",
     "                                   + offload_dispatch_s\n"
     "                                   + handoff_s) * 1e3,",
     "                                   + npu_pre_overhead\n"
     "                                   + handoff_s) * 1e3,", True),
    ("module_active_not_stage", "ppact/runtime.py",
     '        add("Accelerator", m["Stage accelerator (ms)"],',
     '        add("Accelerator", m["Compute time (ms)"],', True),

    # --- dual accelerator --------------------------------------------------
    ("preprocess_on_primary", "ppact/system.py",
     "pre_rate = second_rate if pre_on_secondary else compute_rate",
     "pre_rate = compute_rate", True),
    ("secondary_area_dropped", "ppact/system.py",
     "second_area = second.die_area_at(accel_node) if second else 0.0",
     "second_area = 0.0", True),
    ("secondary_leakage_dropped", "ppact/system.py",
     "    second_static = _idle(second)", "    second_static = 0.0", True),
    ("module_idle_ignored", "ppact/system.py",
     "        return (stated if stated > 0\n"
     "                else engine.static_power_at(accel_node))",
     "        return engine.static_power_at(accel_node)", True),
    ("utilisation_not_derated", "ppact/system.py",
     "    compute_rate = (comp.peak_mac_per_s_at(accel_node)\n"
     "                    * comp.effective_utilization(app.total_mac, accel_node))",
     "    compute_rate = comp.peak_mac_per_s_at(accel_node) * comp.utilization",
     True),
    ("framework_charged_per_token", "ppact/system.py",
     '    if app.workload_class == "text":\n        framework_s = 0.0',
     '    if False:\n        framework_s = 0.0', True),
    ("zero_split_penalised", "ppact/system.py",
     "eff = PARALLEL_SPLIT_EFFICIENCY if actually_divided else 1.0",
     "eff = PARALLEL_SPLIT_EFFICIENCY", True),
    ("parallel_preprocess_hidden_again", "ppact/system.py",
     "        if pre_on_secondary:\n            t_s += npu_pre_time",
     "        pass", True),
    ("accuracy_averaged_not_worst", "ppact/system.py",
     "        loss = max(loss, second.accuracy_loss_pp(app.model_family))",
     "        loss = (loss + second.accuracy_loss_pp(app.model_family)) / 2", False),

    # --- memory ------------------------------------------------------------
    ("efficiency_applied_twice", "ppact/system.py",
     "bandwidth = peak_bandwidth * bw_efficiency",
     "bandwidth = peak_bandwidth * bw_efficiency * bw_efficiency", True),
    ("stacks_missing_from_bandwidth", "ppact/system.py",
     'peak_bandwidth = memres.metrics["Package peak bandwidth (GB/s)"] * n_mem * 1e9',
     'peak_bandwidth = memres.metrics["Package peak bandwidth (GB/s)"] * 1e9', True),
    ("peak_used_as_operating_point", "ppact/memory.py",
     "    @property\n    def effective_bandwidth_gbytes_s(self) -> float:\n"
     '        """What a controller actually delivers."""\n'
     "        return self.bandwidth_gbytes_s * self.bandwidth_efficiency",
     "    @property\n    def effective_bandwidth_gbytes_s(self) -> float:\n"
     '        """What a controller actually delivers."""\n'
     "        return (self.peak_pin_speed_gbps or self.pin_speed_gbps) \\\n"
     "            * self.package_io_width / 8.0 * self.bandwidth_efficiency",
     True),
    ("hbm_footprint_into_logic", "ppact/system.py",
     "                       + second_area + cpu.die_area_at(soc_node) + isp_area)",
     "                       + second_area + cpu.die_area_at(soc_node) + isp_area\n"
     "                       + mem.die_area_mm2 * n_mem)",
     True),
    ("interposer_cost_dropped", "ppact/memory.py",
     "        return (self.interposer_cost_usd + self.advanced_package_cost_usd",
     "        return (0.0 * self.interposer_cost_usd + self.advanced_package_cost_usd",
     True),

    ("memory_background_dropped", "ppact/system.py",
     "                + mem.background_power_w * n_mem * latency_s)",
     "                + 0.0 * mem.background_power_w * n_mem * latency_s)", True),

    # --- LLM ---------------------------------------------------------------
    ("llm_uses_cnn_reuse", "ppact/system.py",
     "        weight_traffic = app.weight_bytes * app.weight_read_factor",
     "        weight_traffic = app.weight_bytes * weight_fetches", True),
    ("kv_traffic_dropped", "ppact/system.py",
     "        kv_traffic = app.kv_bytes_per_token * app.context_tokens",
     "        kv_traffic = 0.0", True),
    ("prefill_scales_weights_per_token", "ppact/system.py",
     "        prefill_bytes = (app.weight_bytes * app.weight_read_factor\n"
     "                         + app.kv_bytes_per_token * app.prefill_tokens)",
     "        prefill_bytes = (app.weight_bytes * app.weight_read_factor\n"
     "                         * app.prefill_tokens)", False),

    ("serving_efficiency_dropped", "ppact/system.py",
     "        serving_overhead_s = core_time * (1.0 / LLM_SINGLE_STREAM_SERVING_EFFICIENCY - 1.0)",
     "        serving_overhead_s = 0.0", True),
    ("serving_overhead_on_vision", "ppact/system.py",
     '    if app.workload_class == "text" and 0 < LLM_SINGLE_STREAM_SERVING_EFFICIENCY < 1:',
     "    if 0 < LLM_SINGLE_STREAM_SERVING_EFFICIENCY < 1:", True),

    # --- accuracy ----------------------------------------------------------
    ("qat_reads_ptq_table", "ppact/accuracy.py",
     'QUANTISATION_LOSS_PP[(family, method, "INT8")] = v',
     'QUANTISATION_LOSS_PP[(family, method, "INT8")] = base[family][0]', True),
    ("model_family_ignored", "ppact/system.py",
     "    loss = comp.accuracy_loss_pp(app.model_family)",
     '    loss = comp.accuracy_loss_pp("cnn")', False),
    ("accuracy_gate_removed", "ppact/system.py",
     '        "accuracy": deployment_accuracy >= app.required_accuracy_pct,',
     '        "accuracy": True,', True),
    ("cooling_gate_removed", "ppact/system.py",
     '        "memory_cooling": cooling_ok,',
     '        "memory_cooling": True,', True),
    ("capacity_gate_removed", "ppact/system.py",
     '        "capacity": capacity >= app.required_memory_bytes,',
     '        "capacity": True,', True),

    # --- assumptions -------------------------------------------------------
    ("contention_always_on", "ppact/system.py",
     "        contention = DUAL_MEMORY_CONTENTION * concurrency",
     "        contention = DUAL_MEMORY_CONTENTION", False),
    ("contention_in_sequential", "ppact/system.py",
     '    if second is not None and mode == "parallel":\n'
     "        t_primary = mac_primary / compute_rate if compute_rate > 0 else 0.0",
     "    if second is not None:\n"
     "        t_primary = mac_primary / compute_rate if compute_rate > 0 else 0.0",
     False),

    ("host_change_moves_accelerator", "ppact/system.py",
     "    compute_rate = (comp.peak_mac_per_s_at(accel_node)",
     "    compute_rate = (cpu.clock_ghz / 2.4 * comp.peak_mac_per_s_at(accel_node)",
     True),

    ("host_traffic_dropped", "ppact/system.py",
     "    cpu_dram_bytes = cpu_pre_bytes + cpu_post_bytes",
     "    cpu_dram_bytes = 0.0", True),
    # Replaced at 3.54.0: the 50% cap became a 10% floor when the host got
    # its own roofline. Removing the floor is the mutation that matters now -
    # it lets one agent be starved to nothing, which is how two earlier
    # versions of this split failed.
    ("host_floor_removed", "ppact/system.py",
     "        host_bandwidth = max(bandwidth - accel_demand, bandwidth * 0.10)",
     "        host_bandwidth = max(bandwidth - accel_demand, 0.0)",
     True),
    ("infeasible_performance_still_usable", "ppact/system.py",
     "        for key in PERFORMANCE_METRICS:\n            if key in result.metrics:\n                result.metrics[key] = float(\"nan\")",
     "        for key in PERFORMANCE_METRICS:\n            if False and key in result.metrics:\n                result.metrics[key] = float(\"nan\")",
     True),
    ("infeasible_performance_zeroed", "ppact/system.py",
     '                result.metrics[key] = float("nan")',
     '                result.metrics[key] = 0.0', True),
    ("bound_strength_collapsed_to_two", "ppact/system.py",
     "    if _ratio > 4.0:", "    if _ratio > 1.0:", True),
    ("infeasible_reported_as_ok", "ppact/system.py",
     "    result.status = (STATUS_DOES_NOT_FIT if gate.get(\"capacity\") is False\n                     else status)",
     "    result.status = status", True),
    ("merge_charged_at_full_split", "ppact/system.py",
     "        actually_divided = 0.0 < active_split < 1.0",
     "        actually_divided = 0.0 < active_split <= 1.0", True),
    ("out_of_range_knob_clamped_silently", "ppact/system.py",
     "    if not (0.0 <= config.work_split <= 1.0):",
     "    if False and not (0.0 <= config.work_split <= 1.0):", True),
    ("sequential_becomes_parallel", "ppact/system.py",
     "    else:   # sequential\n        mac_secondary = app.total_mac * active_split",
     "    else:   # sequential\n        mac_secondary = 0.0 * app.total_mac * active_split",
     True),
    ("merge_penalty_dropped", "ppact/system.py",
     "        eff = PARALLEL_SPLIT_EFFICIENCY if actually_divided else 1.0",
     "        eff = 1.0", True),
    ("pair_finishes_before_its_slower_half", "ppact/system.py",
     "        compute_time = max(t_p, t_s) / eff",
     "        compute_time = min(t_p, t_s) / eff", True),
    ("offload_transfer_charged_to_the_engine", "ppact/system.py",
     '        "Stage memory (ms)": (memory_time + offload_transfer_s) * 1e3,',
     '        "Stage memory (ms)": memory_time * 1e3,', True),
    ("environment_difference_fails_the_run", "ppact/reproducibility.py",
     "    if not substantive_ok:", "    if not substantive_ok or True:", True),
    ("different_os_graded_as_same_machine", "ppact/reproducibility.py",
     '    if a.get("system") != b.get("system"):',
     '    if False and a.get("system") != b.get("system"):', True),
    ("history_grows_without_bound", "ppact/workspace.py",
     "                      + [e for e in data[\"recent\"] if e != entry])[:HISTORY_LIMIT]",
     "                      + [e for e in data[\"recent\"] if e != entry])", True),
    ("history_duplicates_entries", "ppact/workspace.py",
     "                      + [e for e in data[\"recent\"] if e != entry])[:HISTORY_LIMIT]",
     "                      + list(data[\"recent\"]))[:HISTORY_LIMIT]", False),
    ("lesson_marking_always_correct", "ppact/lessons.py",
     "    elif chosen == right:\n        print(f\"  Correct.\")",
     "    elif True:\n        print(f\"  Correct.\")", True),
    ("duplicate_demo_key_unchecked", "ppact/demo.py",
     "        if d.key in seen:", "        if False and d.key in seen:", True),
    ("quiz_two_correct_answers_unchecked", "ppact/lessons.py",
     "        if len(right) != 1:", "        if False and len(right) != 1:",
     True),
    ("demo_table_width_unchecked", "ppact/demo.py",
     "        if rendered > 78:", "        if False and rendered > 78:", True),
    ("failing_design_gets_ranked", "ppact/challenge.py",
     "    if not all(met):\n        return {\"passes\": False",
     "    if False and not all(met):\n        return {\"passes\": False", True),
    ("rank_counted_against_everything", "ppact/challenge.py",
     "    better = sum(1 for s in pop[\"solutions\"]",
     "    better = sum(1 for s in pop[\"feasible\"]", True),
    ("framework_claims_unchecked", "ppact/framework.py",
     "            if it.metric and not _metric_exists(it.metric):",
     "            if False and not _metric_exists(it.metric):", True),
    ("absent_item_may_claim_something", "ppact/framework.py",
     "                if it.metric or it.function:",
     "                if False and (it.metric or it.function):", True),
    ("menu_loops_without_input", "ppact/modes.py",
     '            print(f"  (no input available - stopping)")\n            return 0',
     '            print(f"  (no input available)")\n            return default',
     True),
    # --- logical consistency mutations ----------------------------------
    # Each disables one contradiction rule. A rule that can be removed
    # without anything noticing is a rule that was not doing anything.
    ("lc_capacity_may_be_ready", "tests_logical_consistency.py",
     "    if have < need and passes:",
     "    if False and have < need and passes:", True),
    ("lc_status_may_contradict_violations", "tests_logical_consistency.py",
     "                if passes and gates:",
     "                if False and passes and gates:", True),
    ("lc_breakdown_residue_ignored", "tests_logical_consistency.py",
     "    if abs(residue) > 1e-9:",
     "    if abs(residue) > 1e9:", True),
    ("lc_accelerator_may_be_recommended_under_host_limit",
     "tests_logical_consistency.py",
     "    if names_accel and top.share_pct >= 60 and \"accelerator\" not in \\",
     "    if False and names_accel and top.share_pct >= 60 and \"accelerator\" not in \\",
     True),
    ("lc_score_may_move_physics", "tests_logical_consistency.py",
     "    if differing:\n        return False, (\n            f\"Priority contradiction:",
     "    if False and differing:\n        return False, (\n            f\"Priority contradiction:",
     True),
    ("lc_chart_may_plot_another_design", "tests_logical_consistency.py",
     "            if abs(plotted - raw) > 1e-9:",
     "            if abs(plotted - raw) > 1e9:", True),
    ("lc_score_may_imply_deployability", "tests_logical_consistency.py",
     "    if implied:",
     "    if False and implied:", True),

    # --- standard review contract mutations ------------------------------
    # Each removes one guarantee the review contract exists to give.
    ("review_margin_band_ignored", "ppact/visual/text.py",
     "            if r.over:\n                verdict = f\"EXCEEDS by",
     "            if False and r.over:\n                verdict = f\"EXCEEDS by",
     True),
    ("review_requirement_direction_dropped", "ppact/visual/text.py",
     '            kind = "max" if r.lower_is_better else "min"',
     '            kind = "max"', True),
    ("review_scope_line_removed", "ppact/review.py",
     '    out.append("     Scope: the current design only")\n    out.append("")\n    lim = a.limiting',
     '    lim = a.limiting', True),
    ("review_starting_point_caveat_removed", "ppact/review.py",
     '                "easier to interpret. It is NOT a recommended architecture, "',
     '                "easier to interpret. It is the usual choice, "', True),
    ("review_clipping_raw_value_hidden", "ppact/visual/balance.py",
     '                out.append(f"    raw value      {ax.raw:.4g} {ax.unit}   "',
     '                out.append(f"    raw value      hidden   "', True),

    # --- process node display mutations ----------------------------------
    ("node_vendor_key_shown_again", "ppact/process.py",
     "        return self.display_name or self.name",
     "        return self.name", True),
    ("node_string_sort_restored", "ppact/process.py",
     "        return -self.node_nm",
     "        return 0.0", True),
    ("node_description_folded_into_name", "ppact/process.py",
     '"N7", "7 nm", display_name="7nm", node_nm=7.0,',
     '"N7", "7 nm", display_name="7nm (mainstream)", node_nm=7.0,', True),
    ("node_selection_origin_dropped", "ppact/review.py",
     '        return f"{node_name(chosen)}  (selected)"',
     '        return f"{node_name(chosen)}"', True),
    ("node_comparison_column_narrowed", "ppact/review.py",
     "        W = 30",
     "        W = 24", True),

    # --- documentation mutations ---------------------------------------
    # Eight ways a document could drift from the program. Each disables a
    # guard in the AUDIT rather than editing a document, because a mutation
    # that edited README.md would leave the tree dirty for every mutation
    # after it.
    ("docs_dead_application_unchecked", "tests_docs.py",
     "            check(P, f\"{doc}: `{key}` is not a retired application name\",",
     "            if False: check(P, f\"{doc}: `{key}` ok\",", True),
    ("docs_retired_term_unchecked", "tests_docs.py",
     "            check(P, f\"{doc}: retired term {term!r} is gone\", hit is None,",
     "            check(P, f\"{doc}: retired term {term!r} is gone\", True,", True),
    ("docs_balance_formula_unchecked", "tests_docs.py",
     "              f\"{anchor.at_zero:g}\" in text and f\"{anchor.at_hundred:g}\"\n              in text,",
     "              True,", True),
    ("docs_not_established_unchecked", "tests_docs.py",
     "        check(P, f\"{item!r} is stated somewhere as not established\", found,",
     "        check(P, f\"{item!r} is stated somewhere as not established\", True,",
     True),
    ("docs_version_mismatch_unchecked", "tests_docs.py",
     "    check(P, \"the manifest states the product version\",\n          man[\"product_version\"] == ppact.PRODUCT_VERSION,",
     "    check(P, \"the manifest states the product version\",\n          True,", True),
    ("docs_hardcoded_count_unchecked", "tests_docs.py",
     "        check(P, \"README carries no hard-coded validation count\",\n              not counts, str(counts[:3])",
     "        check(P, \"README carries no hard-coded validation count\",\n              True, str(counts[:3])", True),
    ("docs_informational_claim_unchecked", "tests_docs.py",
     "        check(P, f\"{doc}: host connection is marked informational\",\n              \"informational\" in text.lower(),",
     "        check(P, f\"{doc}: host connection is marked informational\",\n              True,", True),
    ("docs_missing_mode_unchecked", "tests_docs.py",
     "    check(P, \"the modes it lists are the modes that exist\",\n          man[\"public_modes\"] == [m.title for m in modes.MODES],",
     "    check(P, \"the modes it lists are the modes that exist\",\n          True,", True),
    ("about_opens_with_the_boundary", "ppact/about.py",
     'REQUIRED_ORDER = ("purpose", "method", "evolution", "boundary",\n                  "interpretation")',
     'REQUIRED_ORDER = ("boundary", "purpose", "method", "evolution",\n                  "interpretation")',
     True),
    ("host_connection_status_dropped", "ppact/arch_classes.py",
     "    out += [f\"                   {line}\"\n            for line in _wrap(HOST_CONNECTION_STATUS, 56)]",
     "    out += []", True),
    ("banner_version_hardcoded", "ppact/branding.py",
     'title = f"{PRODUCT_NAME} (v{PRODUCT_VERSION})"',
     'title = "AI System PPACT Studio (v9.9)"', True),
    ("contention_not_applied_to_the_share", "ppact/system.py",
     "            accel_bandwidth = accel_bandwidth * (1.0 - contention)",
     "            accel_bandwidth = accel_bandwidth", True),
    ("history_keeps_duplicates", "ppact/workspace.py",
     "                      + [e for e in data[\"recent\"] if e != entry])[:HISTORY_LIMIT]",
     "                      + [e for e in data[\"recent\"]])[:HISTORY_LIMIT]", True),
    ("history_unbounded", "ppact/workspace.py",
     "[:HISTORY_LIMIT]", "[:10000]", True),
    ("search_ignores_concepts", "ppact/workspace.py",
     "    for word, tasks in CONCEPTS.items():",
     "    for word, tasks in {}.items():", True),
    ("gap_not_limit_minus_real", "ppact/decide.py",
     "        return self.bound_gain_pct - self.best_gain_pct",
     "        return self.bound_gain_pct", True),
    ("whatif_compares_to_the_last_change", "ppact/decide.py",
     "        print_whatif(app_key, base_cfg, cfg, changed)",
     "        print_whatif(app_key, cfg, cfg, changed)", True),
    ("handover_omits_the_decision", "ppact/decide.py",
     '    "The facts are the tool\'s. The decision is the designer\'s.",',
     '    "The facts are the tool\'s.",', True),
    ("memory_given_an_invented_bound", "ppact/decide.py",
     "        out.append(Ceiling(lever, None, None, best_gain, best_lat,",
     "        out.append(Ceiling(lever, 50.0, 1.0, best_gain, best_lat,", True),
    ("efficiency_not_the_ratio", "ppact/decide.py",
     "        eff = (best_gain / bound_gain * 100) if bound_gain > 1e-9 else None",
     "        eff = 100.0 if bound_gain > 1e-9 else None", True),
    ("cost_rate_not_divided", "ppact/decide.py",
     "                        o.gain_pct / o.cost_delta))",
     "                        o.gain_pct))", True),
    ("headroom_bound_inflated", "ppact/decide.py",
     "        out.append(Headroom(name, v / total * 100, total - v,",
     "        out.append(Headroom(name, v / total * 100, total - v * 2,", True),
    ("options_estimated_not_measured", "ppact/decide.py",
     "        out.append(Option(label, change, lat, (1 - lat / b_lat) * 100, cost,",
     "        out.append(Option(label, change, lat * 0.9, (1 - lat / b_lat) * 100, cost,",
     True),
    ("confidence_ignores_reversals", "ppact/decide.py",
     "                if sign != baseline_sign:", "                if False:",
     True),
    ("verdict_printed_before_reasons", "ppact/decide.py",
     '    print(f"\\n  WHY:")', '    print(f"\\n  zWHY:")', True),
    ("breakdown_drops_a_term", "ppact/decide.py",
     '    ("engine hand-off", "Handoff (ms)",',
     '    ("engine hand-off", "Handoff (ms)__gone",', True),
    ("residue_hidden_from_the_reader", "ppact/decide.py",
     "        if abs(residue) > 1e-6:", "        if False and abs(residue) > 1e-6:",
     True),
    ("small_change_called_robust", "ppact/decide.py",
     "    if change < margin_fraction:", "    if change < 0.0:", True),
    ("ranking_not_ordered_by_time", "ppact/decide.py",
     "    return sorted(parts, key=lambda x: -x[1])",
     "    return sorted(parts, key=lambda x: x[1])", True),
    ("answer_shown_on_first_wrong_guess", "ppact/lessons.py",
     "        if attempt < ATTEMPTS_BEFORE_ANSWER:",
     "        if False and attempt < ATTEMPTS_BEFORE_ANSWER:", True),
    ("later_attempt_overwrites_first_guess", "ppact/progress.py",
     "            if a.lesson not in out:", "            if True:", True),
    ("improvement_reported_on_one_answer", "ppact/progress.py",
     "        if len(early) < 2 or len(late) < 2:",
     "        if len(early) < 1 or len(late) < 1:", True),
    ("easy_mode_compares_to_the_first_row", "ppact/lessons.py",
     "            prev = rows[idx - 1][1] if idx else None",
     "            prev = rows[0][1] if idx else None", True),
    ("lesson_two_change_rule_unchecked", "ppact/lessons.py",
     "            if n > MAX_CHANGES_PER_STEP:",
     "            if False and n > MAX_CHANGES_PER_STEP:", True),
    ("grouped_fields_counted_separately", "ppact/lessons.py",
     "            decisions += 1\n            remaining -= group",
     "            decisions += 0\n            remaining -= set()", True),
    ("first_screen_vocabulary_unchecked", "ppact/modes.py",
     "            if word in text:", "            if False and word in text:",
     True),
    ("mode_line_length_unchecked", "ppact/modes.py",
     "        if len(rendered) > 78:", "        if False and len(rendered) > 78:",
     True),
    ("certify_skips_the_interpreter_check", "certify.py",
     "    if not _check_interpreter():", "    if True or not _check_interpreter():",
     True),
    ("certify_skips_the_layout_check", "certify.py",
     "    if not _check_layout():", "    if True or not _check_layout():",
     True),
    ("package_hash_ignores_a_file", "ppact/reproducibility.py",
     "    files = sorted(f for f in os.listdir(out_dir) if f != \"evidence_hash.txt\")\n    body = \"\\n\".join(",
     "    files = []\n    body = \"\\n\".join(", True),
    ("coefficient_digest_ignores_values", "ppact/reproducibility.py",
     "        json.dumps([(c[\"name\"], c[\"live\"]) for c in coeffs],",
     "        json.dumps([(c[\"name\"], 0) for c in coeffs],", True),
    ("seed_difference_not_reported", "ppact/reproducibility.py",
     "    if ref.get(\"seed\") != now.get(\"seed\"):",
     "    if False and ref.get(\"seed\") != now.get(\"seed\"):", True),
    ("memory_energy_leaks_into_latency", "ppact/system.py",
     "    accel_demand = dram_bytes / core_time if core_time > 0 else 0.0",
     "    accel_demand = dram_bytes / core_time * (1.0 + mem.energy_pj_per_bit / 50.0) if core_time > 0 else 0.0",
     True),
    ("liveness_ignores_dead_coefficients", "ppact/sensitivity.py",
     "        dead = [m for m in spec[\"affects\"]",
     "        dead = [] or [m for m in ()", True),
    ("liveness_ignores_leaks", "ppact/sensitivity.py",
     "        leaks = [m for m in spec[\"must_not_affect\"]",
     "        leaks = [] or [m for m in ()", True),
    ("locality_coefficient_ignored", "ppact/system.py",
     "                     * HOST_LOCALITY_EXPOSURE",
     "                     * 1.0", True),
    ("rank_flip_reported_as_stable", "ppact/sensitivity.py",
     "        outcome = RANK_FLIP",
     "        outcome = STABLE", True),
    ("sensitivity_uses_only_the_nominal", "ppact/sensitivity.py",
     "    pts = [low + i * step for i in range(n)]",
     "    pts = [nominal for i in range(n)]", True),
    ("sensitivity_low_and_high_swapped", "ppact/sensitivity.py",
     "def _samples(low, nominal, high, n=21):",
     "def _samples(high, nominal, low, n=21):", True),
    ("flip_point_outside_the_pair", "ppact/sensitivity.py",
     "                flip = (v1 + v2) / 2.0",
     "                flip = (v1 + v2) * 2.0", True),
    ("no_influence_never_detected", "ppact/sensitivity.py",
     "    if values and spread <= abs(scale) * 1e-9:",
     "    if False and values and spread <= abs(scale) * 1e-9:", True),
    ("contract_names_a_metric_that_does_not_exist", "ppact/system.py",
     '        "Accelerator active power (W)", family="power",',
     '        "Accel power (W)", family="power",', True),
    ("single_job_rate_put_back_in_throughput", "ppact/system.py",
     '        "Single-job rate (inf/s)", family="host pipeline rate",',
     '        "Single-job rate (inf/s)", family="throughput",', True),
    ("boundary_contract_drops_a_stage", "ppact/system.py",
     'PIPELINE_STAGES = ("sensor", "isp", "host preprocess", "dispatch",',
     'PIPELINE_STAGES = ("sensor", "host preprocess", "dispatch",', True),
    ("isp_left_out_of_sensor_to_control", "ppact/system.py",
     '        "Sensor-to-control (ms)": (latency_s * 1e3 + isp_active_s * 1e3',
     '        "Sensor-to-control (ms)": (latency_s * 1e3 + 0.0 * isp_active_s',
     True),
    ("contradicting_chain_printed_anyway", "ppact/explain.py",
     "        if chain_contradicts(chain, am, bm):",
     "        if False and chain_contradicts(chain, am, bm):", True),
    ("chain_test_ignores_latency", "ppact/explain.py",
     "        and bm[\"Latency (ms)\"] >= am[\"Latency (ms)\"] * (1 - NEGLIGIBLE)",
     "        and True", True),
    ("bus_share_reports_achieved_not_allocated", "ppact/system.py",
     "            (bandwidth - accel_bandwidth) / bandwidth * 100.0",
     "            (cpu_dram_bytes / max(cpu_active_s, 1e-12)) / bandwidth * 100.0",
     True),
    ("isp_left_out_of_the_interval", "ppact/system.py",
     "        isp_active_s,\n        memory_time + offload_transfer_s,",
     "        0.0,\n        memory_time + offload_transfer_s,", True),
    ("cpu_left_out_of_the_interval", "ppact/system.py",
     "    _stations = (\n        cpu_active_s,", "    _stations = (\n        0.0,",
     True),
    ("fixed_jobs_use_the_window", "ppact/runtime.py",
     "        total_time_ms = fill_ms + interval_ms * jobs",
     "        total_time_ms = window_ms", True),
    ("fill_charged_per_job", "ppact/runtime.py",
     "        total_time_ms = fill_ms + interval_ms * jobs",
     "        total_time_ms = (fill_ms + interval_ms) * jobs", True),
    ("framework_charged_for_idle_engine", "ppact/system.py",
     "        secondary_runs = second is not None and (",
     "        secondary_runs = second is not None or (", True),
    ("gated_engine_still_runs", "ppact/system.py",
     "    if secondary_gated:\n        # Powered down: it runs nothing, whatever the knobs say.\n        active_split = active_share = 0.0",
     "    if False:\n        # Powered down: it runs nothing, whatever the knobs say.\n        active_split = active_share = 0.0",
     True),
    ("gated_engine_costs_nothing", "ppact/system.py",
     "    second_static = _idle(second) * (GATED_LEAKAGE_FRACTION\n                                     if secondary_gated else 1.0)",
     "    second_static = _idle(second) * (0.0\n                                     if secondary_gated else 1.0)", True),
    ("handoff_charged_at_zero_split", "ppact/system.py",
     "        handoff_s = DUAL_DISPATCH_US * 1e-6 if actually_divided else 0.0",
     "        handoff_s = DUAL_DISPATCH_US * 1e-6", True),
    ("alternative_share_ignored", "ppact/system.py",
     "        mac_secondary = app.total_mac * active_share",
     "        mac_secondary = app.total_mac * 0.5", True),
    ("capacity_reads_latency", "ppact/system.py",
     '        "Pipeline capacity (inf/s)": (1e3 / pipeline_interval_ms',
     '        "Pipeline capacity (inf/s)": (throughput * 0 + 1e3 / metrics_latency_placeholder',
     True),
    ("delivered_ignores_arrival_rate", "ppact/system.py",
     "        \"Delivered throughput (inf/s)\": min(",
     "        \"Delivered throughput (inf/s)\": max(", True),
    ("interval_is_sum_not_max", "ppact/system.py",
     "    pipeline_interval_ms = max(_stations) * 1e3",
     "    pipeline_interval_ms = sum(_stations) * 1e3", True),
    ("host_states_collapsed", "ppact/system.py",
     "HOST_BALANCE_BAND = 0.25", "HOST_BALANCE_BAND = 0.0", True),
    ("host_hidden_inverted", "ppact/system.py",
     "    cpu_hidden_s = HOST_MEMORY_OVERLAP * min(cpu_compute_s, cpu_transfer_s)",
     "    cpu_hidden_s = HOST_MEMORY_OVERLAP * max(cpu_compute_s, cpu_transfer_s)",
     True),
    ("host_roofline_dropped", "ppact/system.py",
     "    cpu_active_s = cpu_compute_s + cpu_transfer_s - cpu_hidden_s",
     "    cpu_active_s = cpu_compute_s", True),

    # --- CPU ---------------------------------------------------------------
    ("dispatch_scales_with_work", "ppact/system.py",
     "    dispatch_s = cpu.dispatch_overhead_us * 1e-6\n\n    if app.workload_class",
     "    dispatch_s = cpu.dispatch_overhead_us * 1e-6 * app.streams\n\n    if app.workload_class",
     False),
    ("nms_always_applied", "ppact/system.py",
     "        nms_factor = 3.0 if app.uses_nms else 1.0",
     "        nms_factor = 3.0", False),
    ("cpu_clock_ignored", "ppact/cpu.py",
     "        return self.clock_ghz * 1e9 * self.cores * self.parallel_efficiency",
     "        return 1e9 * self.cores * self.parallel_efficiency", True),

    # --- process -----------------------------------------------------------
    ("sram_scales_like_logic", "ppact/compute.py",
     "return self.sram_area_mm2 * get_node(node).sram_area",
     "return self.sram_area_mm2 * get_node(node).logic_area", False),
    ("peak_tops_not_node_adjusted", "ppact/system.py",
     '        "Peak TOPS": comp.peak_mac_per_s_at(accel_node) * OPS_PER_MAC / 1e12,',
     '        "Peak TOPS": comp.peak_tops,', True),
]


# ==============================================================================
# Runner
# ==============================================================================

# STOP AT THE FIRST FAILURE.
#
# A mutation is killed the moment any check notices it; running the remaining
# forty paths afterwards tells us nothing and costs the same as running them
# for a survivor. With the model suite past four thousand checks that turned
# the whole run into a quadratic - 129 mutations times the full suite - and it
# stopped finishing inside any sensible budget.
#
# Coverage is unchanged. A killed mutation is killed whichever check caught
# it, and a SURVIVOR still runs every path, which is the only case where
# running them all matters.
TIER1 = """
import sys, io, contextlib
sys.path.insert(0, {root!r})
import tests_model as M
verdict = "SURVIVED"
for fn in ({paths}):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            fn()
    except Exception:
        verdict = "KILLED"
        break
    if any(not ok for _, _, ok, _ in M.RESULTS):
        verdict = "KILLED"
        break
print(verdict)
"""

PATHS = ("M.path_g, M.path_h, M.path_i, M.path_j, M.path_k, M.path_l, M.path_m, "
         "M.path_n, M.path_o, M.path_p, M.path_q, M.path_r, M.path_s, M.path_t, "
         "M.path_u, M.path_v, M.path_w, M.path_x, M.path_y, M.path_z, "
         "M.path_aa, M.path_ab, M.path_ac, M.path_ad, M.path_ae, M.path_af, "
         "M.path_ag, M.path_ah, M.path_ai, M.path_aj, M.path_ak, M.path_al, "
         "M.path_am, M.path_an, M.path_ao, M.path_ap, M.path_aq, M.path_ar, M.path_as, M.path_at, M.path_au, M.path_av, M.path_aw, M.path_ax, M.path_ay, M.path_az, M.path_yy, M.path_xw, M.path_zz")
# NOTE: this list has been forgotten twice, each time leaving hundreds of new
# checks outside mutation coverage while the totals still looked healthy.
# tests_model.py asserts that every path_* function defined there appears
# here, so a third time fails a test rather than passing silently.

DIFFERENTIAL = """
import sys, io, contextlib
sys.path.insert(0, {root!r})
import tests_differential as D
for fn in (D.test_pipeline_forms_agree, D.test_runtime_matches_event_simulation,
           D.test_memory_bound_never_exceeded, D.test_public_reference_by_hand):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            fn()
    except Exception:
        pass
print("KILLED" if any(not ok for _, ok, _ in D.RESULTS) else "SURVIVED")
"""

SCENARIOS = """
import sys, io, contextlib
sys.path.insert(0, {root!r})
import tests_scenarios as S
try:
    with contextlib.redirect_stdout(io.StringIO()):
        S.main()
except SystemExit:
    pass
except Exception:
    pass
print("KILLED" if any(not ok for _, ok, _ in S.RESULTS) else "SURVIVED")
"""

CORNER = """
import sys, io, contextlib
sys.path.insert(0, {root!r})
import tests_corner as C
for fn in (C.path_a, C.path_b, C.path_c, C.path_d, C.path_e, C.path_f):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            fn()
    except Exception:
        pass
print("KILLED" if any(not ok for _, _, ok, _ in C.RESULTS) else "SURVIVED")
"""


def apply_mutation(workdir, path, find, replace):
    full = os.path.join(workdir, path)
    with open(full, encoding="utf-8") as fh:
        text = fh.read()
    count = text.count(find)
    if count != 1:
        return False, count
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(text.replace(find, replace))
    return True, 1


def run_one(name, path, find, replace, critical, quick):
    work = tempfile.mkdtemp(prefix="mut_")
    try:
        dest = os.path.join(work, "PPACT_Simulator")
        shutil.copytree(HERE, dest)
        ok, count = apply_mutation(dest, path, find, replace)
        if not ok:
            return "INVALID", f"pattern appears {count} times"
        script = TIER1.format(root=dest, paths=PATHS)
        p = subprocess.run([sys.executable, "-c", script], capture_output=True,
                           text=True, timeout=900, cwd=dest)
        out = p.stdout.strip().splitlines()
        verdict = out[-1] if out else "ERROR"
        for extra in (DIFFERENTIAL, SCENARIOS, CORNER):
            if verdict != "SURVIVED" or quick:
                break
            p2 = subprocess.run([sys.executable, "-c", extra.format(root=dest)],
                                capture_output=True, text=True, timeout=600, cwd=dest)
            o2 = p2.stdout.strip().splitlines()
            if o2 and o2[-1] == "KILLED":
                verdict = "KILLED"
        if verdict not in ("KILLED", "SURVIVED"):
            return "ERROR", (p.stderr or p.stdout)[-200:]
        return verdict, ""
    except subprocess.TimeoutExpired:
        return "TIMEOUT", ""
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    quick = "--quick" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    muts = [m for m in MUTATIONS if not only or m[0] in only]

    print("=" * 78)
    print(" MUTATION TESTING")
    print("=" * 78)
    print(f"  {len(muts)} mutations. A SURVIVOR is a behaviour nothing watches.\n")

    # CHECKPOINT.
    #
    # Three runs of this suite ended without writing anything: no OOM in
    # dmesg, no accumulated children, no signal observed. The cause is not
    # established, and raising a timeout would only postpone the silence.
    #
    # What can be fixed without knowing the cause is the silence itself. A
    # verdict is recorded the moment it is reached, so a run that ends
    # mid-way leaves an account of how far it got.
    from ppact.mutation_checkpoint import Checkpoint
    cp = Checkpoint(".", registered=len(muts))
    done = cp.resume_from()
    if done:
        print(f"  {cp.resume_reason}\n")
    elif getattr(cp, "resume_reason", "") not in ("", "no checkpoint"):
        print(f"  starting fresh: {cp.resume_reason}\n")

    results = []
    for name, path, find, replace, critical in muts:
        if name in done:
            prior = done[name]
            results.append((name, critical, prior.get("status", "KILLED"),
                            prior.get("detail", "")))
            print(f"  {'CRITICAL' if critical else '        '} "
                  f"{name:<36s}{'(from checkpoint)':<14s}")
            continue
        cp.begin(name, target_rule="mutation suite")
        t0 = time.time()
        verdict, detail = run_one(name, path, find, replace, critical, quick)
        cp.finish(name, verdict, time.time() - t0, detail=detail)
        results.append((name, critical, verdict, detail))
        tag = "CRITICAL" if critical else "        "
        mark = {"KILLED": "killed", "SURVIVED": "SURVIVED <-",
                "INVALID": "INVALID", "ERROR": "ERROR", "TIMEOUT": "TIMEOUT"}[verdict]
        print(f"  {tag} {name:<36s}{mark:<14s}{time.time() - t0:5.0f}s"
              + (f"  {detail}" if detail else ""))

    total = len(results)
    killed = sum(1 for _, _, v, _ in results if v == "KILLED")
    crit = [r for r in results if r[1]]
    crit_killed = sum(1 for _, _, v, _ in crit if v == "KILLED")
    survivors = [r for r in results if r[2] == "SURVIVED"]
    invalid = [r for r in results if r[2] in ("INVALID", "ERROR", "TIMEOUT")]
    cp.finalise({
        "killed_mutants": killed,
        "survived_mutants": len(survivors),
        "critical_mutants": len(crit),
        "critical_killed": crit_killed,
        "invalid_mutants": len(invalid),
    })

    print("\n" + "=" * 78)
    print(f"  overall kill rate   {killed}/{total} "
          f"({killed / max(total, 1) * 100:.0f}%)   target 90%")
    print(f"  critical kill rate  {crit_killed}/{len(crit)} "
          f"({crit_killed / max(len(crit), 1) * 100:.0f}%)   target 100%")
    if survivors:
        print(f"\n  SURVIVORS - nothing tests these:")
        for name, critical, _, _ in survivors:
            print(f"    {'CRITICAL ' if critical else ''}{name}")
    if invalid:
        print(f"\n  did not apply:")
        for name, _, v, d in invalid:
            print(f"    {name}: {v} {d}")
    print("=" * 78)
    return 0 if (crit_killed == len(crit) and killed >= total * 0.9) else 1


if __name__ == "__main__":
    sys.exit(main())
