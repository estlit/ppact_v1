"""
ppact.system - roofline, constraint gate, system scoring

Combines an application with a CPU + Compute + Memory candidate.

Axes do not compose the same way. Power, area and cost are additive across
blocks; performance is a bottleneck (a min), and thermal is a spatial
property of where the heat leaves. Summing all five is the classic error.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Dict, List, Optional, Sequence, Tuple

from .core import Anchor
from .application import Application, APPLICATION_LIBRARY
from .compute import COMPUTE_LIBRARY
from .cpu import CPU_LIBRARY
from .memory import MEMORY_LIBRARY, evaluate as evaluate_memory
from .process import get_node, PROFILES
from . import preprocess as pp

# --- Dual-accelerator execution ----------------------------------------------
#
# Two accelerators are not one accelerator twice as fast. Both dies exist for
# the whole run, so area, cost and leakage are paid whatever they are doing;
# work has to be handed between them; and splitting a workload is never
# perfectly efficient. Without those three terms the model would say that
# adding silicon always helps, which is the opposite of what it should teach.
EXECUTION_MODES = ("single", "sequential", "parallel", "alternative")

DUAL_DISPATCH_US = 60.0          # per job, per hand-off between engines
PARALLEL_SPLIT_EFFICIENCY = 0.85  # partitioning, synchronisation, merge

# TWO DISTINCT EFFECTS, KEPT APART
#
# 1. SHARED BANDWIDTH SATURATION is already in the roofline and needs no
#    parameter. Splitting the arithmetic across two engines shortens the
#    compute term and leaves the transfer term untouched, so on a narrow bus
#    the gain saturates: for the same pair, parallel execution saves 0.98 ms on
#    HBM and only 0.25 ms on a single LPDDR5 package. That is a model result.
#
# 2. CONTROLLER CONTENTION ESTIMATE is this coefficient: an allowance for loss
#    under concurrent requests that the bandwidth arithmetic does not capture.
#    Deliberately not attributed to a mechanism. There is no bank model here,
#    no row-buffer policy and no arbitration, so naming row locality as the
#    cause would describe a simulation that does not exist. What can honestly
#    be said is that two masters cost something extra and this is an estimate
#    of how much.
#
# The distinction matters because the SIGN FLIP - parallel becoming slower than
# not splitting at all - comes entirely from (2). It is a consequence of a
# number chosen here, not something the model produced on its own, and it
# should be read that way. Scaled by concurrency so that an engine doing
# nothing alongside another pays nothing: the penalty is a function of how much
# the two actually overlap, not a flat charge for having two.
DUAL_MEMORY_CONTENTION = 0.12

# How much of the host's own memory traffic hides behind its arithmetic.
# Preprocessing is sequential and prefetches well, which argues for a high
# figure; sharing a bus with an accelerator argues for a lower one. Checked
# across 0.70 to 0.92 - no starting point changes verdict, so nothing rests
# on the exact value. It lives here rather than inside the function so that it
# can be registered as a coefficient and moved by a test.
HOST_MEMORY_OVERLAP = 0.70

# What the host reads and writes per pixel, and how much of it reaches DRAM.
# A frame arrives as three bytes and leaves as a four-byte tensor; the
# exposure factor is the fraction that is not absorbed by cache. At 1.0 every
# byte goes to memory, which is the worst case and not the usual one.
HOST_BYTES_PER_PIXEL_IN = 3.0
HOST_BYTES_PER_PIXEL_OUT = 4.0
HOST_LOCALITY_EXPOSURE = 1.0

# Within this fraction either side of equal, the host is BALANCED rather than
# limited by one or the other. Two states would call a ratio of 1.02 a
# memory-limited host and send a student shopping for memory.
HOST_BALANCE_BAND = 0.25

# SCOPE: single-stream autoregressive decode. Not a hardware property. It moves
# with model size, batch, context length, sampling, framework, card count and
# tensor parallelism, and the name says single-stream so that nobody reaches
# for it when the question is about concurrency.
#
# What a real serving stack delivers against the memory ceiling, for TEXT
# workloads only. Without it the model produced 93% of the theoretical rate,
# and published single-user figures for an 8B model on a 1.5 TB/s part sit at
# 40-60 tokens per second against a ceiling of 92 (FP16) to 181 (FP8) - a
# quarter to a half. The missing losses are a continuous-batching scheduler,
# sampling and detokenisation, framework dispatch per token, and memory the
# arithmetic does not see. None of them is modelled individually; this is an
# allowance for all of them together, and it is an assumption, not a mechanism.
# A BAND, not a number. Two published deployments bracket it at 0.28-0.32 if
# their weights are FP8 or 0.54-0.64 if FP16, and neither states the precision.
# Forcing one value inside that ambiguity would be a guess dressed as a
# calibration, so the model carries three and reports what each gives.
#
# The default is the TYPICAL entry. It was 0.55 - the optimistic end of a
# single reading - until a second deployment showed that reading was not
# supported.
LLM_SERVING_EFFICIENCY_BAND = {"low": 0.30, "typical": 0.45, "high": 0.60}
LLM_SINGLE_STREAM_SERVING_EFFICIENCY = LLM_SERVING_EFFICIENCY_BAND["typical"]

# One definition of an operation for the whole model. A multiply-accumulate is
# counted as TWO operations, which is the convention every TOPS figure in the
# libraries assumes. Mixing this with a one-op convention halves or doubles
# every performance number in the system, silently.
OPS_PER_MAC = 2

# Result status. A configuration that cannot be evaluated says so rather than
# scoring zero: a silent zero is indistinguishable from a bad design, and the
# student cannot tell which they are looking at.
STATUS_OK = "OK"
STATUS_NO_DRAM_TRAFFIC = "NO_DRAM_TRAFFIC"
STATUS_ZERO_BANDWIDTH = "INVALID_CONFIGURATION: ZERO_EFFECTIVE_BANDWIDTH"
STATUS_ZERO_COMPUTE = "INVALID_CONFIGURATION: ZERO_COMPUTE_RATE"
# A model that does not fit in memory cannot run at any speed. Reporting a
# token rate for it describes a machine that cannot exist, and a student
# comparing 4 tokens per second against 35 would be comparing an impossible
# design with a possible one as though they were both options.
STATUS_DOES_NOT_FIT = "INFEASIBLE: MODEL_DOES_NOT_FIT_IN_MEMORY"

# What a design that cannot hold its model has no answer for. Everything here
# describes RUNNING; everything not here describes the board, and a board that
# cannot run the model still has an area, a price and a cooling class.
PERFORMANCE_METRICS = (
    "Latency (ms)", "Single-job rate (inf/s)", "Throughput (inf/s)",
    "Pipeline capacity (inf/s)", "Delivered throughput (inf/s)",
    "Pipeline interval (ms)", "Compute time (ms)", "Memory time (ms)",
    "Energy per inference (mJ)", "Compute data-wait (ms)",
    "End-to-end latency (ms)", "Pure inference (ms)",
    "Sensor-to-control (ms)", "Ideal core time (ms)",
    "Delivered core time (ms)",
)


# specified for datacenter environments and is not offered in a grade that
# survives an under-hood temperature cycle. This single fact removes HBM from
# automotive designs before any performance number is considered.
AUTOMOTIVE_QUALIFIED_MEMORY = {"LPDDR5", "GDDR6"}


@dataclass(frozen=True)
class SystemConfig:
    cpu: str
    compute: str
    memory: str
    memory_devices: int = 1
    # None means "use what this product family would actually be built on".
    # A node belongs to a die: with integration="monolithic" the accelerator is
    # forced onto the host node, because they are the same piece of silicon.
    soc_node: Optional[str] = None
    accel_node: Optional[str] = None
    integration: Optional[str] = None
    profile: Optional[str] = None       # named preset from ppact.process.PROFILES
    # None derives the overlap from the accelerator's buffering and tiling.
    # Setting 1.0 reproduces the perfect-overlap assumption the model used
    # before this existed, which is useful for seeing what it was hiding.
    overlap_ratio: Optional[float] = None
    # An interface narrower than the memory itself caps what reaches the
    # accelerator. This stands in for a bus model rather than being one: no
    # queues, no arbitration, just a ceiling.
    interface_bandwidth_gbytes_s: Optional[float] = None
    # Where the preprocessing runs. This is the decision a student actually
    # makes: not whether to add an accelerator, but which work moves onto one.
    preprocessing_mode: str = "cpu_only"
    # A second accelerator, and how the two share the work.
    #   sequential   one after the other on the same job
    #   parallel     the inference is split between them
    #   alternative  one engine or the other per job, never both
    secondary_compute: Optional[str] = None
    # Installed and powered down is NOT the same as absent. A gated engine
    # keeps its area and its purchase price and loses its leakage; an absent
    # one costs nothing at all. Treating the two as one state teaches that
    # "we do not use it" and "we do not fit it" have the same PPACT, and they
    # do not.
    secondary_enabled: bool = True
    execution_mode: str = "sequential"
    work_split: float = 0.5          # share of inference on the secondary
    alternative_share: float = 0.5   # share of JOBS handled by the secondary
    # One hand-off for all streams, or one per stream. The fixed cost is per
    # call, so this multiplies it.
    # HOW THE ACCELERATOR REACHES ITS HOST. Descriptive only in this
    # release, and the word "only" is load-bearing.
    #
    # Published products deploy the same silicon as a bare SoC, a USB stick,
    # a PCIe card, a module and a box. The library had no way to say which,
    # so a user who knows those products found the Studio silent about the
    # first decision they make.
    #
    # NOTHING IN THE ENGINE READS THIS FIELD. No latency term, no bandwidth,
    # no power, no cost, no gate. A check evaluates every design at every
    # host connection and requires that every metric come out identical to
    # the last digit - so a design built before this field existed produces
    # exactly the figures it did then.
    #
    # It is here because exposing a modern option and saying plainly that it
    # is not yet analysed is better than either omitting it or pretending.
    # A link that IS modelled would change the latency decomposition, which
    # is verified to zero residue across 180 configurations, and that is a
    # separate phase.
    host_connection: str = "on_board"
    offload_batching: bool = True
    # None uses the memory type's own figure. A student can override it to see
    # what a better or worse controller and access pattern are worth.
    bandwidth_efficiency: Optional[float] = None

    def resolve(self, app):
        """Return (soc_node, accel_node, integration) for this candidate."""
        if self.profile:
            p = PROFILES[self.profile]
            soc, accel, integ = p["soc_node"], p["accel_node"], p["integration"]
        else:
            soc = self.soc_node or app.default_soc_node
            integ = self.integration or app.integration
            accel = self.accel_node or app.default_accel_node
        if integ == "monolithic":
            # One die cannot carry two processes. The host node wins, because
            # that is the die being taped out.
            accel = soc
        return soc, accel, integ

    @property
    def label(self) -> str:
        """Every block appears, including the CPU.

        Two candidates differing only in host processor are genuinely different
        designs: the CPU contributes die area, and in a tight SoC budget that
        alone decides pass or fail. A label that hides it makes a sweep look
        like it contains duplicate rows.
        """
        m = MEMORY_LIBRARY[self.memory].name
        suffix = f" x{self.memory_devices}" if self.memory_devices > 1 else ""
        if self.profile:
            tag = f" [{self.profile}]"
        elif self.soc_node or self.accel_node:
            from .process import node_name as _nn
            tag = f" @{_nn(self.soc_node)}/{_nn(self.accel_node)}"
        else:
            tag = ""
        return (f"{CPU_LIBRARY[self.cpu].name} + "
                f"{COMPUTE_LIBRARY[self.compute].name} + {m}{suffix}{tag}")


@dataclass
class SystemResult:
    app: Application
    config: SystemConfig
    metrics: Dict[str, float] = field(default_factory=dict)
    gate: Dict[str, bool] = field(default_factory=dict)
    scores: Dict[str, float] = field(default_factory=dict)
    bound_by: str = ""
    # Five levels, because a two-way label called a design that gains 26% from
    # a faster memory by the same name as one that gains nothing.
    bound_strength: str = "balanced"
    compute_memory_ratio: float = 1.0
    # Three states for the HOST: compute-limited, balanced,
    # memory-limited. Two would call a ratio of 1.02 a
    # memory-limited host and send a student shopping.
    host_state: str = "compute-limited"
    soc_node: str = ""
    accel_node: str = ""
    integration: str = ""
    execution_mode: str = "single"
    status: str = "OK"
    arithmetic_intensity: Optional[float] = None

    @property
    def is_valid(self) -> bool:
        return not self.status.startswith("INVALID")

    @property
    def passes(self) -> bool:
        return all(self.gate.values())

    @property
    def label(self) -> str:
        return self.config.label


def evaluate_system(app: Application, config: SystemConfig) -> SystemResult:
    cpu = CPU_LIBRARY[config.cpu]
    comp = COMPUTE_LIBRARY[config.compute]
    second = (COMPUTE_LIBRARY[config.secondary_compute]
              if config.secondary_compute else None)
    secondary_gated = second is not None and not config.secondary_enabled
    mode = (config.execution_mode if second else "single")
    if mode not in EXECUTION_MODES:
        raise KeyError(f"Unknown execution mode '{mode}'. "
                       f"Available: {', '.join(EXECUTION_MODES)}")
    # The two share parameters are not interchangeable and were easy to
    # confuse, so only the one that applies is read and the other is reported
    # as zero rather than silently ignored:
    #   work_split         fraction of ONE JOB's arithmetic on the secondary
    #   alternative_share  fraction of JOBS routed to the secondary
    # A 0.5 work_split halves every job; a 0.5 alternative_share sends every
    # other job elsewhere. They produce different latencies and different
    # energy, and reading the wrong one would be invisible in the output.
    # An out-of-range knob is a MISTAKE, not a value to be tidied. Clamping it
    # silently gave a student who typed 1.5 the answer for 1.0 and no reason to
    # wonder why - which is the opposite of what a teaching model should do.
    if not (0.0 <= config.work_split <= 1.0):
        raise ValueError(
            f"work_split must be between 0 and 1, got {config.work_split}. "
            f"It is the fraction of ONE job's arithmetic placed on the "
            f"secondary engine, so a value outside that range does not "
            f"describe anything.")
    if not (0.0 <= config.alternative_share <= 1.0):
        raise ValueError(
            f"alternative_share must be between 0 and 1, got "
            f"{config.alternative_share}. It is the fraction of JOBS routed to "
            f"the secondary engine.")

    if secondary_gated:
        # Powered down: it runs nothing, whatever the knobs say.
        active_split = active_share = 0.0
    elif mode == "alternative":
        active_split, active_share = 0.0, min(1.0, max(0.0, config.alternative_share))
    elif mode in ("sequential", "parallel"):
        active_split, active_share = min(1.0, max(0.0, config.work_split)), 0.0
    else:
        active_split = active_share = 0.0
    mem = MEMORY_LIBRARY[config.memory]
    soc_node, accel_node, integration = config.resolve(app)
    memres = evaluate_memory(mem)
    n_mem = config.memory_devices

    # Effective, not peak. Using the pin-rate figure would move the roofline
    # ridge point by a quarter and quietly turn memory-bound designs into
    # compute-bound ones - the single most misleading simplification available
    # in a model like this.
    bw_efficiency = (config.bandwidth_efficiency
                     if config.bandwidth_efficiency is not None
                     else mem.bandwidth_efficiency)
    peak_bandwidth = memres.metrics["Package peak bandwidth (GB/s)"] * n_mem * 1e9
    # Filled in below once the two engines' turns are known; the roofline needs
    # a bandwidth first, so contention is applied as a second pass.
    bandwidth = peak_bandwidth * bw_efficiency
    contention = 0.0
    if config.interface_bandwidth_gbytes_s:
        bandwidth = min(bandwidth, config.interface_bandwidth_gbytes_s * 1e9)
    capacity = memres.metrics["Package capacity (GB)"] * n_mem * 1e9

    # --- DRAM traffic --------------------------------------------------------
    # Activations spill to DRAM whenever the live working set exceeds on-chip
    # SRAM. This is the single term that makes buffer size matter, and it is
    # why a bigger MAC array without a bigger buffer buys very little.
    # Reuse is architectural, not just a matter of buffer size. effective_sram
    # is the buffer weighted by how well the schedule exploits it, so a shader
    # array and a systolic array with identical SRAM no longer produce identical
    # DRAM traffic - which is the single largest difference between a GPU and an
    # NPU running the same network.
    if comp.effective_sram_kb <= 0:
        reload_factor = 8.0
    else:
        reload_factor = max(1.0, app.activation_working_set_kb / comp.effective_sram_kb)

    # Weights are fetched once by a stationary schedule and re-fetched by an
    # engine that cannot pin them.
    weight_fetches = 1.0 / comp.dataflow_efficiency
    if app.workload_class == "text":
        # Autoregressive decode. Weights are read once per token by
        # construction - there is nothing to reuse - so the convolution model
        # above does not apply and is deliberately bypassed rather than
        # parameterised away.
        weight_traffic = app.weight_bytes * app.weight_read_factor
        kv_traffic = app.kv_bytes_per_token * app.context_tokens
        other_traffic = app.activation_bytes
        dram_bytes = weight_traffic + kv_traffic + other_traffic
        reload_factor = 1.0
        weight_fetches = app.weight_read_factor
    else:
        weight_traffic = app.weight_bytes * weight_fetches
        kv_traffic = 0.0
        other_traffic = app.activation_bytes * app.streams * reload_factor
        dram_bytes = weight_traffic + other_traffic

    # --- Roofline ------------------------------------------------------------
    # Utilisation reached on THIS workload, not the engine's best case.
    compute_rate = (comp.peak_mac_per_s_at(accel_node)
                    * comp.effective_utilization(app.total_mac, accel_node))
    second_rate = (second.peak_mac_per_s_at(accel_node)
                   * second.effective_utilization(app.total_mac, accel_node)
                   if second else 0.0)

    # --- preprocessing offloaded to an accelerator ---------------------------
    #
    # Sized first, because in parallel mode it shares an engine with part of the
    # inference and the two CANNOT run at once on the same array. Computing the
    # split first and then hiding preprocessing behind it double-booked the
    # secondary: it appeared to do its share of the arithmetic and the
    # preprocessing in the same instant.
    pixels_per_stream = app.input_pixels if app.workload_class == "vision" else 0.0
    total_pixels = pixels_per_stream * app.streams
    npu_pre_time = npu_pre_overhead = 0.0
    npu_pre_macs = 0.0
    offload_calls = 0
    offload_dispatch_s = offload_transfer_s = 0.0
    pre_on_secondary = False
    if app.workload_class == "vision" and pp.uses_npu_preprocessing(config.preprocessing_mode):
        npu_pre_macs = total_pixels * pp.npu_mac_per_pixel(config.preprocessing_mode)
        # With a second engine the preprocessing runs there - which is the whole
        # reason a vision NPU exists. On one engine it competes with inference.
        pre_on_secondary = second is not None
        pre_rate = second_rate if pre_on_secondary else compute_rate
        npu_pre_time = npu_pre_macs / pre_rate if pre_rate > 0 else 0.0
        offload_calls = 1 if config.offload_batching else max(1, app.streams)
        offload_dispatch_s = offload_calls * pp.NPU_PREPROCESS_DISPATCH_US * 1e-6
        offload_transfer_s = (total_pixels * 3.0 / bandwidth) if bandwidth > 0 else 0.0
        npu_pre_overhead = offload_dispatch_s + offload_transfer_s

    # How the inference itself divides, and what that costs to co-ordinate.
    handoff_s = 0.0
    if second is None:
        mac_primary, mac_secondary = app.total_mac, 0.0
        compute_time = app.total_mac / compute_rate if compute_rate > 0 else 0.0
    elif mode == "parallel":
        mac_secondary = app.total_mac * active_split
        mac_primary = app.total_mac - mac_secondary
        t_p = mac_primary / compute_rate if compute_rate > 0 else 0.0
        t_s = mac_secondary / second_rate if second_rate > 0 else 0.0
        # Preprocessing occupies the secondary too, so it is added to that
        # engine's turn rather than hidden behind it.
        if pre_on_secondary:
            t_s += npu_pre_time
        # The slower half sets the pace, and the split is not free: partition,
        # synchronise, merge. An efficiency of one here would make two engines
        # exactly twice as good, which no partitioned workload ever is.
        # The partitioning penalty is charged only where there is a partition.
        # With work_split at zero the secondary is doing preprocessing beside
        # the inference, not a share of it - there is nothing to synchronise or
        # merge, and charging for it made overlapping preprocessing look slower
        # than not overlapping it.
        # BOTH endpoints run on one engine. A split of 0 puts everything on
        # the primary and a split of 1 puts everything on the secondary, and
        # neither divides a job - so neither pays to partition, synchronise or
        # merge. Charging at 0 was fixed at 3.59.0; the same error sat at 1,
        # where a job entirely on the secondary was costing 18% for a merge
        # with nothing to merge against.
        actually_divided = 0.0 < active_split < 1.0
        eff = PARALLEL_SPLIT_EFFICIENCY if actually_divided else 1.0
        compute_time = max(t_p, t_s) / eff
        handoff_s = DUAL_DISPATCH_US * 1e-6 if actually_divided else 0.0
    elif mode == "alternative":
        # Only one engine runs per job. The other still exists, still leaks,
        # and still had to be bought.
        #
        # The compute time below is a MEAN over jobs, not any one job's. With
        # a fast and a slow engine the distribution is bimodal - some jobs take
        # the fast path and some the slow one - and NO job experiences the
        # average. A percentile would say something different and this model
        # does not compute one.
        mac_secondary = app.total_mac * active_share
        mac_primary = app.total_mac * (1.0 - active_share)
        t_p = mac_primary / compute_rate if compute_rate > 0 else 0.0
        t_s = mac_secondary / second_rate if second_rate > 0 else 0.0
        compute_time = t_p + t_s
    else:   # sequential
        mac_secondary = app.total_mac * active_split
        mac_primary = app.total_mac - mac_secondary
        t_p = mac_primary / compute_rate if compute_rate > 0 else 0.0
        t_s = mac_secondary / second_rate if second_rate > 0 else 0.0
        compute_time = t_p + t_s
        handoff_s = DUAL_DISPATCH_US * 1e-6
    status = STATUS_OK
    if bandwidth <= 0:
        status = STATUS_ZERO_BANDWIDTH
    memory_time = dram_bytes / bandwidth if bandwidth > 0 else 0.0
    # Explicit overlap. The model previously took max(compute, memory), which is
    # the perfect-overlap corner of this expression and made data-wait zero by
    # construction - it could not have reported a stall even where one plainly
    # existed.
    #
    #   overlap 1.0  ->  max(compute, memory)   transfer fully hidden
    #   overlap 0.0  ->  compute + memory       fetch, compute, fetch again
    overlap = (config.overlap_ratio if config.overlap_ratio is not None
               else comp.overlap_ratio)
    # Clamped rather than trusted. An overlap outside 0..1 has no physical
    # meaning, and left unclamped it produced a negative hidden time and a
    # latency longer than fully serial execution - a number with no reading.
    overlap = min(1.0, max(0.0, overlap))
    hidden_time = overlap * min(compute_time, memory_time)
    exposed_compute = compute_time - hidden_time
    exposed_memory = memory_time - hidden_time
    core_time = exposed_compute + exposed_memory + hidden_time

    # What the accelerator spends waiting for operands. Note the deliberate
    # asymmetry: the memory side is reported as transfer time, never as a stall.
    # Separating "idle because nothing was requested" from "blocked in a queue"
    # needs a queueing model this does not have, and inventing the distinction
    # would put an unfounded number on the screen.
    compute_data_wait = exposed_memory
    total_exposed = exposed_compute + exposed_memory
    if total_exposed > 0:
        compute_contribution = exposed_compute / total_exposed * 100.0
        memory_contribution = exposed_memory / total_exposed * 100.0
    else:
        compute_contribution = memory_contribution = 0.0

    # --- CPU work -------------------------------------------------------------
    #
    # Three stages, each split into a fixed setup and a workload-proportional
    # part. Dispatch stays fixed by definition: it is the cost of starting a
    # job, not of doing one, and Phase 3 needs that separation to distinguish a
    # pipeline interval from a per-run overhead.
    cpu_rate = cpu.cycles_per_second_at(soc_node)
    dispatch_s = cpu.dispatch_overhead_us * 1e-6

    if app.workload_class == "text":
        pre_cycles = cpu.fixed_preprocess_cycles + app.tokens_per_inference * cpu.cycles_per_token * 0.3
        post_cycles = cpu.fixed_postprocess_cycles + app.tokens_per_inference * cpu.cycles_per_token * 0.7
    else:
        pixels = app.input_pixels * app.streams
        nms_factor = 3.0 if app.uses_nms else 1.0
        cpu_share, isp_share, npu_share = pp.split(config.preprocessing_mode)
        pre_cycles = (cpu.fixed_preprocess_cycles
                      + pixels * cpu.cycles_per_pixel * cpu_share)
        post_cycles = (cpu.fixed_postprocess_cycles
                       + app.output_elements * cpu.cycles_per_output_element * nms_factor)

    preprocess_s = pre_cycles / cpu_rate if cpu_rate > 0 else 0.0
    postprocess_s = post_cycles / cpu_rate if cpu_rate > 0 else 0.0
    # Graph launch, runtime and driver cost. Charged per inference for a
    # vision pipeline, which launches a graph per frame - and NOT per token for
    # autoregressive decode, which launches once and iterates. Charging it per
    # token took 20% off an LLM's rate for a cost it does not pay.
    if app.workload_class == "text":
        framework_s = 0.0
    else:
        framework_s = comp.framework_overhead_ms * 1e-3
        # Only for an engine that actually LAUNCHES something. This is a graph
        # launch per frame, not a driver that exists - an engine given no work
        # launches no graph, and charging it made a declared-but-unused
        # secondary cost 0.25 ms a frame for a dispatch that never happens.
        secondary_runs = second is not None and (
            active_split > 0 or active_share > 0 or pre_on_secondary)
        if secondary_runs:
            framework_s += second.framework_overhead_ms * 1e-3
    cpu_compute_s = preprocess_s + dispatch_s + postprocess_s + framework_s
    cpu_active_s = cpu_compute_s

    # --- What the HOST moves through the same DRAM ---------------------------
    #
    # The CPU had no memory traffic at all, which cannot be true of anything
    # that touches pixels. Preprocessing reads a raw frame and writes a
    # normalised tensor; post-processing reads the output and writes a much
    # smaller result. Those bytes cross the same bus as the accelerator's.
    #
    # Where the work moves to an ISP or an accelerator the host stops paying
    # for it - a second reason to offload, on top of the time, and one nobody
    # can see while the host is assumed to move no data.
    BYTES_PER_PIXEL_IN = 3.0
    BYTES_PER_PIXEL_OUT = 4.0
    on_host = not (pp.uses_isp(config.preprocessing_mode)
                   or pp.uses_npu_preprocessing(config.preprocessing_mode))
    cpu_pre_bytes = (total_pixels
                     * (HOST_BYTES_PER_PIXEL_IN + HOST_BYTES_PER_PIXEL_OUT)
                     * HOST_LOCALITY_EXPOSURE
                     if on_host else 0.0)
    cpu_post_bytes = (app.output_elements * app.streams * 8.0
                      if app.workload_class == "vision" else 0.0)
    cpu_dram_bytes = cpu_pre_bytes + cpu_post_bytes

    # The accelerator sees what is left of the bus while the host works. The
    # two are separate agents - the accelerator does not wait for the host's
    # reads - so this is a narrower bus, not a longer queue. Capped at half:
    # a host that could saturate the bus alone is a different problem, and
    # this model does not represent it.
    # --- and whether the HOST is waiting for those bytes ---------------------
    #
    # The host's time was cycles over rate and nothing else, so a CPU moving
    # 140 MB never waited for a single one of them. It has the same roofline
    # the accelerator has: it cannot finish faster than its own transfers, and
    # a host that is memory bound does not get faster when you give it more
    # cores.
    #
    # The host's share of the bus is what is left after the accelerator, for
    # the same reason the accelerator's is what is left after the host: two
    # agents, one bus. The split is by demand, which is the simplest rule that
    # gives neither of them the whole thing.
    # Each agent asks for the rate its own work implies. If the two together
    # fit on the bus, neither waits and neither is throttled - a rule that
    # divides the bus by demand alone starves whichever agent asks for less,
    # which produced a host with 0.35 MB of traffic waiting 1.35 ms for it.
    # The accelerator takes the rate its own work implies, capped so it can
    # never own the whole bus; the host gets what is left. Splitting by demand
    # alone was circular - the host's transfer time came out exactly equal to
    # its compute time by construction, so it could never be memory bound no
    # matter how narrow the bus.
    # Each agent may use whatever the OTHER one is not asking for, floored so
    # neither can be starved to nothing. Two earlier attempts got this wrong in
    # opposite directions: dividing by demand alone made the host's transfer
    # time equal its compute time by construction, so it could never be memory
    # bound; capping the accelerator at its own demand throttled it to exactly
    # the rate it had asked for, so spare bandwidth went unused.
    # MEM-ARB-001 WAS ATTEMPTED HERE AND REVERTED.
    #
    # The complaint was real: the accelerator takes the rate its own work
    # implies and the host gets the remainder, so a 3.2% aggregate
    # over-demand cut the host's bandwidth in half and a FASTER accelerator
    # made the design 59% slower.
    #
    #     NPU 32x32   H 19.39 + A 37.80 = 57.19  <= B 73.73
    #     NPU 64x64   H 19.39 + A 56.68 = 76.07  >  B 73.73
    #                 host allocation 19.39 -> 9.64 GB/s
    #
    # Demand-proportional sharing was written, and capping the host at
    # host_demand made host transfer time equal host compute time to four
    # decimals - identically, by construction:
    #
    #     transfer = bytes / (bytes / compute) = compute
    #
    # because host_demand is not a demand. It is
    #
    #     the rate at which transfers would finish exactly as compute does
    #
    # derived FROM cpu_compute_s, not from anything the host can pull. Fed
    # into arbitration it makes the host incapable of being memory bound
    # whatever the bus is, which is the failure the comment two attempts
    # ago recorded.
    #
    # Arbitrating on a quantity that is not a demand cannot be made correct
    # by choosing a better arbitration rule. A HOST MEMORY DEMAND MODEL has
    # to exist first - a rate the host would draw if nothing stopped it,
    # defined the same way the accelerator's is - and only then can the two
    # be compared.
    #
    # Until that exists this stays as it was, with its behaviour recorded
    # rather than quietly corrected:
    #
    #     KNOWN DEFECT  MEM-ARB-000
    #     accelerator-priority residual allocation; small aggregate
    #     over-demand starves the host disproportionately.
    accel_demand = dram_bytes / core_time if core_time > 0 else 0.0
    host_demand = cpu_dram_bytes / cpu_compute_s if cpu_compute_s > 0 else 0.0
    if bandwidth <= 0 or cpu_dram_bytes <= 0:
        host_bandwidth, accel_bandwidth = 0.0, bandwidth
    else:
        host_bandwidth = max(bandwidth - accel_demand, bandwidth * 0.10)
        host_bandwidth = min(host_bandwidth, bandwidth)
        accel_bandwidth = bandwidth - min(host_demand, host_bandwidth)
        accel_bandwidth = max(accel_bandwidth, bandwidth * 0.10)
    host_share = (host_bandwidth / bandwidth) if bandwidth > 0 else 0.0
    cpu_transfer_s = (cpu_dram_bytes / host_bandwidth
                      if host_bandwidth > 0 else 0.0)
    # The host overlaps its own reads with its own arithmetic about as well as
    # any out-of-order core does - not perfectly, and not badly.
    cpu_hidden_s = HOST_MEMORY_OVERLAP * min(cpu_compute_s, cpu_transfer_s)
    cpu_active_s = cpu_compute_s + cpu_transfer_s - cpu_hidden_s
    cpu_data_wait_s = cpu_active_s - cpu_compute_s
    # Three states, not two. A ratio of 1.02 is not a memory-limited host,
    # and calling it one invites a student to buy memory for a design that is
    # balanced. The band is deliberately wide: near it, the answer depends on
    # assumptions this model does not carry.
    if cpu_dram_bytes <= 0 or cpu_compute_s <= 0:
        cpu_state = "compute-limited"
    else:
        ratio = cpu_transfer_s / cpu_compute_s
        if ratio > 1.0 + HOST_BALANCE_BAND:
            cpu_state = "memory-limited"
        elif ratio < 1.0 - HOST_BALANCE_BAND:
            cpu_state = "compute-limited"
        else:
            cpu_state = "balanced"
    cpu_bound_by = "memory" if cpu_state == "memory-limited" else "compute"
    if host_share > 0 and accel_bandwidth > 0:
        memory_time = dram_bytes / accel_bandwidth
        hidden_time = overlap * min(compute_time, memory_time)
        exposed_compute = compute_time - hidden_time
        exposed_memory = memory_time - hidden_time
        core_time = exposed_compute + exposed_memory + hidden_time
        compute_data_wait = exposed_memory

    # --- Preprocessing moved off the CPU --------------------------------------
    #
    # The ISP sits in the sensor path, so its work is hidden behind capture and
    # adds no latency - only silicon and static power. The accelerator is fast
    # per pixel but charges a dispatch and a transfer for every frame, and that
    # fixed cost is what makes offloading a small frame slower than not
    # offloading it at all.


    # The ISP does real work in real time. It is normally pipelined with sensor
    # capture, so most of it never reaches the end-to-end latency - but "hidden"
    # is not "zero", and if the ISP cannot keep up with the frame rate the
    # remainder is exposed.
    _isp = pp.uses_isp(config.preprocessing_mode)
    isp_area = pp.ISP_AREA_MM2 * get_node(soc_node).logic_area if _isp else 0.0
    isp_power = pp.ISP_STATIC_POWER_W * get_node(soc_node).energy if _isp else 0.0
    isp_energy = (total_pixels * pp.ISP_ENERGY_PJ_PER_PIXEL * 1e-12 if _isp else 0.0)

    isp_active_s = isp_hidden_s = isp_exposed_s = 0.0
    if _isp and total_pixels > 0:
        isp_active_s = total_pixels / (pp.ISP_PIXELS_PER_SECOND
                                       * get_node(soc_node).fmax)
        frame_period_s = (1.0 / app.target_inferences_per_s
                          if app.target_inferences_per_s > 0 else isp_active_s)
        isp_hidden_s = min(isp_active_s, frame_period_s)
        isp_exposed_s = max(0.0, isp_active_s - frame_period_s)


    # In parallel mode the preprocessing is already inside the secondary
    # engine's turn, so adding it again here would count it twice. In every
    # other mode it is serial with the inference.
    # --- controller contention estimate --------------------------------------
    #
    # Only parallel execution has two engines issuing at once, and only in
    # proportion to how much their turns overlap. A secondary that finishes in
    # a tenth of the primary's turn contends for a tenth of it. This is an
    # estimate, not a mechanism - see ppact.coefficients.
    if second is not None and mode == "parallel":
        t_primary = mac_primary / compute_rate if compute_rate > 0 else 0.0
        t_secondary = (mac_secondary / second_rate if second_rate > 0 else 0.0)
        if pre_on_secondary:
            t_secondary += npu_pre_time
        longer = max(t_primary, t_secondary)
        concurrency = (min(t_primary, t_secondary) / longer) if longer > 0 else 0.0
        contention = DUAL_MEMORY_CONTENTION * concurrency
        if contention > 0:
            bandwidth = bandwidth * (1.0 - contention)
            # The bus just got narrower, so the split of it computed further
            # up is a split of a bus that no longer exists. Rescaling both
            # shares by the same factor keeps the partition exact and keeps
            # each agent's fraction of the bus what it was - the contention
            # takes bandwidth from the pair, not from one of them.
            #
            # Without this the accelerator kept its pre-contention allocation
            # while the reported bus shrank beneath it, and the host's share -
            # computed as the remainder - went NEGATIVE. Found by a random
            # stress draw at 3.99.0: -225 GB/s on a twelve-stack HBM4 board.
            accel_bandwidth = accel_bandwidth * (1.0 - contention)
            memory_time = dram_bytes / bandwidth if bandwidth > 0 else 0.0
            hidden_time = overlap * min(compute_time, memory_time)
            exposed_compute = compute_time - hidden_time
            exposed_memory = memory_time - hidden_time
            core_time = exposed_compute + exposed_memory + hidden_time
            compute_data_wait = exposed_memory
            total_exposed = exposed_compute + exposed_memory
            if total_exposed > 0:
                compute_contribution = exposed_compute / total_exposed * 100.0
                memory_contribution = exposed_memory / total_exposed * 100.0
            bound = "memory" if memory_time > compute_time else "compute"

    # A two-way label hides the case that matters most. A design with 1.6x more
    # arithmetic than transfers is called "compute bound" and still gains 26%
    # from a faster memory - the exposed data-wait was small and not zero.
    # A design at 15x gains nothing. Both were "compute".
    #
    # Five levels, and the middle three are where a memory upgrade is a real
    # question rather than an obvious yes or an obvious no.
    _ratio = (compute_time / memory_time if memory_time > 0
              else float("inf") if compute_time > 0 else 1.0)
    if _ratio > 4.0:
        bound_strength = "strongly compute-bound"
    elif _ratio > 1.25:
        bound_strength = "weakly compute-bound"
    elif _ratio >= 0.8:
        bound_strength = "balanced"
    elif _ratio >= 0.25:
        bound_strength = "weakly memory-bound"
    else:
        bound_strength = "strongly memory-bound"

    exposed_pre = 0.0 if (pre_on_secondary and mode == "parallel") else npu_pre_time
    hidden_pre = npu_pre_time - exposed_pre
    offload_s = exposed_pre + npu_pre_overhead + handoff_s

    # What the secondary engine is doing with its time. Reported separately
    # because "the second accelerator is busy" and "the second accelerator is
    # on the critical path" are different statements, and only the second one
    # changes the latency.
    secondary_inference_s = (mac_secondary / second_rate
                             if second and second_rate > 0 else 0.0)
    secondary_pre_s = npu_pre_time if pre_on_secondary else 0.0
    secondary_active_s = secondary_inference_s + secondary_pre_s
    if second is None:
        secondary_hidden_s = secondary_exposed_s = 0.0
    elif mode == "parallel":
        # Whatever fits inside the primary's turn costs nothing extra.
        secondary_hidden_s = min(secondary_active_s, compute_time)
        secondary_exposed_s = secondary_active_s - secondary_hidden_s
    else:
        secondary_hidden_s = 0.0
        secondary_exposed_s = secondary_active_s

    accel_area_uplift = (pp.NPU_PREPROCESS_AREA_UPLIFT
                         if pp.uses_npu_preprocessing(config.preprocessing_mode) else 0.0)
    accel_power_uplift = (pp.NPU_PREPROCESS_POWER_UPLIFT
                          if pp.uses_npu_preprocessing(config.preprocessing_mode) else 0.0)

    # One job at a time: the CPU prepares, hands over, waits, then finishes.
    # Phase 3 overlaps these across jobs; until then the serial sum is the
    # honest reading, and CPU time is added HERE and nowhere else so that it
    # cannot be counted twice.
    # A text workload pays for the serving stack AROUND the arithmetic, so it
    # is a term of its own rather than a scaling of the core. Dividing core
    # time by an efficiency broke the roofline invariant - core has to stay
    # between max(compute, transfer) and their sum, and an overhead that
    # inflates it is not part of either.
    serving_overhead_s = 0.0
    if app.workload_class == "text" and 0 < LLM_SINGLE_STREAM_SERVING_EFFICIENCY < 1:
        serving_overhead_s = core_time * (1.0 / LLM_SINGLE_STREAM_SERVING_EFFICIENCY - 1.0)

    latency_s = (cpu_active_s + offload_s + isp_exposed_s + core_time
                 + serving_overhead_s)
    cpu_accelerator_wait_s = (core_time + offload_s + isp_exposed_s
                              + serving_overhead_s)
    # Share of a SINGLE JOB's latency, not utilisation. Utilisation needs an
    # observation interval with more than one job in it, which is Phase 3.
    cpu_latency_share = cpu_active_s / latency_s * 100.0 if latency_s > 0 else 0.0
    # Preprocessing reuses the main array, so the two cannot overlap.
    accel_active_s = npu_pre_time + core_time

    bound = "memory" if memory_time > compute_time else "compute"

    # A workload can legitimately have no DRAM traffic - a model small enough
    # to live entirely on chip. Arithmetic intensity is then undefined rather
    # than infinite, and it is recorded as None with a status rather than as
    # inf: an infinity propagates silently into scores and JSON, and the first
    # place it surfaces is far from where it was created.
    if dram_bytes > 0:
        arithmetic_intensity = app.total_mac / dram_bytes
    else:
        arithmetic_intensity = None
        status = STATUS_NO_DRAM_TRAFFIC
    ridge_point = compute_rate / bandwidth if bandwidth > 0 else 0.0

    # SINGLE-JOB rate: one over the latency, which is what a design with one
    # job in flight achieves. It is NOT the pipeline rate - a second engine
    # taking alternate jobs raises the pipeline rate and cannot raise this one,
    # and reading this figure to judge such a design reports a real gain as
    # none. ppact.runtime.simulate gives the pipeline rate.
    throughput = 1.0 / latency_s if latency_s > 0 else 0.0
    effective_tops = (app.total_mac * OPS_PER_MAC / core_time / 1e12
                      if core_time > 0 else 0.0)

    # Closed-loop reaction: the network is only part of the delay between the
    # obstacle appearing and the vehicle responding.
    end_to_end_ms = latency_s * 1e3 + app.control_overhead_ms
    reaction_distance_m = app.cruise_speed_m_s * end_to_end_ms / 1e3

    # --- Energy --------------------------------------------------------------
    e_compute = ((mac_primary * comp.energy_pj_per_mac_at(accel_node)
                  + mac_secondary * (second.energy_pj_per_mac_at(accel_node)
                                     if second else 0.0)) * 1e-12)
    # Traffic energy plus background: refresh, PHY and termination draw
    # whether or not anything is being read.
    e_memory = (dram_bytes * 8 * mem.energy_pj_per_bit * 1e-12
                + mem.background_power_w * n_mem * latency_s)
    # The CPU is only busy for the dispatch window; for the rest of the
    # inference it waits on the accelerator. Charging it full active power for
    # the whole latency made control logic look like the dominant energy
    # consumer, which is the opposite of what measurements show.
    dispatch_s = cpu.dispatch_overhead_us * 1e-6
    cpu_active_w = cpu.active_power_at(soc_node)
    cpu_idle_w = cpu.idle_power_at(soc_node)
    if comp.uses_host_cpu:
        # No accelerator: the host cores ARE the compute engine, so they are at
        # full load for the whole inference. Charging idle power here would make
        # a CPU-only design look dramatically more efficient than it is.
        # No accelerator: the host does the arithmetic as well, so it is busy
        # for the whole inference rather than only around it.
        e_cpu = cpu_active_w * latency_s
    else:
        e_cpu = (cpu_active_w * cpu_active_s
                 + cpu_idle_w * cpu_accelerator_wait_s)
    # Leakage does not care which engine is busy. An idle accelerator still
    # draws, which is why "alternative" mode costs power it never uses.
    # Module idle power where a module figure is stated, die leakage otherwise.
    # A module carries its DRAM, PMIC and interface whether or not the array is
    # busy, and that is what a "5 W" rating on a 25 TOPS part describes.
    def _idle(engine):
        if engine is None:
            return 0.0
        stated = engine.module_idle_power_w
        return (stated if stated > 0
                else engine.static_power_at(accel_node))
    # A gated engine keeps its area and its price and gives up most of its
    # leakage. Not all of it: power gating leaves retention and the rails do
    # not vanish, and a model that took it to zero would make "fit it and
    # switch it off" look free.
    GATED_LEAKAGE_FRACTION = 0.15
    second_static = _idle(second) * (GATED_LEAKAGE_FRACTION
                                     if secondary_gated else 1.0)
    e_static = ((_idle(comp) * (1.0 + accel_power_uplift) + second_static)
                * latency_s + isp_power * latency_s + isp_energy)
    energy_j = e_compute + e_memory + e_cpu + e_static
    system_power = energy_j / latency_s if latency_s > 0 else 0.0

    # --- Area, cost, thermal -------------------------------------------------
    # The die the planner is actually specifying is CPU + accelerator. DRAM is
    # a purchased part: its silicon drives cost, but a DRAM die does not consume
    # the SoC reticle. Gating both on one number would reject a design for
    # silicon it never has to tape out.
    # Both dies exist whatever they are doing. This is the term that stops a
    # second accelerator being free.
    second_area = second.die_area_at(accel_node) if second else 0.0
    soc_silicon_mm2 = (comp.die_area_at(accel_node) * (1.0 + accel_area_uplift)
                       + second_area + cpu.die_area_at(soc_node) + isp_area)
    memory_silicon_mm2 = mem.die_area_mm2 * mem.dies_per_package * n_mem
    silicon_mm2 = soc_silicon_mm2 + memory_silicon_mm2
    board_mm2 = comp.package_footprint_mm2 + mem.board_area_mm2 * n_mem
    # SoC blocks are priced from the silicon they occupy on the chosen node;
    # a purchased part carries its own price instead.
    second_cost = second.silicon_cost_at(accel_node) if second else 0.0
    cost = (comp.silicon_cost_at(accel_node) * (1.0 + accel_area_uplift)
            + second_cost
            + isp_area * get_node(soc_node).usd_per_mm2
            + cpu.silicon_cost_at(soc_node)
            + memres.metrics["Package cost (USD)"] * n_mem)
    # Mask and NRE, amortised over lifetime volume. Reported only: a product
    # team that buys an existing SoC pays none of it, and a team taping one out
    # pays it whatever the BOM says. Charging it to the BOM gate would answer a
    # different question than the one the gate asks.
    masks = {get_node(soc_node).mask_set_usd}
    if integration != "monolithic":
        masks.add(get_node(accel_node).mask_set_usd)
    nre_per_unit = sum(masks) / max(app.production_volume, 1)

    footprint = (comp.package_footprint_mm2
                 + (second.package_footprint_mm2 if second else 0.0)
                 + mem.package_footprint_mm2 * n_mem)
    power_density = system_power / footprint
    # Margin, not temperature. A real junction figure needs thermal resistance,
    # ambient and a time-domain power trace; reporting one without them would
    # be a number with no basis behind it. A negative margin means the cooling
    # assumption has been exceeded, NOT that a temperature was computed.
    limit = max(app.thermal_limit_w_per_mm2, 1e-9)
    thermal_margin = 1.0 - power_density / limit

    # Split by domain, because "the design is over its thermal budget" and
    # "the memory is over its thermal budget" call for different fixes. HBM
    # concentrates a lot of power into a small package footprint and can put a
    # system over the limit on its own, which a single figure cannot show.
    compute_fp = (comp.package_footprint_mm2
                  + (second.package_footprint_mm2 if second else 0.0))
    memory_fp = mem.package_footprint_mm2 * n_mem
    compute_power_w = (e_compute + e_static) / latency_s if latency_s > 0 else 0.0
    memory_power_w = e_memory / latency_s if latency_s > 0 else 0.0
    compute_margin = 1.0 - (compute_power_w / compute_fp) / limit if compute_fp > 0 else 0.0

    # The memory is judged against the cooling ITS OWN package class assumes,
    # not against the product's. Measuring an HBM stack with a phone's passive
    # limit produced -398% - correct arithmetic, no information. What a
    # planner needs is the compatibility statement below.
    from .memory import COOLING_RANK
    mem_limit = {"passive": 0.05, "airflow": 0.25, "active": 1.20}.get(
        mem.cooling_requirement, limit)
    memory_margin = (1.0 - (memory_power_w / memory_fp) / mem_limit
                     if memory_fp > 0 else 0.0)
    cooling_ok = (COOLING_RANK.get(app.cooling, 0)
                  >= COOLING_RANK.get(mem.cooling_requirement, 0))

    # --- Deployment accuracy -------------------------------------------------
    # With two engines the product must be accurate on EVERY job, so the worse
    # of the two governs. Averaging them would let a design pass on the strength
    # of the jobs that happened to land on the better engine.
    loss = comp.accuracy_loss_pp(app.model_family)
    if second is not None:
        loss = max(loss, second.accuracy_loss_pp(app.model_family))
    deployment_accuracy = app.reference_accuracy_pct - loss
    accuracy_margin = deployment_accuracy - app.required_accuracy_pct
    # Accuracy beyond requirement + margin is not useful to the product, so it
    # is capped before being reported. Without the cap, a high-precision engine
    # would look better and better on a number the product cannot spend.
    useful_accuracy = min(deployment_accuracy,
                          app.required_accuracy_pct + app.accuracy_margin_limit_pp)

    # --- prefill, reported beside decode -------------------------------------
    #
    # The two halves of an LLM request have opposite characters. Prefill
    # processes the whole prompt at once and is compute bound; decode emits one
    # token at a time and is bound by how fast the weights can be read. A single
    # figure for "LLM performance" hides which one a design is good at, and they
    # call for different hardware.
    prefill_compute_s = prefill_memory_s = 0.0
    if app.workload_class == "text" and app.prefill_tokens > 0:
        prefill_mac = app.mac_per_inference * app.prefill_tokens
        prefill_compute_s = prefill_mac / compute_rate if compute_rate > 0 else 0.0
        # The weights are read once for the whole prompt, not once per token -
        # which is exactly why prefill is compute bound and decode is not.
        prefill_bytes = (app.weight_bytes * app.weight_read_factor
                         + app.kv_bytes_per_token * app.prefill_tokens)
        prefill_memory_s = prefill_bytes / bandwidth if bandwidth > 0 else 0.0


    # The pipeline interval is the SLOWEST station, not the sum of them. Each
    # station can work on a different job at the same time, so the rate a
    # steady stream achieves is set by whichever one takes longest.
    _stations = (
        cpu_active_s,
        (mac_primary / compute_rate if compute_rate > 0 else 0.0)
        + (0.0 if pre_on_secondary else npu_pre_time)
        + offload_dispatch_s + handoff_s,
        secondary_active_s,
        isp_active_s,
        memory_time + offload_transfer_s,
    )
    pipeline_interval_ms = max(_stations) * 1e3

    # THE THROUGHPUT STATIONS, named and exported.
    #
    # This tuple decides the steady-state rate and had no names. The
    # latency flow has its own, different, list - host active, offload
    # overhead, accelerator core - and the two were being treated as one
    # model. They are not: a stage absent from the flow can still set the
    # pipeline rate, and the ISP does exactly that.
    #
    #     isp_assisted   ISP active 10.027 ms sets the interval
    #                    slowest FLOW station is 2.910 ms
    #
    # Deriving a capacity from a flow station gave 343.67 inf/s against
    # the engine's 99.73, and it agreed only when the ISP was idle - which
    # made the agreement a coincidence.
    _throughput_stations = (
        ("host", cpu_active_s),
        ("accelerator", (mac_primary / compute_rate
                         if compute_rate > 0 else 0.0)
         + (0.0 if pre_on_secondary else npu_pre_time)
         + offload_dispatch_s + handoff_s),
        ("secondary accelerator", secondary_active_s),
        ("ISP", isp_active_s),
        ("shared memory", memory_time + offload_transfer_s),
    )

    metrics = {
        "Reference accuracy (%)": app.reference_accuracy_pct,
        "Prefill compute (ms)": prefill_compute_s * 1e3,
        "Prefill memory (ms)": prefill_memory_s * 1e3,
        "Time to first token (ms)": max(prefill_compute_s, prefill_memory_s) * 1e3,
        "Prefill bound by": 0.0 if prefill_compute_s >= prefill_memory_s else 1.0,
        "Accuracy loss (pp)": comp.accuracy_loss_pp(app.model_family),
        "Deployment accuracy (%)": deployment_accuracy,
        "Required accuracy (%)": app.required_accuracy_pct,
        "Accuracy margin (pp)": accuracy_margin,
        "Useful accuracy (%)": useful_accuracy,
        "Latency (ms)": latency_s * 1e3,
        # THREE BOUNDARIES, never conflated. A "100 ms" requirement usually
        # means the third; a datasheet inference figure means the first.
        "Pure inference (ms)": (compute_time + exposed_memory) * 1e3,
        "End-to-end pipeline (ms)": latency_s * 1e3,
        # The ISP sits BETWEEN the sensor and the control, so its time belongs
        # here even though it is hidden from the pipeline latency. Overlapping
        # frames raises the rate; it does not shorten any one frame's journey,
        # and this metric is about one frame's journey. Found at 3.74.0 by an
        # independent recomputation that noticed a station occupying 10 ms
        # inside a 4.7 ms sensor-to-control figure.
        "Sensor-to-control (ms)": (latency_s * 1e3 + isp_active_s * 1e3
                                   + app.capture_latency_ms
                                   + app.control_latency_ms),
        "CPU preprocess (ms)": preprocess_s * 1e3,
        "CPU dispatch (ms)": dispatch_s * 1e3,
        "Framework overhead (ms)": framework_s * 1e3,
        "Effective utilisation": comp.effective_utilization(app.total_mac, accel_node),
        "CPU postprocess (ms)": postprocess_s * 1e3,
        "CPU active (ms)": cpu_active_s * 1e3,
        "CPU accelerator-wait (ms)": cpu_accelerator_wait_s * 1e3,
        "CPU latency share (%)": cpu_latency_share,
        "Pixels per stream": pixels_per_stream,
        "Streams": float(app.streams),
        "Total pixels per job": total_pixels,
        "Preprocess offload (ms)": npu_pre_time * 1e3,
        "Preprocess exposed (ms)": exposed_pre * 1e3,
        "Preprocess hidden (ms)": hidden_pre * 1e3,
        "Secondary inference (ms)": secondary_inference_s * 1e3,
        "Secondary preprocess (ms)": secondary_pre_s * 1e3,
        "Secondary active (ms)": secondary_active_s * 1e3,
        "Secondary hidden (ms)": secondary_hidden_s * 1e3,
        "Secondary exposed (ms)": secondary_exposed_s * 1e3,
        "Offload calls": float(offload_calls),
        "Offload dispatch (ms)": offload_dispatch_s * 1e3,
        "Offload transfer (ms)": offload_transfer_s * 1e3,
        "Offload overhead (ms)": npu_pre_overhead * 1e3,
        "ISP active (ms)": isp_active_s * 1e3,
        "ISP energy (mJ)": isp_energy * 1e3,
        "ISP hidden (ms)": isp_hidden_s * 1e3,
        "ISP exposed (ms)": isp_exposed_s * 1e3,
        "Accelerator total active (ms)": accel_active_s * 1e3,
        "ISP area (mm2)": isp_area,
        "Accelerator area uplift (%)": accel_area_uplift * 100.0,
        "End-to-end latency (ms)": end_to_end_ms,
        "Reaction distance (m)": reaction_distance_m,
        # THREE rates, named apart. A single name invited exactly one defect:
        # a design routing alternate jobs to two engines raises the pipeline
        # capacity and cannot raise the single-job rate, and reading the wrong
        # one reported a real gain as none.
        #
        #   single-job rate      one over the latency, one job in flight
        #   pipeline capacity    steady-state rate, the slowest station
        #   delivered            min(capacity, what actually arrives)
        #
        # "Throughput (inf/s)" is retained as an alias for the single-job rate
        # so that older callers keep working, but nothing new should read it.
        "Throughput (inf/s)": throughput,
        "Single-job rate (inf/s)": throughput,
        # Named, in seconds, so a caller reads the engine's own stations
        # rather than re-deriving them from a different decomposition.
        "Throughput stations (s)": {name: value for name, value
                                    in _throughput_stations},
        "Pipeline capacity (inf/s)": (1e3 / pipeline_interval_ms
                                      if pipeline_interval_ms > 0 else 0.0),
        "Delivered throughput (inf/s)": min(
            (1e3 / pipeline_interval_ms if pipeline_interval_ms > 0 else 0.0),
            app.target_inferences_per_s),
        "Pipeline interval (ms)": pipeline_interval_ms,
        "Effective TOPS": effective_tops,
        # Node-adjusted, like the effective figure it is compared against.
        # Quoting the reference-node peak beside a node-scaled effective number
        # let effective exceed peak on a fast node - an impossible reading that
        # only surfaced once a bound was checked for.
        "Peak TOPS": comp.peak_mac_per_s_at(accel_node) * OPS_PER_MAC / 1e12,
        "Compute time (ms)": compute_time * 1e3,
        "Memory time (ms)": memory_time * 1e3,
        "Overlap ratio": overlap,
        "Hidden transfer (ms)": hidden_time * 1e3,
        "Compute active (ms)": compute_time * 1e3,
        "Compute data-wait (ms)": compute_data_wait * 1e3,
        # NOT operations over peak operations - that is the engine's own
        # arithmetic utilisation, reported separately below. This is the share
        # of the accelerator's busy period spent computing rather than waiting,
        # and the two were confused once when a published band was read
        # against the wrong one.
        "Engine arithmetic utilisation (%)": comp.utilization * 100.0,
        "Compute utilisation (%)": (compute_time / core_time * 100.0
                                    if core_time > 0 else 0.0),
        "Latency contribution, compute (%)": compute_contribution,
        "Latency contribution, memory (%)": memory_contribution,

        "Ridge point (MAC/B)": ridge_point,
        "DRAM traffic (MB)": dram_bytes / 1e6,
        "Host DRAM traffic (MB)": cpu_dram_bytes / 1e6,
        "  host preprocess traffic (MB)": cpu_pre_bytes / 1e6,
        "  host postprocess traffic (MB)": cpu_post_bytes / 1e6,
        # The share ALLOCATED, not the rate achieved. Reporting the achieved
        # rate while computing the accelerator's bandwidth from the allocation
        # meant the two did not add up to the bus - a 1.5% residue that no
        # agent owned.
        "Host bandwidth share (%)": (
            (bandwidth - accel_bandwidth) / bandwidth * 100.0
            if bandwidth > 0 and cpu_dram_bytes > 0 else 0.0),
        "Host bandwidth allocated (GB/s)": (bandwidth - accel_bandwidth) / 1e9
                                            if cpu_dram_bytes > 0 else 0.0,
        "Host compute time (ms)": cpu_compute_s * 1e3,
        "Host transfer time (ms)": cpu_transfer_s * 1e3,
        "Host data-wait (ms)": cpu_data_wait_s * 1e3,
        "Host bound by": 0.0 if cpu_bound_by == "compute" else 1.0,
        "Host hidden memory (ms)": cpu_hidden_s * 1e3,
        "Bandwidth left to the accelerator (GB/s)": accel_bandwidth / 1e9,
        "  weight traffic (MB)": weight_traffic / 1e6,
        "  KV cache traffic (MB)": kv_traffic / 1e6,
        "  other traffic (MB)": other_traffic / 1e6,
        "Weight read factor": (app.weight_read_factor
                               if app.workload_class == "text" else weight_fetches),
        # Split so a memory report can say what direction the traffic goes.
        # Writes are the output tensor; everything else is read in.
        "DRAM read (MB)": max(0.0, dram_bytes - app.activation_bytes) / 1e6,
        "DRAM write (MB)": min(dram_bytes, app.activation_bytes) / 1e6,
        "Activation reload factor": reload_factor,
        "Weight fetches": weight_fetches,

        "Peak bandwidth (GB/s)": peak_bandwidth / 1e9,
        "Effective bandwidth (GB/s)": bandwidth / 1e9,
        "Bandwidth efficiency (%)": bw_efficiency * 100.0,
        "Shared bandwidth contention (%)": contention * 100.0,
        "BW to sustain peak (GB/s)": (compute_rate / arithmetic_intensity / 1e9
                                      if arithmetic_intensity else 0.0),
        "Memory power (W)": e_memory / latency_s,
        "Compute power (W)": (e_compute + e_static) / latency_s,
        "Energy per inference (mJ)": energy_j * 1e3,
        "  compute share (%)": e_compute / energy_j * 100 if energy_j > 0 else 0.0,
        "  memory share (%)": e_memory / energy_j * 100 if energy_j > 0 else 0.0,
        "  cpu share (%)": e_cpu / energy_j * 100 if energy_j > 0 else 0.0,
        "  static share (%)": e_static / energy_j * 100 if energy_j > 0 else 0.0,
        "System power (W)": system_power,
        # Split so that a multi-job run can charge static power over the run
        # rather than over the sum of the jobs, which would overcount it.
        "Static energy per inference (mJ)": e_static * 1e3,
        "Dynamic energy per inference (mJ)": (energy_j - e_static) * 1e3,
        "Static power (W)": (e_static / latency_s if latency_s > 0 else 0.0),
        # A ceiling the average can never exceed. Reported so that a design
        # drawing more than its parts are rated for is visible rather than
        # merely arithmetically possible.
        "Accelerator module ceiling (W)": (
            (comp.module_max_power_w or 0.0)
            + ((second.module_max_power_w or 0.0) if second else 0.0)),
        # Power drawn by a module WHILE IT IS WORKING, not averaged over the
        # job. Averaging first and summing afterwards understates the peak, and
        # can put it below the average once several jobs are in flight - which
        # is not a number that can be true.
        "CPU active power (W)": cpu_active_w,
        "Accelerator active power (W)": (e_compute / compute_time
                                         if compute_time > 0 else 0.0),
        "Memory active power (W)": (e_memory / memory_time
                                    if memory_time > 0 else 0.0),
        # Stage occupancy, per job. Phase 3 turns these into utilisation.
        "Stage CPU (ms)": cpu_active_s * 1e3,
        # Compute occupancy, NOT core time. Core time includes the transfers,
        # and in a pipeline the transfers for the next job overlap the compute
        # for this one - so counting them in the accelerator's station as well
        # as in the memory station double counts them. The dual-engine stages
        # below were always compute-only; this one was not, which overstated
        # the single-accelerator interval by up to 9% and by more the faster
        # the memory got. Found by mutation testing.
        # The transfer belongs to the MEMORY station and is already counted
        # there. Including it here as well put the same bytes in two stations
        # at once - found by comparing the module's busy time against an
        # independent event simulation, which is the only thing that could
        # have noticed. What stays here is the dispatch and the hand-off:
        # bubbles on the accelerator, not traffic.
        # Three terms the report must be able to separate: the roofline
        # invariant applies to the ideal core alone, and the serving loss is
        # explained outside it rather than folded in.
        "Ideal core time (ms)": core_time * 1e3,
        "Serving overhead (ms)": serving_overhead_s * 1e3,
        "Delivered core time (ms)": (core_time + serving_overhead_s) * 1e3,
        "Stage accelerator (ms)": (compute_time + exposed_pre
                                   + offload_dispatch_s
                                   + handoff_s) * 1e3,
        "Stage accelerator core (ms)": (core_time + offload_s) * 1e3,
        # Per-engine stage occupancy. In a pipeline the two are separate
        # stations even in sequential mode - one can start the next job while
        # the other finishes this one - so the interval is a max over both, and
        # only the single-job LATENCY is a sum.
        "Stage accelerator 1 (ms)": ((mac_primary / compute_rate if compute_rate > 0
                                      else 0.0)
                                     + (0.0 if pre_on_secondary else npu_pre_time)
                                     + offload_dispatch_s + handoff_s) * 1e3,
        "Stage accelerator 2 (ms)": secondary_active_s * 1e3,
        "Stage ISP (ms)": isp_active_s * 1e3,
        "Stage memory (ms)": (memory_time + offload_transfer_s) * 1e3,
        "Accel MAC area (mm2)": comp.mac_area_at(accel_node),
        "Accel SRAM area (mm2)": comp.sram_area_at(accel_node),
        "Accel control area (mm2)": comp.control_area_at(accel_node),
        "Accel die area (mm2)": comp.die_area_at(accel_node),
        "Secondary die area (mm2)": second_area,
        "Secondary compute time (ms)": (mac_secondary / second_rate * 1e3
                                        if second and second_rate > 0 else 0.0),
        "Primary compute time (ms)": (mac_primary / compute_rate * 1e3
                                      if compute_rate > 0 else 0.0),
        "Handoff (ms)": handoff_s * 1e3,
        "Work split (MAC fraction)": active_split,
        "Alternative share (job fraction)": active_share,
        "Preprocessing on secondary": 1.0 if pre_on_secondary else 0.0,
        "Accel silicon cost (USD)": comp.silicon_cost_at(accel_node),
        # The node moves the SILICON and nothing else. Reporting only the
        # system total hides the change, because on a cheap product the die is
        # a small share of the bill of materials - and reporting only the die
        # would overstate what a node change buys the product.
        "Logic die cost (USD)": (comp.silicon_cost_at(accel_node)
                                 * (1.0 + accel_area_uplift)
                                 + second_cost
                                 + cpu.silicon_cost_at(soc_node)),
        "CPU die area (mm2)": cpu.die_area_at(soc_node),
        "Mask/NRE per unit (USD)": nre_per_unit,
        "Accel SRAM share (%)": (comp.sram_area_at(accel_node)
                                 / max(comp.die_area_at(accel_node), 1e-9) * 100.0),
        "SoC silicon (mm2)": soc_silicon_mm2,
        "Memory silicon (mm2)": memory_silicon_mm2,
        "Total silicon (mm2)": silicon_mm2,
        "Board area (mm2)": board_mm2,
        "System cost (USD)": cost,
        "Power density (W/mm2)": power_density,
        "Thermal margin (%)": thermal_margin * 100.0,
        "  compute thermal margin (%)": compute_margin * 100.0,
        "  memory thermal margin (%)": memory_margin * 100.0,
        "Memory cooling compatible": 1.0 if cooling_ok else 0.0,
        "Memory cost index": memres.metrics["Cost index"] * n_mem,
        "Logic silicon (mm2)": soc_silicon_mm2,
        "Package footprint (mm2)": footprint,
        "  compute footprint (mm2)": compute_fp,
        "  memory footprint (mm2)": memory_fp,
        "Memory capacity (GB)": capacity / 1e9,
    }

    gate = {
        # Accuracy first. A device that cannot meet the requirement is not a
        # candidate, however good its PPACT profile is - and conversely, extra
        # accuracy earns nothing once the requirement is met. That asymmetry is
        # what stops a GPU from winning on precision it was never asked for.
        "accuracy": deployment_accuracy >= app.required_accuracy_pct,
        "throughput": throughput >= app.target_inferences_per_s,
        "latency": latency_s * 1e3 <= app.latency_budget_ms,
        "power": system_power <= app.power_budget_w,
        "cost": cost <= app.bom_budget_usd,
        "soc_die": soc_silicon_mm2 <= app.soc_silicon_budget_mm2,
        "board": board_mm2 <= app.board_budget_mm2,
        "thermal": power_density <= app.thermal_limit_w_per_mm2,
        "capacity": capacity >= app.required_memory_bytes,
        # A memory that needs a cold plate cannot ship in a passively cooled
        # product, whatever its bandwidth. Stated as a requirement rather than
        # as the large negative margin it used to produce.
        "memory_cooling": cooling_ok,
    }
    if app.closed_loop:
        gate["reaction"] = reaction_distance_m <= app.stopping_distance_budget_m
    if app.requires_automotive_grade:
        gate["auto_qual"] = (comp.automotive_grade and cpu.automotive_grade
                             and mem.name in AUTOMOTIVE_QUALIFIED_MEMORY)

    # Only defined quantities enter the numeric table. An undefined one is
    # absent, not zero, and the status says why.
    if arithmetic_intensity is not None:
        metrics["Arithmetic intensity (MAC/B)"] = arithmetic_intensity
        metrics["Data reuse (MAC per DRAM byte)"] = arithmetic_intensity

    result = SystemResult(app=app, config=config, metrics=metrics,
                          status=(STATUS_DOES_NOT_FIT
                                  if gate.get("capacity") is False else status),
                          gate=gate, bound_by=bound,
                          bound_strength=bound_strength,
                          compute_memory_ratio=_ratio,
                          host_state=cpu_state)
    # A design whose model does not fit cannot run at any speed. The status
    # says so, and anything reading the performance figures should check it -
    # a token rate for a machine that cannot hold its weights describes
    # nothing.
    result.status = (STATUS_DOES_NOT_FIT if gate.get("capacity") is False
                     else status)

    # Hiding the numbers is not enough. A latency computed for a machine that
    # cannot hold its weights is still a number, and it will reappear in a
    # sweep, a score or a comparison written later. So the performance figures
    # are made UNUSABLE rather than merely unprinted: not-a-number propagates,
    # every comparison against it is false, and anything that tries to rank on
    # it produces nan instead of a plausible position.
    #
    # Zero would have been worse than either. Zero reads as "it runs and is
    # slow"; the actual state is that the configuration does not exist.
    #
    # The PHYSICAL and ECONOMIC figures survive, because they are true of the
    # board whether or not it can run the model: what capacity was needed, what
    # was fitted, what it would cost, what cooling it implies.
    if result.status == STATUS_DOES_NOT_FIT:
        for key in PERFORMANCE_METRICS:
            if key in result.metrics:
                result.metrics[key] = float("nan")
        for axis in ("Performance", "Power"):
            if axis in result.scores:
                result.scores[axis] = float("nan")
        # The label too. "Compute bound" describes how a machine spends its
        # time, and this one does not spend any.
        result.bound_by = "not evaluated"
        result.bound_strength = "not evaluated"
        result.compute_memory_ratio = float("nan")
    result.arithmetic_intensity = arithmetic_intensity
    result.soc_node = soc_node
    result.accel_node = accel_node
    result.integration = integration
    result.execution_mode = mode
    return result


# ==============================================================================
SYSTEM_ANCHORS: Dict[str, Anchor] = {
    "Performance": Anchor(
        "Throughput", "inferences per second", at_zero=1.0, at_hundred=1000.0, log_scale=True,
        rationale="Sustainable pipeline capacity on the selected application, not peak TOPS."),
    "Power": Anchor(
        "Energy per inference", "mJ", at_zero=2000.0, at_hundred=1.0, log_scale=True,
        rationale="Energy, not watts: a part that draws twice the power but "
                  "finishes four times sooner is the more efficient choice."),
    "Area": Anchor(
        "Total silicon", "mm2", at_zero=4000.0, at_hundred=10.0, log_scale=True,
        rationale="ABSOLUTE silicon across CPU, compute and every memory die. "
                  "Not area per GB/s - that normalization is what makes an "
                  "HBM stack look small."),
    "Cost": Anchor(
        "System BOM", "USD", at_zero=20000.0, at_hundred=10.0, log_scale=True,
        rationale="Absolute build cost of the three blocks."),
    # TRAFFIC replaced Thermal as the fifth axis.
    #
    # Thermal is computed FROM power and area - a verdict on a design
    # rather than a dimension of one - and stays as a deployment gate.
    #
    # Traffic has an anchor and no score. One of its ten components is
    # modelled, and a point that moved only when shared memory moved
    # would be a memory score wearing the label of nine other things. The
    # anchor is here so the axis has a place; `_AXIS_METRIC` deliberately
    # gives it none.
    "Traffic": Anchor(
        "System integration quality", "score", at_zero=0.0,
        at_hundred=100.0, log_scale=False,
        rationale="How evenly data supply and consumption are matched "
                  "inside the system. NOT COMPUTED: one of ten "
                  "components is modelled - see TR-D1."),
}

SYSTEM_AXES: List[str] = list(SYSTEM_ANCHORS.keys())

# ==============================================================================
# Requirement-centred normalisation
# ==============================================================================
#
# The absolute anchors above answer "where does this design sit among all
# designs". The spider asks a different question - "how does this design
# stand against what THIS application requires" - and the anchors answered
# it badly:
#
#     a design sitting exactly on its requirement scored
#         smart_camera       Performance 39.2   Area 81.7   Cost 83.5
#         industrial_vision  Performance 59.3   Area 34.7   Cost 34.1
#         llm_service        Performance 51.5   Area  4.8   Cost  0.0
#
# Zero to 83.5 for the same statement. And the spans differ - 2.60 decades
# on Area against 3.30 on Cost - so a tenfold improvement was worth 38.5
# points on one axis and 30.3 on another.
#
# Here 50 means one thing on every axis: the design meets its requirement
# exactly. A doubling is worth 20 points wherever it happens.
#
#     score = 50 + K * log2(ratio)
#
#     Performance   ratio = actual / target        higher is better
#     Area, Cost    ratio = budget / actual        lower is better
#
# The absolute anchors are NOT deleted. They answer a real question and
# belong in an absolute benchmark view, not on this chart.

REQUIREMENT_K = 20.0

# Axis -> (metric, application attribute, higher_is_better).
# POWER IS ABSENT. Its spider metric is energy per inference and its
# constraint is a power budget in watts: different physical quantities,
# and a score relating them would present energy efficiency as budget
# compliance. See PW-Q1.
REQUIREMENT_AXES: Dict[str, Tuple[str, str, bool]] = {
    "Performance": ("Delivered throughput (inf/s)",
                    "target_inferences_per_s", True),
    "Area": ("SoC silicon (mm2)", "soc_silicon_budget_mm2", False),
    "Cost": ("System cost (USD)", "bom_budget_usd", False),
}


def requirement_score(axis: str, actual: float, requirement: float
                      ) -> Optional[float]:
    """50 at the requirement, +20 per doubling of margin, clipped to 0-100.

    Returns None when either figure is missing: an axis with no declared
    requirement has nothing to be relative to, and defaulting it to an
    absolute anchor would put two different questions on one chart.
    """
    spec = REQUIREMENT_AXES.get(axis)
    if spec is None or not requirement or actual is None:
        return None
    if actual <= 0 or requirement <= 0:
        return None
    _, _, higher_better = spec
    ratio = (actual / requirement) if higher_better else (
        requirement / actual)
    if ratio <= 0:
        return None
    return max(0.0, min(100.0, 50.0 + REQUIREMENT_K * math.log2(ratio)))

_AXIS_METRIC = {
    # THE CANONICAL KEY, not the alias.
    #
    # `"Throughput (inf/s)"` is kept so older callers keep working and
    # this file says nothing new should read it - and this table, which
    # is read on every benchmark chart, was reading it. Same value,
    # same number on every screen; only the name the code asks for
    # changes.
    #
    # SUSTAINED CAPACITY, not one over the latency.
    #
    # This read the single-job rate, which is exactly `1000 / latency`
    # in all 41 library designs - and the bar chart drawn beside this
    # spider already plots `Latency (ms)`. One axis of five was
    # redrawing another picture on the same screen.
    #
    # Pipeline capacity differs from `1000 / latency` in 39 of those 41:
    # it carries the slowest station, the overlap between stations and
    # what the design sustains under load, which is the thing a
    # benchmark of system capability is for.
    #
    # Demo 002 decides it. Its answer is that the large engine is
    # SLOWER than the medium one, and the two candidates disagree:
    # single-job rate rises 48.10 to 54.58 while capacity falls 106.34
    # to 59.76 as the pipeline interval opens from 9.40 to 16.73 ms.
    # The axis was contradicting the demonstration it appeared in.
    "Performance": "Pipeline capacity (inf/s)",
    # POWER HAS NO SPIDER METRIC.
    #
    # Its axis metric was `Energy per inference (mJ)` and its constraint is
    # `power_budget_w` in watts. Different physical quantities: a score
    # relating them would present energy efficiency as budget compliance.
    #
    # It also produced nan on llm_service, which is what an axis does when
    # nobody has decided what it measures.
    #
    # Restored when PW-Q1 fixes the budget's basis and a power figure in
    # the same quantity and window exists.
    "Area": "Total silicon (mm2)",
    "Cost": "System cost (USD)",
    # Traffic has no metric. An axis with an anchor and no metric renders
    # as NOT ESTABLISHED, which is the honest shape - dropping the axis
    # would show a four-sided figure and suggest PPACT has four axes.
}


def score_system(res: SystemResult) -> SystemResult:
    """Score every axis that HAS a metric, and no others.

    An axis with an anchor and no metric scores None rather than 0.0.
    Zero is a score - it says the design is as bad as the anchor allows -
    and Traffic has not been measured at all.
    """
    res.scores = {
        a: (SYSTEM_ANCHORS[a].score(res.metrics[_AXIS_METRIC[a]])
            if a in _AXIS_METRIC else None)
        for a in SYSTEM_AXES}
    return res


# ==============================================================================

def default_candidates(app_key: str) -> List[SystemConfig]:
    """A sensible starting slate. Students are expected to edit this."""
    if app_key == "autonomous_vehicle":
        return [
            SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 4),
            SystemConfig("cortex_a78_x4", "npu_128x128", "LPDDR5", 4),
            SystemConfig("cortex_a78_x4", "npu_128x128", "LPDDR5", 8),
            SystemConfig("cortex_a78_x4", "npu_128x128", "GDDR6", 4),
            SystemConfig("cortex_a78_x4", "npu_128x128", "HBM3E", 1),
        ]
    if app_key in ("ai_inference", "llm_service"):
        return [
            SystemConfig("server_x86_x32", "datacenter_gpu", "HBM3E", 6),
            SystemConfig("server_x86_x32", "datacenter_gpu", "HBM3E", 8),
            SystemConfig("server_x86_x32", "datacenter_gpu", "GDDR6", 12),
        ]
    return [
        SystemConfig("cortex_a53_x4", "npu_16x16", "LPDDR5", 1),
        SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2),
        SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 2),
        SystemConfig("cortex_a78_x4", "npu_32x32", "GDDR6", 4),
        SystemConfig("cortex_a78_x4", "npu_64x64", "HBM3E", 1),
    ]


# ==============================================================================
# Why a design failed, without counting one reason twice
# ==============================================================================
#
# Four failing gates are not four problems. Thermal margin is computed from
# system power over area, so a design over its power budget is usually over
# its thermal one as well - reporting both as findings counts the same fact
# twice and makes a design look worse than it is.
#
# A cooling-class mismatch is different in kind: it does not depend on any
# number, and no amount of power reduction fixes it. A part that needs airflow
# cannot go in a sealed enclosure at any wattage.

GATE_DERIVATION = {
    # gate -> the gate it follows from, if any
    "thermal": "power",
    "soc_die": "area",
    "board": "area",
}

GATE_KIND = {
    "memory_cooling": "class mismatch - not a magnitude, and not fixable by "
                      "reducing anything",
    "accuracy": "quality - a different network, not a different board",
    "capacity": "does not fit - no bandwidth or power change helps",
}


def gate_causes(result) -> dict:
    """Independent failures, and the ones that follow from them."""
    failed = [g for g, ok in result.gate.items() if not ok]
    derived, independent = {}, []
    for g in failed:
        parent = GATE_DERIVATION.get(g)
        if parent and parent in failed:
            derived[g] = parent
        else:
            independent.append(g)
    return {"failed": failed, "independent": independent, "derived": derived,
            "kinds": {g: GATE_KIND[g] for g in failed if g in GATE_KIND}}


def print_gate_causes(result) -> None:
    c = gate_causes(result)
    if not c["failed"]:
        print("  every requirement met")
        return
    print(f"  {len(c['failed'])} gate(s) failed, "
          f"{len(c['independent'])} independent reason(s):")
    for g in c["independent"]:
        note = c["kinds"].get(g, "")
        print(f"    {g}" + (f"   {note}" if note else ""))
    for g, parent in c["derived"].items():
        print(f"    {g}   follows from {parent}, not a separate finding")
    if len(c["failed"]) > len(c["independent"]):
        print("  Counting the derived ones as findings would make this design")
        print("  look worse than it is - fixing the parent fixes them.")


# ==============================================================================
# Showing a result that has no performance
# ==============================================================================
#
# Not-a-number is right INSIDE the model - it propagates and cannot be used by
# accident. It is wrong on a student's screen, where it reads as a crash. The
# two are different audiences and the same value serves neither on its own.

NOT_EVALUATED = "Not Evaluated"


def show(value, fmt="{:.3f}"):
    """A metric as a person should read it."""
    if isinstance(value, float) and value != value:
        return NOT_EVALUATED
    try:
        return fmt.format(value)
    except (ValueError, TypeError):
        return str(value)


def rank(results, key, lower_is_better=True):
    """Rank feasible designs and EXCLUDE infeasible ones.

    Not sort them last - exclude them. Where not-a-number lands in a sort
    depends on the language, the library and the comparison order, and a
    design that cannot exist should not have a position at all.
    """
    feasible = [r for r in results if "INFEASIBLE" not in r.status]
    excluded = [r for r in results if "INFEASIBLE" in r.status]
    ordered = sorted(feasible,
                     key=lambda r: r.metrics.get(key, float("inf")),
                     reverse=not lower_is_better)
    return ordered, excluded


def print_infeasible(result) -> None:
    """What can still be said about a board that cannot run the model."""
    from .memory import MEMORY_LIBRARY, evaluate as mem_eval
    m = result.metrics
    print(f"  Status                 INFEASIBLE")
    print(f"  Reason                 model does not fit in usable memory")
    mem = MEMORY_LIBRARY[result.config.memory]
    installed = mem.capacity_gbyte * result.config.memory_devices
    required = m.get("Required capacity (GB)", 0.0)
    print(f"  Installed capacity  {installed:>12.1f} GB")
    if required:
        print(f"  Required capacity   {required:>12.1f} GB")
        print(f"  Deficit             {required - installed:>12.1f} GB")
    print()
    for label, key in (("Latency", "Latency (ms)"),
                       ("Delivered throughput", "Delivered throughput (inf/s)"),
                       ("Energy per job", "Energy per inference (mJ)"),
                       ("Pipeline capacity", "Pipeline capacity (inf/s)")):
        print(f"  {label:<22s}{show(m.get(key, float('nan'))):>16s}")
    print(f"  {'Bottleneck':<22s}{result.bound_strength:>16s}")
    print(f"  {'Overall PPACT score':<22s}{'Not Applicable':>16s}")
    print()
    for label, key, fmt in (("System cost", "System cost (USD)", "{:.2f}"),
                            ("Logic silicon", "Logic silicon (mm2)", "{:.2f}"),
                            ("Board area", "Board area (mm2)", "{:.1f}")):
        print(f"  {label:<22s}{show(m.get(key, float('nan')), fmt):>16s}")
    print(f"  {'Cooling class':<22s}{mem.cooling_requirement:>16s}")
    print("\n  These are true of the board. The performance figures are not")
    print("  'slow' or 'zero' - they do not exist, because the configuration")
    print("  does not.")


# ==============================================================================
# What each metric measures, from where to where
# ==============================================================================
#
# The ISP defect at 3.74.0 was not an arithmetic error. Every number was
# internally consistent and one of them was named for a boundary it did not
# measure:
#
#     reported name       sensor-to-control latency
#     actually measured   post-ISP-to-control latency
#
# Three thousand checks passed because all of them compared numbers and none
# of them compared a number with its NAME. A boundary written down can be
# checked; a boundary carried in someone's head cannot.
#
# Every entry states a start point and an end point, and lists the stages that
# fall between them. A stage in the pipeline that appears in no contract, or a
# contract listing a stage the model does not have, is a defect.

BOUNDARY_LINE = "=" * 78


def _wrap_line(text: str, width: int) -> List[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines or [""]


@dataclass(frozen=True)
class Boundary:
    metric: str
    start: str
    end: str
    includes: Tuple[str, ...]
    excludes: Tuple[str, ...] = ()
    note: str = ""
    family: str = "latency"


# Contracts come in FAMILIES. Within a family the members must nest, because
# they measure the same kind of thing over wider and wider boundaries and a
# reader is entitled to subtract one from another. Across families they are
# not comparable at all - an energy is not a shorter latency.
#
# The stages a frame passes through, in order. A metric's contract must be a
# CONTIGUOUS run of these - a boundary that skips a stage in the middle is
# measuring two things with a hole between them.
PIPELINE_STAGES = ("sensor", "isp", "host preprocess", "dispatch",
                   "accelerator", "host postprocess", "control")

# What each family is measured over. Latency and throughput are measured over
# the pipeline STAGES; power, cost and capacity are measured over the system's
# PARTS, and a contract in one cannot be checked against the stage list.
FAMILY_SCOPE = {
    "latency": "stages",
    "throughput": "stages",
    # A family of one. The single-job rate is one over a latency that excludes
    # the ISP, so it cannot be ordered against a capacity that includes it -
    # and an independent check at 3.76.0 found it exceeding the capacity by
    # more than twice on an ISP-assisted design. That is not a defect in
    # either number; it is a defect in comparing them.
    "host pipeline rate": "stages",
    "power": "parts",
    "cost": "parts",
    "capacity": "parts",
}

SYSTEM_PARTS = ("accelerator", "secondary accelerator", "host cpu", "isp",
                "memory devices", "memory interface", "board", "package",
                "development")

METRIC_BOUNDARIES: Tuple[Boundary, ...] = (
    Boundary(
        "Pure inference (ms)",
        start="the accelerator has its input in memory",
        end="the accelerator has produced its output",
        includes=("accelerator",),
        excludes=("sensor", "isp", "host preprocess", "dispatch",
                  "host postprocess", "control"),
        note="What a datasheet quotes. It is the smallest of the three and "
             "the one most often compared against a requirement written for "
             "one of the others."),
    Boundary(
        "Latency (ms)",
        start="the host begins work on a frame",
        end="the host has a formatted result",
        includes=("host preprocess", "dispatch", "accelerator",
                  "host postprocess"),
        excludes=("sensor", "isp", "control"),
        note="The pipeline the designer controls. It excludes the ISP "
             "deliberately - the ISP is upstream and overlaps the next frame - "
             "and that exclusion is why this figure must never be called "
             "sensor-to-control."),
    Boundary(
        "Sensor-to-control (ms)",
        start="the sensor exposes a frame",
        end="a control output is available",
        includes=("sensor", "isp", "host preprocess", "dispatch",
                  "accelerator", "host postprocess", "control"),
        excludes=(),
        note="Everything. This is what a product requirement usually means "
             "and what a reaction-time specification is written against."),

    # --- throughput ------------------------------------------------------
    Boundary(
        "Single-job rate (inf/s)", family="host pipeline rate",
        start="one job starts at the host",
        end="that same job finishes at the host",
        includes=("host preprocess", "dispatch", "accelerator",
                  "host postprocess"),
        excludes=("sensor", "isp", "control"),
        note="One over the pipeline LATENCY, so it inherits that boundary and "
             "excludes the ISP. It is therefore NOT comparable with the "
             "pipeline capacity and is in a family of its own: with an ISP in "
             "the path this figure can exceed the capacity, because no job "
             "actually completes at that rate - the frame passed through a "
             "stage this boundary does not count. Two rates over different "
             "boundaries cannot be ordered, and putting them in one family "
             "asserted that they could."),
    Boundary(
        "Pipeline capacity (inf/s)", family="throughput",
        start="a steady stream is arriving",
        end="the slowest station sets the rate",
        includes=("isp", "host preprocess", "dispatch", "accelerator",
                  "host postprocess"),
        excludes=("sensor", "control"),
        note="The service ceiling, before any limit from what arrives. The "
             "ISP is IN this one and out of the latency, because a station "
             "that overlaps frames limits the rate without lengthening a "
             "job."),
    Boundary(
        "Delivered throughput (inf/s)", family="throughput",
        start="work is offered at the arrival rate",
        end="completed work leaves the system",
        includes=("sensor", "isp", "host preprocess", "dispatch",
                  "accelerator", "host postprocess", "control"),
        excludes=(),
        note="Capacity capped by arrivals. A machine that could do more and "
             "is not being asked to reports its capacity here, not its "
             "ambition."),

    # --- power and energy -------------------------------------------------
    Boundary(
        "Accelerator active power (W)", family="power",
        start="the accelerator die's supply",
        end="the same",
        includes=("accelerator",),
        excludes=("secondary accelerator", "host cpu", "isp",
                  "memory devices", "memory interface", "board", "package",
                  "development"),
        note="One die. A vendor's module figure is a different boundary and "
             "comparing the two was a retracted finding at 3.32.0."),
    Boundary(
        "System power (W)", family="power",
        start="the product's supply rail",
        end="the same",
        includes=("accelerator", "secondary accelerator", "host cpu", "isp",
                  "memory devices", "memory interface", "board"),
        excludes=("package", "development"),
        note="What a battery feels. Averaged over the observation interval, "
             "which is why it can rise while energy per job falls."),
    Boundary(
        "Energy per inference (mJ)", family="power",
        start="one job starts",
        end="that job finishes",
        includes=("accelerator", "secondary accelerator", "host cpu", "isp",
                  "memory devices", "memory interface", "board"),
        excludes=("package", "development"),
        note="Energy over ONE job, not over time. A design can improve this "
             "and worsen the average power, and repeatedly does."),

    # --- cost -------------------------------------------------------------
    Boundary(
        "Logic die cost (USD)", family="cost",
        start="silicon the product fabricates",
        end="the same",
        includes=("accelerator", "secondary accelerator", "host cpu", "isp"),
        excludes=("memory devices", "memory interface", "board", "package",
                  "development"),
        note="What a process node moves. Everything else on this list is "
             "bought and does not shrink with a node."),
    Boundary(
        "System cost (USD)", family="cost",
        start="the bill of materials",
        end="an assembled and tested unit",
        includes=("accelerator", "secondary accelerator", "host cpu", "isp",
                  "memory devices", "memory interface", "board", "package"),
        excludes=("development",),
        note="Recurring cost per unit. Development is excluded here and "
             "amortised separately, because a mask set is not a cost per "
             "unit."),

    # --- capacity ---------------------------------------------------------
    Boundary(
        "Memory capacity (GB)", family="capacity",
        start="memory devices fitted",
        end="the same",
        includes=("memory devices",),
        excludes=("accelerator", "secondary accelerator", "host cpu", "isp",
                  "memory interface", "board", "package", "development"),
        note="What is on the board. Not all of it is available to a model."),
)


def check_metric_boundaries() -> List[str]:
    """Every scope item accounted for, contracts contiguous, families nesting.

    BIDIRECTIONAL by design. Checking only that an included stage contributes
    would miss an omitted one, and checking only completeness would let a
    contract name a stage the model does not have. The ISP defect was the
    first kind and a mutation at 3.75.0 was the second.

    This does not check that the CODE honours a contract - only that the
    contracts are complete and consistent with each other, which is what a
    contract can do on its own. tests_independent.py checks the code.
    """
    problems = []
    for b in METRIC_BOUNDARIES:
        scope = (PIPELINE_STAGES if FAMILY_SCOPE.get(b.family) == "stages"
                 else SYSTEM_PARTS)
        named = set(b.includes) | set(b.excludes)

        # completeness: nothing in scope may be left undecided
        missing = set(scope) - named
        if missing:
            problems.append(
                f"{b.metric}: says nothing about {', '.join(sorted(missing))} "
                f"- something in scope that appears in no contract is "
                f"something nobody has decided about")
        # exclusion: nothing named may be outside scope
        unknown = named - set(scope)
        if unknown:
            problems.append(
                f"{b.metric}: names {', '.join(sorted(unknown))}, which is "
                f"not in the {FAMILY_SCOPE.get(b.family, '?')} of a "
                f"{b.family} metric")
        overlap = set(b.includes) & set(b.excludes)
        if overlap:
            problems.append(f"{b.metric}: {', '.join(overlap)} both included "
                            f"and excluded")

        # contiguity applies to a pipeline, where order means something.
        # A parts list has no order, so a gap in it is not a gap.
        if FAMILY_SCOPE.get(b.family) == "stages":
            idx = sorted(scope.index(x) for x in b.includes if x in scope)
            if idx and idx != list(range(idx[0], idx[-1] + 1)):
                gap = [scope[i] for i in range(idx[0], idx[-1] + 1)
                       if i not in idx]
                problems.append(
                    f"{b.metric}: skips {', '.join(gap)} in the middle - a "
                    f"boundary with a hole measures two things and reports "
                    f"one")

    # within a family, the members must nest. Across families they are not
    # comparable and nothing is claimed.
    for family in sorted({b.family for b in METRIC_BOUNDARIES}):
        members = [b for b in METRIC_BOUNDARIES if b.family == family]
        members.sort(key=lambda b: len(b.includes))
        for a, c in zip(members, members[1:]):
            if not set(a.includes) <= set(c.includes):
                problems.append(
                    f"{family}: {a.metric} is not contained in {c.metric} - "
                    f"two boundaries in one family that overlap without "
                    f"nesting cannot be subtracted from each other")
    return problems


def print_metric_boundaries() -> None:
    print(f"\n{BOUNDARY_LINE}")
    print(" WHAT EACH METRIC MEASURES")
    print(BOUNDARY_LINE)
    print("  A number is not a measurement until its start and end points are")
    print("  stated. The defect this table exists to prevent was not an")
    print("  arithmetic error - it was a figure named for a boundary it did")
    print("  not measure, and every check passed because they compared")
    print("  numbers with numbers and never a number with its name.\n")
    for i, line in enumerate(_wrap_line(" -> ".join(PIPELINE_STAGES), 68)):
        print(f"  {'stages: ' if i == 0 else '          '}{line}")
    for i, line in enumerate(_wrap_line(", ".join(SYSTEM_PARTS), 68)):
        print(f"  {'parts:  ' if i == 0 else '          '}{line}")
    print()
    last_family = None
    for b in METRIC_BOUNDARIES:
        if b.family != last_family:
            print(f"  -- {b.family.upper()} "
                  f"(measured over {FAMILY_SCOPE.get(b.family, '?')}) "
                  + "-" * 30)
            last_family = b.family
        print(f"  {b.metric}")
        print(f"    from   {b.start}")
        print(f"    to     {b.end}")
        for i, line in enumerate(_wrap_line(", ".join(b.includes), 66)):
            print(f"    {'covers ' if i == 0 else '       '}{line}")
        if b.excludes:
            for i, line in enumerate(_wrap_line(", ".join(b.excludes), 66)):
                print(f"    {'omits  ' if i == 0 else '       '}{line}")
        if b.note:
            for line in _wrap_line(b.note, 70):
                print(f"    {line}")
        print()
    problems = check_metric_boundaries()
    if problems:
        print("  PROBLEMS:")
        for p in problems:
            print(f"    - {p}")
    else:
        print("  Every stage is accounted for in every contract, each contract")
        print("  is contiguous, and the three nest from narrowest to widest -")
        print("  so a figure from one can be compared with a figure from")
        print("  another by adding the stages between them, and never by")
        print("  assuming they mean the same thing.")
    print(BOUNDARY_LINE)
