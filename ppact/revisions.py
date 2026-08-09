"""
ppact.revisions - why model parameters changed

A parameter that moves because a result was inconvenient is not calibration, it
is fitting the model to the answer. The difference is invisible in the code
afterwards - both look like a number - so it has to be written down at the
time.

Each entry records five things, and the fourth is the one that matters:

    observed        what went wrong
    suspected       which of the possible causes was picked
    changed         the parameter that moved
    evidence        why the new value is right INDEPENDENTLY of the failure
    affected        what else the change touches

A revision with no independent evidence is a warning sign, and is recorded as
such rather than quietly omitted.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Revision:
    version: str
    observed: str
    suspected: str
    changed: str
    evidence: str
    affected: str
    independent: bool = True     # False when the only reason was the failure


REVISIONS: List[Revision] = [
    Revision(
        version="3.6.0",
        observed="Every Industrial Vision design failed the accuracy gate, "
                 "including the reference - which by definition ships.",
        suspected="Three causes were possible: the quantisation loss figures "
                  "were unrealistic, the reference configuration was wrong for "
                  "the requirement, or the requirement itself was too high. "
                  "The first was chosen.",
        changed="INT8 post-training quantisation loss, 2.0 pp -> 1.2 pp, and "
                "the QAT figures with it.",
        evidence="A well-calibrated INT8 CNN loses well under one point to "
                 "post-training quantisation; two points is closer to what "
                 "poorly calibrated INT8 or an early toolchain gives. The "
                 "original figure was too pessimistic on its own terms.",
        affected="Every application. A single global constant moved medical, "
                 "LLM and image classification together, which is itself the "
                 "problem this revision exposed.",
        independent=True),
    Revision(
        version="3.6.0",
        observed="The reference configuration for four applications did not "
                 "meet the product requirements.",
        suspected="The reference configurations were undersized, not the model.",
        changed="Starting points for Drone, Autonomous Vehicle, AI Inference "
                "and LLM Service were resized upward.",
        evidence="A shipping product meets its own requirements. A drone that "
                 "misses its reaction distance is not on sale, and a 70B model "
                 "does not fit in six HBM stacks - both are checkable without "
                 "reference to the score.",
        affected="Reference scores for those four applications.",
        independent=True),
    Revision(
        version="3.8.0",
        observed="The 3.6.0 accuracy revision used one global constant for all "
                 "model families and quantisation methods.",
        suspected="A single number cannot describe a CNN under QAT and a "
                  "transformer under PTQ, and tuning it to fix one application "
                  "silently moved all nine.",
        changed="Replaced with a table indexed by model family, quantisation "
                "method and precision.",
        evidence="Quantisation sensitivity is well known to differ by "
                 "architecture: transformers lose more than CNNs to INT8 "
                 "post-training quantisation, and detection heads more than "
                 "classifiers. Treating them as one number was the error, "
                 "independent of any reference passing or failing.",
        affected="All applications, but now separably.",
        independent=True),
    Revision(
        version="3.9.0",
        observed="Seven design entries described two accelerators - a GPU beside "
                 "an NPU, or a vision NPU beside a main one - and the model had "
                 "one compute block, so each carried an 'approximated' flag.",
        suspected="The architectures were real; the model was missing a term.",
        changed="A second accelerator with three execution modes (sequential, "
                "parallel, alternative). Area, cost and leakage sum for both "
                "dies whatever they are doing; hand-off and split efficiency "
                "are charged where they occur.",
        evidence="Two engines are not one engine twice as fast, and a model "
                 "that made them so would teach the opposite of the truth. "
                 "The check that matters is that adding silicon can make a "
                 "design WORSE - which it now does: a sequential pair with a "
                 "slower secondary is slower than a single engine, and an "
                 "accelerator doing nothing still costs power and money.",
        affected="Every dual-engine design entry, and the runtime dashboard, "
                 "which now reports the two separately.",
        independent=True),
    Revision(
        version="3.9.0",
        observed="With a GPU taking a fifth of the inference, the Autonomous "
                 "Vehicle reference no longer met its reaction distance.",
        suspected="Two readings were available: the reference was undersized, "
                  "or the share was wrong. The share was wrong - and it is "
                  "worth being explicit that this is the same kind of change "
                  "as the 3.6.0 accuracy revision, made after a failure.",
        changed="GPU share of the inference in the ADAS reference, 0.20 -> 0.05.",
        evidence="Independent of the failure: in an ADAS SoC the GPU is there "
                 "for planning, rendering and non-network tasks. It does not "
                 "run a fifth of the perception network, and modelling it as if "
                 "it did was wrong on its own terms. The design note now says "
                 "explicitly that pushing the share to a tenth breaks the "
                 "safety requirement, so the sensitivity is visible rather "
                 "than tuned away.",
        affected="The Autonomous Vehicle reference only.",
        independent=True),
    Revision(
        version="3.10.0",
        observed="In parallel mode the secondary engine appeared to run its "
                 "share of the inference and the preprocessing simultaneously.",
        suspected="Preprocessing was sized after the work split and then hidden "
                  "behind it, which double-books one engine.",
        changed="Preprocessing is now sized first and added to the secondary's "
                "turn, so the parallel maximum accounts for both. The "
                "partitioning efficiency penalty is charged only when there is "
                "an actual partition.",
        evidence="One array cannot do two things at once, whatever the mode. "
                 "This was an arithmetic error rather than a calibration "
                 "choice, and needed no judgement to identify.",
        affected="Every parallel-mode configuration with accelerator "
                 "preprocessing.",
        independent=True),
    Revision(
        version="3.11.0",
        observed="Splitting a workload across two engines changed neither the "
                 "DRAM traffic nor the effective bandwidth. The model had no "
                 "term for two masters issuing at once.",
        suspected="Memory contention was simply absent, not mis-valued.",
        changed="Added a 12% bandwidth penalty when two engines issue "
                "concurrently - parallel mode with a non-zero split. "
                "Sequential and alternative modes are unaffected, because only "
                "one engine is issuing at a time.",
        evidence="A controller seeing interleaved streams from two masters "
                 "loses row locality and pays more read/write turnaround. This "
                 "is why the parallel advantage survives on a wide bus and "
                 "disappears on a narrow one - a reversal the model could not "
                 "previously produce, and which is the point where the memory "
                 "choice and the accelerator choice meet.",
        affected="Parallel-mode configurations only.",
        independent=True),
    Revision(
        version="3.12.0",
        observed="The previous entry was reported as if the model had produced "
                 "a reversal on a narrow bus. It had not: with the coefficient "
                 "set to zero, parallel execution still wins at LPDDR5 x1 by "
                 "0.245 ms. The sign flip came entirely from the number added "
                 "in the same change.",
        suspected="Two effects were being conflated - shared-bandwidth "
                  "saturation, which is in the roofline and needs no "
                  "parameter, and an interleaving penalty, which is a choice.",
        changed="The coefficient is now scaled by how much the two engines "
                "actually overlap rather than charged flat, and the "
                "documentation separates the two effects. The saturation "
                "result is stated as a model output; the sign flip is stated "
                "as depending on the coefficient.",
        evidence="The saturation is checkable with the coefficient at zero: "
                 "the parallel gain falls from 0.98 ms on HBM to 0.25 ms on a "
                 "single LPDDR5 package, a four-fold reduction that no added "
                 "parameter produced. The interleaving penalty is separately "
                 "real - two masters do cost a controller row locality - but "
                 "its magnitude here is an estimate, and the headline result "
                 "should not have been presented as emergent.",
        affected="How the LPDDR reversal is described, not whether the model "
                 "runs. The regression tests now fix the saturation as the "
                 "robust finding and mark the reversal as coefficient-"
                 "dependent.",
        independent=True),
    Revision(
        version="3.14.0",
        observed="Changing LPDDR for HBM moved the single-job latency but not "
                 "the throughput. Memory was not a pipeline station, so its "
                 "occupancy could never reach the interval.",
        suspected="An omission in the runtime rather than a wrong value: the "
                  "stage list had CPU, ISP and the accelerator, and nothing "
                  "for the transfers.",
        changed="Memory is now a station like the others, and a dual pair is "
                "two stations rather than one. The interval is a max over all "
                "of them.",
        evidence="A memory that cannot keep up limits a pipeline exactly as a "
                 "slow engine does; leaving it out meant the widest memory in "
                 "the library could not change what the system produced per "
                 "second. Needs no calibration to see.",
        affected="Every runtime result. Memory capacity now ranges from 3,020 "
                 "jobs on a single LPDDR5 package to 85,585 on one HBM3E "
                 "stack for the same accelerators, and the three execution "
                 "modes now differ in throughput and not only in latency.",
        independent=True),
    Revision(
        version="3.15.0",
        observed="Memory packaging was a single number, and a negative thermal "
                 "margin could not say whether the compute or the memory put "
                 "the design over.",
        suspected="Two separate boundaries were being collapsed: cost into one "
                  "figure, and heat into one domain.",
        changed="Packaging cost split into interposer, advanced package and "
                "assembly-and-test. Thermal margin split into compute and "
                "memory domains. Logic silicon reported separately from "
                "package footprint.",
        evidence="HBM's price is 47% packaging against roughly 24% for LPDDR "
                 "and GDDR - a difference a lumped figure cannot show, and one "
                 "that changes what HBM IS: ordinary memory in a very "
                 "expensive package. Likewise a mobile design with one HBM "
                 "stack has a compute margin of 92% and a memory margin of "
                 "-399%: the same total figure, but a completely different "
                 "problem to solve.",
        affected="Cost and thermal reporting for every configuration. The "
                 "totals are unchanged; what changed is that they can now be "
                 "attributed.",
        independent=True),
    Revision(
        version="3.16.0",
        observed="An HBM stack in a mobile product reported a memory thermal "
                 "margin of -398%. Arithmetically correct, and useless.",
        suspected="The memory was being judged against the PRODUCT's cooling "
                  "limit rather than against the class its own package "
                  "assumes. The same stack has +30% margin under a datacenter "
                  "limit, so the number was measuring a mismatch, not a "
                  "problem with the memory.",
        changed="Each memory declares the cooling it requires - passive, "
                "airflow or active. The margin is computed against that, and "
                "the mismatch is reported as a gate: this memory needs cooling "
                "this product does not have.",
        evidence="A large negative percentage invites the reading that a part "
                 "is 400% too hot, which is not a quantity. The compatibility "
                 "statement is checkable and actionable; the percentage was "
                 "neither. Independent of any calibration: the arithmetic was "
                 "comparing two different cooling assumptions.",
        affected="GDDR6 now fails in passively cooled products too, which is "
                 "correct - it needs a heatsink. Starting points all still "
                 "ship. Gate counts moved for Industrial Vision and Medical "
                 "Device.",
        independent=True),
    Revision(
        version="3.16.0",
        observed="One HBM3E profile stood for every stack height and capacity.",
        suspected="Not an error, but a missing distinction: 8-high 24 GB and "
                  "12-high 36 GB differ in capacity, yield and assembly cost "
                  "while sharing bandwidth and interface width.",
        changed="Split into HBM3E 24GB and HBM3E 36GB. Added a cost index "
                "beside the dollar figure, and a cost-confidence field which "
                "is LOW for both HBM entries.",
        evidence="Stack height buys capacity, not speed - both profiles move "
                 "1228.8 GB/s over the same 1024-bit interface. HBM wafer "
                 "prices and die areas are contract-dependent and not "
                 "publicly verifiable, so quoting $112 without a confidence "
                 "marker invited it to be read as a price.",
        affected="Memory library and every cost comparison. The index makes "
                 "the comparison survive being wrong about absolute prices.",
        independent=True),
    Revision(
        version="3.17.0",
        observed="Checked against a published product for the first time. Six "
                 "24 GB HBM3E stacks - the way an H200 is actually built - came "
                 "out at 7.37 TB/s against a published 4.80. The model was 54% "
                 "high on HBM bandwidth.",
        suspected="The library used the HBM3E component ceiling of 9.6 Gbps as "
                  "if it were an operating point. Shipping designs run their "
                  "stacks at about 6.25 for power and thermal reasons.",
        changed="Deployed pin rate set to 6.4 Gbps, with the 9.6 Gbps ceiling "
                "recorded separately. Six stacks now give 144 GB and 4.92 TB/s "
                "against a published 141 GB and 4.80 TB/s - within 2.5%.",
        evidence="A vendor's own figures, and the arithmetic is unambiguous: "
                 "4.8 TB/s over six 1024-bit stacks is 6.25 Gbps per pin. "
                 "Independent of anything in this model.",
        affected="Every HBM configuration. The error biased HBM comparisons "
                 "the wrong way in a tool whose point is that HBM is not "
                 "always the answer - it made the expensive option look 54% "
                 "better than it is. Worth noting how the discrepancy was "
                 "nearly missed: a check using four 36 GB stacks landed within "
                 "2% of the published bandwidth by accident, because the wrong "
                 "stack count and the wrong pin rate cancelled.",
        independent=True),
    Revision(
        version="3.17.0",
        observed="With HBM bandwidth corrected downward, the LLM Service "
                 "reference no longer met its own throughput requirement.",
        suspected="The requirement, not the reference. 60 tokens per second "
                  "single-stream on a 70B model was set when HBM bandwidth was "
                  "54% too high, and no published product reaches it.",
        changed="LLM Service target lowered to 35 tokens per second and the "
                "latency budget to 32 ms. The reference is now six 24 GB "
                "stacks, matching how an H200-class part is built.",
        evidence="70 GB of weights read per token over 4.9 TB/s is about 14 ms "
                 "before anything else, so 60 tokens per second single-stream "
                 "is not reachable on one node. Published single-stream 70B "
                 "figures sit in this range. The direction of the change was "
                 "forced by the bandwidth correction; the specific value comes "
                 "from the arithmetic, not from what made a test pass - which "
                 "is a distinction worth stating because from the outside the "
                 "two look identical.",
        affected="LLM Service only. Its reference now ships with a thin "
                 "margin, which is the right description of a serving node.",
        independent=True),
    Revision(
        version="3.17.0",
        observed="A known limitation surfaced while checking the above: the "
                 "model applies a weight-refetch factor derived from dataflow "
                 "efficiency to LLM decode, where every weight is read exactly "
                 "once per token.",
        suspected="The reuse model was built for convolution and does not "
                  "describe autoregressive decode.",
        changed="Nothing yet. Recorded rather than patched, because changing "
                "it would move every LLM result and needs its own check.",
        evidence="In decode there is no reuse to lose: the arithmetic "
                 "intensity is one MAC per weight byte by construction. The "
                 "model currently reads the weights between 1.5 and 2.2 times "
                 "depending on the engine, which overstates traffic.",
        affected="LLM Service and Mobile AI throughput, in the pessimistic "
                 "direction. CLOSED at 3.18.0.",
        independent=True),
    Revision(
        version="3.18.0",
        observed="Closing the item above. Text workloads were running through "
                 "the convolution reuse path, which read the weights 1.5 to "
                 "2.2 times per token.",
        suspected="Not a wrong coefficient - a wrong model. Decode has no "
                  "reuse to lose: each parameter produces one token and is "
                  "read once.",
        changed="Text workloads now use a decode traffic model - weights once "
                "times a read factor, plus KV cache proportional to context, "
                "plus activations - and bypass the reuse path entirely. "
                "Prefill is computed and reported separately, because it is "
                "compute bound where decode is memory bound.",
        evidence="Arithmetic intensity in decode is one MAC per weight byte by "
                 "construction. The default read factor of 1.05 is an "
                 "allowance for cache behaviour and kernel boundaries, not for "
                 "reuse, and is marked estimated.",
        affected="Six HBM3E stacks now give 55.8 tokens per second where they "
                 "gave 38.6 - a 45% correction in the optimistic direction, "
                 "the opposite of the bandwidth correction that preceded it. "
                 "Both errors were in the model; they happened to partly "
                 "cancel, which is why neither showed up until the two were "
                 "checked separately.",
        independent=True),
    Revision(
        version="3.19.0",
        observed="HBM4 added as a separate generation rather than as a faster "
                 "HBM3E.",
        suspected="Not a defect - a gap. HBM4 changes the interface, not the "
                  "clock, and a multiplier on HBM3E would have described the "
                  "wrong thing.",
        changed="Two HBM4 profiles, 12-high 36 GB and 16-high 48 GB. Interface "
                "2048 bits over 32 channels; operating pin rate 6.4 Gbps, the "
                "same as HBM3E deploys at; specification ceiling 11 Gbps "
                "recorded separately. Energy per bit 2.6 pJ against 3.9.",
        evidence="JEDEC doubled the interface to 2048 bits in April 2025. SK "
                 "hynix demonstrated 1.6 TB/s per stack - which at 2048 bits "
                 "is 6.4 Gbps, no faster than HBM3E runs. The bandwidth comes "
                 "from width, and so does the power saving. Micron cites over "
                 "2.8 TB/s per stack at over 11 Gbps, which the model "
                 "reproduces as its ceiling at 2.82.",
        affected="Memory library only. Every HBM3E result is unchanged, "
                 "including the 55.8 tokens per second figure, and all nine "
                 "starting points still ship.",
        independent=True),
    Revision(
        version="3.20.0",
        observed="The first HBM4 demonstration put a 24 GB HBM3E stack beside "
                 "a 36 GB HBM4 stack and reported the difference as the "
                 "generation effect. The memory subsystem cost rose 75%.",
        suspected="Three things were changing at once - interface width, "
                  "capacity and package - and all of it was being attributed "
                  "to the generation.",
        changed="Four comparisons, each holding something different: equal "
                "capacity, equal stack count, minimum to fit the model, and "
                "equal total bandwidth. Each states what it holds constant and "
                "which effects are inside it.",
        evidence="Held at equal capacity the same generation change costs 22%, "
                 "not 75%. The remaining 53 points were buying memory, not "
                 "buying HBM4. Nothing needed calibrating to see this - only "
                 "holding one variable still.",
        affected="How the HBM4 case is presented. No model values changed. The "
                 "most useful of the four turned out to be the equal-bandwidth "
                 "comparison, where HBM4 reaches the same rate with half the "
                 "stacks, 48% less footprint and 39% less cost - an argument "
                 "about packaging rather than about speed.",
        independent=True),
    Revision(
        version="3.21.0",
        observed="The equal-bandwidth comparison matched on EFFECTIVE "
                 "bandwidth while the two sides carried different controller "
                 "efficiencies - 0.85 for HBM3E and 0.88 for HBM4. The 3.5% "
                 "edge HBM4 appeared to hold came entirely from that "
                 "assumption, not from the wider interface.",
        suspected="An assumption smuggled into a comparison built to isolate "
                  "one variable.",
        changed="Peak, effective and controller efficiency are now shown as "
                "three separate rows, and the report says when the two "
                "efficiencies differ and by how much. The HBM4 efficiency "
                "figure is registered as a low-confidence coefficient with "
                "the comparison named as what rests on it. Capacity "
                "requirement and margin are shown, because half the stacks is "
                "half the capacity and 'the same bandwidth from fewer stacks' "
                "only holds where the model still fits.",
        evidence="Peak bandwidth is identical on both sides at 9,830 GB/s. "
                 "Nothing needed measuring to see that the remaining "
                 "difference was the efficiency figures.",
        affected="Presentation of the equal-bandwidth comparison. No model "
                 "values changed. Also corrected the wording of the "
                 "conclusion: HBM4's value is not 'packaging' but reaching a "
                 "target bandwidth with fewer stacks and a smaller footprint, "
                 "which is one consequence among several.",
        independent=True),
    Revision(
        version="3.22.0",
        observed="Results were being described as VERIFIED after being "
                 "compared with published datasheets.",
        suspected="An overclaim rather than an error. The model was FITTED to "
                  "those figures, so agreement is by construction: adjusting a "
                  "profile until it matches a datasheet is alignment, not "
                  "confirmation.",
        changed="Five evidence levels - published reference, reference-"
                "aligned, simulated, estimated, engineering assumption - with "
                "every significant figure placed in one. VERIFIED is not among "
                "them, and its absence is stated rather than left to be "
                "noticed. The external comparison is retitled REFERENCE "
                "ALIGNMENT.",
        evidence="Verification would mean measuring hardware or checking "
                 "against a golden model. Neither happened. The word would "
                 "have been the strongest claim in the project and the least "
                 "supported one.",
        affected="Wording throughout, and one real defect: the dual-"
                 "accelerator report was tagging both of its own latency "
                 "figures 'measured'. The regression suite now refuses any "
                 "line that labels a simulator output as measured.",
        independent=True),
    Revision(
        version="3.23.0",
        observed="Mutation testing: of 36 deliberate defects, 8 survived the "
                 "whole suite. Four were critical. A thousand passing tests "
                 "had not been evidence that anything was being watched.",
        suspected="Checks written around totals rather than around the parts "
                  "that make them. Folding wait time into active time kept "
                  "active+wait+idle equal to the window, so the partition "
                  "looked sound while its contents were wrong.",
        changed="Three verification paths added - accounting, ownership "
                "fingerprinting and assumption isolation - plus a mutation "
                "harness and a differential suite that recomputes the pipeline "
                "by discrete-event simulation.",
        evidence="Kill rate went from 78% to 100%, and critical from 81% to "
                 "100%. More to the point, the survivors pointed at two real "
                 "defects rather than at missing tests.",
        affected="Two model defects, both in the pipeline. See below.",
        independent=True),
    Revision(
        version="3.23.0",
        observed="The single-accelerator pipeline station was core time - "
                 "compute plus transfer minus overlap - while the dual-engine "
                 "stations were compute only.",
        suspected="An inconsistency introduced when memory became a station: "
                  "the transfers were then counted in the memory station as "
                  "well as inside the accelerator's.",
        changed="The single station is now compute occupancy, matching the "
                "dual definition.",
        evidence="In a pipeline the transfers for the next job overlap the "
                 "compute for this one, so a station's occupancy is its own "
                 "work. No calibration needed to see it once the two "
                 "definitions were put side by side.",
        affected="Single-accelerator pipeline interval, overstated by up to "
                 "9.3% and by more the faster the memory - the error grew "
                 "exactly where a student would be evaluating whether faster "
                 "memory was worth buying.",
        independent=True),
    Revision(
        version="3.23.0",
        observed="The offload transfer appeared in the memory station AND in "
                 "the accelerator station. Found by comparing module busy time "
                 "against an independent discrete-event simulation.",
        suspected="Double counting, not a wrong value.",
        changed="The accelerator station keeps the dispatch and the hand-off - "
                "bubbles on the engine - and the transfer stays with the "
                "memory.",
        evidence="The same bytes cannot occupy two stations at once. Nothing "
                 "in the analytical model could have noticed: the module took "
                 "its active time from the stage, so both were wrong together "
                 "and agreed with each other.",
        affected="Any configuration with accelerator preprocessing. The "
                 "accounting checks now compare each station against its "
                 "PARTS rather than against itself.",
        independent=True),
    Revision(
        version="3.24.0",
        observed="Scenario testing, with directions written down beforehand: a "
                 "drone swapping LPDDR5 for HBM3E came out drawing 8.7% LESS "
                 "system power. Predicted up, model said down.",
        suspected="Memory energy was traffic only - bytes times eight times "
                  "picojoules per bit - with no term for the power a memory "
                  "draws whether or not it is being read.",
        changed="Added background power per package: refresh across every die, "
                "the PHY and I/O termination. 0.15 W for LPDDR5, 0.85 for "
                "GDDR6, 5.0 to 7.5 for an HBM stack.",
        evidence="HBM moves a bit for 3.9 pJ against LPDDR5's 5.0, so per bit "
                 "it IS more efficient - the model was not wrong about that. "
                 "It was wrong that a workload moving 222 MB per inference "
                 "would therefore draw less. An HBM stack does not idle at a "
                 "fifth of a watt. Checkable without calibration: the "
                 "component model already carried a 25.6 W peak figure the "
                 "system never used.",
        affected="Every configuration. A drone's memory power goes from 0.69 W "
                 "to 5.32 W when it takes HBM, which is the direction that "
                 "matters in a tool whose point is that HBM is not free. The "
                 "LLM case is unchanged in direction: HBM4 still lowers energy "
                 "per token, because there the traffic is enormous and the "
                 "rate doubles. This is the defect that a thousand internal "
                 "consistency checks could not have found - nothing was "
                 "inconsistent, a term was simply missing.",
        independent=True),
    Revision(
        version="3.25.0",
        observed="Nine real NPU adoption cases were assembled as a benchmark "
                 "set. Seven of them describe architectures this model cannot "
                 "express.",
        suspected="Not a defect - a coverage boundary that had not been "
                  "written down. The temptation was to map each case onto the "
                  "nearest thing the model does support and report a number.",
        changed="Each case records what the model is missing and refuses to "
                "produce a figure when it cannot represent the architecture. "
                "The four kinds of number - company baseline, company target, "
                "simulator result, field measurement - are kept apart, and the "
                "fourth is empty because none of these systems is built.",
        evidence="A three-accelerator inspection system run through a two-"
                 "accelerator model produces a number about a different "
                 "machine. The missing features are concrete and checkable: "
                 "three or more engines, different models per engine, sensor "
                 "fusion, image tiling, retrieval as a pipeline stage, "
                 "concurrent users and percentile latency.",
        affected="Nothing computational. What changed is that the model now "
                 "states where it stops. Two of nine cases run; the useful "
                 "result of the exercise is the list of seven that do not.",
        independent=True),
    Revision(
        version="3.26.0",
        observed="The industry case set was rebuilt from the source proposals "
                 "rather than from summaries. Five of ten cases turned out to "
                 "be expressible, not two - the real architectures are simpler "
                 "than the summaries suggested.",
        suspected="A second-hand description had made several cases sound more "
                  "exotic than they are. One of them - the same detector on "
                  "two modules in parallel - is exactly what the dual-engine "
                  "model was built for.",
        changed="Case database rebuilt with the stated KPI figures, and the "
                "runners mapped onto engines matched by peak TOPS.",
        evidence="Source proposals with named models, backbones, resolutions "
                 "and measured baselines. Still SECONDARY - these are company "
                 "proposals - but read directly rather than relayed.",
        affected="Five cases now run. The rest still refuse.",
        independent=True),
    Revision(
        version="3.26.0",
        observed="Mapping the cases exposed that the compute library tops out "
                 "well below the parts these products use: 49 TOPS at the "
                 "largest, against an 80 TOPS edge box in the field. Worse, "
                 "'Mobile GPU' at 2.5 TOPS was standing in for Orin-class "
                 "modules of tens of TOPS.",
        suspected="A library built for phone and small-camera parts being "
                  "asked about industrial edge boxes.",
        changed="Added an Orin-class edge GPU at about 50 dense TOPS and an "
                "80 TOPS class NPU.",
        evidence="Without them a GPU-to-NPU comparison was measuring an "
                 "eighteen-fold compute jump that does not exist in the "
                 "products described - the accelerator improvements were "
                 "coming out at 95% when the companies claim a half to a "
                 "third of that. Checkable from the datasheets in the "
                 "proposals, without any calibration.",
        affected="Nothing existing: all nine starting points still ship and "
                 "every suite passes. What changed is that the library now "
                 "spans the range these cases live in. A residual gap remains "
                 "in NPU static power - a 25 TOPS module rated at 5 W total is "
                 "more efficient than anything modelled here.",
        independent=True),
    Revision(
        version="3.27.0",
        observed="An embedded GPU appeared to run YOLOv8s at 320x320 in 0.26 ms "
                 "of compute. Such a part measures several milliseconds.",
        suspected="Utilisation was a constant. A detector that small does not "
                  "fill a general-purpose engine - kernels launch and drain "
                  "before the array is busy - and the per-inference software "
                  "cost was absent entirely.",
        changed="Utilisation is now derated by how much work there is relative "
                "to what an engine needs to fill: 1.0 ms at peak for a GPU, "
                "0.25 for a systolic NPU. A fixed framework overhead is "
                "charged per inference for vision pipelines and NOT for "
                "autoregressive decode, which launches a graph once.",
        evidence="Independent of any target: 42% utilisation on a 2.7 GMAC "
                 "workload implies an engine that fills instantly, which no "
                 "GPU does. Worth recording that the FIRST value chosen - 3 ms "
                 "to fill - was picked because it put the agricultural case "
                 "near 9 ms, and it took 17% off the LLM token rate as a side "
                 "effect. That was calibrating to a target. The value now used "
                 "is sub-millisecond, which is what launch and fill actually "
                 "cost, and the LLM moved 3.6%.",
        affected="Every small-model latency. The agricultural GPU baseline "
                 "went from 1.21 ms to 4.47 ms, which is in the range such "
                 "parts measure.",
        independent=True),
    Revision(
        version="3.27.0",
        observed="A dual-module design appeared to be 126% WORSE on power than "
                 "the GPU it replaced, against a company claim of three times "
                 "the inferences per watt.",
        suspected="Two boundary errors at once: comparing a module rating "
                  "against die leakage, and comparing WATTS for a claim about "
                  "work per joule.",
        changed="Power split into die leakage, module idle and a module "
                "maximum, with the module figure taking precedence where one "
                "is stated. Reports now show inferences per watt beside watts.",
        evidence="A part rated '25 TOPS, 5 W' states a module figure covering "
                 "die, DRAM, PMIC and interface. And a design doing three "
                 "times the work in a third of the time draws more watts while "
                 "using less energy - comparing watts made that look like a "
                 "regression. Inferences per watt comes out at 2.0 to 3.4 "
                 "across the two cases, against a claimed 3.0.",
        affected="Every power comparison. The apparent reversal was a metric "
                 "choice, not a model defect - which is the more embarrassing "
                 "of the two.",
        independent=True),
    Revision(
        version="3.27.0",
        observed="Correcting utilisation left the AI Inference reference short "
                 "of its throughput target.",
        suspected="Batching. A serving node processes many requests at once; "
                  "the model processes one.",
        changed="Reference resized to eight stacks, with the reason stated in "
                "the entry. Batching recorded as an open limitation.",
        evidence="An unbatched GPU reaches under 1% of peak on a 7 GMAC "
                 "inference, which is correct for one request and wrong for a "
                 "serving node. The model has no batch dimension. OPEN.",
        affected="AI Inference only. The figure is pessimistic and is labelled "
                 "as such rather than corrected by a coefficient.",
        independent=True),
    Revision(
        version="3.28.0",
        observed="A signed programme review sheet was recorded as a PUBLISHED "
                 "REFERENCE on the strength of being signed and dated.",
        suspected="Authority was being confused with availability. Only the "
                  "second is what that level is for.",
        changed="PUBLISHED REFERENCE now requires public availability, and the "
                "suite refuses any entry at that level whose basis names an "
                "internal, proposal or review source.",
        evidence="A reference exists so someone can look it up and disagree. A "
                 "document nobody outside can see fails that test however well "
                 "signed it is - the same error as the VERIFIED wording "
                 "corrected at 3.22.0, in a different place.",
        affected="Evidence classification only.",
        independent=True),
    Revision(
        version="3.29.0",
        observed="Checked against an external case database for the first "
                 "time. The memory-bound decode arithmetic matched almost "
                 "exactly - 18.75 and 93.75 against a published 19 and 94. The "
                 "DELIVERED rate did not: the model produced 93% of that "
                 "ceiling and published deployments reach a quarter to a half.",
        suspected="The roofline was right and the serving stack was absent - "
                  "no scheduler, sampling, detokenisation or per-token "
                  "framework dispatch.",
        changed="Added a serving-stack efficiency for text workloads, as a "
                "SEPARATE overhead term rather than a scaling of core time - "
                "dividing core time broke the roofline invariant on 444 of "
                "2000 random draws. The LLM reference moved from six HBM "
                "stacks to eight: the CONFIGURATION changed, not the "
                "requirement.",
        evidence="No deployment reaches 93% of a memory ceiling.",
        affected="Every LLM result. The reference goes from 55.8 to 38.9 "
                 "tokens per second. First correction in the project driven by "
                 "an EXTERNAL comparison rather than internal inconsistency - "
                 "a whole term was missing and nothing inside could notice.",
        independent=True),
    Revision(
        version="3.30.0",
        observed="A second published deployment - 32B on four cards at 60 "
                 "tokens per second - brackets the serving efficiency at 0.32 "
                 "under FP8 or 0.64 under FP16. The first reference brackets "
                 "at 0.28 or 0.54. Neither states its precision.",
        suspected="The coefficient cannot be pinned from public sources, and "
                  "0.55 was chosen from one reading at its optimistic end.",
        changed="Nothing numerical. Both readings recorded as RANGE checks, "
                "and the coefficient marked OPEN with the size of the possible "
                "error stated: if the figures are FP8 - likelier for both "
                "parts - every LLM token rate here is about 1.7x too high.",
        evidence="Two independent deployments agreeing on shape and "
                 "disagreeing on value depending on an unstated parameter. "
                 "Picking a number would have looked like calibration and been "
                 "a guess.",
        affected="Nothing computed. The largest uncertainty in the model is "
                 "now named, and can only be narrowed by measurement. OPEN.",
        independent=True),
    Revision(
        version="3.30.0",
        observed="Accelerator power had never been compared with a real "
                 "module. A published 25 TOPS vision module draws about 3 W at "
                 "the MODULE boundary; the nearest library part spends 6 W on "
                 "static power alone at the SILICON boundary.",
        suspected="The library is pessimistic about accelerator power. A "
                  "module figure includes regulators, memory interface and "
                  "board, so silicon-only static power should come out well "
                  "below it and instead comes out above.",
        changed="A power gap report that does the comparison and prints it. "
                "The values are unchanged.",
        evidence="0.146 W per TOPS of static power against a module rated at "
                 "0.120 W per TOPS including everything around it.",
        affected="RETRACTED at 3.32.0 - the comparison used silicon leakage "
                 "against a module figure and the finding does not survive "
                 "being made at the same boundary on both sides. Left in the "
                 "log rather than deleted: a withdrawn finding is part of the "
                 "record, and removing it would hide that the project spent a "
                 "version believing it.",
        independent=True),
    Revision(
        version="3.31.0",
        observed="External cases were being used one at a time, with no rule "
                 "separating the ones that set coefficients from the ones that "
                 "test them. At 3.30.0 a case intended as independent evidence "
                 "was used to bracket the serving coefficient.",
        suspected="Without a split, every external case becomes calibration "
                  "the moment it disagrees, and the whole exercise turns into "
                  "fitting with extra steps.",
        changed="Twelve cases split into CALIBRATION, HOLDOUT and CHALLENGE. A "
                "holdout case may not be used to choose anything, and the "
                "regression suite enforces it. The contaminated case is moved "
                "to calibration and MARKED as contaminated rather than quietly "
                "reclassified; its performance-per-watt claim, which was never "
                "used, remains available as holdout.",
        evidence="Agreement with a case that set a coefficient is agreement by "
                 "construction. Only the holdout results are not circular, and "
                 "of four, the model fails one and cannot compare two.",
        affected="No values. What changed is that the project can now say "
                 "which of its agreements mean anything. The coefficient was "
                 "also renamed to declare its scope - single-stream decode - "
                 "because it is a property of a serving stack, not of "
                 "hardware.",
        independent=True),
    Revision(
        version="3.31.0",
        observed="The LLM reference had been moved from six HBM stacks to "
                 "eight after serving losses were added, because six no longer "
                 "met the token-rate requirement.",
        suspected="Defensible engineering and indistinguishable from fitting a "
                  "design to a target. From outside there is no way to tell "
                  "which it was.",
        changed="Both are now shown. A published-class reference at six "
                "stacks, matching a shipping part, which does NOT meet the "
                "requirement; and a requirement-matched reference at eight, "
                "which does.",
        evidence="A published part missing a requirement is a finding about "
                 "the requirement. Hiding it by moving the reference would "
                 "have removed the only interesting thing in the comparison.",
        affected="LLM Service design options. The failing configuration is "
                 "reported rather than replaced.",
        independent=True),
    Revision(
        version="3.32.0",
        observed="The power gap reported at 3.30.0 does not exist. It compared "
                 "silicon leakage - 6 W - against a module figure of 3 W and "
                 "concluded the model was pessimistic. The system does not "
                 "read that field when a module idle power is stated; it uses "
                 "1.4 W. At the module boundary the model spans 1.4 to 3.6 W "
                 "against a published 2-5 W range.",
        suspected="The report written to expose boundary errors contained one. "
                  "Two power fields exist for exactly this reason and the "
                  "comparison used the wrong one.",
        changed="The report now compares at the module boundary on both sides "
                "and excludes any published figure that includes a host. The "
                "3.30.0 finding is retracted, and the power-model invariants "
                "are checked instead: monotone in utilisation, floored at "
                "module idle, capped at module maximum, and two lightly-used "
                "modules do not draw twice the maximum.",
        evidence="The model produces 1.47 W for a 25 TOPS-class part under a "
                 "light load and 3.0 W under a heavy one. A published typical "
                 "of 3 W sits inside that span, which is the most a range can "
                 "confirm.",
        affected="No values. A false defect was withdrawn, which is worth as "
                 "much as finding a real one - it had been recorded as OPEN "
                 "and would have justified changing every accelerator entry.",
        independent=True),
    Revision(
        version="3.32.0",
        observed="One external source made three separate claims - a TOPS "
                 "rating, a typical power and an operating range - and the "
                 "case was being treated as a single unit.",
        suspected="A source is not a claim. Using one of its claims to fit a "
                  "coefficient does not spend the others, but it does mean "
                  "they are no longer independent of it.",
        changed="Claims split. The TOPS rating and the typical power are "
                "calibration; the operating range is CORROBORATION, a fourth "
                "set for evidence that is consistent but not independent, and "
                "it records that it shares a source with the calibration "
                "claim.",
        evidence="Calling a same-source range a holdout would overstate what "
                 "agreement with it shows - it shares every assumption the "
                 "vendor made.",
        affected="A holdout case exposed that the product-class NPU power "
                 "question needed examining, and was therefore promoted to "
                 "calibration rather than left unused to preserve a clean "
                 "holdout. The cost is real: no absolute-value confirmation "
                 "now remains in the holdout set, and the report says so "
                 "rather than leaving it to be inferred from a short list. "
                 "Needs a module power figure from a different vendor.",
        independent=True),
    Revision(
        version="3.33.0",
        observed="Two independent-vendor module figures were checked, and they "
                 "disagree with each other by more than either disagrees with "
                 "the model. One vendor states about 3 W typical for a 25 TOPS "
                 "M.2 module; another states 6-8 W for a 24 TOPS module of the "
                 "same form factor.",
        suspected="Watts per TOPS at a given class is not a quantity with a "
                  "single value. Calibrating to either figure would have been "
                  "fitting to a vendor rather than to a product class.",
        changed="Both added as HOLDOUT, and the spread itself recorded as a "
                "case. Nothing was calibrated to either.",
        evidence="A factor of 2.3 between two vendors at the same TOPS class "
                 "and form factor. The model gives 2.5-2.7 W under a "
                 "multi-camera load, below the low end but inside the spread, "
                 "and a single-vendor calibration would have moved it away "
                 "from the other vendor by as much as it moved it toward one.",
        affected="No values. The holdout set now has an absolute-value case "
                 "again, from a vendor that had no part in any calibration - "
                 "which was the gap left open at 3.32.0. Also: a figure "
                 "described as 'under 3 W average' turned out on checking to "
                 "be the PER-CHIP average, with the module at 6-8 W. The same "
                 "boundary trap, caught before it entered the database. The "
                 "vendor's full figures were then confirmed: 0.5-3 W per chip "
                 "by workload, 0.6-2 W per chip average, 6-8 W for the "
                 "four-chip module, passively cooled. Their own numbers are "
                 "internally tight - four chips at 0.6-2 W is 2.4-8 W, so the "
                 "module figure sits at the top of what the chip figures "
                 "allow.",
        independent=True),
    Revision(
        version="3.33.0",
        observed="A deviation had been reported against a library field the "
                 "model never reads.",
        suspected="Nothing connected an external claim to the code path that "
                  "would answer it, so any field with a plausible name could "
                  "be compared against anything.",
        changed="A metric provenance table: each external claim names its "
                "formula, the metrics it maps to, and the function that "
                "consumes them. The suite checks that every mapped metric is "
                "one the model actually produces, and that the power report "
                "compares module figures against module power rather than "
                "silicon leakage or a design ceiling.",
        evidence="The rule is cheap and the error it prevents cost a version. "
                 "A claim that cannot be traced to a consuming function should "
                 "not generate a deviation report at all.",
        affected="Verification only. Five named checks, one for each way the "
                 "boundary can be mixed up.",
        independent=True),
    Revision(
        version="3.34.0",
        observed="The same published module is passively cooled at its 6-8 W "
                 "average, which is a statement about the COOLING model rather "
                 "than the power model and had never been checked.",
        suspected="Nothing - this was an opportunity rather than a defect. A "
                  "cooling classification that no real product had been put "
                  "against is a classification nobody has tested.",
        changed="Added as a direction-only holdout case. Nothing calibrated.",
        evidence="8 W over the package footprint is 0.025 W/mm2 against a "
                 "passive limit of 0.03, so the model admits exactly what the "
                 "vendor ships - and refuses the same footprint at the "
                 "module's 15 W design ceiling, which is also right, because "
                 "the vendor quotes an average and not a maximum.",
        affected="RETRACTED at 3.36.0. The vendor's own support documentation "
                 "requires the chips to stay below 100 C, states they throttle "
                 "to half frequency above it, and recommends strong airflow "
                 "over the module. Passive-only operation is not established, "
                 "and the cooling model still has no external confirmation of "
                 "any kind.",
        independent=True),
    Revision(
        version="3.35.0",
        observed="A published comparison of three product classes - an M.2 "
                 "edge module at 6-8 W, an embedded GPU module at 15-60 W, and "
                 "a desktop GPU at 100-450 W - spans 39x from end to end. The "
                 "library spans 15x for the same three classes driven to "
                 "saturation, and the understatement grows with size: about "
                 "half at the edge, a fifth at the top.",
        suspected="The accelerator power range is too narrow rather than "
                  "misplaced. Utilisation falls with array size in this model, "
                  "so a large part never reaches the power its class is rated "
                  "for.",
        changed="Nothing. Recorded as a holdout ratio case, and the ORDERING "
                "is now a regression check - ordering is structural, the range "
                "is calibration, and only the first should be enforced.",
        evidence="A ladder is a stronger test than any single point because it "
                 "cannot be satisfied by fitting one part. It also cannot be "
                 "acted on lightly: three points from one comparison table, "
                 "each under a workload nobody states, is too thin a basis for "
                 "reshaping every accelerator entry.",
        affected="No values. This is the third power finding in three "
                 "versions, and the only one that has survived scrutiny - the "
                 "first was a boundary error in my own report, the second "
                 "dissolved into a 2.3x disagreement between vendors, and this "
                 "one stands because it is about a range rather than a point. "
                 "OPEN.",
        independent=True),
    Revision(
        version="3.36.0",
        observed="The cooling confirmation claimed at 3.34.0 does not hold. "
                 "The vendor whose module was cited requires each chip below "
                 "100 C, throttles to half frequency above it, and recommends "
                 "strong airflow over the same part described elsewhere as "
                 "fan-less.",
        suspected="The arithmetic was right and the conclusion did not follow. "
                  "A power density under a passive limit is a statement about "
                  "watts per square millimetre; a thermal outcome depends on "
                  "heatsink area and resistance, ambient temperature, natural "
                  "against forced convection, chassis, sustained against burst "
                  "load, junction temperature and the host's own heat. The "
                  "limit represents none of them.",
        changed="The claim is split into four: a per-chip average that is "
                "genuinely comparable, a module figure that deviates, a "
                "thermal DIRECTION that the model does support - cooling "
                "governs whether rated performance is reached - and the "
                "passive-only claim itself, left at BOUNDARY REVIEW REQUIRED "
                "because the vendor's marketing and support documentation "
                "disagree and neither states an ambient temperature, a chassis "
                "or a sustained load. A new status was added for exactly this.",
        evidence="Vendor support documentation, publicly available and "
                 "explicit. Needed no interpretation.",
        affected="The passive cooling limit is now registered as an "
                 "ENGINEERING ASSUMPTION with NO external confirmation, which "
                 "is what it always was. This is the second confirmation I "
                 "have claimed and withdrawn in three versions, both times "
                 "because a number landing where I expected was treated as "
                 "agreement rather than as a coincidence that still needed "
                 "checking.",
        independent=True),
    Revision(
        version="3.37.0",
        observed="The model could compute a value but not say whether it was "
                 "ordinary. A latency of 320 ms means nothing to a student who "
                 "does not know that industrial inspection lives between 1 and "
                 "30 ms.",
        suspected="Nothing wrong - a missing layer. Judgement about what is "
                  "normal for a product class sat outside the tool entirely.",
        changed="A result interpreter: typical bands for seven metrics across "
                "five domains, with a per-metric guide and a measurement "
                "template that turns a clock, a cycle count and a power "
                "reading into the derived figures.",
        evidence="The bands sit BELOW the system model, not above it. They "
                 "describe accelerators - TOPS, TOPS per watt, utilisation - "
                 "and say nothing about CPU time, pipelines, dual engines, "
                 "footprint, cost or thermal margin, which is most of what "
                 "this model computes. Every mapping declares which simulator "
                 "metric it reads and whether the boundaries agree; two are "
                 "marked WIDER on our side and softened rather than compared "
                 "silently.",
        affected="Nothing computed. The report states three times that a value "
                 "outside a band is a prompt rather than a score, and the "
                 "suite checks that it does. Note on the diagram in that "
                 "module: it first drew the ranges and the simulation as "
                 "successive stages, which reads as though the bands feed the "
                 "model. Corrected at 3.38.0 - they enter the interpreter from "
                 "the side and never touch a calculation.",
        independent=True),
    Revision(
        version="3.37.0",
        observed="On its first run the interpreter flagged four of nine "
                 "starting points as having abnormally high utilisation.",
        suspected="A definition collision, not a finding. The model reports a "
                  "'Compute utilisation' that is compute time over core time - "
                  "the share of an engine's busy period spent computing rather "
                  "than waiting - and the published band means operations "
                  "achieved over operations possible. Two different quantities "
                  "under one word.",
        changed="The engine's arithmetic utilisation is now reported "
                "separately and is what the band reads. With the right "
                "mapping, eight of nine references look ordinary.",
        evidence="The metric-provenance rule added at 3.33.0 checks that a "
                 "mapped key EXISTS. It does not check that it MEANS the same "
                 "thing, which is a different and harder property - and this "
                 "is the third comparison in this project undone by a name "
                 "that fitted where the definition did not.",
        affected="One new reported metric. No behaviour changed.",
        independent=True),
    Revision(
        version="3.38.0",
        observed="The interpreter compared a result against one thing - the "
                 "domain band - and reported the requirement count as an "
                 "aside. And its own diagram implied the bands were an input "
                 "to the simulation.",
        suspected="Two separate framing errors. A result has three natural "
                  "comparisons and they answer different questions: the "
                  "REQUIREMENT says whether it ships, the REFERENCE says "
                  "whether it beats where the course starts, and the BAND says "
                  "whether it is ordinary. None subsumes the others, and "
                  "collapsing them throws away what makes the comparison worth "
                  "making.",
        changed="The report is now three numbered sections plus a paragraph on "
                "reading them together, which handles all four combinations of "
                "ships and ordinary. The diagram shows the ranges entering the "
                "interpreter from the side.",
        evidence="An example makes the case: one design option is 58% faster "
                 "than the reference with 2.4x its throughput, sits inside "
                 "every domain band, and does not ship - it misses the "
                 "accuracy requirement. One verdict could not have carried "
                 "that.",
        affected="Presentation only. No computed value changed, which is the "
                 "property this module has to preserve.",
        independent=True),
    Revision(
        version="3.39.0",
        observed="The domain verdicts read LOW, OK and HIGH. LOW is a failing "
                 "grade in every other context a student meets, and being "
                 "under a typical band is not a failure - a design that meets "
                 "its latency requirement on less peak compute than usual is "
                 "doing something right.",
        suspected="A word choice that quietly turned a description into a "
                  "grade, in the one module built to avoid exactly that.",
        changed="Below / Within / Above Typical Range, and every flagged "
                "metric now carries the sentence that this is not a failure by "
                "itself and only the requirements decide whether a product can "
                "ship.",
        evidence="Needed no argument: the module's own purpose is to describe "
                 "rather than score, and three of its five verdict words were "
                 "scores.",
        affected="Wording. No computed value and no verdict changed.",
        independent=True),
    Revision(
        version="3.39.0",
        observed="Nothing enforced that the three comparisons were actually "
                 "independent of each other.",
        suspected="Not a defect but an unguarded property. If a domain band "
                  "could move a requirement verdict, the bands would have "
                  "become a grading scheme, and nothing would have said so.",
        changed="Metamorphic checks in three directions: moving a domain band "
                "must leave the requirements, the raw metrics and the "
                "reference comparison untouched; moving the reference must "
                "leave the requirements and the bands untouched; moving a "
                "requirement threshold must change ONLY the requirement "
                "verdict.",
        evidence="Independence is the property that makes three comparisons "
                 "worth more than one. A test that only reads the report would "
                 "not have caught a coupling, because a coupled report still "
                 "prints three sections.",
        affected="Verification only - no computed value and no report line "
                 "changed. What changed is that a future edit cannot couple "
                 "the three without a test failing.",
        independent=True),
    Revision(
        version="3.40.0",
        observed="The serving efficiency was carried as one number, 0.55, "
                 "inside a published bracket of 0.28 to 0.64 that nothing "
                 "public can narrow.",
        suspected="Choosing a point inside an ambiguity is a guess dressed as "
                  "a calibration, and it hides that the answer depends on "
                  "software nobody has specified.",
        changed="A band - 0.30 low, 0.45 typical, 0.60 high - with a sweep "
                "that reports what each gives. The typical entry is 0.45, down "
                "from a 0.55 that came from the optimistic end of a single "
                "reading.",
        evidence="The LLM reference now ships under a typical and a good "
                 "serving stack and not under a poor one, which is the honest "
                 "verdict: whether that design works depends on a coefficient "
                 "two published deployments bracket without settling.",
        affected="Every LLM result falls about 18%. The requirement-matched "
                 "reference moved from eight HBM stacks to ten - its THIRD "
                 "move, each traceable to a named model change. The pattern is "
                 "worth noticing on its own: a reference that has to grow "
                 "every time the model gets more honest is telling you the "
                 "requirement was set against an optimistic model.",
        independent=True),
    Revision(
        version="3.40.0",
        observed="Company cases were being reported ad hoc, with different "
                 "fields each time.",
        suspected="Nothing wrong computationally - a missing format. Without "
                  "one, the field most easily left out is the one that matters "
                  "most.",
        changed="An eight-field revalidation record: starting point, "
                "measurement boundary, workload, expected direction, simulator "
                "result, company target, deviation analysis, and unsupported "
                "portions. A case the model cannot express produces no record "
                "at all, and a target measured at a wider boundary produces no "
                "deviation.",
        evidence="A record that omits what could not be simulated reads as "
                 "though the whole system had been. The suite now checks that "
                 "all eight fields appear, that estimated workload figures say "
                 "so, and that a wider-boundary target is refused rather than "
                 "compared.",
        affected="Presentation of the company cases. No computed value "
                 "changed.",
        independent=True),
    Revision(
        version="3.41.0",
        observed="Two thousand internal checks establish that the equations "
                 "are consistent with each other, and nothing establishes that "
                 "the model reaches the conclusion a designer would reach on a "
                 "real product.",
        suspected="A missing level of validation rather than a defect. "
                  "Equation, scenario and industry are three different claims "
                  "and only the first was being made.",
        changed="Six fixed scenarios, each declaring which level it reaches, "
                "what it can settle and what it cannot. A scenario may claim "
                "the industry level ONLY if a real company objective is "
                "attached, and the suite enforces it.",
        evidence="Of the six, one carries figures a company committed to and "
                 "five carry requirements this course wrote. Presenting all "
                 "six as industry-validated would be the same error as calling "
                 "a self-consistent model a verified one - a level label is a "
                 "claim, and five of these cannot make it.",
        affected="Nothing computed. The summary states the level counts rather "
                 "than a total, because a total would say six where the honest "
                 "answer is one.",
        independent=True),
    Revision(
        version="3.41.0",
        observed="The industry scenario compared a student design against the "
                 "COURSE's reference while applying the COMPANY's target, "
                 "which is stated relative to the system they are replacing. "
                 "Power reduction came out at -101% against a target of +50%.",
        suspected="Two baselines in one comparison. Their 'half the power' is "
                  "measured against the GPU module they are removing, not "
                  "against a small accelerator the course happens to use as a "
                  "starting point.",
        changed="An industry-anchored scenario now runs the company's own "
                "application and compares against the company's own baseline.",
        evidence="With the right baseline the same design gives a 55.1% power "
                 "reduction against a 50% target - direction agreeing, where "
                 "before it appeared to disagree by a factor of two. The "
                 "arithmetic never changed; the reference did.",
        affected="GRS-001 only. Another instance of the recurring failure in "
                 "this project: not a wrong number, but two things measured "
                 "from different starting points and set beside each other.",
        independent=True),
    Revision(
        version="3.42.0",
        observed="A case with a real company objective that the model could "
                 "only partly reach had nowhere to sit: INDUSTRY overclaimed "
                 "and SCENARIO threw the objective away.",
        suspected="Two levels where three are needed. Most real cases land in "
                  "the middle - a KPI exists and part of its boundary is "
                  "modelled.",
        changed="INDUSTRY-PARTIAL added between them, with a written promotion "
                "checklist of seven conditions and a per-scenario list of what "
                "specifically blocks it.",
        evidence="The wall-climbing inspection case has a published 20 ms and "
                 "15 ms, a single model and a single stream - and its KPI row "
                 "is named for detection AND region-of-interest extraction, "
                 "measured as an average over a hundred images. So it is not "
                 "pure inference, and where it starts is not stated. That one "
                 "unknown is the whole difference between the two levels.",
        affected="GRS-002 split into a vision-only entry at INDUSTRY-PARTIAL "
                 "and a whole-product entry that is not modelled at all. The "
                 "report states that promotion is a question about EVIDENCE - "
                 "tuning a coefficient until a published figure is matched "
                 "would move the number and leave the level where it is.",
        independent=True),
    Revision(
        version="3.42.0",
        observed="Every industry-anchored scenario reported n/a for its "
                 "requirement count.",
        suspected="Two builder calls where one was needed - the second popped "
                  "the temporary application the first had registered, so the "
                  "evaluation found nothing to run.",
        changed="One call returning the application, the reference and the "
                "cleanup flag together.",
        evidence="An n/a where a count belongs, on every row that used the "
                 "path.",
        affected="Both industry-anchored scenarios. Also fixed alongside: a "
                 "latency target measured at AI_PIPELINE was being refused as "
                 "'wider than the model reaches' when AI_PIPELINE is exactly "
                 "what the model reports. Refusing every latency comparison is "
                 "as wrong as making them all - the check now refuses only the "
                 "two boundaries that really are wider.",
        independent=True),
    Revision(
        version="3.43.0",
        observed="A student's work is almost always a MOVE - host to "
                 "accelerator, one engine to two, narrow memory to wide - and "
                 "nothing checked what must be true across one.",
        suspected="A gap in internal validation rather than a defect. A "
                  "migration touches compute, memory, power, area and cost at "
                  "once, so a defect in any of them shows up as a broken "
                  "relation. Nothing was looking for broken relations.",
        changed="Six migrations, each stating its consequences at three "
                "strengths: MUST follows from the structure and a violation is "
                "a defect; USUALLY holds for most workloads; DEPENDS is "
                "genuinely either way and says so rather than leaving a "
                "student to read one run as a rule.",
        evidence="A MUST claim needs no calibration to test, which makes these "
                 "the strongest structural checks in the package. Twelve of "
                 "them across six moves, and none is violated.",
        affected="Verification only. The migrations also carry the teaching "
                 "results this course exists to deliver - that a smaller node "
                 "usually makes a chip MORE expensive, that a second engine "
                 "can make a system worse, and that an offload's break-even is "
                 "a frame size rather than a principle.",
        independent=True),
    Revision(
        version="3.43.0",
        observed="The first run reported a MUST violation: adding a second "
                 "accelerator die left the system cost 'unchanged'.",
        suspected="A tolerance, not a defect. The cost rose 0.47% and a 0.5% "
                  "threshold read that as flat.",
        changed="A MUST claim is now tested on SIGN alone. A USUALLY claim "
                "keeps a visibility threshold and gains a third outcome - "
                "held in sign, too small to design around - which is neither "
                "agreement nor failure.",
        evidence="A MUST claim says the direction must be right, not that the "
                 "change must be large. Reading a real rise as unchanged "
                 "turned a correct model into a reported defect.",
        affected="Two claims move into the new third outcome, and both are "
                 "worth reading: on a cheap product the accelerator die is a "
                 "rounding error against the bill of materials. That is a "
                 "result, so it is reported rather than rounded into "
                 "agreement.",
        independent=True),
    Revision(
        version="3.44.0",
        observed="Process node coverage was two checks and one hard-coded "
                 "N12, and the node was selectable only inside the design "
                 "game - not on the main path.",
        suspected="An axis the model honoured and the interface did not offer. "
                  "To a student that is not a design variable at all, and it "
                  "is the axis where intuition fails hardest.",
        changed="A node sweep across all nine nodes, a systematic verification "
                "path, and the node made selectable on the runtime path with "
                "the sweep printed beside the result.",
        evidence="Every axis except cost improves monotonically as the node "
                 "shrinks, and cost turns around: the cheapest node for a "
                 "representative design is N7 at $39.20 while the smallest is "
                 "A16 at $44.55 - 14% more money for 51% less silicon. That is "
                 "the result students find hardest to believe and it was not "
                 "reachable from the menu.",
        affected="Verification and the interface. No computed value changed.",
        independent=True),
    Revision(
        version="3.44.0",
        observed="The sweep claimed the cost turning point 'belongs to THIS "
                 "design'. It does not: the cheapest node is N7 for all 108 "
                 "combinations of application, engine and memory in this "
                 "library.",
        suspected="A mechanism stated as an observation. The turn DOES move "
                  "with the SRAM fraction, because SRAM shrinks at roughly "
                  "half the rate of logic - but every accelerator here sits "
                  "near two thirds SRAM, so none of them exercises it.",
        changed="The sweep prints the underlying curve - silicon cost per unit "
                "of function against node, for an all-logic, a half and a "
                "mostly-SRAM die - and states that the turn does NOT move "
                "between these designs while the mechanism behind it is real.",
        evidence="An all-logic die turns at N7 and a mostly-SRAM one at N12, "
                 "which is visible in the curve and invisible in the library's "
                 "engines. Claiming design-dependence that the library cannot "
                 "show would have taught a student to expect a variation they "
                 "would never see.",
        affected="Wording and one new report. Also corrected a check that "
                 "forced yield to fall monotonically with node: a mature "
                 "cost-optimised derivative yields BETTER than its parent, "
                 "which is right in the library and was wrong in the test.",
        independent=True),
    Revision(
        version="3.45.0",
        observed="A node change was reported only as a system cost, where it "
                 "shows as 0.02% to 5%. The node had moved the DIE by up to "
                 "56%.",
        suspected="One number standing for two. A node moves silicon and "
                  "nothing else - memory, package, board and assembly are "
                  "bought - so on a product where the die is a small part of "
                  "the bill of materials, a large die saving is a small system "
                  "saving.",
        changed="Both are reported. The sweep shows a logic die cost beside "
                "the system cost and states that the first says what the node "
                "did and the second what the product gets.",
        evidence="From 28 nm to 7 nm on one design the die falls 38.6% and the "
                 "system 5.3%. Reporting only the die overstates what the "
                 "product gains; reporting only the system hides what the node "
                 "did. Both mislead, in opposite directions.",
        affected="One new metric and the sweep's presentation. No computed "
                 "value changed.",
        independent=True),
    Revision(
        version="3.45.0",
        observed="The sweep named a lowest-cost node without saying whose "
                 "assumptions produced it, and the two finest nodes were "
                 "labelled with numbers that read as physical dimensions.",
        suspected="A model result presented as a fact about the industry. "
                  "Wafer prices and yields here are estimates and they are "
                  "exactly what decides the answer.",
        changed="The result is qualified as belonging to this library and this "
                "design, the words optimal and best are refused, and the sweep "
                "says a real programme also weighs volume, mask cost and "
                "schedule. Nodes below 3 nm display as '-class'.",
        evidence="Node names have not described a physical dimension for many "
                 "years. Printing '1.6 nm' invites a student to read a "
                 "measurement where a generation label is meant.",
        affected="Wording. Also added design-type presets - compute-heavy, "
                 "balanced, SRAM-heavy, control-class - which show the cost "
                 "turn moving between 7 nm and 12 nm with the memory fraction. "
                 "The library's own engines all sit near two thirds SRAM and "
                 "cannot show it, which the presets say explicitly rather than "
                 "leaving a claim unillustrated.",
        independent=True),
    Revision(
        version="3.45.0",
        observed="OPEN: the model assumes one node for the whole system. Real "
                 "products put CPU, accelerator and I/O on different "
                 "processes, and an HBM base die on another again.",
        suspected="Not a defect at the level the course teaches - a monolithic "
                  "SoC is the right default - but a real limit on what the "
                  "model can represent.",
        changed="Nothing. Recorded so that a chiplet question is answered with "
                "'not modelled' rather than with a monolithic number.",
        evidence="A node is a property of a DIE, not of a system. Where the "
                 "dies differ, one node cannot describe them, and averaging "
                 "would produce a figure about no real part.",
        affected="Nothing computed. OPEN.",
        independent=True),
    Revision(
        version="3.46.0",
        observed="The node sweep named a cheapest node from RECURRING cost "
                 "alone. A mask set was modelled and reported; the physical "
                 "implementation, verification, IP porting, EDA and re-spin "
                 "were not modelled at all.",
        suspected="A wafer price is a cost per unit and a tape-out is not. "
                  "Answering 'what node should this product use' from "
                  "recurring cost alone leaves out the term that dominates at "
                  "low volume.",
        changed="A development-cost model with five effort lines beside the "
                "mask set and a probability-weighted re-spin allowance, "
                "parameterised by design reuse, migration distance, re-spin "
                "risk and IP porting. Effective unit cost is recurring plus "
                "development over volume, and a break-even volume is computed "
                "between any two nodes.",
        evidence="At fifty thousand units a smart camera is cheapest to "
                 "MANUFACTURE at 7 nm and cheapest to SHIP at 28 nm - the "
                 "development cost is ten times the recurring cost. At five "
                 "hundred million units the same design's economic node "
                 "reaches 7 nm. The node sweep could not have shown either.",
        affected="One new module. The sweep now says it reports recurring cost "
                 "only and points at where the other question is answered. "
                 "Effort deliberately does NOT scale like a mask set: a 28 nm "
                 "design still needs timing closure, verification and a test "
                 "program, so effort carries a floor and rises gently where "
                 "masks rise fifty-fold.",
        independent=True),
    Revision(
        version="3.47.0",
        observed="The economics report was read as saying a mobile part needs "
                 "five hundred million units to justify 7 nm. Real mobile SoCs "
                 "ship at around fifty million per model and use leading nodes "
                 "anyway.",
        suspected="Two things at once. First, the die being amortised is an AI "
                  "block of eight to twenty square millimetres, not an "
                  "application processor of a hundred or more - a node change "
                  "moves proportionally fewer dollars, so the break-even comes "
                  "out proportionally higher. Second, and more important, the "
                  "presentation implied cost is what drives a node decision.",
        changed="The report states which silicon it amortises, and says that a "
                "migration with no cost break-even is an ORDINARY result "
                "rather than a verdict against the move.",
        evidence="Between N12 and N7 on these designs the die gets DEARER, not "
                 "cheaper: SRAM shrinks at about half the rate of logic while "
                 "the wafer price doubles, and the accelerators here are two "
                 "thirds SRAM. Meanwhile power falls 4% and energy per "
                 "inference 4%. A phone is thermally limited, not die-cost "
                 "limited, which is why leading nodes ship in volumes far "
                 "below any cost break-even. The model had this right and the "
                 "report was inviting the wrong reading of it.",
        affected="Wording and two new report sections. No computed value "
                 "changed. The break-even figures themselves are correct for "
                 "the dies they describe and should not be carried to a full "
                 "SoC - which the report now says.",
        independent=True),
    Revision(
        version="3.48.0",
        observed="Every node report led with cost, and cost is not why parts "
                 "move node.",
        suspected="A presentation that made the industry look irrational. A "
                  "leading node costs more to develop and, between adjacent "
                  "generations on an SRAM-heavy die, often more to "
                  "manufacture. Parts move for speed and for power, and they "
                  "move because a competitor will.",
        changed="A decision report ordered the way the decision is actually "
                "made: what performance buys, what power buys, and what it "
                "costs - with cost labelled as what the first two are paid "
                "for.",
        evidence="On a compute-bound design 16 nm to 7 nm gives 19% less "
                 "latency and 31% less power for 266% more effective unit cost "
                 "at fifty thousand units. Nobody makes that trade to save "
                 "money, and a report that presented cost first would have "
                 "made the trade look like a mistake.",
        affected="Presentation. No computed value changed. The report also "
                 "warns when a design is memory bound, where a finer node buys "
                 "almost no speed - 16 nm to 3 nm moves a memory-bound "
                 "latency by 0.3% and a compute-bound one by 32%, and knowing "
                 "which you have is the first thing to check before paying for "
                 "a node.",
        independent=True),
    Revision(
        version="3.49.0",
        observed="The node decision report treated the process node as the "
                 "whole question. It is not: a finer node makes the arithmetic "
                 "faster and does nothing to a DRAM, so on a memory-bound "
                 "design the entire performance case for the node evaporates.",
        suspected="Two axes presented as one. A process node is where the "
                  "logic is fabricated; a memory generation is a part bought "
                  "from a memory supplier with its own interface and package. "
                  "Neither implies the other.",
        changed="A combined report covering all four options - neither, node "
                "only, memory only, both - with what binds before and after "
                "each.",
        evidence="On a memory-bound mobile design 16 nm to 7 nm buys 0.3% less "
                 "latency and four times the memory channels buys 73.8%. On a "
                 "compute-bound inspection design the same two changes buy "
                 "40.1% and 2.8%. A node report alone would have sold compute "
                 "to a design that was waiting on transfers.",
        affected="Presentation. No computed value changed. The report also "
                 "names the case worth paying for when the immediate gain is "
                 "small: a node fine enough to move the bottleneck - "
                 "Industrial Vision turns from compute bound to memory bound "
                 "at 1.6 nm-class - can be the right move because of where it "
                 "leaves the next problem.",
        independent=True),
    Revision(
        version="3.50.0",
        observed="The memory half of the node decision offered exactly one "
                 "option - four times the packages - and the menu used it as "
                 "the default. It broke the cost gate, which was reported as a "
                 "finding.",
        suspected="A real finding presented from the most expensive starting "
                  "point. Buying packages is the answer people reach for "
                  "first and it is usually the dearest on the list; framing "
                  "the memory question around it turns 'what is the "
                  "bottleneck' into 'how much do you want to spend'.",
        changed="Five options: a better dataflow, more on-chip buffer, less "
                "traffic, more packages, a faster class - reported with what "
                "each buys per dollar. The menu now steps the packages by two "
                "rather than four.",
        evidence="On an inspection design a doubling of packages buys 12.6% "
                 "less latency for 68.5% more system cost, and moving to a "
                 "different memory class buys 7.0% for 29.5% LESS. Two of the "
                 "five cost nothing on the bill of materials at all. A report "
                 "that showed only the first would have taught a student to "
                 "solve every memory problem by spending.",
        affected="Presentation. No computed value changed. Two guards were "
                 "added: a cheaper memory class carries a cooling warning "
                 "rather than reading as a free win, and the reuse-based "
                 "options are OMITTED for autoregressive decode rather than "
                 "listed as options that buy nothing - every weight is read "
                 "once per token by construction, so there is nothing for them "
                 "to save, and that is a property of the workload rather than "
                 "a failure of the option.",
        independent=True),
    Revision(
        version="3.51.0",
        observed="'Half the weights' sat in the same list as a compiler "
                 "improvement and a package purchase, and had the second-best "
                 "latency.",
        suspected="A quality change presented as an implementation choice. "
                  "Halving the weights makes the network a DIFFERENT network; "
                  "the others implement the same one. Putting them in one "
                  "table invites a student to pick whichever row has the best "
                  "number.",
        changed="Two tables - same network, and a different network - with the "
                "second stating that its latency is not comparable with the "
                "first. Every row now shows accuracy, and every option is "
                "classified by what it costs: engineering, silicon, bill of "
                "materials, or the model itself.",
        evidence="It is a faster car against a shorter journey. The report "
                 "also admits what its accuracy column cannot see: the model "
                 "computes quantisation loss, not the accuracy a genuinely "
                 "smaller network would give up, so the row understates the "
                 "cost of that choice.",
        affected="Presentation. No computed value changed.",
        independent=True),
    Revision(
        version="3.51.0",
        observed="Swapping one LPDDR5 package for one GDDR6 package showed a "
                 "29.5% cost REDUCTION.",
        suspected="Not a like-for-like comparison. The GDDR6 entry is half the "
                  "width and half the capacity of the LPDDR5 one, so one for "
                  "one halves the memory - and it is dearer per gigabyte, "
                  "2.54 against 2.23.",
        changed="A class swap now matches CAPACITY, and the report names the "
                "package count and the cooling the new class requires.",
        evidence="Matched at four gigabytes the same move costs 9.5% MORE, not "
                 "29.5% less, and needs airflow a passively cooled product "
                 "does not have. The library was right about both packages; "
                 "the comparison was between different amounts of memory.",
        affected="The memory options report. No library value changed. Also "
                 "added: each option now says whether it REMOVES the "
                 "bottleneck or merely moves it, because an option that moves "
                 "it has not finished the job - it has changed which question "
                 "to ask next.",
        independent=True),
    Revision(
        version="3.52.0",
        observed="The 'half the weights' row showed the accuracy unchanged at "
                 "98.55% and the design still shipping, which read as a free "
                 "lunch: less traffic, no cost, no accuracy loss.",
        suspected="The accuracy model covers quantisation and nothing else. "
                  "Halving the weights is not one operation - pruning, "
                  "distillation, a smaller architecture and a lower precision "
                  "all halve the bytes and cost entirely different amounts - "
                  "so the figure being printed was the ORIGINAL network's, "
                  "carried over unchanged because nothing in the model knew "
                  "the network had changed.",
        changed="An unpriced model change now reports its accuracy as NOT "
                "PRICED and its verdict as UNKNOWN, with an explanation of why "
                "and how to supply one. Given a figure, the deployment "
                "accuracy and every gate are re-evaluated against it.",
        evidence="At an assumed cost of 1.5 points the same row fails the "
                 "accuracy gate where every architecture option passes - which "
                 "is the comparison a designer needs and the opposite of what "
                 "the report was showing.",
        affected="The memory options report. No computed value changed; what "
                 "changed is that the model now declines to answer a question "
                 "it has no basis for rather than answering it with a number "
                 "from a different network.",
        independent=True),
    Revision(
        version="3.53.0",
        observed="The CPU appeared in the model as area and power, and nowhere "
                 "as a decision. There was no migration that changed the host, "
                 "and the node and memory reports did not mention it.",
        suspected="Half the host was modelled - the half that decides nothing. "
                  "The accelerator computes the network; the host lays out and "
                  "normalises the pixels, launches the job, runs "
                  "non-maximum suppression and formats the result, and none of "
                  "that is touched by a faster accelerator.",
        changed="A host migration with seven claims, and a host options report "
                "showing what the CPU is holding, what a different one would "
                "change, and the offload alternative beside it.",
        evidence="On an inspection design running its preprocessing on a small "
                 "host, the host holds 91% of the frame. Moving from a "
                 "four-core A53 to a four-core A78 cuts the latency 69.7% for "
                 "1.3% more system cost, and the accelerator's arithmetic does "
                 "not move at all. A student reading only the accelerator's "
                 "specification would not see it coming - which is what this "
                 "simulator exists to make visible.",
        affected="One new migration, one new report, and a mutation that "
                 "checks the two axes stay separate: a host change that moved "
                 "the accelerator's compute time would be wired wrong, and now "
                 "fails a test if it ever is.",
        independent=True),
    Revision(
        version="3.54.0",
        observed="The CPU had no DRAM traffic at all, which cannot be true of "
                 "anything that touches pixels. Preprocessing reads a frame "
                 "and writes a normalised tensor across the same bus the "
                 "accelerator uses.",
        suspected="A missing term rather than a wrong one. Every byte in the "
                  "model belonged to the accelerator, so the host appeared to "
                  "cost time and never bandwidth.",
        changed="Host traffic is computed from the pixels it touches and the "
                "outputs it formats, and the accelerator sees the bus that is "
                "left. The two are separate agents - the accelerator does not "
                "wait for the host's reads - so this narrows the bus rather "
                "than lengthening a queue, and the share is capped at half "
                "because a host that could saturate the bus alone is a "
                "different problem this model does not represent.",
        evidence="On an inspection design preprocessing on the host, the host "
                 "moves 140 MB and takes 13.2% of the bandwidth, and the "
                 "accelerator's transfer time rises from 0.78 to 0.90 ms. "
                 "Offloading gives that bandwidth back - a second reason to "
                 "offload, on top of the time, and one nobody could see while "
                 "the host was assumed to move no data.",
        affected="Every vision configuration where preprocessing runs on the "
                 "host. Two checks needed correcting alongside: one divided "
                 "traffic by the interface bandwidth rather than by what the "
                 "accelerator sees, and one demanded a strict inequality "
                 "between a wide bus and a merely sufficient one - it had been "
                 "passing on a difference below 1e-10, which is "
                 "floating-point noise and not a property. Saturation means "
                 "those two SHOULD be equal.",
        independent=True),
    Revision(
        version="3.54.0",
        observed="The host's time was cycles over rate and nothing else. A CPU "
                 "moving 140 MB of pixels never waited for a single byte of "
                 "it.",
        suspected="The accelerator had a roofline and the host did not, so the "
                  "model could not represent the commonest edge failure: a "
                  "fast host on a narrow bus, where more cores buy a faster "
                  "wait.",
        changed="The host now has the same roofline the accelerator has - it "
                "cannot finish before its own transfers - and reports its "
                "arithmetic, its transfers, its exposed wait and what bounds "
                "it.",
        evidence="On one LPDDR5 package the same preprocessing is compute "
                 "bound on an A53, memory bound on an A78 and memory bound on "
                 "a server x86. Four packages move the A78 back to compute "
                 "bound. Without a host roofline all six looked identical in "
                 "kind and differed only in speed.",
        affected="Every configuration where the host touches pixels. Doubling "
                 "the CPU clock no longer halves the host's time - it halves "
                 "the arithmetic and leaves the transfers alone, which is the "
                 "point. A regression check that asserted the halving has been "
                 "rewritten; it had been quietly asserting that a host never "
                 "waits.",
        independent=True),
    Revision(
        version="3.54.0",
        observed="Two attempts at splitting the bus between host and "
                 "accelerator failed in opposite directions before one worked.",
        suspected="Dividing by demand alone made the host's transfer time "
                  "equal its compute time by construction, so it could never "
                  "be memory bound however narrow the bus. Capping the "
                  "accelerator at its own demand throttled it to exactly the "
                  "rate it had asked for, so spare bandwidth went unused and "
                  "two starting points stopped shipping.",
        changed="Each agent may use whatever the other is not asking for, with "
                "a floor so neither can be starved to nothing.",
        evidence="The first version gave a host with 0.35 MB of traffic a 1.35 "
                 "ms wait for it. The second cost the AI Inference reference "
                 "12% of its throughput with no physical cause. Both were "
                 "visible immediately in the starting points, which is what "
                 "they are for.",
        affected="A regression check that the host share is capped at half the "
                 "bus was replaced: the cap became a floor when the question "
                 "changed from 'can the host take too much' to 'can either be "
                 "starved'.",
        independent=True),
    Revision(
        version="3.55.0",
        observed="The host was reported as compute bound or memory bound, and "
                 "a ratio of 1.02 counted as memory bound.",
        suspected="Two states where three are needed. Most real configurations "
                  "sit near the crossover, and naming a side there invites a "
                  "student to buy memory for a design that is balanced.",
        changed="Three states - compute-limited, balanced, memory-limited - "
                "with a band of 25% either side of equal, and a report that "
                "declines to pick a side inside it.",
        evidence="Across four memory widths and three hosts the model produces "
                 "all three states, and the balanced one is not rare: a "
                 "four-core A53 on one LPDDR5 package spends 30.2 ms computing "
                 "and 22.7 ms transferring, which is not a memory-limited host "
                 "and is not a compute-limited one either. The report says so "
                 "and names what the answer depends on rather than resolving "
                 "it.",
        affected="Reporting only. Two coefficients that had been local "
                 "variables inside the evaluation function are now module "
                 "constants, registered and mutable - a coefficient a test "
                 "cannot move is a coefficient nobody has checked.",
        independent=True),
    Revision(
        version="3.55.0",
        observed="Every check on the host roofline compared one model result "
                 "with another, which catches a change and not an error.",
        suspected="Nothing wrong - a missing kind of test. A model can be "
                  "internally consistent and arithmetically wrong, and "
                  "self-comparison cannot tell the difference.",
        changed="A fixture with an answer arrived at without the model: at an "
                "overlap of 0.7, ten milliseconds of arithmetic against four "
                "of transfers must expose 1.2 ms and total 11.2 ms. Plus "
                "explicit double-counting checks - the host's bytes appear in "
                "its own stage time, in the accelerator's available bandwidth "
                "and in the memory energy, and each must count them once.",
        evidence="The two memory models now interact, which is exactly the "
                 "condition under which a term gets added twice. One of the "
                 "new checks confirms that increasing the network's weights "
                 "leaves the host's traffic alone - the host does not read the "
                 "network's weights, and a model where it did would have "
                 "looked plausible.",
        affected="Verification only - no computed value changed. What changed "
                 "is that the host roofline now has one check whose answer "
                 "does not come from the model being tested.",
        independent=True),
    Revision(
        version="3.56.0",
        observed="Building five applications for a second accelerator produced "
                 "four wrong predictions of my own and one real gap in the "
                 "model.",
        suspected="Each was a different mistake. Two knobs mean different "
                  "things and setting the wrong one is silent; the "
                  "single-job rate is not the pipeline rate; an offload can "
                  "buy more latency than the host time it removes because it "
                  "returns bandwidth too; and splitting a job lowers energy "
                  "per job even where it cannot raise delivered throughput.",
        changed="A dual-accelerator suite of thirty-three checks, and a note "
                "in the model saying which rate its throughput figure is.",
        evidence="The gap that matters: throughput in evaluate_system is one "
                 "over the LATENCY, so a design routing alternate jobs to two "
                 "engines shows no gain there however well it works - the "
                 "pipeline rate rises 63% on an accelerator-limited robot and "
                 "the single-job figure does not move at all. A check reading "
                 "the wrong one reports a real gain as none, which is how the "
                 "first version of this suite was written.",
        affected="No computed value. Two of the five applications are recorded "
                 "as NOT EXPRESSIBLE rather than approximated: a safety design "
                 "has two completion times and this model has one, and a "
                 "prefill/decode split needs two accelerator paths per "
                 "inference. Reporting a number for either would answer a "
                 "different question.",
        independent=True),
    Revision(
        version="3.56.0",
        observed="Predicted that a second engine on an under-loaded drone "
                 "would raise energy per job. It FELL, from 33.8 to 29.7 mJ.",
        suspected="Splitting the job halves the core time, so each job spends "
                  "less time paying static power - and that saves more than "
                  "the second engine's leakage costs.",
        changed="The prediction, not the model. The finding is more "
                "interesting than the one expected: the second engine is worth "
                "having on energy per job and worth nothing on delivered "
                "throughput, because the camera does not send more frames "
                "because there is more silicon.",
        evidence="Average system power still rises, 1.49 to 2.07 W, which is "
                 "what a battery feels. Both figures are now reported, because "
                 "reporting either alone gives the opposite impression.",
        affected="One scenario expectation.",
        independent=True),
    Revision(
        version="3.57.0",
        observed="One name, Throughput, stood for three different rates.",
        suspected="The defect found at 3.56.0 was not a slip - it was what a "
                  "single name makes inevitable. A design routing alternate "
                  "jobs to two engines raises the pipeline capacity and cannot "
                  "raise the single-job rate, and whoever reads the wrong one "
                  "reports a real gain as none.",
        changed="Three names: single-job rate, one over the latency with one "
                "job in flight; pipeline capacity, one over the slowest "
                "station; delivered throughput, the capacity capped by what "
                "arrives. The bare name is kept as an alias so older callers "
                "work, and nothing new reads it.",
        evidence="On an accelerator-limited robot, alternating jobs takes the "
                 "capacity from 9.8 to 19.7 per second, moves the single-job "
                 "rate by 0.2%, and delivers 15.0 because that is what the "
                 "sensor sends. Three numbers, three meanings, and the "
                 "delivered figure now matches the runtime simulation exactly "
                 "- two independent paths to the same answer.",
        affected="One new metric group and the domain-range mapping, which "
                 "read the single-job rate where it meant the delivered one.",
        independent=True),
    Revision(
        version="3.57.0",
        observed="Two mutations survived - a delivered rate that ignored the "
                 "arrival cap, and a pipeline interval computed as a sum "
                 "rather than a maximum - although checks existed for both.",
        suspected="Not a gap in the checks. The mutation runner names the "
                  "paths it exercises in a hand-maintained string, and the "
                  "newest path was missing from it. This has now happened "
                  "twice, each time leaving hundreds of checks outside "
                  "coverage while the totals looked healthy.",
        changed="The list is now asserted: every path defined in the model "
                "suite must appear in the mutation runner, or a test fails.",
        evidence="A list that must be maintained by hand will be forgotten "
                 "again. The second time it happened was the argument for "
                 "checking it rather than for being more careful.",
        affected="Coverage. Both mutations die once the path runs.",
        independent=True),
    Revision(
        version="3.58.0",
        observed="Nothing tested the two assumptions a student actually brings "
                 "to a second accelerator: that each engine should get half "
                 "the work, and that a slower second engine still helps a "
                 "little.",
        suspected="Both are usually wrong and the model already knew it - "
                  "nothing was asking.",
        changed="An allocation sweep and eight scenarios covering "
                "heterogeneous routing, a share sweep, two grades of slower "
                "secondary, the single-engine reductions, and arrival-limited "
                "and capacity-limited runtimes.",
        evidence="With a 32x32 primary and a 16x16 secondary the capacity "
                 "peaks at a 0.20 share, not 0.50, and an even split costs 57% "
                 "of the capacity available at the peak. The sweep finds 0.20; "
                 "the capacity ratio - 27.29 over 27.29 plus 101.57 - says "
                 "0.21 without using the model at all. Two paths to the same "
                 "answer. On the parallel side a moderately slower secondary "
                 "is worth 18% at its best split and beats a single engine "
                 "only between 0.20 and 0.40; a very slow one is worth 5% and "
                 "only at 0.20. Outside those ranges the pair is SLOWER than "
                 "having one engine.",
        affected="One new report, wired into the runtime menu. The teaching "
                 "point is the one the scenarios were built to find: a second "
                 "accelerator used wrongly makes the system worse than not "
                 "having one at all.",
        independent=True),
    Revision(
        version="3.58.0",
        observed="An engine declared and given no work still cost 0.06 ms of "
                 "hand-off, so the single-engine reduction did not hold "
                 "exactly.",
        suspected="The synchronisation was charged unconditionally. Nothing is "
                  "handed off when nothing was split.",
        changed="The hand-off is charged only when the split is non-zero.",
        evidence="Merging results that do not exist. Found by the reduction "
                 "check, which is what a reduction check is for.",
        affected="Every zero-split configuration. The framework overhead still "
                 "doubles and defensibly so - a declared engine has a driver "
                 "and a context whether or not work is sent to it - and the "
                 "suite now asserts that this is the ONLY remaining "
                 "difference, so the reduction is exact in the arithmetic and "
                 "explained in the latency.",
        independent=True),
    Revision(
        version="3.59.0",
        observed="An engine declared and given no work still cost 0.25 ms a "
                 "frame of framework overhead, which I had defended as a "
                 "driver that exists whether or not work is sent to it.",
        suspected="The defence was for the wrong quantity. That overhead is a "
                  "GRAPH LAUNCH per frame - the code says so a few lines "
                  "above - and an engine given no work launches no graph. A "
                  "per-board driver and a per-frame launch are different "
                  "costs and I had reasoned about one while charging the "
                  "other.",
        changed="The launch is charged only for an engine that runs "
                "something.",
        evidence="The performance reduction is now exact: a secondary at zero "
                 "share gives the single-engine latency to nine decimal "
                 "places, where before it was 5% slower for a dispatch that "
                 "never happened.",
        affected="Every zero-work dual configuration.",
        independent=True),
    Revision(
        version="3.59.0",
        observed="'The same as one engine' was one idea covering three "
                 "different claims, and an engine fitted but unused was "
                 "indistinguishable from one never fitted in the way the "
                 "results were described.",
        suspected="Workload, performance and physical reduction come apart. "
                  "The first two hold whenever the work is zero; the third "
                  "holds only when the engine is not on the board.",
        changed="A reduction report showing which of the three hold for each "
                "way of not using an engine, and a new state - installed and "
                "power-gated - between used and absent.",
        evidence="Four states that differ: absent, fitted-and-unused, "
                 "fitted-and-gated, fitted-and-used. The gated one keeps its "
                 "area and its price and gives up 85% of its leakage, not all "
                 "of it - retention and rails do not vanish, and a model that "
                 "took it to zero would make 'fit it and switch it off' look "
                 "free. 'We do not use it' and 'we do not fit it' are "
                 "different products and now compute differently.",
        affected="One new configuration flag and one new report. No existing "
                 "value changed.",
        independent=True),
    Revision(
        version="3.60.0",
        observed="Asking the runtime for a fixed number of jobs still measured "
                 "the sixty-second window. One job came out at 0.02 per "
                 "second.",
        suspected="A fixed count finishes when the last job finishes, not when "
                  "the clock runs out. The figure being reported was a "
                  "statement about the window and not about the design.",
        changed="A fixed job count now ends at fill plus one interval per job, "
                "and the throughput follows from that.",
        evidence="With the fix the pipeline fill is visible and behaves: one "
                 "job reaches 48% of the capacity, ten reach 90%, a hundred "
                 "99%, a thousand 99.9%. The fill is paid ONCE - a thousand "
                 "jobs pay it once, not a thousand times - which is the whole "
                 "reason a long run converges. Before the fix all four "
                 "returned jobs over sixty and the convergence could not be "
                 "seen at all.",
        affected="Every fixed-count runtime call. The duration-based path is "
                 "unchanged.",
        independent=True),
    Revision(
        version="3.61.0",
        observed="The host's reported bandwidth share and the accelerator's "
                 "available bandwidth did not add up to the bus. About 1.5% of "
                 "it belonged to nobody.",
        suspected="Two different quantities under one name. The share reported "
                  "was the rate the host ACHIEVED; the accelerator's bandwidth "
                  "came from the ALLOCATION, and those are not the same "
                  "number.",
        changed="The reported share is the allocated one, and an explicit "
                "allocated figure in gigabytes per second sits beside it.",
        evidence="The two now sum to the bus exactly, at every memory width, "
                 "to nine decimal places. A residue no agent owns is a "
                 "residue nobody will find.",
        affected="One reported percentage. No timing changed - the allocation "
                 "was always the figure the model computed with.",
        independent=True),
    Revision(
        version="3.61.0",
        observed="Six scenarios asked when a second accelerator is worth "
                 "having inside a whole system rather than on its own.",
        suspected="Nothing was checking that the CPU and the ISP are stations "
                  "in the pipeline, so a design limited by either could have "
                  "reported an accelerator gain that no product would see.",
        changed="Group E: a host-limited design, a host upgrade, an "
                "ISP-limited design, a shared bus, and an offload compared "
                "against a second engine.",
        evidence="The results are the ones worth teaching. On a host-limited "
                 "design a second engine buys NEGATIVE 0.8% - its own graph "
                 "launch lands on the host, which is already the constraint. "
                 "On an ISP-limited one an accelerator eight times the size "
                 "changes the capacity by nothing at all, though it does "
                 "improve the single-job latency: capacity and latency are "
                 "different questions and only one of them is capped. And "
                 "against a host-bound reference, offloading the preprocessing "
                 "beats adding a second accelerator - the host was the "
                 "problem, and a second accelerator does not touch it.",
        affected="Verification only. Three mutations added: leaving the CPU "
                 "out of the interval, leaving the ISP out, and reporting an "
                 "achieved share where an allocated one belongs.",
        independent=True),
    Revision(
        version="3.62.0",
        observed="Nothing tested what happens BETWEEN two engines - the "
                 "hand-off, the merge, the synchronisation, the ordering. Only "
                 "what each one computes.",
        suspected="That is the gap the whole feature sits in. A student adding "
                  "a second accelerator pictures two engines working; they do "
                  "not picture a hand-off, and it is the hand-off that decides "
                  "whether the second engine was worth fitting.",
        changed="Group D: independent against dependent work, the merge "
                "penalty, the synchronisation wait, pipeline bubbles, "
                "dependency chains, and the transfer that moving work to an "
                "accelerator costs.",
        evidence="Four results worth teaching. A sequential dependency leaves "
                 "the total arithmetic exactly unchanged and makes ONE job "
                 "SLOWER by the hand-off, while still raising the pipeline "
                 "capacity - the gain is in the stream and never in the job. "
                 "An even split between a 32x32 and a 16x16 leaves the fast "
                 "engine waiting 37 ms for the slow one. A merge efficiency "
                 "of 0.4 makes two engines slower than one. And one job gets "
                 "nothing at all from a second engine because there is no "
                 "second job for it to take: the gain grows from 0% at one job "
                 "to 96% at a thousand.",
        affected="Verification only. Four mutations added, including one that "
                 "lets a pair finish before its slower half - which is what "
                 "'two engines means twice as fast' would look like if it "
                 "were true.",
        independent=True),
    Revision(
        version="3.62.0",
        observed="A student pictures CPU to NPU as a wire. It is a transfer.",
        suspected="Nothing wrong in the model - the transfer was computed - "
                  "but nothing pointed at it, so the one structural fact that "
                  "explains why small offloads lose was invisible.",
        changed="A scenario that names it and checks where it is charged: to "
                "the MEMORY station, not to the accelerator, because the "
                "engine is not busy while bytes are on a bus.",
        evidence="The offload still wins on a five-megapixel stream despite "
                 "paying the transfer, and loses on a 640x480 one because of "
                 "it. That is the same break-even the scenario suite has "
                 "moved three times, and this is where it comes from.",
        affected="Verification only - no computed value changed. What changed "
                 "is that the transfer is now named, and a mutation that "
                 "charged it to the accelerator instead of to memory now "
                 "fails a test.",
        independent=True),
    Revision(
        version="3.63.0",
        observed="A work_split of 1.5 was silently clamped to 1.0 and the "
                 "student got an answer with no reason to wonder why.",
        suspected="Tidying an out-of-range value is the opposite of what a "
                  "teaching model should do. The number does not describe "
                  "anything, and quietly substituting one that does teaches "
                  "nothing.",
        changed="Both allocation knobs are validated and raise with a message "
                "saying what the knob means. The boundaries themselves - 0 and "
                "1 - remain valid.",
        evidence="The two knobs already mean different things and setting the "
                 "wrong one is invisible; adding a silent clamp on top of that "
                 "meant two ways to be wrong without being told.",
        affected="Any caller passing an out-of-range share or split. None in "
                 "the package did.",
        independent=True),
    Revision(
        version="3.63.0",
        observed="A comparison could report 'better' or 'worse' as though the "
                 "requirement, the reference and the domain band answered one "
                 "question.",
        suspected="They answer three, and they disagree constantly. A design "
                  "can beat the reference on every axis a student looks at and "
                  "still not be sellable.",
        changed="A proposal comparison with the three kept apart, an explicit "
                "note when energy per job and average power move in opposite "
                "directions, and a boundary audit when EVERY axis improves.",
        evidence="The example that made the case: replacing a small "
                 "accelerator and moving the preprocessing off the host "
                 "improves latency 86% and REDUCES the pipeline capacity 24%, "
                 "because the bottleneck lands on the ISP. A report saying "
                 "'better' would have been true and useless. The all-improved "
                 "audit exists because a comparison where nothing got worse is "
                 "also what a mismatched boundary looks like.",
        affected="One new report. No computed value changed.",
        independent=True),
    Revision(
        version="3.64.0",
        observed="A job placed entirely on the secondary engine - a work_split "
                 "of 1 - was paying 18% for a merge with nothing to merge "
                 "against.",
        suspected="The same error corrected at 3.59.0, sitting at the other "
                  "end. A split of 0 puts everything on the primary and a "
                  "split of 1 puts everything on the secondary; NEITHER "
                  "divides a job, so neither pays to partition, synchronise or "
                  "merge. The zero end had been fixed and the one end had not "
                  "been looked at.",
        changed="The partition cost applies only when the split is strictly "
                "between the endpoints.",
        evidence="A job entirely on a 32x32 secondary now computes in 27.206 "
                 "ms against a lone 32x32's 27.204 - the same machine doing "
                 "the same work. Before, it took 32.007 ms because a merge was "
                 "charged for combining one result with nothing. Found by "
                 "checking the endpoint, which is what endpoints are for.",
        affected="Every full-split configuration. Three existing mutations "
                 "needed their patterns updating, which is the sort of "
                 "maintenance a rename costs and the reason the pattern check "
                 "runs before the suite.",
        independent=True),
    Revision(
        version="3.64.0",
        observed="The last four boundary scenarios: a low arrival rate, all "
                 "jobs to the secondary, all of one job to the secondary, and "
                 "a job too small to divide.",
        suspected="Nothing - these are the safety checks that say the model "
                  "does not fall over at the ends or on small work.",
        changed="Four scenarios added. One found the merge defect above.",
        evidence="The small-work result is the one worth teaching: dividing a "
                 "20 MMAC job gains 0.0% and dividing a 20 GMAC job gains 44%, "
                 "with the gain rising monotonically between them. If a job is "
                 "small enough, the cost of dividing it exceeds the cost of "
                 "doing it.",
        affected="Verification only. The dual-accelerator work is now closed: "
                 "reduction, allocation, work split, dependency and hand-off, "
                 "CPU/ISP/memory interaction, runtime and arrival rate, "
                 "interpretation, and invalid or unsupported input.",
        independent=True),
    Revision(
        version="3.65.0",
        observed="The second thing a student reaches for after a second "
                 "accelerator is a faster memory, and nothing tested that "
                 "assumption the way the dual-engine pack tests the first one.",
        suspected="Same shape, same error: that a faster part makes a system "
                  "faster. A memory is not one axis - choosing it moves "
                  "capacity, bandwidth, power, cooling class, package area and "
                  "price at once, and on a compute-bound design it moves "
                  "everything except the answer.",
        changed="A memory decision pack: unused capacity, unused bandwidth, "
                "the bottleneck's verdict, capacity against bandwidth, a stack "
                "sweep, cooling incompatibility, shared-bus accounting, and "
                "capacity that is not delivery.",
        evidence="The two results that make the case sit side by side. On a "
                 "compute-bound inspection design a memory with sixteen times "
                 "the bandwidth buys 26% of the latency for six times the "
                 "price. On a memory-bound mobile design the same upgrade buys "
                 "88% - and fails the power, cost, thermal AND cooling gates. "
                 "Neither design would have been served by reading a "
                 "bandwidth number.",
        affected="Verification only. A memory purchase is now checked never to "
                 "change the arithmetic or the accuracy, and stack count is "
                 "checked to buy width rather than a faster stack.",
        independent=True),
    Revision(
        version="3.65.0",
        observed="Two of the new scenarios failed on first run because they "
                 "read the DELIVERED rate where they meant the CAPACITY.",
        suspected="The delivered figure is capped at what the requirement "
                  "asks for, so it cannot show a capacity gain. This is the "
                  "same mistake the dual-accelerator suite made at 3.57.0, "
                  "arriving on the memory axis instead.",
        changed="The scenarios read the capacity, and one of them now checks "
                "BOTH: capacity rises and delivered does not.",
        evidence="Separating the three rates was worth doing and did not make "
                 "the mistake impossible - it made it findable, which is what "
                 "a name can do. The suite caught it on the first run.",
        affected="Two scenario expectations.",
        independent=True),
    Revision(
        version="3.66.0",
        observed="A design was called compute bound and gained 26% from a "
                 "faster memory. Another was called compute bound and gained "
                 "nothing. The label was the same.",
        suspected="A two-way label hides the case that matters. The first has "
                  "1.6 times more arithmetic than transfers and a small "
                  "exposed data-wait; the second has 15 times and none. Both "
                  "are 'compute' and only one of them should ignore a memory "
                  "upgrade.",
        changed="Five levels - strongly compute-bound, weakly compute-bound, "
                "balanced, weakly memory-bound, strongly memory-bound - with "
                "the compute-to-memory ratio reported so the label can be "
                "checked.",
        evidence="The middle three are where a memory upgrade is a real "
                 "question rather than an obvious yes or an obvious no, and "
                 "they were all being answered with one word.",
        affected="Reporting only - no timing changed. What changed is that "
                 "the label a student reads now distinguishes a design that "
                 "should ignore a memory upgrade from one that should not.",
        independent=True),
    Revision(
        version="3.66.0",
        observed="An over-specified memory failed four gates and that was "
                 "reported as four findings.",
        suspected="Thermal margin is computed from system power over area, so "
                  "a design over its power budget is usually over its thermal "
                  "one too. Reporting both counts one fact twice and makes the "
                  "design look worse than it is.",
        changed="Gate failures are separated into independent reasons and ones "
                "that follow from another gate, with a note on the kinds that "
                "are different in nature - a cooling-class mismatch is not a "
                "magnitude and no amount of power reduction fixes it.",
        evidence="Four gates, three reasons. The distinction matters for what "
                 "a student does next: two of those can be fixed by spending "
                 "less, and the third cannot be fixed at all with that part.",
        affected="Reporting only - no gate verdict changed. What changed is "
                 "how many problems a failing design is said to have.",
        independent=True),
    Revision(
        version="3.66.0",
        observed="A configuration whose model does not fit in memory was "
                 "reporting 4 tokens per second.",
        suspected="It cannot run at any speed. A student comparing 4 against "
                  "35 would be comparing an impossible design with a possible "
                  "one as though both were options.",
        changed="A capacity failure sets the result status to INFEASIBLE, so "
                "anything reading the performance figures can see that they "
                "describe a machine which cannot exist.",
        evidence="An HBM3E pair has more bandwidth than eight LPDDR5 packages "
                 "and still does not fit a 90 GB model. Capacity is a "
                 "different purchase from bandwidth, and no amount of the "
                 "second buys the first - which is the whole point of the "
                 "scenario.",
        affected="Any configuration failing the capacity gate. The metrics are "
                 "still computed and now carry a status saying not to believe "
                 "them.",
        independent=True),
    Revision(
        version="3.67.0",
        observed="Marking an infeasible design was not enough. The latency, "
                 "the token rate and the energy were still computed and still "
                 "numbers, so a sweep or a ranking written later would use "
                 "them without knowing.",
        suspected="Hiding output is a presentation fix for a structural "
                  "problem. A figure that exists will be read.",
        changed="A capacity failure now replaces every PERFORMANCE metric with "
                "not-a-number. It propagates, every comparison against it is "
                "false, and anything that tries to rank on it produces "
                "not-a-number instead of a plausible position. Zero was "
                "rejected as worse than either: zero reads as 'it runs and is "
                "slow' and the actual state is that the configuration does not "
                "exist. The physical and economic figures survive, because a "
                "board that cannot run the model still has an area, a price "
                "and a cooling class.",
        evidence="The suppression immediately found four places that had been "
                 "computing on machines which cannot exist: a migration whose "
                 "narrow-memory baseline was 4 GB against a 5 GB model, a "
                 "runtime path with the same baseline, and two stack sweeps "
                 "starting below the capacity a 70 GB model needs. All four "
                 "had been producing plausible numbers for years.",
        affected="Four test series moved to feasible starting points, and "
                 "three exhaustive loops now skip infeasible draws with a "
                 "guard that most draws must still be checked - a skip that "
                 "swallowed the sample would be worse than the problem it "
                 "solves.",
        independent=True),
    Revision(
        version="3.67.0",
        observed="The five bottleneck names were presented as a result. Only "
                 "the ratio is.",
        suspected="Where 1.61 falls among five names is a threshold placed by "
                  "hand, not something the model derives.",
        changed="The thresholds are registered as an ENGINEERING ASSUMPTION "
                "and the ratio is reported beside the label.",
        evidence="A reader can now disagree with the boundary without "
                 "disagreeing with the model, which is the difference between "
                 "a classification and a measurement.",
        affected="Documentation and the coefficient registry.",
        independent=True),
    Revision(
        version="3.68.0",
        observed="Not-a-number is right inside the model and wrong on a "
                 "screen, where it reads as a crash. And a sort containing it "
                 "puts an impossible design somewhere that depends on the "
                 "language.",
        suspected="Two audiences, one value. The propagation must stay; the "
                  "presentation must not show it.",
        changed="A display helper that renders it as 'Not Evaluated', a "
                "ranking function that EXCLUDES infeasible designs rather than "
                "sorting them last, and a report for an infeasible board that "
                "shows what is still true of it - installed capacity, cost, "
                "area, cooling class - with the overall score as Not "
                "Applicable rather than a low number. The bottleneck label is "
                "suppressed too: 'compute bound' describes how a machine "
                "spends its time and this one does not spend any.",
        evidence="Where not-a-number lands in a sort depends on the library "
                 "and the comparison order. A design that cannot exist should "
                 "not have a position at all.",
        affected="Presentation and ranking. The stored values are unchanged.",
        independent=True),
    Revision(
        version="3.68.0",
        observed="A stack sweep showed totals, which say more is better.",
        suspected="The margin is the design question and the total is not. "
                  "They are different lessons from the same sweep.",
        changed="A marginal utility report: what each ADDITIONAL stack bought, "
                "and what a one per cent gain cost at that step.",
        evidence="On an LLM node the gain falls 32.4%, 23.9%, 18.9%, 15.5% "
                 "across four steps of equal price, so the cost of a single "
                 "per cent doubles. The delivered rate never moves at all - "
                 "every stack on the list bought capacity the workload never "
                 "asked for. The report refuses to name a knee: where to stop "
                 "depends on the requirement and on how many are being built, "
                 "and neither is in the table.",
        independent=True,
        affected="One new report, shown in the runtime menu for HBM "
                 "configurations."),
    Revision(
        version="3.68.0",
        observed="Nothing showed the case where a second engine and a faster "
                 "memory are only worth having together.",
        suspected="Each was being tested alone, and alone each can look "
                  "useless.",
        changed="A two-by-two: single and dual engine against LPDDR5 and HBM, "
                "with the interaction reported.",
        evidence="On a robot workload a second engine on one LPDDR5 package "
                 "makes the latency 17% WORSE - both engines wait for the same "
                 "memory. The same second engine on HBM makes it 19% better. A "
                 "student who adds the engine first concludes it does not "
                 "work, and the order they try things in decides what they "
                 "learn. Also added: three cases - host-limited, ISP-limited "
                 "and arrival-limited - where sixteen times the bandwidth "
                 "moves the delivered rate by under 5% and the cost by more "
                 "than half.",
        affected="Verification only - no computed value changed. What changed "
                 "is that the interaction between the two upgrades is now "
                 "measured rather than assumed absent.",
        independent=True),
    Revision(
        version="3.69.0",
        observed="A student picking a faster memory saw a latency figure. That "
                 "teaches only that faster memory is faster.",
        suspected="Three questions were arriving as one number: does the model "
                  "FIT, did the system get QUICKER, and can the product still "
                  "be BUILT. A design can pass the first two and fail the "
                  "third, and the third is the one that decides whether it "
                  "ships.",
        changed="A memory choice report that asks WHY before it shows what: "
                "three reasons a faster memory may help and three it may not, "
                "then capacity, then performance, then feasibility. A design "
                "whose model still does not fit stops at the first section - "
                "there is no performance to report and more bandwidth does not "
                "make it fit.",
        evidence="On a passively cooled drone the report reads: latency 2.6% "
                 "better, delivered throughput unchanged, energy per job 277% "
                 "WORSE, and two gates failed including a cooling class that "
                 "no amount of power reduction fixes. Every one of those is a "
                 "different answer to a different question, and a single "
                 "latency figure would have shown the only one that flattered "
                 "the choice.",
        affected="Presentation. The wording was also made plainer: 'HBM "
                 "exposes dual-NPU compute' became 'the second one was waiting "
                 "for memory, not short of work', and a capacity gain nobody "
                 "uses is now described as a machine that could do more and is "
                 "not being asked to.",
        independent=True),
    Revision(
        version="3.70.0",
        observed="The memory system was verified thoroughly and the LLM was "
                 "not. Context length, KV cache, batch and quantisation are "
                 "what an LLM deployment is actually decided on, and only one "
                 "context and one precision were ever run.",
        suspected="A gap in coverage rather than a defect. The model carries "
                  "a KV cache and a per-token cost and nothing was sweeping "
                  "them.",
        changed="Two sweeps: context length and quantisation width.",
        evidence="The context sweep is the one that teaches most. The weights "
                 "are IDENTICAL in every row - the same 70 GB model - and the "
                 "board runs out of memory anyway, because the cache follows "
                 "the conversation rather than the network. It grows exactly "
                 "in proportion: a board that holds the model at 4k tokens "
                 "stops holding it at 512k, where the cache alone is 84 GB. "
                 "Traffic per token rises 56% across the range, which is why "
                 "a long conversation is slower on the same machine.",
        affected="Two new reports, both in the runtime menu for text "
                 "workloads. No computed value changed.",
        independent=True),
    Revision(
        version="3.70.0",
        observed="The quantisation sweep printed a delivered token rate of 35 "
                 "for a design that fails its throughput gate at 31.6.",
        suspected="The delivered figure is capped at what the requirement asks "
                  "for, so it reads 35 whenever the capacity clears 35. An "
                  "interactive requirement is written against the SINGLE-JOB "
                  "rate, which is what the gate reads.",
        changed="The sweep shows the single-job rate and says which it is.",
        evidence="The delivered figure would have hidden the failure "
                 "entirely - the table would have shown a design meeting its "
                 "target while the verdict said it did not.",
        affected="One report column. This is the fourth time the three rates "
                 "have had to be told apart since they were named at 3.57.0, "
                 "and each time the wrong one was the flattering one.",
        independent=True),
    Revision(
        version="3.70.0",
        observed="Quantisation needs an accuracy cost and the model has no "
                 "basis for one.",
        suspected="What a network loses depends on the network, the "
                  "calibration and the method. Computing it would be "
                  "inventing it.",
        changed="Four figures registered as an ENGINEERING ASSUMPTION and "
                "PRINTED with every sweep, with a warning not to quote any "
                "verdict resting on them until they are replaced by measured "
                "ones.",
        evidence="The sweep's most interesting row depends on them: INT4 is "
                 "the only width that fits this board and it clears the "
                 "accuracy requirement by 0.4 points. Move the assumed cost by "
                 "half a point and that conclusion reverses, which is exactly "
                 "why the number is printed rather than buried.",
        affected="Documentation and the evidence register.",
        independent=True),
    Revision(
        version="3.71.0",
        observed="Batch size was fixed at one, so the model could not show the "
                 "single structural fact that makes an LLM server different "
                 "from a phone.",
        suspected="The WEIGHTS ARE SHARED and the CACHE IS NOT. Sixteen users "
                  "read the same seventy gigabytes once per step and carry "
                  "sixteen separate caches, so the cost per user falls and the "
                  "memory per user does not. A single-stream model cannot "
                  "express that asymmetry, and it explains most of how these "
                  "machines are sized.",
        changed="A batch sweep from one user to a hundred and twenty-eight.",
        evidence="Sixty-four users give 31.8 times the aggregate rate for "
                 "twice the per-user latency, and the traffic per user falls "
                 "thirty-seven fold - which is the entire economic case for "
                 "batching and is a property of the MEMORY rather than of the "
                 "arithmetic. At a hundred and twenty-eight the cache alone is "
                 "84 GB and the model stops fitting, so the server runs out of "
                 "USERS before it runs out of speed.",
        affected="One new report. Note on the arithmetic: the per-user cache "
                 "is derived from the per-token cost and the context length, "
                 "NOT from the application's kv_cache_bytes - the library "
                 "describes that figure as an aggregate for batched serving, "
                 "and using it per user would have multiplied an "
                 "already-multiplied quantity by the batch again.",
        independent=True),
    Revision(
        version="3.72.0",
        observed="Three LLM axes remained: how big the model is, how much of "
                 "the work is prompt rather than answer, and what a mixture of "
                 "experts changes.",
        suspected="Nothing wrong - the last of a list. The MoE one is the only "
                  "structural addition; the other two are sweeps the model "
                  "could already have run.",
        changed="A model size sweep across seven parameter counts, a prompt "
                "length sweep with the prefill-decode crossover, and a dense "
                "against mixture-of-experts comparison.",
        evidence="The MoE result is the one worth having. Memory follows the "
                 "TOTAL parameters and arithmetic follows the ACTIVE ones, "
                 "because every expert must be resident - which ones a token "
                 "needs is not known until it arrives. So it reads 24 GB per "
                 "token like a 24B dense model, stores 240 GB like a 240B one, "
                 "and produces the SAME token rate as the small model. A "
                 "student sizing the board from that token rate "
                 "under-provisions it ten-fold. The prompt sweep gives the "
                 "other useful number: at a 32-token prompt it takes 2 tokens "
                 "of answer for decode to cost as much as prefill did, and at "
                 "8192 it takes 433 - below that a product is a prefill "
                 "machine and above it a decode machine.",
        affected="Three new reports, all in the runtime menu for text "
                 "workloads. Two limits declared rather than approximated: "
                 "MoE routing cost is not modelled, and the model still has "
                 "ONE accelerator path per inference so it cannot send prefill "
                 "to one machine and decode to another - which is exactly what "
                 "a large deployment does, and exactly because the two differ "
                 "as much as this sweep shows.",
        independent=True),
    Revision(
        version="3.73.0",
        observed="The simulator printed what a design does and never why. A "
                 "student reading 'prefill 16x longer' learns which design "
                 "won, not the mechanism, and cannot carry it to a design the "
                 "tool has never shown them.",
        suspected="Half the teaching was missing rather than wrong. The "
                  "numbers were right and the reason they came out that way "
                  "existed only in the source comments.",
        changed="Eight causal chains - long prompts, MoE storage against "
                "bandwidth, KV cache growth, batching, a memory that did not "
                "help, a second engine that made things worse, quantisation "
                "and a finer node - plus a decision explanation that separates "
                "what a change achieved from what it cost.",
        evidence="The MoE case is the one students stop at: 240 GB stored and "
                 "24 GB read per token looks like an error until someone says "
                 "the router cannot know which experts a token needs before "
                 "the token arrives, so every expert must already be resident. "
                 "Storage follows total parameters and bandwidth follows "
                 "active ones, and that single sentence is the whole design.",
        affected="One new module and a menu entry. Nothing computed changed.",
        independent=True),
    Revision(
        version="3.73.0",
        observed="The first explanation I attached to a run contradicted it: "
                 "a chain titled 'why a faster memory changed nothing' printed "
                 "under a result where the latency had improved 88%.",
        suspected="An explanation is a claim about a mechanism, and one "
                  "attached to a run it does not describe teaches the "
                  "mechanism and a counter-example at once. The student cannot "
                  "tell which to believe.",
        changed="Every chain that can be tested against a run carries a test. "
                "A contradicting chain is refused out loud rather than "
                "printed, and automatic selection can only choose a chain that "
                "fits.",
        evidence="The first version of the test checked only the delivered "
                 "rate and passed on that same 88% run, because delivered was "
                 "capped by arrivals. 'Changed nothing' has to include the "
                 "latency, and what counts as nothing is now a stated "
                 "threshold rather than an exact comparison - a compute-bound "
                 "design still gains one to three percent from a wider bus, "
                 "and an exact test would reject every real example.",
        affected="Verification of the explanations. Two mutations added: "
                 "printing a contradicting chain anyway, and a test that "
                 "ignores the latency.",
        independent=True),
    Revision(
        version="3.73.0",
        observed="A design that fails a cost gate was being read as a design "
                 "that failed.",
        suspected="What a design is FOR changes whether its failures matter. A "
                  "cost gate is decisive for a product and irrelevant for a "
                  "bench prototype; an accuracy gate is decisive for both.",
        changed="The explanation gives a verdict per context - industrial "
                "deployment, research prototype, teaching example - and names "
                "which gates each one genuinely cannot ignore.",
        evidence="An LLM part that fails cost, power and cooling is not a "
                 "product and is an excellent teaching example, and saying "
                 "both is more useful than a single verdict. The report also "
                 "states what it does not know: the market, the schedule, the "
                 "competition and what a customer will pay, none of which is a "
                 "smaller part of the decision than the numbers above it.",
        affected="Presentation only - no computed value changed. What changed "
                 "is that a failing gate is now reported with the contexts it "
                 "does and does not block.",
        independent=True),
    Revision(
        version="3.73.0",
        observed="Two mutations were surviving that had nothing to do with "
                 "this release: collapsing five bound strengths into two, and "
                 "letting an infeasible design report a latency.",
        suspected="Both behaviours were added without a check that they hold. "
                  "Found by running the full mutation suite rather than only "
                  "the new mutations, which is the argument for running it "
                  "whole every time.",
        changed="Two checks. All five bound strengths must be reachable across "
                "the library, and a model that does not fit must report no "
                "performance figure at all.",
        evidence="Reporting a latency for a design that cannot run invites a "
                 "student to compare the speed of something that does not "
                 "exist. And a design at five times more arithmetic than "
                 "transfers still gains 26% from a faster memory where one at "
                 "fifteen times gains nothing - collapsing those two into "
                 "'compute bound' says they are the same design.",
        affected="Verification only - no computed value changed. Both "
                 "behaviours were already correct and neither was checked.",
        independent=True),
    Revision(
        version="3.74.0",
        observed="Every suite in the package compares the model with itself. "
                 "That catches a change and cannot catch an error - a formula "
                 "can be wrong and perfectly consistent, and nothing that "
                 "calls it will notice.",
        suspected="Internal consistency had been mistaken for correctness. "
                  "Three thousand checks, and none of them derived a quantity "
                  "a second way.",
        changed="An independent recomputation that derives the same "
                "quantities from the library data and the stated definitions "
                "without calling the functions under test, graded by what kind "
                "of evidence each check is: closed form, independent "
                "numerical, structural, boundary.",
        evidence="Seventy-three checks across six axes. The grades are "
                 "reported separately and deliberately: a closed-form check "
                 "proves the arithmetic, a structural one proves a relation "
                 "holds and says nothing about whether the numbers are right, "
                 "and a boundary check proves the model declines a question "
                 "rather than answering it badly. Reporting them as one total "
                 "would hide that.",
        affected="Verification only. Two of the new checks were themselves "
                 "wrong on the first run - one divided by yield twice where "
                 "the price per square millimetre already includes it, and "
                 "one asserted that a pipeline interval cannot exceed a job's "
                 "latency. The first was the check being wrong about the "
                 "model; the second was the check being wrong about "
                 "pipelines, and both are the outcome an independent "
                 "recomputation exists to distinguish.",
        independent=True),
    Revision(
        version="3.74.0",
        observed="An ISP station occupied 10.03 ms per frame inside a "
                 "sensor-to-control figure of 4.66 ms.",
        suspected="The ISP's time was hidden because it overlaps the NEXT "
                  "frame. Overlapping frames raises the RATE; it does not "
                  "shorten any one frame's journey, and sensor-to-control is "
                  "about one frame's journey. The ISP sits between the sensor "
                  "and the control by definition, so its time belongs in a "
                  "figure named for that boundary.",
        changed="The ISP's active time is added to sensor-to-control. The "
                "pipeline latency is unchanged - it measures from the "
                "accelerator's input and is documented as doing so.",
        evidence="On an inspection design the figure moves from 4.66 to 14.69 "
                 "ms, which is what a frame actually takes to become a "
                 "control decision. Nothing in three thousand existing checks "
                 "broke, and that is the finding: no check was looking at "
                 "this boundary, which is how a metric ends up named for "
                 "something it does not measure.",
        affected="Every configuration with an ISP in the path. A check and a "
                 "mutation now hold the boundary.",
        independent=True),
    Revision(
        version="3.75.0",
        observed="The ISP defect was not an arithmetic error. Every number was "
                 "consistent and one was named for a boundary it did not "
                 "measure - reported as sensor-to-control, actually "
                 "post-ISP-to-control.",
        suspected="Three thousand checks passed because all of them compared "
                  "numbers with numbers and none compared a number with its "
                  "NAME. A boundary written down can be checked; one carried "
                  "in someone's head cannot.",
        changed="A metric boundary contract: each latency states its start "
                "point, its end point and which pipeline stages fall between "
                "them, with structural checks that every stage is accounted "
                "for, every contract is contiguous, and the three nest.",
        evidence="An independent check now adds up the stages a boundary "
                 "claims to cover and compares that with what it reports, so "
                 "the gap between the pipeline latency and sensor-to-control "
                 "must be exactly the ISP plus capture plus control. A "
                 "mutation that removes a stage from the pipeline list is "
                 "caught by the contracts still naming it - a contract about "
                 "a stage the model does not have describes nothing.",
        affected="Verification and documentation.",
        independent=True),
    Revision(
        version="3.75.0",
        observed="Six predictions were written, hashed and locked before the "
                 "runs. Three aligned and three disagreed.",
        suspected="Nothing in advance - that is the point of locking them.",
        changed="Nothing in the model. All three disagreements were "
                "PREDICTION defects on investigation, recorded in a separate "
                "adjudication file rather than by editing the predictions.",
        evidence="H-01 predicted a host-limited design's capacity would be "
                 "unchanged by a second engine; it FELL 0.8%, because the "
                 "second engine launches its own graph and that launch lands "
                 "on the host the prediction had itself identified as the "
                 "constraint. H-06 predicted a finer node would raise the peak "
                 "arithmetic; nothing moved, because the application already "
                 "defaults to that node and the prediction never checked its "
                 "baseline. Both are the model being more careful than I was.",
        affected="Nothing computed. The prediction file is not edited when it "
                 "is wrong - a prediction adjusted after the result is not a "
                 "prediction, and this is stated in the file rather than "
                 "trusted to discipline.",
        independent=True),
    Revision(
        version="3.75.0",
        observed="H-05 predicted that splitting work between two engines "
                 "cannot change accuracy. It fell 1.05%.",
        suspected="Looked like a model defect. It is not: the 32x32 is "
                  "quantisation-aware trained and the 16x16 is post-training "
                  "quantised, so running half the work on the second one "
                  "genuinely lowers the result's quality. The prediction "
                  "assumed engines differ only in how many multipliers they "
                  "have.",
        changed="A claim already in the suite - that a second engine does not "
                "change accuracy - narrowed to what is actually true: it holds "
                "for an IDENTICAL engine. The existing check used two "
                "identical engines and so had never tested the other case.",
        evidence="A locked prediction found a check that was passing for the "
                 "wrong reason. That is what a holdout is for, and it took one "
                 "of six to find it.",
        affected="One check narrowed and one added.",
        independent=True),
    Revision(
        version="3.76.0",
        observed="The boundary contract covered latency only. The same class "
                 "of error - a figure named for a boundary it does not "
                 "measure - can happen to any metric.",
        suspected="Nothing yet, which is why it was worth writing the rest "
                  "down.",
        changed="Contracts for throughput, power, energy, cost and capacity, "
                "with the checker made family-aware: latency and throughput "
                "are measured over pipeline STAGES, power and cost over "
                "system PARTS, and requiring a power contract to name every "
                "pipeline stage would require it to answer a question it is "
                "not asking. Verification is bidirectional - everything in "
                "scope must be decided about, and nothing named may be "
                "outside scope.",
        evidence="The contracts found two errors as soon as they were "
                 "written. Both are recorded below.",
        affected="Documentation and verification.",
        independent=True),
    Revision(
        version="3.76.0",
        observed="The power contract named 'Accel power (W)'. The model "
                 "reports 'Accelerator active power (W)'.",
        suspected="A contract about a metric nobody reports describes "
                  "nothing.",
        changed="The name, and a check that every contracted metric appears "
                "in a real result.",
        evidence="Found within a minute of the contracts existing, which is "
                 "the argument for writing them.",
        affected="Two contract entries.",
        independent=True),
    Revision(
        version="3.76.0",
        observed="An independent check asserted that the single-job rate "
                 "cannot exceed the pipeline capacity. On an ISP-assisted "
                 "design it exceeds it by more than twice - 214.5 against "
                 "99.7 per second.",
        suspected="Not a defect in either number. The single-job rate is one "
                  "over the pipeline LATENCY, which excludes the ISP; the "
                  "capacity includes it. No job completes at 214 per second - "
                  "the frame passed through a stage the first boundary does "
                  "not count.",
        changed="The single-job rate moved into a family of its own. Two "
                "rates over different boundaries cannot be ordered, and "
                "putting them in one family asserted that they could.",
        evidence="This is the same lesson as the ISP latency defect arriving "
                 "on the throughput axis: the arithmetic was right both "
                 "times and the comparison was not. The contracts now say "
                 "which figures may be subtracted from which, and a mutation "
                 "that puts the single-job rate back among the throughputs "
                 "fails.",
        affected="One contract's family. No computed value changed.",
        independent=True),
    Revision(
        version="3.76.0",
        observed="A locked prediction proposed moving a design to 3 nm when "
                 "it was already on 3 nm, and the migration reported all its "
                 "claims as holding.",
        suspected="A move from a configuration to itself is not a move. "
                  "Reporting 'no change' for it reads as a finding about the "
                  "move rather than about the setup.",
        changed="A migration whose source and target are identical reports NO "
                "MIGRATION OCCURRED and makes no claims.",
        evidence="Every claim would have been trivially true and none of them "
                 "about the move.",
        affected="The migration checker.",
        independent=True),
    Revision(
        version="3.77.0",
        observed="Every verdict in the package was computed from one value of "
                 "each coefficient, so a conclusion that survives any "
                 "plausible figure and one that reverses on half a point were "
                 "reported the same way.",
        suspected="That is the most misleading thing this model could do. "
                  "Several conclusions were already suspected to be fragile - "
                  "the INT4 accuracy verdict clears its requirement by 0.4 "
                  "points against an assumption nobody has measured.",
        changed="A sensitivity module that moves one coefficient at a time "
                "across a stated range, finds where the verdict flips, and "
                "classifies the result: robust pass, robust fail, "
                "conditional, or boundary-adjacent - the last meaning the "
                "flip is close to the nominal value and the verdict is a "
                "property of the ASSUMPTION rather than of the design.",
        evidence="Four sweeps, three outcomes. The INT4 accuracy verdict "
                 "flips at 3.875 points against a nominal 3.5, which is 12% "
                 "of the range - it is boundary-adjacent and should not be "
                 "quoted without a measurement. The LLM throughput gate fails "
                 "across the whole serving-efficiency range from 0.28 to "
                 "0.64, so that verdict does NOT depend on the coefficient at "
                 "all. Both facts are invisible in a single-value report and "
                 "a reader cannot tell the two kinds apart from the number.",
        affected="One new module and a menu entry. No computed value changed.",
        independent=True),
    Revision(
        version="3.77.0",
        observed="A coefficient registry can contain an entry the code never "
                 "reads.",
        suspected="Decoration in a registry is a claim that something was "
                  "considered when it was not.",
        changed="A sweep whose value never moves the result is classified NO "
                "INFLUENCE and says so, and a test builds a deliberately "
                "inert coefficient to confirm the detector fires.",
        evidence="A detector that has never fired is not known to work.",
        affected="Verification only - no coefficient was found to be inert, "
                 "which is itself worth having checked.",
        independent=True),
    Revision(
        version="3.77.0",
        observed="A mutation that swapped the low and high ends of a sweep "
                 "survived.",
        suspected="It produces the same SET of sample points in reverse "
                  "order, and every outcome test read only the set. The order "
                  "does matter: the flip scan takes the FIRST disagreement "
                  "between adjacent pairs, so a descending sweep reports the "
                  "last crossing as the first. With a single crossing the two "
                  "coincide and nothing shows.",
        changed="A check that the samples ascend and span the declared range.",
        evidence="A property that only differs when a coefficient crosses "
                 "twice is still a property, and finding it needed a check "
                 "rather than an outcome comparison.",
        affected="Verification only - the sweep order was already correct and "
                 "nothing was testing that it stayed so.",
        independent=True),
    Revision(
        version="3.78.0",
        observed="Phase S1 asked whether a verdict survives its assumption. It "
                 "did not ask whether the WINNER changes.",
        suspected="A ranking that holds across a coefficient's range is a "
                  "design decision; one that flips inside it is a coefficient "
                  "decision wearing a design decision's clothes.",
        changed="A hand-off break-even table across frame sizes, a ranking "
                "stability report, and a full coefficient liveness audit.",
        evidence="The break-even table gives three kinds of answer at once: "
                 "at 1920x1080 and above the offload wins at every hand-off "
                 "cost from zero to 1500 microseconds, at 320x240 the host "
                 "wins above 250, and at 640x480 the crossing sits at 600. "
                 "Two structural results and one that depends on a "
                 "coefficient nobody has measured. On the ranking side, two "
                 "designs at a small frame swap first place at 150 "
                 "microseconds - a RANK FLIP - while the same comparison at "
                 "five megapixels is stable across the whole range.",
        affected="Three new reports. No computed value changed.",
        independent=True),
    Revision(
        version="3.78.0",
        observed="A stable winner can hide a changing order. At a small frame "
                 "the dual design wins throughout while second and third place "
                 "swap.",
        suspected="Reporting that as a rank flip would overstate it and "
                  "ignoring it would lose a real result.",
        changed="Order changes are reported separately from winner changes.",
        evidence="Second place moving is a real result and it is not an "
                 "answer to 'which should we build'.",
        affected="One report - no computed value changed. What changed is "
                 "that a stable winner no longer implies a stable order.",
        independent=True),
    Revision(
        version="3.78.0",
        observed="Two mutations that disabled the liveness detectors survived, "
                 "because every coefficient in the registry is live and "
                 "leak-free and disabling a detector that never fires changes "
                 "nothing observable.",
        suspected="The same gap the decorative-coefficient detector had at "
                  "3.77.0, arriving twice more. A detector that has never "
                  "fired is not known to work.",
        changed="Positive controls for both: a coefficient declared to affect "
                "the latency that the code never reads, and a real "
                "coefficient given a false declaration that it must not touch "
                "something it does touch. Both must be caught.",
        evidence="Six production coefficients move exactly what they declare "
                 "and nothing else - which is worth knowing and was not "
                 "checked before, and could not have been checked without "
                 "writing down what each one is supposed to affect. A "
                 "coefficient with no declared effect cannot be found to have "
                 "none.",
        affected="Verification. Also promoted the host's per-pixel byte counts "
                 "and locality exposure from local variables to module "
                 "constants, so a sweep can move them - the same argument that "
                 "promoted the host overlap at 3.55.0.",
        independent=True),
    Revision(
        version="3.79.0",
        observed="A memory energy figure changes what a transfer COSTS and not "
                 "how long it takes, which makes it the cleanest leakage test "
                 "in the package: a coefficient that should touch three "
                 "quantities and must not touch six.",
        suspected="Nothing in advance. The test exists because the invariance "
                  "is checkable, not because it was doubted.",
        changed="Two sweeps kept apart. A COMMON scale moves every memory's "
                "energy by the same factor and nothing about time or money "
                "may move; a RELATIVE one moves HBM alone and a ranking may "
                "legitimately reorder.",
        evidence="Under a common scale from 0.7 to 1.3, latency, capacity, "
                 "delivered throughput, traffic, cost and accuracy are "
                 "identical to twelve decimal places while energy and power "
                 "move as declared. No leakage. A mutation that wires the "
                 "energy figure into the memory demand is caught.",
        affected="Verification. The thermal verdict is explicitly a "
                 "CONSEQUENCE of the power rather than a second independent "
                 "finding, and is not counted as one.",
        independent=True),
    Revision(
        version="3.79.0",
        observed="Under a relative scale, energy per job and average power "
                 "give different answers.",
        suspected="They are different questions and have been throughout this "
                  "project - this is the fifth time they have come apart.",
        changed="Nothing. The result is reported as two verdicts rather than "
                "one.",
        evidence="Moving HBM's energy from 0.6 to 1.6 times nominal flips "
                 "which memory is more efficient PER JOB at a scale of 1.2, "
                 "and leaves the average-power gate failing at every point in "
                 "the range. Energy per job is CONDITIONAL and average power "
                 "is ROBUST FAIL. A report giving one number for 'efficiency' "
                 "would be right about half of it and silent about which "
                 "half.",
        affected="Reporting only - no computed value changed. What changed is "
                 "that the two are no longer summarised as one.",
        independent=True),
    Revision(
        version="3.79.0",
        observed="The declared list of what memory energy may affect named "
                 "'Memory energy (mJ)', which the model does not report.",
        suspected="The same error the boundary contract caught at 3.76.0, "
                  "arriving in the coefficient registry instead.",
        changed="The name, and the memory energy field added to the liveness "
                "audit - which now covers a library FIELD as well as module "
                "constants.",
        evidence="Caught the same way both times: by requiring that a "
                 "declaration name something real. Seven coefficients now move "
                 "exactly what they declare and nothing else.",
        affected="Verification only - the audit gained a coefficient it could "
                 "not previously reach.",
        independent=True),
    Revision(
        version="3.80.0",
        observed="Four thousand passing checks say the model is "
                 "self-consistent today. They say nothing about tomorrow, "
                 "another machine, or someone editing a coefficient and "
                 "forgetting.",
        suspected="Nothing wrong - a missing kind of evidence. A result that "
                  "cannot be reproduced is an anecdote however many checks "
                  "produced it.",
        changed="A reproducibility package: source checksums, a coefficient "
                "snapshot, the environment, a certified seed, a fingerprint "
                "of what the model computes, and a comparison in THREE levels "
                "rather than one - categorical results exactly, timings to "
                "1e-9 relative, and estimated costs to the precision they are "
                "quoted at.",
        evidence="Demanding bit-identical numbers across platforms fails for "
                 "reasons that have nothing to do with the model; demanding "
                 "nothing fails to notice a real drift. A verdict that "
                 "changes is a different answer at any tolerance, so verdicts "
                 "are compared exactly and numbers are not.",
        affected="One new module and a menu entry. No computed value "
                 "changed.",
        independent=True),
    Revision(
        version="3.80.0",
        observed="A reproducibility checker that has never rejected a "
                 "modified package is not known to work.",
        suspected="The same gap found three times already - a detector nobody "
                  "has made fire.",
        changed="Four positive controls: a moved coefficient, a changed "
                "scenario input, a different seed and an altered source "
                "digest. Each must be caught with its own named reason rather "
                "than a bare failure.",
        evidence="'The rerun did not match' is not a finding. A coefficient "
                 "difference is fixable by restoring a value; a source "
                 "difference means a different program ran; a seed difference "
                 "means the run was exploratory and never claimed to be a "
                 "reproduction.",
        affected="Verification. The tamper check itself had to be rewritten: "
                 "the first version called the package writer, which "
                 "overwrote the very tampering it was trying to detect and "
                 "then reported that tampering is undetectable.",
        independent=True),
    Revision(
        version="3.80.0",
        observed="The package can establish grade R2 and no more.",
        suspected="R3 needs a second machine and R5 needs someone who did not "
                  "write it. Neither can be claimed from inside.",
        changed="The grade is stated as R2 in the report, with the higher "
                "levels described and explicitly not claimed.",
        evidence="Claiming a reproduction level that requires an independent "
                 "party is the same error as calling a self-written "
                 "prediction a blind holdout, which this project already made "
                 "and corrected at 3.75.0.",
        affected="Reporting. The three numbers that belong together are the "
                 "internal validation readiness, the external evidence "
                 "coverage, and the reproducibility grade - and they are not "
                 "one number.",
        independent=True),
    Revision(
        version="3.81.0",
        observed="The natural next thing to write was an internal validation "
                 "percentage. A developer who computes their own validation "
                 "score has produced another self-assessment.",
        suspected="A number invites comparison with other numbers and hides "
                  "what it is made of. A list of what exists and what does "
                  "not is checkable by a reader.",
        changed="An evidence status list with three states - implemented, "
                "achieved, pending, limited - and a test that no percentage "
                "appears in it.",
        evidence="Three items are not implemented and say why: a "
                 "second-machine reproduction needs a machine this was not "
                 "written on, an independent holdout needs a predictor who "
                 "does not run the engine, and external evidence cannot be "
                 "raised by internal work at all.",
        affected="Reporting only - no computed value changed. What changed is "
                 "that the summary can no longer be read as a score.",
        independent=True),
    Revision(
        version="3.81.0",
        observed="Reaching R3 needed a procedure short enough that someone "
                 "would actually run it.",
        suspected="A summary that needs interpreting will not be run, and a "
                  "reproduction nobody runs is not evidence.",
        changed="certify.py: one command, no arguments, nine lines of output, "
                "with the conditions the run must meet printed before it "
                "starts. It puts its own folder first on the path so a "
                "development copy elsewhere cannot be the thing that gets "
                "tested.",
        evidence="It refuses to decide the grade. The package cannot tell two "
                 "computers apart when they report the same platform string, "
                 "so a match on a second machine has to be recorded as R3 by "
                 "hand - guessing would overstate it, which is the same error "
                 "as calling a self-written prediction a blind holdout.",
        affected="One new script. The evidence package must be regenerated as "
                 "the LAST step before a release: the source digest covers "
                 "the test files too, so editing a test invalidates it, and "
                 "that is correct - a different test suite is a different "
                 "claim.",
        independent=True),
    Revision(
        version="3.82.0",
        observed="certify.py failed on a real machine with ModuleNotFoundError "
                 "for ppact.reproducibility - a file that is in the archive "
                 "and was in the extracted folder.",
        suspected="The notebook kernel had already imported ppact from "
                  "another directory. Inserting a folder at the front of the "
                  "path does NOT redirect a package that is already in "
                  "sys.modules, so the import resolved against the cached "
                  "copy and looked for a file that exists here and not "
                  "there.",
        changed="certify.py inspects what is already loaded BEFORE importing "
                "anything, and refuses with both folder names rather than "
                "guessing.",
        evidence="Worse than the error would have been the silent case: an "
                 "older copy that does contain the module would have "
                 "certified successfully, and the result would have been "
                 "about the wrong folder. A script that assumes a clean "
                 "interpreter is wrong in the one environment students "
                 "actually use.",
        affected="certify.py only. The refusal exits non-zero and tells a "
                 "notebook user to restart the kernel, which is a smaller "
                 "cost than a certification of a directory nobody meant to "
                 "test.",
        independent=True),
    Revision(
        version="3.82.0",
        observed="A mutation that disabled the partial-extraction guard "
                 "survived.",
        suspected="The guard had never fired - the fourth detector in this "
                  "project found in that state.",
        changed="A positive control: certify.py is run in a folder with "
                "ppact/reproducibility.py and the recorded package removed, "
                "and must refuse.",
        evidence="It must also NOT report that as a failed reproduction. "
                 "Blaming the model for a missing file is the wrong finding, "
                 "and would send someone looking for a defect that is not "
                 "there.",
        affected="Verification only - no computed value changed. What changed "
                 "is that a guard which had never been observed to work now "
                 "has been.",
        independent=True),
    Revision(
        version="4.19.0",
        observed="A view comparing figures against stated constraints was "
                 "named Static Timing, after the report whose structure "
                 "it borrowed.",
        suspected="A chip designer reads that name as clock edges, setup "
                  "and hold, and cycle-accurate paths. None of those "
                  "exists in this model, and a system architect reading "
                  "the same words imports the same wrong picture.",
        changed="Renamed to Performance Constraints throughout - module, "
                "view, screen heading, menu entry and definition "
                "document. An intermediate rename to Constraint Slack was "
                "applied and corrected: it named the analysis after the "
                "figure it produces rather than after what it evaluates. "
                "The slack field itself is unchanged.",
        evidence="What the analogy was worth is that a timing engineer "
                 "expects slack to be against a NAMED constraint and "
                 "expects a report to say which path it describes. Those "
                 "two habits are kept. The vocabulary promised precision "
                 "the model does not have.",
        affected="Naming and presentation. No computed value changed.",
    ),
    Revision(
        version="4.18.0",
        observed="A block capacity derived from latency flow station times "
                 "reported 343.67 inf/s where the engine reported 99.73.",
        suspected="The latency flow and the throughput calculation use "
                  "DIFFERENT station lists, and the two were treated as "
                  "one model.",
        changed="The engine now exports Throughput stations (s) by name, "
                "and both the capacity view and the flow's throughput "
                "reference read from it rather than deriving a rate from "
                "flow times.",
        evidence="The ISP sets the pipeline interval at 10.027 ms and has "
                 "no box in the latency flow at all; shared memory is a "
                 "throughput station while correctly not being a latency "
                 "stage. The definition document had called the "
                 "derivation verified on the strength of one "
                 "configuration - the one where the ISP was idle, so the "
                 "slowest drawn station happened to also set the rate. "
                 "One case is not a check: the configurations where a "
                 "derivation breaks are the ones nobody picks as an "
                 "example.",
        affected="Presentation. One metric key was added and no computed "
                 "value changed across 1,296 configurations.",
    ),
    Revision(
        version="4.17.3",
        observed="Two earlier RC3 archives were deleted from the output "
                 "directory while building a third, and the third was "
                 "written under a file name that did not match the release "
                 "label inside it.",
        suspected="The deletion was an attempt to avoid overwriting. It is "
                  "worse than overwriting: an overwrite leaves one archive, "
                  "a delete leaves none, and neither 4.17.0 nor 4.17.1 can "
                  "be rebuilt because this project keeps no version "
                  "control.",
        changed="The label is v1.0-RC3.1 rather than 'RC3 Final' a second "
                "time, and check_release compares the archive file name "
                "against the declared release.",
        evidence="'Final' was applied at 4.17.1 and a further change "
                 "followed, so a second Final would be false about the "
                 "first. Nothing had ever compared the file name to the "
                 "label: the name was typed by whoever built the archive "
                 "and the label came from a constant, so two different "
                 "releases could wear one name - in the one place a "
                 "recipient looks first. Absence of an archive path is "
                 "reported as not checked rather than as a pass.",
        affected="Release naming and the integrity check. No computed "
                 "value changed.",
    ),
    Revision(
        version="4.17.3",
        observed="Two archives were deleted from the output folder during a "
                 "build: v1.0-RC3 (4.17.0) and v1.0-RC3-Final (4.17.1).",
        suspected="They were removed to avoid overwriting them, which is "
                  "the opposite of what the instruction asked for.",
        changed="Nothing can be changed. They cannot be regenerated: the "
                "source has moved to 4.17.2 and this project keeps no "
                "version history.",
        evidence="Overwriting leaves one archive; deleting leaves none. "
                 "The record is here rather than tidied away, because a "
                 "revision log that omits what was lost is a log that "
                 "cannot be trusted about what was kept.",
        affected="Two archives, permanently. No code and no computed "
                 "value.",
    ),
    Revision(
        version="4.17.3",
        observed="'Final' was applied at 4.17.1 and a further change "
                 "followed, so the label would have named two different "
                 "builds.",
        suspected="Nothing wrong with the code. The naming had run out of "
                  "room.",
        changed="This build is v1.0-RC3.1.",
        evidence="A label that admits the final release was not final is "
                 "more accurate than one that hides it. check_release "
                 "already compares the archive file name against the "
                 "label, so an archive named for one release cannot carry "
                 "another - that check was written at 4.11.0 and is the "
                 "reason this could only go wrong in the name I typed, not "
                 "in the package.",
        affected="The release label only. No engine value, no renderer, no "
                 "document and no check changed - what changed is the name "
                 "on the archive and the constant every screen reads it "
                 "from.",
    ),
    Revision(
        version="4.17.3",
        observed="An archive named v1.0-RC3.zip contained a build labelled "
                 "'v1.0-RC3 Final', and every integrity check passed. Two "
                 "earlier RC3 archives were also deleted from the output "
                 "directory while trying to avoid overwriting them.",
        suspected="The file name is chosen by hand at packaging time and "
                  "the label comes from a constant. The two facts never "
                  "met, so nothing could notice they disagreed.",
        changed="archive_name_matches_label() compares them, and returns "
                "None - explicitly not a pass - when no archive name is "
                "supplied. The release is v1.0-RC3.1.",
        evidence="Deleting to avoid overwriting is worse than overwriting: "
                 "an overwrite leaves one archive, a deletion leaves none, "
                 "and the two removed builds cannot be regenerated because "
                 "the source has moved on and this project keeps no "
                 "version control.",
        affected="Packaging. 'Final' was applied to 4.17.1 and a change "
                 "followed it; reusing the name would say the earlier "
                 "build had not existed.",
    ),
    Revision(
        version="4.17.2",
        observed="The process table used one foundry's naming - N7, N5, A16 "
                 "- while the architecture library refuses vendor names on "
                 "itself and states that no trademark appears in it.",
        suspected="Nobody chose the names. They were the shorthand that "
                  "came to hand, and the vendor-neutrality rule had never "
                  "been applied to the one table where it also belonged.",
        changed="Every user-facing name is now the dimension: 28nm, 16nm, "
                "12nm, 7nm, 5nm, 4nm, 3nm, 2nm, 1.6nm. display_name, "
                "node_nm and description are separate fields, so a remark "
                "about why a node is in the table is no longer folded into "
                "its name.",
        evidence="A dimension is an industry-wide descriptor belonging to "
                 "nobody, and this package models a generalized scaling "
                 "trend rather than any foundry's process, so borrowing a "
                 "vendor's names also misdescribed what is here. Ordering "
                 "uses node_nm: a string sort gives 1.6nm, 12nm, 16nm, "
                 "2nm. Internal keys are unchanged - moving them touches "
                 "saved files, golden data and the revision log, and "
                 "mixing that with a display change would make a numeric "
                 "regression and a storage migration fail together.",
        affected="Display only. 1,296 configurations differ in nothing. "
                 "Architecture Summary now shows the real node and whether "
                 "it was selected or supplied by the application, which "
                 "'product default' named neither.",
    ),
    Revision(
        version="4.17.2",
        observed="Two node mutations survived: dropping the '(selected)' "
                 "marker, and narrowing the comparison column back to 24 "
                 "characters.",
        suspected="Nothing checked either. Both were guarantees added to "
                  "the screen in the same change that added no rules for "
                  "them - the gap R13 was created for, appearing again one "
                  "change later.",
        changed="Three rules: a chosen node is marked as chosen, an "
                "application default is marked as one, and no summary "
                "field is truncated mid-word.",
        evidence="A column width is not a presentation preference here. At "
                 "24 characters '(application default)' becomes "
                 "'(application defau', and the origin is half of what the "
                 "field says. The R13 fixture also had to name its nodes "
                 "explicitly: a rule about marking a chosen node had no "
                 "chosen node to look at.",
        affected="Verification. No computed value changed.",
    ),
    Revision(
        version="4.17.2",
        observed="A unified multi-runtime launcher and Streamlit execution "
                 "were requested for RC3. Neither exists: the string "
                 "'streamlit' appears nowhere in this package.",
        suspected="Nothing. They were never built.",
        changed="Recorded as NOT ESTABLISHED in METHODOLOGY and deferred "
                "to RC4 in DEFERRED, rather than written during a release "
                "that freezes what has been verified.",
        evidence="A release note saying 'Streamlit supported' would be a "
                 "plan rather than an observation. What RC4 has to "
                 "demonstrate is not that the code exists but that three "
                 "runtimes produce the same figures from the same "
                 "ReviewAnalysis.",
        affected="Documentation. No code was added.",
    ),
    Revision(
        version="4.17.1",
        observed="Five new mutations, each disabling one guarantee the "
                 "review sections make, survived the full suite while "
                 "dying when run alone.",
        suspected="Nothing in the project checked what a section PROMISES "
                  "once it is present. R1-R10 asked which sections appear; "
                  "removing a scope line, a margin band or the "
                  "starting-point caveat broke nothing any suite could "
                  "see.",
        changed="R13 checks the guarantees themselves - scope lines, "
                "banded margins with their thresholds printed, ceiling "
                "versus floor, the starting-point disclaimer, and a "
                "clipped axis naming the value it hid.",
        evidence="Written because the mutations were right. A guarantee "
                 "nobody verifies is not a guarantee, and the totals "
                 "looked healthy the whole time.",
        affected="Verification only. 1,296 configurations differ in "
                 "nothing.",
    ),
    Revision(
        version="4.17.1",
        observed="R13 itself failed twice on its first attempt, and both "
                 "faults were the same shape as the ones it was written to "
                 "catch.",
        suspected="Every design in its fixtures was inside every budget, "
                  "so the exceeding branch never ran; and the clipping "
                  "check looked for the words 'raw value' rather than the "
                  "number, then searched the whole review and found the "
                  "figure in a table further down.",
        changed="A failing design was added to the fixtures, and the "
                "clipping check now reads the number inside the clipping "
                "block.",
        evidence="A guarantee about what happens when a design fails "
                 "cannot be checked with designs that succeed, and a "
                 "renderer printing 'raw value hidden' satisfied a check "
                 "looking for a label. Both are the same mistake: "
                 "verifying that a name exists rather than that the value "
                 "a reader needs is where they are told to look.",
        affected="Two checks. Distribution mutation: 157 of 157, survivors "
                 "0, run to completion inside the extracted archive.",
    ),
    Revision(
        version="4.17.1",
        observed="Five mutations disabling review-contract guarantees - the "
                 "margin bands, the scope lines, the starting-point caveat, "
                 "the requirement direction, the clipped raw value - all "
                 "SURVIVED a full run while passing when run alone.",
        suspected="Nothing tested them. R1 to R10 check which SECTIONS "
                  "appear; none checked what a section promises once it is "
                  "there.",
        changed="R13, on the guarantees themselves, plus a verification "
                "path so the mutation runner enforces the contract.",
        evidence="Confirmed before fixing: with the scope line removed, "
                 "both the contract suite and the language audit exited 0. "
                 "A guarantee nobody verifies is not a guarantee, and five "
                 "of them had been added to the product in the same session "
                 "that added no rules for them.",
        affected="Verification. No computed value changed.",
    ),
    Revision(
        version="4.17.1",
        observed="R13 passed the margin-band mutation on its first attempt, "
                 "and the clipping mutation twice.",
        suspected="Both were faults in the new rule rather than in the "
                  "product.",
        changed="R13 now exercises a design that FAILS its requirements, "
                "and reads the clipped raw value inside the clipping block "
                "rather than anywhere in the review.",
        evidence="Every design R13 used was within every budget, so the "
                 "exceeding branch never ran - a guarantee about failure "
                 "cannot be checked with designs that succeed. The clipping "
                 "check looked for the words 'raw value', which a renderer "
                 "printing 'raw value hidden' satisfies, and then found the "
                 "figure in the raw-value table further down the same "
                 "review. Both are the same mistake: checking that a label "
                 "exists rather than that the value is where the reader is "
                 "told to look.",
        affected="R13 only. No engine value, no renderer and no document "
                 "changed - what changed is whether two of its checks can "
                 "fail.",
    ),
    Revision(
        version="4.17.0",
        observed="Architecture Balance was rendered on one analysis path "
                 "out of eight, and measured bars with physical units "
                 "existed only as an image no console path produced. The "
                 "introduction material had promised a three-layer result "
                 "since RC2.",
        suspected="The promise lived in prose and the assembly lived in "
                  "each workflow separately, so each screen carried "
                  "whatever its author remembered.",
        changed="A Standard Engineering Review Contract, as a document AND "
                "as code: WORKFLOW_REGISTRY says which paths are analyses "
                "and which variant each is, STANDARD_REVIEW_CONTRACT fixes "
                "the sections and their order, and ReviewAnalysis computes "
                "everything once so no renderer can call the engine. All "
                "eight analysis workflows now route through one exit "
                "point.",
        evidence="tests_review_contract reports ABSENT, VIOLATED or PASS "
                 "per rule - 'not built yet' and 'built wrong' need "
                 "different work. It ran in audit mode at 4 pass / 10 "
                 "violated / 10 absent and finishes at 47 / 0 / 0, with "
                 "--enforce failing on any unmet rule so a diagnostic that "
                 "always exits 0 cannot become the certification check.",
        affected="Presentation only. 1,296 configurations were compared "
                 "after every migration step and differ in nothing.",
    ),
    Revision(
        version="4.17.0",
        observed="Single-design analyses had no review of their own; the "
                 "design game reached a score screen and then asked "
                 "whether to show the engineering result.",
        suspected="Asking implies the core result is optional, and a user "
                  "who answered no had completed an analysis and received "
                  "a number.",
        changed="Two variants. A single analysis gets Latency Composition "
                "and a one-profile Architecture Balance; a comparison gets "
                "Latency Change Breakdown and the two-profile comparison. "
                "The question was removed.",
        evidence="A single analysis is NOT compared against a starting "
                 "configuration to manufacture a change. A baseline on "
                 "every screen is read as the recommended design whatever "
                 "the label says, which cost a full release cycle at "
                 "4.15.0, and a default comparison would have reintroduced "
                 "it through the back door. build_review refuses a single "
                 "workflow given a starting configuration and a comparison "
                 "workflow given none.",
        affected="Every analysis path. No computed value changed.",
    ),
    Revision(
        version="4.17.0",
        observed="Two pictures called 'the measured results' contained "
                 "different measurements: the console text showed seven "
                 "contract metrics, the image showed board area and a "
                 "reaction distance and omitted throughput and energy.",
        suspected="They came from separate functions with separate metric "
                  "lists.",
        changed="Both render the same MetricReading list. Requirements "
                "state whether they are a ceiling or a floor, margins are "
                "banded CRITICAL / TIGHT / COMFORTABLE with the thresholds "
                "printed, and a panel spanning more than twenty times its "
                "requirement switches to a log axis.",
        evidence="A reader who has seen two complete-looking pictures "
                 "cannot tell which is the result. 'Delivered throughput "
                 "60, limit 60' read as a near-miss when the requirement "
                 "was a floor met exactly; 'Total silicon 498 of 500' and "
                 "'System cost 37 of 1500' both read 'within requirement', "
                 "and one is a memory package away from failing.",
        affected="Presentation. Seven metrics, one definition, two "
                 "renderers.",
    ),
    Revision(
        version="4.16.1",
        observed="The mutation suite had passed 152/152 in the verified "
                 "development tree, and the clean distribution matched that "
                 "tree's source digest - but the suite had never been run "
                 "to completion inside the extracted distribution.",
        suspected="Nothing. The two trees should behave identically, and "
                  "the digests say they are the same source.",
        changed="Ran it. 152/152, survivors 0, critical 143/143, inside the "
                "archive a user would receive.",
        evidence="'Should behave identically' and 'was observed to behave "
                 "identically' are different statements, and only the "
                 "second is evidence. The distinction has come up "
                 "repeatedly in this project and was not going to be "
                 "blurred in the last step of it.",
        affected="Nothing in the program. The release label becomes "
                 "v1.0-RC2 Final, and every claim in the release record is "
                 "now something that was watched rather than inferred.",
    ),
    Revision(
        version="4.16.0",
        observed="Thousands of checks verified that the model computes what "
                 "it says. None asked whether the numbers, the deployment "
                 "status, the explanation, the score, the chart and the "
                 "recommendation agree with each other.",
        suspected="A model can be wrong about the world and internally "
                  "coherent. It can also be plausible about the world and "
                  "say two contradictory things on one screen - and the "
                  "second is worse: a reader who catches the contradiction "
                  "stops trusting everything, and a reader who does not "
                  "carries away whichever half they read.",
        changed="Twenty-one cross-model contradiction cases, each with a "
                "positive control, and each failure printing BOTH "
                "statements that cannot be true together. LC21 drives the "
                "whole user flow rather than internal functions, because a "
                "suite that checks functions can pass while the screens "
                "compute something else.",
        evidence="Deliberately excluded: whether coefficients match a "
                 "commercial part, whether estimated power equals measured "
                 "silicon. Those are questions about the world and are "
                 "listed under what is not established.",
        affected="Verification. Registered in verify_release.py and in the "
                 "validation report, and certification now REFUSES a "
                 "release whose record shows the suite failed or not run - "
                 "'not run' is not a pass, at the gate as everywhere else.",
    ),
    Revision(
        version="4.16.0",
        observed="Three of the new cases failed on first run, and all three "
                 "were faults in the test rather than in the model.",
        suspected="A contradiction case is a comparison, and a comparison "
                  "that moves two things at once cannot attribute what it "
                  "finds.",
        changed="LC17 varied the cooling class on ONE application instead of "
                "comparing two applications; LC06 chose a change that "
                "actually reduces latency, so its invariant fires; LC04, "
                "LC05 and LC12 unpack the decomposition as it is returned.",
        evidence="LC17 reported a 252 against 249 mm2 'contradiction' that "
                 "was two different workloads. The rule now followed: change "
                 "one modelled factor at a time unless the case explicitly "
                 "evaluates an interaction. Two controls had also been "
                 "'caught' by an exception, which is not the rule catching "
                 "anything, and were fixed rather than counted.",
        affected="Three cases and two controls. No engine value changed.",
    ),
    Revision(
        version="4.15.0",
        observed="'Reference design' read as the recommended architecture to "
                 "every student who met it, and the tool exists to explore a "
                 "design space rather than recommend a point in it.",
        suspected="Nobody chose the word. It was simply what came to hand - "
                  "and terminology drifts back the same way: a term is "
                  "removed, months pass, somebody writes the natural phrase, "
                  "and the philosophy is gone with no defect to point at.",
        changed="A terminology registry. Each concept carries one canonical "
                "name, one definition quoted verbatim by every document, the "
                "aliases that must never appear, and WHY each alias is "
                "wrong. Seven concepts, versioned, with a compatibility "
                "statement.",
        evidence="The reason field matters most and is checked: a ban "
                 "without a reason is a rule somebody relaxes under "
                 "pressure, because they cannot see what it was protecting. "
                 "L16 became a philosophy audit over the registry - "
                 "forbidden, deprecated, contradictory, duplicate and "
                 "ambiguous.",
        affected="Eleven modules and every document. No computed value "
                 "changed.",
    ),
    Revision(
        version="4.15.0",
        observed="The first scan reported 51 violations, of which 45 were "
                 "the word 'ships' used as an ordinary verb.",
        suspected="The retired thing was 'ships' as a COLUMN HEADING and a "
                  "verdict, which tests_language L08 already governs "
                  "precisely and with positive controls. The registry was "
                  "reaching past its subject.",
        changed="Removed from the registry, with the reason written where "
                "the next person will look for it.",
        evidence="A check with 51 false positives is a check somebody turns "
                 "off, and a rule that reaches past its subject stops being "
                 "obeyed. Of the six genuine findings, three were fixed and "
                 "three are in the revision log - a HISTORICAL RECORD states "
                 "past fact, and renaming a defect there would make the "
                 "record disagree with what happened.",
        affected="The registry's scope. Three prose lines.",
    ),
    Revision(
        version="4.15.0",
        observed="Two audits flagged the canonical definition as a violation "
                 "of itself: 'it is not a recommendation, not an optimal "
                 "design' contains 'optimal design'.",
        suspected="Neither rule could read a negation, and one judged lines "
                  "in isolation while the definition wraps across two.",
        changed="Both read negations; the terminology scan judges a line "
                "with its neighbours.",
        evidence="A rule that cannot read a denial makes the correct wording "
                 "impossible to write. The wrapping case failed in three "
                 "documents at once and would have failed in any document "
                 "that quoted the definition, which is all of them.",
        affected="Two audits. A DEFERRED entry records that the framework is "
                 "NOT extracted: an interface chosen against one product is "
                 "shaped like that product, and a second Studio will find "
                 "the joints. Separability is checked rather than claimed - "
                 "neither registry imports the engine at module level, and "
                 "the question registry reaches it in eight option builders, "
                 "which is the seam.",
    ),
    Revision(
        version="4.14.0",
        observed="A user was shown `Memory packages [1]:` above `1. 1  2. 2  "
                 "3. 4  4. 8` and could not tell what they were selecting. "
                 "Four bare integers under what is nearly the internal "
                 "variable name.",
        suspected="Not one bad prompt. Thirty-nine prompts had the same "
                  "shape, because each was written where it was needed and "
                  "nothing held them to a standard.",
        changed="A question registry. A screen asks for a question BY KEY "
                "and cannot invent a wording, an option label or a default. "
                "Each definition carries a professional parameter name, an "
                "explanation, what the choice affects, per-option "
                "engineering labels, term definitions, help text and a "
                "validation message.",
        evidence="The audit was written before the questions were migrated, "
                 "because eleven prompts fixed by hand are eleven prompts "
                 "clear today and the twelfth is written the old way. It "
                 "refused the starting state on three counts and now runs "
                 "895 checks. Direct user-facing prompts outside the "
                 "registry: 0.",
        affected="Prompts and their wording. A behavioural pack checks that "
                 "every option resolves to a real library key and that a "
                 "design built from the defaults evaluates - the migration "
                 "changed how a question READS and must not move a result.",
    ),
    Revision(
        version="4.14.0",
        observed="The prompt printed 'Type H for additional details' and no "
                 "H handler existed. Typing H produced 'Enter a number from "
                 "1 to 4'.",
        suspected="Worse than offering no help: a reader learns the program "
                  "does not mean what it says.",
        changed="A help path that accepts H, h, ? and help, prints the "
                "terms, the metrics the choice can move, the default, every "
                "option and whether the selection changes the design or only "
                "the score, then returns to the same question with the same "
                "default.",
        evidence="ask_question takes an injectable input function, because a "
                 "help handler nobody can drive is a help handler nobody "
                 "knows works - and this one was promised on screen before "
                 "it existed. Every registered question is driven through "
                 "every spelling, plus help-then-Enter and "
                 "help-then-bad-entry. The expected count is a RELATION - "
                 "questions x spellings x cases - so adding a question "
                 "raises it and dropping one lowers it, where a fixed number "
                 "would pass the day a question vanished.",
        affected="The prompt runner. No computed value changed.",
    ),
    Revision(
        version="4.14.0",
        observed="Thirty-five of the prompts were navigation - 'Choose', "
                 "'Show', 'What would you like to do' - not parameters.",
        suspected="Forcing the parameter contract onto those puts a "
                  "paragraph about engineering consequences above a list of "
                  "menu items, and noise is how a standard stops being "
                  "read.",
        changed="A second kind with a smaller contract: a name, what the "
                "choice leads to, and options whose labels say where they "
                "go. What it does NOT get is an exemption - a navigation "
                "prompt goes through the same runner, handles H, and refuses "
                "a bad entry with the same wording.",
        evidence="The distinction is what a question must DECLARE, not "
                 "whether it is governed. Two checks in this project were "
                 "found reading old prompt wording out of source files and "
                 "reporting the migration as a regression; both were changed "
                 "to check the registry instead, because a check that reads "
                 "a string cannot see a question that moved.",
        affected="Navigation prompts. No computed value changed.",
    ),
    Revision(
        version="4.13.0",
        observed="A student opening the release found a README written for "
                 "somebody maintaining the library.",
        suspected="The four documents were correct and none of them told a "
                  "student what to do in the first hour, or what to do when "
                  "Colab could not find the package.",
        changed="STUDENT_GUIDE.md - Colab and Jupyter start-up, a table of "
                "the four errors a student actually hits and what each "
                "means, an hour-by-hour first session, and the two "
                "distinctions worth getting right early: latency is not "
                "throughput, and NOT READY does not mean a long latency. "
                "EXERCISES.md - twelve exercises with no answers in them.",
        evidence="The exercise sheet ends with what a good answer looks "
                 "like, in the project's own terms: not 'the memory is the "
                 "bottleneck' but 'the accelerator waits 3.2 ms of an 11.5 "
                 "ms job, so memory is 28% of the time and cannot give back "
                 "more than that'. Both documents were written against the "
                 "existing audit and passed it without amendment.",
        affected="Two new documents, registered in the manifest, the "
                 "integrity check and the documentation digest. No engine "
                 "value changed.",
    ),
    Revision(
        version="4.13.0",
        observed="A student receiving the archive had README, ABOUT, HELP "
                 "and METHODOLOGY - four documents written for somebody "
                 "deciding whether to trust the tool, not for somebody with "
                 "ten minutes and a Colab tab.",
        changed="STUDENT_GUIDE.md - getting it running, the first five "
                "minutes, how to read a result, and a table of every message "
                "that can stop them, with what it means. EXERCISES.md - "
                "twelve exercises with determinate answers, and marking "
                "notes.",
        suspected="Nothing was wrong with the four documents. They answer a "
                  "different question from the one a student asks first.",
        evidence="The exercises are chosen so the obvious answer is wrong at "
                 "least as often as it is right, and each says to write the "
                 "prediction down before running anything. The marking note "
                 "says a right verdict with a wrong reason should not score "
                 "above a wrong verdict with a sound reason and a stated "
                 "assumption: the first is a guess that landed.",
        affected="Two documents, added to the manifest, the digest list and "
                 "the integrity check. No engine value changed.",
    ),
    Revision(
        version="4.12.0",
        observed="The release manifest could not carry a mutation result. "
                 "Certification writes the manifest and does not run the "
                 "suites, so the figure had to be typed in - and one that "
                 "was typed in got overwritten on the next certification, "
                 "silently.",
        suspected="The manifest was being asked to record something the "
                  "process that writes it had no way to observe.",
        changed="verify_release.py runs the suites and writes "
                "rc_verification.json, stamped with the engine version it "
                "ran against. The manifest reads that file. A record "
                "produced against a different engine is reported as STALE "
                "rather than adopted.",
        evidence="Every entry is written after a subprocess exits, from its "
                 "exit code and its own output - the counts come from each "
                 "suite rather than from this runner. A suite skipped by "
                 "--quick is recorded as not run WITH THE REASON, and the "
                 "run ends INCOMPLETE rather than passing. A result from an "
                 "earlier build is evidence about an earlier build.",
        affected="A new runner and the manifest. No engine value changed.",
    ),
    Revision(
        version="4.12.0",
        observed="The manifest carried one combined documentation digest.",
        suspected="It tells a reader that SOMETHING in the documentation "
                  "changed and leaves them to diff four files to find out "
                  "what.",
        changed="Per-file digests, with the combined one kept as the cheap "
                "comparison when nothing changed. check_release.py verifies "
                "them and reports which document was edited after the "
                "release was built.",
        evidence="A new integrity check that runs before certification, "
                 "needs nothing imported, and names the file in every "
                 "failure. Run against the working tree it correctly refuses "
                 "it, listing four development traces.",
        affected="The manifest and a new check.",
    ),
    Revision(
        version="4.12.0",
        observed="Adding EDUCATIONAL_VALIDATION.md made a positive control "
                 "stop catching anything.",
        suspected="The control reversed a not-established claim in "
                  "METHODOLOGY.md alone. The claim was also made elsewhere, "
                  "so the rule was satisfied by the copy the control had not "
                  "touched - correctly.",
        changed="A control may now edit several documents at once, and this "
                "one edits every document carrying the claim.",
        evidence="The rule was right and the control was wrong, which is the "
                 "distinction expected-failure identity exists to surface. A "
                 "control that edits one of several copies proves nothing, "
                 "and it fails silently by passing.",
        affected="Verification. DEFERRED.md and EDUCATIONAL_VALIDATION.md "
                 "were added - the second is a PROTOCOL, not a result, and "
                 "states what would NOT count as one: a single group "
                 "improving on a second attempt, satisfaction, time saved "
                 "alone, or anything measured unblinded by whoever built the "
                 "tool.",
    ),
    Revision(
        version="4.12.0",
        observed="The release manifest could not carry a mutation result. "
                 "Certification writes the manifest and does not run the "
                 "suites, so a mutation figure in it would have been a "
                 "number somebody typed.",
        suspected="Two different jobs had been folded into one program. "
                  "Certification answers 'does this copy reproduce the "
                  "release'. Nothing answered 'did the suites pass on this "
                  "build'.",
        changed="verify_release.py runs the suites as subprocesses and "
                "writes rc_verification.json, reading each count from the "
                "suite's own output. The manifest reads that file and "
                "reports a record produced against a different engine "
                "version as STALE rather than adopting it.",
        evidence="A --quick run skips mutation testing and the record says "
                 "'not run: --quick was requested', the summary says NOT "
                 "RUN, and the exit is INCOMPLETE. An entry absent from the "
                 "record means the suite was not run; it never means the "
                 "suite passed, and the record says so in its own text.",
        affected="A new runner and the manifest. No engine value changed.",
    ),
    Revision(
        version="4.12.0",
        observed="The manifest carried one combined documentation digest.",
        suspected="It tells a reader that SOMETHING in the documentation "
                  "changed and leaves them to diff four files to find out "
                  "what.",
        changed="Per-file digests alongside the combined one. A changed "
                "README is visible immediately, and an unchanged "
                "METHODOLOGY is visible too.",
        evidence="check_release.py compares those digests against the files "
                 "on disk, so a copy whose documents were edited after the "
                 "build is reported as edited rather than passing as "
                 "genuine.",
        affected="The manifest and a new integrity check.",
    ),
    Revision(
        version="4.12.0",
        observed="Adding EDUCATIONAL_VALIDATION.md made a positive control "
                 "pass that should have failed: the one reversing a "
                 "not-established claim to established.",
        suspected="The control edited METHODOLOGY.md alone. The claim was "
                  "also made in DEFERRED.md, so the rule was satisfied by "
                  "the copy the control had not touched - and the rule was "
                  "RIGHT to be satisfied. The control was wrong.",
        changed="A control may now swap several documents at once, and this "
                "one swaps every document carrying the claim.",
        evidence="The failure was correct and arrived the moment a new "
                 "document was added. That is what expected-failure "
                 "identity buys: a control that silently stopped working "
                 "would have left the reversal guard unwatched, which is "
                 "exactly the defect that blocked the release two versions "
                 "ago.",
        affected="Verification. Two documents added: a deferral list with "
                 "reasons, and an educational validation PROTOCOL that "
                 "states what would not count as a result and where a null "
                 "result goes.",
    ),
    Revision(
        version="4.11.0",
        observed="The release archive was named v1.0-RC1 while the manifest "
                 "inside it said v1.0.",
        suspected="Certification regenerates the manifest and had no label "
                  "to regenerate it with, so it fell back to the version. A "
                  "candidate and the release it becomes share a VERSION and "
                  "differ in LABEL, and the two had been treated as one "
                  "thing.",
        changed="RELEASE_LABEL is a single constant beside PRODUCT_VERSION, "
                "read by the manifest and by anything else that needs it.",
        evidence="Mixing a label across a zip name, a manifest and a screen "
                 "is how somebody tests one artefact and ships another. "
                 "Found by reading the manifest out of the built archive "
                 "rather than out of the working tree - the two had "
                 "disagreed and nothing in the tree could show it.",
        affected="One constant and the manifest. No engine value changed.",
    ),
    Revision(
        version="4.11.0",
        observed="A release was described in prose and nowhere in a form a "
                 "program could check.",
        suspected="Years later the text report is something a person has to "
                  "read and interpret. A record a machine can compare a copy "
                  "against is a different kind of evidence.",
        changed="release_manifest.json: product, release label, both "
                "versions, build time, Python, platform, a DOCUMENTATION "
                "digest separate from the source digest, the evidence "
                "package hash, the validation categories, and what is not "
                "established. A copy travels inside the evidence package.",
        evidence="Fields recording a verification result are present ONLY "
                 "when that verification ran during the build. An absent "
                 "field means not run, never that it passed - a manifest "
                 "filling in 'validation: PASS' without a suite having run "
                 "would be the most authoritative-looking lie in the "
                 "package, and a check requires that a manifest built "
                 "without results claims none.",
        affected="Certification output. No engine value changed.",
    ),
    Revision(
        version="4.10.0",
        observed="A mutation that disabled the NOT ESTABLISHED check in the "
                 "documentation audit survived. The audit still reported "
                 "186 of 186.",
        suspected="Not the rule and not the documents - both were correct "
                  "when run directly. The positive-control harness was nine "
                  "blocks, each saving the results list, clearing it, "
                  "running one control, restoring, and appending its own "
                  "verdict. One block forgot to refresh the snapshot "
                  "afterwards, so the NEXT block restored a stale copy and "
                  "silently deleted that control's result.",
        changed="The controls are now a registered list run through one "
                "harness. State capture, restoration, expected-failure "
                "identity and counting happen in one place and cannot be "
                "omitted by a control.",
        evidence="The consequence was worse than a missing check. The lost "
                 "control was the one guarding NOT ESTABLISHED - the "
                 "distinction this project is built on - so a guard could be "
                 "removed and nothing would notice. The reported count was "
                 "also wrong: 185 checks ran, not 186. A count is the only "
                 "thing that notices a discarded result, so registered, "
                 "executed and reported counts are now compared and must "
                 "agree.",
        affected="The documentation audit harness. No documentation content "
                 "and no engine value changed.",
    ),
    Revision(
        version="4.10.0",
        observed="A control that merely required 'the audit failed' would "
                 "pass while the guard it was written for was dead, if some "
                 "other rule happened to fail on the same input.",
        changed="Every control declares WHICH rule must catch it, and is "
                "failed when a different one does.",
        suspected="Nothing yet - written to prevent that, not in response "
                  "to it.",
        evidence="It found an error immediately, and the error was mine: I "
                 "attributed a renamed NOT ESTABLISHED heading to the item "
                 "rule. A renamed heading is caught by the required-sections "
                 "rule instead, because the four items may still be named in "
                 "the README - what is lost is the section a reader is sent "
                 "to. The control was corrected rather than the audit "
                 "weakened.",
        affected="Verification only - no documentation content and no engine "
                 "value changed. What changed is that a control now proves "
                 "the guard it was written for.",
    ),
    Revision(
        version="4.10.0",
        observed="With the harness fixed, a second documentation mutation "
                 "survived: the guard requiring host connection to be marked "
                 "informational had no control at all.",
        suspected="It had been written and never given input to reject, like "
                  "the ten detectors before it.",
        changed="A control added, and three variants of the NOT ESTABLISHED "
                "case rather than one: the item absent from every document, "
                "the heading renamed, the section deleted, and a claim "
                "reversed from not-established to established.",
        evidence="Eighteen controls, all executed and all reported. "
                 "Documentation mutations now 8 of 8. The harness reports a "
                 "control-shaped hole instead of hiding one, which is the "
                 "difference between the two versions.",
        affected="Verification. Release remained blocked until this reached "
                 "8 of 8.",
    ),
    Revision(
        version="4.9.0",
        observed="An inspection of the README found two exercises telling a "
                 "student to work on applications called ondevice_llm and "
                 "automotive. Neither exists. A student following the "
                 "document gets a KeyError.",
        suspected="Not a writing problem - an EXECUTABLE defect. And every "
                  "one of those sentences was true when it was written, "
                  "which is the whole difficulty: fixing the prose without a "
                  "check produces a document that is correct today and wrong "
                  "in three releases, and nobody notices until a student "
                  "does.",
        changed="The documentation audit was written FIRST, and the "
                "documents were then written to pass it. It checks version "
                "agreement, that every documented mode exists and every mode "
                "is documented, that every named application, metric and "
                "function exists, that no retired term or unquantified "
                "adjective survives, that no unimplemented feature is "
                "claimed, and that documented formulas match the code. It "
                "EXECUTES every documented example.",
        evidence="Run against the old README it failed 19 checks, including "
                 "both dead application names, an unquantified 'better', and "
                 "a three-step reading order superseded three releases "
                 "earlier. README, ABOUT, HELP and METHODOLOGY now pass 178 "
                 "of 178.",
        affected="Four documents and a new suite. No engine value changed.",
    ),
    Revision(
        version="4.9.0",
        observed="Prose scanning is fragile in both directions: it misses a "
                 "claim phrased unusually and it fails on a sentence that "
                 "merely mentions a word.",
        changed="A machine-readable registry, docs_manifest.json, listing "
                "the public modes, the application keys and metric names the "
                "documents may use, the documented features, the "
                "informational-only ones, the retired terms and the required "
                "sections. The audit compares that against the code "
                "registries; prose scanning remains as a secondary "
                "safeguard and says so where it is used.",
        suspected="Nothing yet - the registry was written to prevent the "
                  "fragile-regex failure rather than in response to one.",
        evidence="The strict rule caught the word 'ships' used as an "
                 "ordinary verb in ABOUT.md. The sentence was rewritten "
                 "rather than the rule loosened: a strict rule that is easy "
                 "to obey is worth more than a nuanced one that needs "
                 "arguing about each time.",
        affected="Verification. Seventeen vendor and product names are "
                 "refused in documents as well as in library files.",
    ),
    Revision(
        version="4.9.0",
        observed="A README stating a check count is wrong at the next "
                 "release and looks authoritative while it is.",
        suspected="Prose is not run, so nothing corrects it.",
        changed="VALIDATION_REPORT.txt is generated by certify.py, carries "
                "the release and the generation time, and lists the "
                "validation CATEGORIES with the file that provides each. The "
                "README carries categories and no numbers, and the audit "
                "fails on a three-digit count in the README.",
        evidence="The generated report also carries the four things NOT "
                 "established - measured hardware accuracy, educational "
                 "effectiveness, independent external validation and "
                 "commercial product equivalence - because a report listing "
                 "only what passed would be an advertisement. The audit "
                 "requires all four to appear in the documents too.",
        affected="Certification, the README and a generated file. No engine "
                 "value changed.",
    ),
    Revision(
        version="4.8.0",
        observed="Two suites asked whether an answer exists and whether it "
                 "is right. Neither asked whether the answers agree with "
                 "each other.",
        suspected="A student does not check the balance chart. They read the "
                  "last line. If the breakdown says the host holds 90% of "
                  "one job and the takeaway says to upgrade the "
                  "accelerator, the student leaves with the wrong lesson and "
                  "every other check in this package passed while it "
                  "happened.",
        changed="A consistency pack over ten scenarios: the station holding "
                "most of the time, the limit the engine reports, the part "
                "the recommendation names first, the guided answers, and the "
                "takeaway must all point the same way. Station names are "
                "mapped, because 'host active' in a breakdown and 'Host "
                "processor' in a ranking are the same thing said twice.",
        evidence="Every scenario passes, which is also what a detector that "
                 "has never fired looks like. So it was given the exact "
                 "contradiction it exists to catch - a takeaway saying "
                 "'upgrade the accelerator' beside a breakdown showing the "
                 "host at 90% - and caught it in five scenarios, naming both "
                 "sides in the failure. Ninth detector in this project found "
                 "never to have fired.",
        affected="Verification. No engine or presentation value changed.",
    ),
    Revision(
        version="4.8.0",
        observed="Nothing checked that the same input produces the same "
                 "output.",
        suspected="A screen that differs between two identical runs has "
                  "state it should not have - a cached figure, a set "
                  "iterated in hash order, a timestamp - and the difference "
                  "surfaces later as a bug report nobody can reproduce.",
        changed="Five scenarios rendered ten times each: the explanation, "
                "the takeaway, the balance view and the generated questions "
                "must be byte-identical.",
        evidence="Twenty checks, all passing. A formality until the day it "
                 "is not, and the day it is not is the day it is worth "
                 "having.",
        affected="Verification only - no engine or presentation value "
                 "changed. What changed is that instability would now be "
                 "caught here rather than in a bug report.",
    ),
    Revision(
        version="4.8.0",
        observed="A user-validation pass found four defects in the screens "
                 "it was checking.",
        suspected="The screens had been checked for correctness and never "
                  "for whether a reader could answer anything from them.",
        changed="An infeasible design now reports its deployment verdict and "
                "its physical figures - a board that cannot run its model "
                "still costs what it costs, and 'can it ship' has an answer "
                "there. Its takeaway quotes the deficit rather than saying "
                "the model does not fit. The balance chart's overlap test "
                "compares DISPLAYED values, after a guided answer said Power "
                "had moved while the chart showed 51 twice.",
        evidence="Ten scenarios spanning a change that helps, one that does "
                 "not, one that helps and costs, one that breaks a "
                 "requirement and one that cannot run. 716 checks.",
        affected="The explanation screen, the takeaway, and the overlap "
                 "test. No computed value changed.",
    ),
    Revision(
        version="4.6.0",
        observed="The Studio described itself, when it described itself at "
                 "all, with the sentence 'PPACT Studio does not model "
                 "commercial products.'",
        suspected="True, and the wrong first sentence. It tells a reader "
                  "what the Studio is NOT and leaves them to work out what "
                  "it is. A description built that way can only ever be a "
                  "list of refusals.",
        changed="An About page in five sections, in a fixed order: purpose, "
                "method, evolution, design boundary, interpretation. Plus "
                "four core principles - architecture before implementation, "
                "engineering evidence before intuition, vendor-neutral "
                "exploration, continuous refinement through public "
                "industrial information.",
        evidence="The ORDER is the argument and is checked. The boundary "
                 "comes fourth because it is a CONSEQUENCE of the three "
                 "sections before it: a tool built to explore architecture, "
                 "using analytical models, refined by public information, "
                 "could not reproduce a commercial part even if it wanted "
                 "to - the figures needed are not public, and inventing them "
                 "would make an estimate indistinguishable from a "
                 "measurement. Said fourth it reads as a design decision; "
                 "said first it reads as an apology.",
        affected="A new page reachable from Demo and Validation modes and "
                 "from the full tool list. No computed value changed. A "
                 "mutation that moves the boundary to the front is caught.",
    ),
    Revision(
        version="4.5.0",
        observed="Published products deploy the same silicon as a bare SoC, "
                 "a USB stick, a PCIe card, a module and a box. The library "
                 "had no way to say which, so a user who knows those "
                 "products found the Studio silent about the first decision "
                 "they make.",
        suspected="Two bad options were available. Omitting it leaves the "
                  "Studio looking a generation behind. Modelling it means a "
                  "new term in the latency decomposition, which is verified "
                  "to zero residue across 180 configurations and would have "
                  "to be re-verified - and an unverified term is worse than "
                  "no term.",
        changed="A third option: the library RECOGNISES the connection and "
                "the model does not use it. Six classes - on-board, USB 3.x, "
                "PCIe Gen4, PCIe Gen5, Ethernet, UCIe - with on-board as the "
                "default, so a design written before this field existed "
                "behaves exactly as it did.",
        evidence="The whole value of that depends on the second half being "
                 "true, so it is checked exhaustively rather than promised: "
                 "every metric, every gate and the bottleneck verdict are "
                 "compared at all six settings across three applications and "
                 "must be identical, and nine engine modules are checked not "
                 "to mention the field at all.",
        affected="One configuration field and the report. No computed value "
                 "changed - that is the point, and it is enforced.",
    ),
    Revision(
        version="4.5.0",
        observed="A parameter shown in a report reads as a parameter that "
                 "was used.",
        suspected="Exposing a modern option silently would be worse than "
                  "omitting it: the reader would reasonably assume the "
                  "number below it reflected their choice.",
        changed="Every report that prints the connection prints, beside it, "
                "that the analytical model does not use it in this release "
                "and that a check requires every metric to be identical at "
                "every setting.",
        evidence="Saying a field is informational is a promise. Saying a "
                 "check enforces it is a fact a reader can go and verify. A "
                 "mutation that drops the disclaimer is caught. Phase 2 - "
                 "when there is a link term and it has been verified - may "
                 "switch it on; the order matters, because a parameter that "
                 "reaches an equation before it is verified is not made "
                 "honest by how carefully it was written.",
        affected="Presentation only - no computed value changed. What "
                 "changed is that a field a reader can see now says what it "
                 "is and is not.",
    ),
    Revision(
        version="4.4.0",
        observed="A portfolio spanning an SoC, a USB stick, a card, a "
                 "module, a desktop box and a vehicle box showed six "
                 "products differing in almost nothing EXCEPT how they are "
                 "deployed. The model cannot tell them apart at all.",
        suspected="The library had been measured against markets and not "
                  "against DEPLOYMENT, which is the axis it is weakest on. "
                  "It also had nothing at the low end: about ten INT8 TOPS "
                  "in three watts, which is where a great deal of shipping "
                  "silicon sits, was simply absent.",
        changed="Three accelerator classes - an on-device SoC near 10 TOPS, "
                "an embedded module near 25, and a low-profile card near 80 "
                "- plus DDR4 and LPDDR4. Eight deployment classes declared, "
                "of which seven are honestly marked absent.",
        evidence="Adding the 10 TOPS class made it the nearest entry to a "
                 "published 25 TOPS module in 5 W, and a check found the "
                 "envelope did not reach. Closing one gap exposed a "
                 "narrower one, and the module class was added in response. "
                 "That is the framework working: the gap was found by a "
                 "check rather than by a review.",
        affected="The compute and memory libraries and the class registry. "
                 "Fifteen accelerator classes now, across five deployment "
                 "shapes of which one is expressible.",
    ),
    Revision(
        version="4.4.0",
        observed="A coverage report written at 4.3.0 printed percentages: "
                 "'deployment coverage 12.5%', 'architecture 33.3%'.",
        suspected="A percentage needs a denominator, and the denominator "
                  "implied by 'industrial coverage' is the world's "
                  "semiconductor industry. Eleven products from three "
                  "vendors is not a sample of that. The figure looked like a "
                  "measurement against the industry and was a measurement "
                  "against a list this project wrote itself.",
        changed="Every coverage percentage removed and replaced by counts of "
                "things that happened: companies reviewed, products "
                "reviewed, published facts recorded, concepts identified, "
                "classes implemented, work pending. A check now refuses any "
                "percentage in these reports and any heading of the form "
                "'... Coverage'.",
        evidence="A reader can check every line of the replacement. Nobody "
                 "could check 33.3%, and the credibility cost of a number "
                 "like that is larger than anything it bought. I wrote it "
                 "one release earlier and it was wrong to write.",
        affected="The validation reports. No library or engine value "
                 "changed.",
    ),
    Revision(
        version="4.3.0",
        observed="Coverage had been measured against automotive silicon "
                 "only. A data-centre inference datasheet showed a shape the "
                 "library could not express at all: a 150 W passively cooled "
                 "card with 256 MB of on-chip buffer and stacked memory.",
        suspected="Coverage measured against one market is coverage of one "
                  "market. Automotive and data-centre inference are the two "
                  "halves of where AI silicon is being built, and the "
                  "library had entries shaped like one of them.",
        changed="Two accelerator classes - a server vision card near 64 TOPS "
                "and a data-centre inference card near 512 - and LPDDR4X. "
                "Three profiles from a second vendor as evidence.",
        evidence="The distinguishing feature of the inference card class is "
                 "the buffer: hundreds of megabytes rather than tens, which "
                 "is what lets a part hold a working set a smaller cache "
                 "would stream. The previous-generation vision part is "
                 "included precisely because it is not the newest - it fixes "
                 "the low end of the server band, which a flagship alone "
                 "cannot.",
        affected="The compute and memory libraries and the class registry. "
                 "No equation changed. Coverage now reads 12 accelerator "
                 "classes across 4 of 5 domains, with 'training' still "
                 "empty and saying so.",
    ),
    Revision(
        version="4.3.0",
        observed="The second vendor's comparative claims are excluded from "
                 "evidence for a DIFFERENT reason from the first's.",
        suspected="The first named no baseline at all. This one names its "
                  "baselines - and states in its own disclaimer that the "
                  "competitor figures were measured by itself.",
        changed="Recorded as UNKNOWN with that reason written out, and the "
                "vendor-neutrality check extended to the second vendor's "
                "names, its architecture name, and the competitor parts it "
                "benchmarks against.",
        evidence="A benchmark of a rival, run by the rival's competitor, is "
                 "not a neutral measurement. Using it would put one vendor's "
                 "view of another into this library. Both exclusions are now "
                 "on the record with their separate reasons, which is more "
                 "useful than one rule applied twice.",
        affected="Two facts and the neutrality check. Seventeen vendor and "
                 "product names are now refused in library files and "
                 "permitted in evidence files.",
    ),
    Revision(
        version="4.3.0",
        observed="The rack-scale profile is the one the Studio is furthest "
                 "from: eight accelerators, a host, a chassis power budget "
                 "and a rack power budget.",
        suspected="A design here is a single device. None of those four is "
                  "expressible, and adding a class would not change that.",
        changed="Nothing. It is recorded as a profile and its gaps go to the "
                "structural backlog, which is a separate development phase.",
        evidence="Data expansion adds entries and changes no equation. "
                 "Rack-scale changes what a design IS. Filling the gap with "
                 "an entry that pretends a rack is one large card would be "
                 "the failure this framework exists to prevent - and it "
                 "would look like progress.",
        affected="The gap report. No library change.",
    ),
    Revision(
        version="4.2.0",
        observed="The library ran from 51 TOPS straight to 600, and had no "
                 "LPDDR5X, no DDR5, no HBM2E and no HBM3. An engineer "
                 "familiar with current accelerators would open the Studio "
                 "and conclude it models hardware from several years ago.",
        suspected="A library coverage problem, not a modelling one. The "
                  "engine was never wrong; the selectable architecture had "
                  "stopped resembling what people build.",
        changed="Six accelerator classes from 100 to 800 TOPS, and four "
                "memory classes: DDR5, LPDDR5X, HBM2E, HBM3. The memory "
                "generations now run DDR5 through HBM4 without a hole.",
        evidence="These are CLASSES, not products. No vendor is named, no "
                 "trademark appears, no proprietary organisation is "
                 "inferred. What is taken from industry is the shape of a "
                 "band - roughly this much arithmetic in roughly this power "
                 "envelope - and every parameter is an engineering estimate "
                 "scaled from the measured entries, marked as one.",
        affected="The compute and memory libraries. No equation changed: "
                 "this is data expansion, deliberately kept apart from the "
                 "structural work.",
    ),
    Revision(
        version="4.2.0",
        observed="Six classes added in one sitting is a maintenance problem "
                 "as much as a fix.",
        suspected="A number typed into a library entry looks exactly like a "
                  "number that was measured, and in a year nobody will "
                  "remember which was which or where it came from.",
        changed="A class registry that carries what the library entry "
                "cannot: confidence, the evidence the estimate rests on, and "
                "the domain it belongs to. A class present in one and absent "
                "from the other is a defect a check reports.",
        evidence="Two entries were written with 'as above' as their evidence "
                 "and the check refused them immediately. Nothing in the "
                 "registry claims high confidence: no vendor publishes "
                 "enough about any of these for a figure to be checked, and "
                 "claiming otherwise is the failure the file exists to "
                 "avoid.",
        affected="A new module and eight checks in the validation suite.",
    ),
    Revision(
        version="4.2.0",
        observed="The first pass named classes after their arithmetic - '250 "
                 "TOPS class'.",
        suspected="That is how a datasheet is indexed and not how a system "
                  "is chosen. Somebody building an automotive controller "
                  "starts from a domain with a power envelope, a memory "
                  "class and a deployment model; the arithmetic follows from "
                  "what fits.",
        changed="The registry is organised by DOMAIN - entry, edge, "
                "automotive, cloud inference, training - with the TOPS "
                "figure a parameter inside a class. A performance-named "
                "entry with no domain is a defect.",
        evidence="Four of five domains have a class; training has none and "
                 "the metrics say so rather than averaging it away. The "
                 "metrics are reported together and never summed, because a "
                 "single 'library quality' number would let a gap in one "
                 "domain be paid for by an entry in another.",
        affected="The registry and the coverage report. No engine value "
                 "changed.",
    ),
    Revision(
        version="4.2.0",
        observed="The library ran from 51 TOPS to 600 with nothing between, "
                 "and had no LPDDR5X, DDR5, HBM2E or HBM3. An engineer who "
                 "knows current accelerators would have concluded it models "
                 "hardware from several years ago, and been right.",
        suspected="A coverage problem in the LIBRARY, not a defect in the "
                  "engine. The analytical model was never wrong; it simply "
                  "had nothing modern to point at.",
        changed="Six accelerator classes across the automotive band and four "
                "memory generations. Every one is an architectural CLASS, "
                "not a product: no vendor is named, no proprietary "
                "organisation is inferred, and what is taken from industry "
                "is the shape of the class - roughly this much arithmetic, "
                "in roughly this envelope, at roughly this price.",
        evidence="Every parameter is marked ESTIMATED in the entry itself. "
                 "The JEDEC interface rates are the exception and are "
                 "labelled as standards. Two entries carry a warning that in "
                 "industry that performance point is reached by pairing "
                 "dies, which this library cannot express - the gap is "
                 "recorded rather than hidden by the entry that fills it.",
        affected="The compute and memory libraries. No equation changed.",
    ),
    Revision(
        version="4.2.0",
        observed="Six classes added in one sitting is a maintenance problem: "
                 "a number typed into a library entry looks exactly like a "
                 "measured one, and in a year nobody remembers which was "
                 "which.",
        suspected="The library entry can carry the parameters and cannot "
                  "carry the provenance.",
        changed="A versioned class registry holding what the entry cannot: "
                "confidence, the evidence the estimate rests on, which "
                "parameters are estimates, and the DOMAIN. A class present "
                "in one and absent from the other is a defect a check "
                "reports.",
        evidence="The first pass named classes after their arithmetic - '250 "
                 "TOPS class' - which is how a datasheet is indexed and not "
                 "how a system is chosen. Nobody starts from a TOPS figure; "
                 "they start from a domain with a power envelope, a memory "
                 "class and a deployment model, and the arithmetic follows. "
                 "The registry is organised by domain and reports that "
                 "'training' has no class at all.",
        affected="A new module and its checks. Nothing computed changed. No "
                 "confidence level above 'medium' exists, because no vendor "
                 "publishes enough for any figure here to be checked.",
    ),
    Revision(
        version="4.2.0",
        observed="A vendor-neutrality check found a commercial product name "
                 "in a library entry: an accelerator was called 'Edge GPU "
                 "(Orin class)'.",
        suspected="It had been there since 3.26.0 and read as a helpful "
                  "reference point. It is a selectable item with a product "
                  "name on it, which is exactly what the philosophy "
                  "forbids.",
        changed="Renamed to 'Edge GPU module class'.",
        evidence="The rule is now precise rather than absolute: a product "
                 "name is allowed in an EVIDENCE file, where it is the thing "
                 "being cited, and forbidden in a LIBRARY file, where it "
                 "would become something a user selects. Banning it "
                 "everywhere would mean the industry cases could not say "
                 "which industry they came from, which is the opposite of "
                 "evidence. Both halves are checked.",
        affected="One library entry name. Structural expansion - deployment "
                 "models, interconnect classes, chiplets, sparsity - is "
                 "listed as a separate phase and deliberately NOT done here: "
                 "it changes the timing decomposition, which is verified to "
                 "zero residue across 180 configurations, and shipping both "
                 "under one version would make the first failure impossible "
                 "to attribute.",
    ),
    Revision(
        version="4.1.0",
        observed="A shipping automotive AI accelerator was described in "
                 "public and the library could express almost none of it.",
        suspected="Not a defect - a blind spot. The library was built for "
                  "teaching and had never been measured against what people "
                  "actually build, so nothing said which concepts were "
                  "missing.",
        changed="A library validation framework: published specifications "
                "held as profiles, and six developer reports - coverage by "
                "category, gaps, alignment, confidence, calibration and "
                "trend.",
        evidence="Three parts from one vendor found ten gaps: no engine in "
                 "the 200-300 TOPS automotive band (the library jumps from 51 "
                 "to 600), no chiplet, no host interconnect, no LPDDR5X, no "
                 "virtualization, no sparsity, no security block, and no way "
                 "to express a co-processor attached to somebody else's host. "
                 "Coverage is reported per category rather than as one "
                 "number, because '68% covered' hides which 32% and which 32% "
                 "is the whole question.",
        affected="A new module and a developer suite. NOTHING was added to "
                 "the library - every gap is a backlog line a person reads. A "
                 "framework that added a part whenever it met one would turn "
                 "an exploration tool into a product catalogue, silently.",
    ),
    Revision(
        version="4.1.0",
        observed="Two vendor claims read as specifications: 2x TOPS per "
                 "dollar and 1.5x TOPS per watt, each 'compared to existing "
                 "solution'.",
        suspected="Neither names a baseline. A ratio against an unnamed "
                  "baseline is not a measurement of anything, and treating it "
                  "as one would put a press release into the evidence.",
        changed="Both recorded as UNKNOWN with the reason, and a check "
                "requires that neither ratio appears among the published "
                "facts.",
        evidence="This is the same rule the project applied to its own "
                 "figures at 3.30.0, when a power comparison was retracted "
                 "because the two numbers came from different boundaries. The "
                 "rule does not change because the number is somebody "
                 "else's.",
        affected="Two facts in one profile, and one check.",
    ),
    Revision(
        version="4.1.0",
        observed="Three profiles from one vendor is a sample of one vendor.",
        suspected="A tally across them would read as an industry trend, and "
                  "would be that vendor's roadmap.",
        changed="The trend report refuses to call a trend below three vendors "
                "or eight profiles, says so in those words, and prints the "
                "tally as 'what these profiles happen to state' instead.",
        evidence="Every report carries the sample size. Success here is not "
                 "the number of profiles - it is whether the library explains "
                 "real design choices with more confidence over time while "
                 "staying clear about what is known, estimated and unknown.",
        affected="One report. The framework is a developer tool and a check "
                 "requires that no Studio menu entry reaches it.",
    ),
    Revision(
        version="4.0.1",
        observed="A deployment check timed out: run_jupyter.py did not finish "
                 "in 300 seconds and produced no output at all.",
        suspected="With no stdin the menu prompt caught the exception and "
                  "returned the DEFAULT, which on the main menu is 1. So it "
                  "ran Quick Start, came back to the menu, took the default "
                  "again, and looped forever. A student whose notebook cannot "
                  "prompt would have seen the same - a launcher that appears "
                  "to hang.",
        changed="No input means STOP, not take the default. A menu that "
                "cannot be answered should end.",
        evidence="The launcher went from a 300-second timeout to finishing in "
                 "two seconds with a clean exit. Found by running a "
                 "deployment check I had reported as not run - the check was "
                 "correct and had never been given the chance to fail.",
        affected="The mode menu. A check now drives the launcher with no "
                 "stdin and requires a clean exit, and a mutation that "
                 "restores the default is caught.",
    ),
    Revision(
        version="4.0.1",
        observed="The launcher's package module list was missing nine "
                 "entries: branding, modes, lessons, progress, challenge, "
                 "demo, decide, framework and workspace.",
        suspected="Each was added over the last several releases and the list "
                  "was never updated with it. The list is what the launcher "
                  "uses to verify and repair an extraction, so those nine "
                  "would not have been noticed missing from a partial "
                  "unzip.",
        changed="All nine added to both launchers.",
        evidence="The check that catches this existed and reported only six, "
                 "because it reads the archive rather than the working tree "
                 "and the archive was stale. Rebuilt, it found nine. A check "
                 "reading an old copy is a check answering an old question.",
        affected="run_jupyter.py and run_colab.py.",
    ),
    Revision(
        version="4.0.0",
        observed="Nine suites checked the arithmetic. Nothing checked the "
                 "WORDS, and the words are what a reader takes away.",
        suspected="A model that computes a 14.4% latency change and prints "
                  "'HBM is faster' has taught nothing - the reader cannot say "
                  "faster at what, by how much, or why, and those are the "
                  "three things they came for. Worse, vocabulary drifts: one "
                  "screen says single-job latency, another says job latency, "
                  "and a reader who does not already know they are the same "
                  "number will assume they are two.",
        changed="A Language QA suite of fifteen packs over sixty-eight "
                "rendered screens: forbidden terminology, canonical names, "
                "units, a WHY behind every conclusion, numbers inside every "
                "WHY, metric naming, deployment wording, recommendation "
                "wording, and the tutorial, demo, challenge, validation, help "
                "and error voices.",
        evidence="It found two genuine drifts - 'end-to-end latency' in the "
                 "capability map and 'job latency' in the runtime docstring - "
                 "and four places where a comparative stood with no figure "
                 "beside it: 'faster than the last brief' as a challenge "
                 "target reason, 'cheaper than the last one', 'almost free, "
                 "and slower' as a lesson row note. Each now carries its "
                 "number.",
        affected="Wording across challenges, lessons, the capability map and "
                 "the runtime documentation. No computed value changed.",
    ),
    Revision(
        version="4.0.0",
        observed="The obvious implementation of a forbidden-word audit is a "
                 "blanket ban.",
        suspected="It would be wrong. 'Performance' is in the product's own "
                  "subtitle; 'small engine' is the NAME of a row in a lesson "
                  "table, not a judgement of one; 'Are two engines twice as "
                  "fast?' is the question a demo is about to answer with "
                  "figures. A blanket ban forces worse writing and is obeyed "
                  "by replacing a clear word with a clumsy one.",
        changed="A word is forbidden AS A VERDICT - standing alone in a table "
                "or on a short line with no number - and never inside a "
                "question or a prose block. The exceptions are listed with "
                "their reasons and printed with every run, so the list cannot "
                "grow without somebody reading it.",
        evidence="The first version of the canonical-name check reported "
                 "'job latency' as a violation because it is a substring of "
                 "'single-job latency' - the canonical name failing itself. "
                 "Fixed with a word boundary, which is the same class of "
                 "error as banning a word without reading its sentence.",
        affected="Verification. Nine allowed uses are declared.",
    ),
    Revision(
        version="4.0.0",
        observed="The program had no startup screen and no product version - "
                 "only an engine version at 3.x.",
        suspected="Reporting 3.99 to a student reports the developer's "
                  "history rather than what they are holding. The engine has "
                  "been revised three hundred times against its own "
                  "arithmetic; the product is on its first release.",
        changed="A banner with the product name, a PRODUCT_VERSION constant "
                "at 1.0, the axes, what the program claims to be, and the "
                "sentence that matters: final engineering decisions remain "
                "the responsibility of the designer. Shown once per session, "
                "not above every return to the menu - a claim repeated ten "
                "times stops being read.",
        evidence="The version is a single constant. This project has already "
                 "shipped a release where certify.py carried one number and "
                 "the package another, and the symptom looked like a defect "
                 "in the model.",
        affected="The startup screen. The engine version is still reported, "
                 "below the product one, because a bug report needs it.",
    ),
    Revision(
        version="3.99.0",
        observed="A random stress draw reported a host bandwidth allocation "
                 "of MINUS 225 GB/s on a twelve-stack HBM4 board.",
        suspected="The bus is split between the host and the accelerator "
                  "early, and dual-engine contention narrows the bus later. "
                  "The accelerator kept its pre-contention allocation while "
                  "the bus shrank beneath it, so the host's share - computed "
                  "as the remainder - went negative.",
        changed="Both shares are rescaled by the same factor when contention "
                "narrows the bus. Contention takes bandwidth from the PAIR, "
                "not from one of them, so each agent's fraction is unchanged "
                "and the partition stays exact.",
        evidence="Three and a half thousand random runnable draws now show a "
                 "worst host allocation of exactly zero and an exact "
                 "partition everywhere. This is the fourth defect in this "
                 "project found by ordering - a quantity computed correctly "
                 "and then invalidated by something that ran after it.",
        affected="Every dual-accelerator configuration in parallel mode. "
                 "Found by a random draw, not by reasoning, which is the "
                 "argument for the stress pack.",
    ),
    Revision(
        version="3.99.0",
        observed="Before a freeze the useful question stops being 'is the "
                 "feature right?' and becomes 'how would I break this?'.",
        suspected="A model can be arithmetically correct and still be a bad "
                  "product: it can contradict itself between two screens, "
                  "report a latency that goes down and then up as a memory "
                  "widens, recommend upgrading the part that holds 3% of the "
                  "time, or crash on a frame of one pixel. None of those is a "
                  "wrong formula, and none would be caught by a suite that "
                  "only checks formulas.",
        changed="A Freeze Validation Suite of eleven packs by quality "
                "attribute - functional, boundary, multi-path, monotonic, "
                "cross-consistency, explanation, failure handling, "
                "regression, numerical stability, random stress, UI and "
                "terminology - plus a certification report.",
        evidence="5,248 checks. It found the negative bandwidth above, five "
                 "screens whose tables ran past the width of a terminal, and "
                 "confirmed that a sensitivity sweep puts every coefficient "
                 "back, that two screens quoting the same design agree to "
                 "twelve decimal places, and that a design where the host "
                 "holds most of the time is never told to buy memory first.",
        affected="Verification, and five screens that now wrap. The report "
                 "ends with what it does NOT establish - second-machine "
                 "reproduction, an independent holdout, external evidence, "
                 "field validation - because a report listing only what "
                 "passed would be an advertisement.",
    ),
    Revision(
        version="3.98.0",
        observed="A search for 'bottleneck' returned one result. Three tools "
                 "answer exactly that question.",
        suspected="Search matched names and docstrings only, and nobody names "
                  "a tool after the question it answers. Worse, ten tools "
                  "were reachable only from a mode and were in neither the "
                  "full tool list nor the search - a tool nobody can find is "
                  "a tool that does not exist.",
        changed="All ten added to the tool list, and a concept index built by "
                "hand: about fifty words a person would actually type, "
                "pointed at the tools that answer them. Mode entry labels are "
                "searched too, because those were written in the words a "
                "reader chose.",
        evidence="'bottleneck' now finds three, 'assumption' two, 'what if' "
                 "one, 'export' one. A check requires that every index entry "
                 "point at a tool that exists, so a dead link fails rather "
                 "than silently finding nothing.",
        affected="The tool list and search. No engine value changed.",
    ),
    Revision(
        version="3.98.0",
        observed="The workspace could list recent designs and export them, "
                 "and could not OPEN one.",
        suspected="That is the whole point of keeping them. The retyping is "
                  "what costs a researcher time, not the arithmetic - a "
                  "design is several fields, and re-entering all of them from "
                  "memory is where the errors come from, because the one "
                  "field remembered wrongly is invisible in the result.",
        changed="Opening a recent or saved design rebuilds it, shows its "
                "numbers, and puts it back at the top of the history so the "
                "next tool picks it up. Plus a single-design markdown export "
                "alongside the CSV.",
        evidence="Nothing computed is ever stored - a check reads the "
                 "workspace file and fails if a latency or a power figure "
                 "appears in it. A file of cached numbers goes stale the "
                 "first time a coefficient moves and nothing notices, so "
                 "every export runs the model again, and a check compares an "
                 "exported latency against a fresh evaluation.",
        affected="The workspace screen. The storage half is checked to call "
                 "no evaluation at all: a workspace that changed a result "
                 "would be worse than none.",
    ),
    Revision(
        version="3.97.0",
        observed="The mutation suite stopped finishing. It ran 78 of 129 "
                 "mutations inside the time available and was killed.",
        suspected="The runner exercised ALL forty-five verification paths for "
                  "every mutation and only then looked at the results. With "
                  "the model suite past four thousand checks that is "
                  "quadratic: 129 mutations times a suite that grows with "
                  "every release.",
        changed="The runner stops at the first failing check.",
        evidence="A mutation is killed the moment any check notices it; "
                 "running the remaining forty paths afterwards tells us "
                 "nothing. Coverage is unchanged - a killed mutation is "
                 "killed whichever check caught it, and a SURVIVOR still runs "
                 "every path, which is the only case where running them all "
                 "matters. The full suite went from not finishing to 284 "
                 "seconds, and reports 129 of 129 with no survivors.",
        affected="The mutation runner only. No engine or test logic changed. "
                 "Reported honestly at 3.96.0 as unfinished rather than "
                 "assumed to pass - the 51 unrun mutations had all been "
                 "killed in earlier releases, which is a reason to expect "
                 "they still would be and not a reason to write that they "
                 "were.",
    ),
    Revision(
        version="3.97.0",
        observed="Three challenges, all built from one starting design.",
        suspected="A set that always hands over the same design teaches one "
                  "lesson however many times it is played.",
        changed="Seventeen challenges across six applications and five "
                "starting designs, including three that start from a design "
                "somebody has already over-specified - too much engine, too "
                "much memory - where the move that helps is REMOVING "
                "something.",
        evidence="Every target was DERIVED, not chosen. For each application "
                 "the whole option space was evaluated, the deployable "
                 "designs collected, and the thresholds placed so the design "
                 "handed over meets one or two of three while between 0.7% "
                 "and 6% of deployable designs meet all three. A bar picked "
                 "by hand is a bar picked to feel right, and the two are not "
                 "the same thing.",
        affected="Challenge Mode. No engine value changed.",
    ),
    Revision(
        version="3.97.0",
        observed="With seventeen practice challenges the final exam was no "
                 "longer the hardest thing in the set - 2.2% passed it "
                 "against a practice median of 2.1%.",
        suspected="A final that is easier than the practice is not a final.",
        changed="The exam's latency target tightened from 5.0 to 4.5 ms, "
                "putting it at 1.1%. The check compares it against the MEDIAN "
                "rather than the single hardest practice challenge, which was "
                "too strict once some of the practice set became "
                "deliberately very tight.",
        evidence="Caught by a check that existed before the set grew, which "
                 "is the argument for writing the property down rather than "
                 "the number.",
        affected="One target and one check.",
    ),
    Revision(
        version="3.96.0",
        observed="The limit table showed what was possible and what was "
                 "reached, and left the difference for the reader to "
                 "subtract.",
        suspected="That difference is the most interesting number on the "
                  "page. It is the RESEARCH value of a station: what the "
                  "physics allows and nothing on the market delivers.",
        changed="A gap column, and achievability as the share of the limit "
                "real parts collect.",
        evidence="On an inspection design the host has a 41.5% gap - the "
                 "physics allows something nobody has built - while the "
                 "preprocessing path reaches 87% of its limit and has 9.5% "
                 "left. A student reads the first as 'there is work to do "
                 "here' and the second as 'the available parts have nearly "
                 "finished'. That is a different question from where the "
                 "money should go, and both are now on one table.",
        affected="The limit table. No engine value changed. A lever with no "
                 "limit has no gap either - a gap from an invented limit "
                 "would be invented too.",
    ),
    Revision(
        version="3.96.0",
        observed="One line - 'this tool cannot decide the exchange rate' - "
                 "was doing more work than the rest of the verdict.",
        suspected="It is the whole philosophy, and it appeared once, in one "
                  "branch of one screen.",
        changed="Every verdict now ends by handing the decision back: what "
                "the tool measured, then what it does not know - what the "
                "latency is worth, what the schedule allows, what a "
                "competitor is shipping, what the customer will pay - and "
                "then that the facts are the tool's and the decision is the "
                "designer's.",
        evidence="A student who watches a program produce a verdict learns "
                 "that programs produce verdicts, and the ones they will use "
                 "later do exactly that: confidently, and without any of the "
                 "four things above.",
        affected="Presentation across the explanation and review screens.",
    ),
    Revision(
        version="3.96.0",
        observed="Interactive what-if was the last item on the list and the "
                 "one a console makes awkward.",
        suspected="A slider is a way of asking 'and if it were a bit more?' "
                  "without paying for the question. The console equivalent is "
                  "a loop, and the property that matters is not the widget - "
                  "it is that the baseline is never lost.",
        changed="A what-if loop over seven knobs. Every screen shows start, "
                "now and the distance between them; there is always a way "
                "back to the starting design; and an explanation of the "
                "accumulated changes is one keystroke away.",
        evidence="A student who can undo a change explores. One who cannot "
                 "commits early and defends. A mutation that compares against "
                 "the last change rather than the start is caught, because "
                 "that is exactly the version that would let someone drift "
                 "and not notice.",
        affected="One new screen, reachable from Education and Research. No "
                 "engine value changed.",
    ),
    Revision(
        version="3.95.0",
        observed="The upper bound was reported alone. A bound on its own "
                 "teaches half the lesson.",
        suspected="'The accelerator can give back at most 14.9%' is the "
                  "limit; 'and the best engine in the library gives 0.0%' is "
                  "the reality, and the gap between them is where engineering "
                  "lives.",
        changed="Each lever now shows the limit, the best any real part "
                "reaches, and what fraction of the limit that is. The two are "
                "computed differently and labelled so: the bound is "
                "arithmetic and cannot be beaten or reached; the measured "
                "figure is a search and could be beaten tomorrow by a part "
                "nobody has made.",
        evidence="On an inspection design the accelerator's limit is 26.5% "
                 "and no engine in the library delivers ANY improvement - the "
                 "thing a student most wants to upgrade returns nothing. "
                 "Moving the preprocessing reaches 87% of its limit. A check "
                 "requires that no measured gain ever exceed its bound, "
                 "because a bound something beats is not a bound.",
        affected="The explanation and review screens. No engine value "
                 "changed.",
    ),
    Revision(
        version="3.95.0",
        observed="Memory has no bound in this table, and it would have been "
                 "easy to give it one.",
        suspected="Memory is not a station in the latency decomposition - its "
                  "time sits inside the accelerator's core figure as "
                  "data-wait. There is no 'if memory took no time' row to "
                  "compute.",
        changed="Memory is listed with its measured best and NO limit, and "
                "the report says why. A mutation that gives it an invented "
                "bound is caught.",
        evidence="A limit that was invented would be worth nothing, and the "
                 "entire value of a limit is that it was not. The measured "
                 "figure is still shown, because that part is real.",
        affected="One table row and its explanation. No engine value "
                 "changed.",
    ),
    Revision(
        version="3.95.0",
        observed="A student without a sense of what a chip costs cannot weigh "
                 "14% against ninety-four dollars.",
        suspected="A rate makes the comparison arithmetic instead of "
                  "intuition.",
        changed="Latency gain per dollar, for every proposal that helps.",
        evidence="Moving the preprocessing returns 244% per dollar; HBM "
                 "returns 0.15%. The best rate is sixteen hundred times the "
                 "worst, and both are improvements - which is the point. They "
                 "are not comparable purchases, and the report says so.",
        affected="The review screen only - no engine value changed. The rate "
                 "is divided out of figures already computed.",
    ),
    Revision(
        version="3.95.0",
        observed="Confidence was shown as a star rating out of five.",
        suspected="A five-star grade reads like a review of a restaurant, and "
                  "invites comparison with things that have nothing to do "
                  "with this.",
        changed="A count: 54 of 54 runs held the direction, across six "
                "assumptions. The verdict wording changed with it - a change "
                "that costs money is headed NO FREE IMPROVEMENT and reports "
                "the gain, the cost, the rate, and that the decision is an "
                "engineering trade-off this tool cannot make, because it does "
                "not know what the latency is worth to the customer.",
        evidence="A tool that priced a millisecond would be inventing a "
                 "market.",
        affected="Presentation only - no computed value changed. What changed "
                 "is that a grade now reports what was run rather than how "
                 "confident it feels.",
    ),
    Revision(
        version="3.94.0",
        observed="'Upgrade the host' is advice, and advice is the weakest "
                 "thing a tool can offer.",
        suspected="A LIMIT is stronger: the host owns 84.7% of one job, so "
                  "everything else together cannot save more than 15.3%, "
                  "however fast or expensive it is. That survives every "
                  "choice of part, every price and every generation, because "
                  "it follows from where the time is rather than from what is "
                  "for sale.",
        changed="Headroom: for each station, what one job would take if that "
                "station took no time at all. It is Amdahl's argument applied "
                "to one job, and it is EXACT here because the decomposition "
                "is exact - a station's share is the most removing it "
                "entirely could return.",
        evidence="Checked as an identity rather than a formula: removing a "
                 "station must leave exactly the rest, to the last digit. And "
                 "checked against reality - no engine in the library beats "
                 "the infinitely-fast-engine bound, and most are WORSE than "
                 "the design they replace, because a bigger engine also costs "
                 "host time. A bound something beats is not a bound.",
        affected="The explanation screen and a new review screen. No engine "
                 "value changed - the bound is read from figures the model "
                 "already produced.",
    ),
    Revision(
        version="3.94.0",
        observed="An expected benefit is easy to work out from a share and "
                 "wrong to.",
        suspected="A figure derived from a percentage is a guess dressed as a "
                  "measurement, and it is the kind that reads as authoritative.",
        changed="Every proposal is BUILT and evaluated. The number quoted is "
                "the number that design produces, and a test compares each "
                "quoted figure against a fresh evaluation.",
        evidence="On an inspection design the comparison is decisive: moving "
                 "the preprocessing off the host gives 64.1% for 26 cents, "
                 "while the faster memory gives 14.4% for 94 dollars and a "
                 "second engine makes it 24.9% worse. None of those is "
                 "guessable from a share.",
        affected="The review screen. No engine value changed.",
    ),
    Revision(
        version="3.94.0",
        observed="Confidence was graded by how large the change was, which "
                 "is a proxy.",
        suspected="A student told ROBUST deserves to know what was tried.",
        changed="Six assumptions are moved across their ranges and the "
                "DIRECTION of the conclusion is checked at every point. The "
                "grade names the number of runs, the number of reversals, and "
                "which assumption caused them.",
        evidence="Fifty-four runs across six assumptions. The dual-engine "
                 "conclusion reverses in none of them, which is what makes it "
                 "a finding about the design. On a 320x240 frame the offload "
                 "conclusion reverses in seven, caused by the offload "
                 "dispatch cost - so it is graded CONDITIONAL and the "
                 "assumption is named. A grade that has only ever been ROBUST "
                 "is a grade nobody has seen work, so the test drives the "
                 "case that reverses.",
        affected="The explanation and review screens. No engine value "
                 "changed; the coefficients are restored after every sweep.",
    ),
    Revision(
        version="3.94.0",
        observed="'Ready' on its own is as vague as the adjectives removed at "
                 "3.93.0.",
        suspected="It reads as a judgement about speed.",
        changed="Deployment status carries its reason: either every "
                "constraint is satisfied, named, or which one is not - with "
                "the note that 'not ready' means a requirement is unmet, not "
                "that the design is slow. A quick design that fails a cooling "
                "class is still not a product.",
        evidence="The review also refuses to call a change that costs money "
                 "an improvement: 14.4% of latency for 94 dollars is a trade, "
                 "and somebody has to decide the exchange rate.",
        affected="Presentation only - no computed value changed. What changed "
                 "is that a one-word verdict now carries the reason it "
                 "rests on.",
    ),
    Revision(
        version="3.93.0",
        observed="The Studio printed words like SLOWER, BETTER and SHIPS as "
                 "whole verdicts.",
        suspected="'SLOWER' names a direction and nothing else. Slower at "
                  "what - one job, the frame rate, the response to a sensor? "
                  "By a millisecond or by a factor of three? Because the "
                  "arithmetic grew, or because two engines queue for one "
                  "memory? Five facts hide behind one word, and the word is "
                  "the part a student remembers.",
        changed="A decision module with a fixed order: what changed with the "
                "named metric and both figures, why with a breakdown, how "
                "sure, and only then what to do. The conclusion is last "
                "because a verdict printed first is one the reader accepts "
                "before seeing its reason.",
        evidence="Each measure is named individually and none is summarised "
                 "as 'performance': single-job latency, pipeline capacity and "
                 "delivered throughput are three questions and a change can "
                 "move one and not the others. The demo column headed 'ships' "
                 "became 'deploy' and now explains itself - it is whether the "
                 "design meets EVERY requirement, not whether it is quick.",
        affected="Presentation across demos, lessons and a new explain "
                 "screen. No engine value changed.",
    ),
    Revision(
        version="3.93.0",
        observed="A reason breakdown has to add up or it is a story about a "
                 "number rather than an account of it.",
        suspected="Nothing - the identity had to be found before it could be "
                  "used.",
        changed="Latency is decomposed into host active, exposed "
                "preprocessing, offload overhead, accelerator core and engine "
                "hand-off. The identity was verified across 180 "
                "configurations spanning every application, engine, "
                "preprocessing mode and single or dual accelerator: residue "
                "zero to the last digit the model carries.",
        evidence="The residue is printed rather than hidden when it is not "
                 "zero, and labelled a defect rather than a rounding. A "
                 "breakdown that silently absorbs a millisecond looks "
                 "complete, which is exactly the danger. That branch had "
                 "never run, so a test now hands it a deliberately broken "
                 "pair - the seventh detector in this project found never to "
                 "have fired.",
        affected="Verification and the explanation screen.",
    ),
    Revision(
        version="3.93.0",
        observed="Easy mode reported 'better' and 'worse'.",
        suspected="Those are the banned words with a friendlier face. A "
                  "direction without a size is half a fact, and easy mode was "
                  "meant to drop the absolute figures, not the meaning.",
        changed="Easy mode shows the change as a percentage against the row "
                "above: -45%, +59%. No adjective, and a student who cannot "
                "yet read a latency in milliseconds can still read a change "
                "of minus forty-five per cent.",
        evidence="A recommendation engine was added on the same principle: "
                 "the upgrade ranking is the share of one job's latency each "
                 "station holds, not an opinion. A station that is 0.4% of "
                 "the time cannot give back more than 0.4%, however much is "
                 "spent on it, and the report says so.",
        affected="Easy mode rendering, and a markdown report that carries the "
                 "same four sections to a file.",
    ),
    Revision(
        version="3.92.0",
        observed="Ten lessons with predictions, and no way for a student to "
                 "know how far through they were, whether they were "
                 "improving, or where to resume after stopping.",
        suspected="A course is not a list of lessons. Everything that varies "
                  "by student - progress, hints taken, difficulty, what has "
                  "been completed - was missing, and a lesson cannot hold it "
                  "without becoming a different lesson for different people.",
        changed="A separate progress module: a bar, first-guess accuracy, an "
                "improvement figure, three difficulties, hints, save and "
                "resume, a certificate, instructor settings, a per-lesson "
                "takeaway, and a final design challenge.",
        evidence="Keeping state out of the lessons means a lesson cannot "
                 "quietly become easier because someone got it wrong, which "
                 "would defeat the exercise.",
        affected="Education Mode. No engine value changed.",
    ),
    Revision(
        version="3.92.0",
        observed="A score is the easiest thing to get wrong in a course.",
        suspected="Prediction accuracy is not a mark. A student who gets "
                  "everything right first time learnt nothing here - they "
                  "already knew it. One who gets the first half wrong and the "
                  "second half right has done exactly what the course is "
                  "for.",
        changed="Two figures kept apart and never averaged: first-guess "
                "accuracy, and the change from the first half of the course "
                "to the second. Only FIRST attempts count, because scoring "
                "later ones would mark persistence as ignorance. An "
                "improvement is not reported at all until at least two "
                "lessons have been answered in each half - a single answer "
                "either side is a coin.",
        evidence="Mutations that let a later attempt overwrite the first "
                 "guess, or report a trend from one answer each side, are "
                 "both caught.",
        affected="Scoring only - no engine value changed. What changed is "
                 "that two questions are answered separately instead of "
                 "averaged into one that answers neither.",
    ),
    Revision(
        version="3.92.0",
        observed="The specification asks for 'most students answered 71% ...' "
                 "so a student can see their misconception is common.",
        suspected="That requires having asked those students something. This "
                  "copy has no cohort data.",
        changed="The distribution shown is of answers recorded ON THIS "
                "MACHINE, labelled as such, and empty until somebody answers. "
                "No percentage is shown when there is nothing to divide.",
        evidence="A made-up percentage would be a lie told in the one place "
                 "a student has no way to check it. The feature is worth "
                 "having when there is real data behind it, and the shape is "
                 "ready for that.",
        affected="Presentation. The certificate carries the same limit: it "
                 "records what was done in this copy and states that it is "
                 "not an assessment by anyone.",
    ),
    Revision(
        version="3.92.0",
        observed="Easy mode showed directions instead of figures, and marked "
                 "the large engine 'better'.",
        suspected="It compared every row to the FIRST one. True, and the "
                  "opposite of what the lesson says - the point is that the "
                  "large engine is worse than the MEDIUM one.",
        changed="Each row is compared to the one above it.",
        evidence="Caught by driving the renderer and reading the row, not by "
                 "reading the source. A check on the order of calls in a file "
                 "does not notice a branch that has been disabled - which is "
                 "also how the hint loop was found to need a behavioural "
                 "test.",
        affected="Easy mode rendering and two verification checks.",
    ),
    Revision(
        version="3.91.0",
        observed="The lessons showed a result and explained it. A student "
                 "reading a result agrees with it.",
        suspected="Agreement is not learning. The moment where anything is "
                  "learnt is being WRONG, and a lesson that never lets a "
                  "student be wrong has removed it.",
        changed="Every lesson asks a multiple-choice question BEFORE the "
                "numbers appear, marks the answer, and explains each wrong "
                "option separately. Telling someone they are wrong without "
                "saying what is true teaches nothing.",
        evidence="This is the same principle the validation work already "
                 "uses: predictions are written down, hashed, and never "
                 "edited when they turn out wrong. What is right for checking "
                 "a model is right for teaching one.",
        affected="All nine lessons. No engine value changed.",
    ),
    Revision(
        version="3.91.0",
        observed="Five lessons and a challenge is not a course.",
        suspected="A course needs a beginning that explains what is being "
                  "traded before anything is traded, and an end that asks for "
                  "all of it at once.",
        changed="Four more lessons - what is being traded, serving a language "
                "model, what performance costs, and heat - and a COURSE order "
                "distinct from the numbering. Renumbering the originals would "
                "have broken every reference to them in this log, and a log "
                "rewritten whenever a menu is reordered is a log nobody "
                "trusts.",
        evidence="The lesson on heat needed a fix the moment it ran: power "
                 "density printed to two decimal places reads 0.00, 0.01, "
                 "0.04, and a lesson claiming a thirteen-fold difference was "
                 "contradicted by its own table. Each metric now gets the "
                 "precision its magnitude needs - 0.0031 against 0.0396.",
        affected="Four new lessons and the table formatting. Every new claim "
                 "is a check.",
    ),
    Revision(
        version="3.91.0",
        observed="Five demos is thin for a lecture, and Validation Mode "
                 "offered four thousand checks with no way in.",
        suspected="Four thousand is a number that sounds like an answer to "
                  "'why should I believe this' and is not one. A student "
                  "cannot read four thousand messages and should not have to.",
        changed="Eleven demos, and a one-screen validation summary that reads "
                "each suite's presence at run time rather than quoting a "
                "stored figure - so a suite that stops running shows as "
                "absent rather than as its last known number. The summary "
                "ends with what is NOT established.",
        evidence="A tool that lists only what it has done is an "
                 "advertisement. The summary names the three things this "
                 "cannot establish about itself and why.",
        affected="Demo and Validation modes.",
    ),
    Revision(
        version="3.91.0",
        observed="A researcher on their fourth iteration cannot remember what "
                 "the second one was.",
        suspected="That is the whole problem, and solving more of it would be "
                  "building a project manager nobody asked for.",
        changed="A short capped history, saved designs, and CSV export. Only "
                "the CONFIGURATION is stored - never a computed figure.",
        evidence="A file of cached results goes stale the first time a "
                 "coefficient moves and nothing notices, so an export "
                 "recomputes. That also means an exported figure and a figure "
                 "on screen cannot disagree. A check reads the store and "
                 "fails if it contains a metric name at all.",
        affected="Research Mode. An unwritable folder is survived rather than "
                 "raised: the history is a convenience and the result already "
                 "happened.",
    ),
    Revision(
        version="3.91.0",
        observed="The five lessons were a demonstration: read the table, read "
                 "the explanation. A student who reads a correct explanation "
                 "feels like they have understood and usually has not.",
        suspected="Only a prediction that turns out wrong reliably changes a "
                  "mind. The order matters more than any of the parts.",
        changed="Ten lessons, each asking the student to commit to an answer "
                "BEFORE anything is shown - then one change, the result, and "
                "why every other answer was wrong. Each wrong option is "
                "explained individually: 'wrong' is useless feedback, and a "
                "student who picked it needs to see where their own reasoning "
                "broke rather than be handed a different one.",
        evidence="A check enforces the order in the source - the question is "
                 "asked before the table is printed and the verdict comes "
                 "after it. Each lesson must have exactly one correct answer "
                 "and at least three options, because a coin flip is not a "
                 "prediction, and every option must carry more than forty "
                 "characters of reasoning.",
        affected="Education Mode. No engine value changed - the lessons hold "
                 "no numbers at all and are checked not to.",
    ),
    Revision(
        version="3.91.0",
        observed="Four new demos were added and three collided with keys "
                 "already present.",
        suspected="A duplicate key does not raise. It silently overwrites in "
                  "the lookup, so one demo becomes unreachable and nothing "
                  "says so - which is how a menu quietly loses an entry "
                  "between releases.",
        changed="A uniqueness check, with a positive control that hands it a "
                "deliberate duplicate.",
        evidence="The three duplicates were removed and two genuinely new "
                 "demos added instead. Fourteen questions, every key "
                 "distinct, every stated answer checked against the numbers "
                 "it rests on.",
        affected="Demo Mode. Two of the new ones are worth naming: a 3 nm "
                 "part that is SLOWER than the 7 nm one on a compute-bound "
                 "design, and a second engine that loses on a narrow memory "
                 "and wins on a wide one - so the order the two upgrades are "
                 "tried in decides what a designer concludes about either.",
    ),
    Revision(
        version="3.91.0",
        observed="Validation Mode listed tools. Four thousand checks is not "
                 "something anyone reads.",
        suspected="A student cannot audit the suite and should not have to. "
                  "What they can read is which areas were checked, how, and "
                  "where the evidence stops.",
        changed="A one-screen summary: ten areas, the suite that covers each, "
                "the reproducibility grade actually recorded, and then the "
                "gaps.",
        evidence="It gives no percentage, and a check enforces that. A "
                 "developer who computes their own validation score has "
                 "produced another self-assessment; a reader can check a list "
                 "and cannot check a number. The section on what is still "
                 "missing is what makes the rest believable - a tool that "
                 "lists only what it can do is an advertisement.",
        affected="Validation Mode only - no computed value changed. What "
                 "changed is that the evidence can be read in one screen "
                 "instead of four thousand lines.",
    ),
    Revision(
        version="3.91.0",
        observed="The lessons showed a comparison and explained it. Nothing "
                 "asked the student anything.",
        suspected="A student who reads a result agrees with it. Agreement is "
                  "not learning - it costs nothing and changes nothing. Being "
                  "WRONG is the part that moves someone, and that requires "
                  "committing to an answer before the answer is visible.",
        changed="Ten lessons, each opening with a prediction taken before any "
                "number appears. Every option carries the reasoning that "
                "leads to it, so a student who chose wrongly sees where their "
                "own reasoning broke rather than being handed a different "
                "one. 'Wrong' on its own is useless feedback.",
        evidence="The course runs 1 to 10: what PPACT is, why the host still "
                 "matters, what makes an engine fast, the memory bottleneck, "
                 "the HBM myth, two engines, serving a language model, cost "
                 "against performance, heat, and a design challenge. The "
                 "one-change-per-step rule from 3.87.0 still holds across all "
                 "ten and is still enforced.",
        affected="Education Mode. No engine value changed.",
    ),
    Revision(
        version="3.91.0",
        observed="A fifteenth demo, on node economics, showed the header as "
                 "'LatencyLogic die cost'.",
        suspected="A metric name longer than its column runs into the one "
                  "before it. The table check measures LINE width and a "
                  "collision inside the line is not a width problem.",
        changed="Header names are truncated to fit their column.",
        evidence="The demo itself is worth having: logic die cost falls from "
                 "28 nm to 7 nm and RISES again at 3 nm, which is dearer and "
                 "slower on this design. A finer node shrinks the die and "
                 "raises the wafer price, and the two cross.",
        affected="Presentation. Fifteen demos now.",
    ),
    Revision(
        version="3.90.0",
        observed="Demo Mode pointed at ordinary tools, all of which ask "
                 "questions before showing anything.",
        suspected="An audience did not choose the parameters and cannot be "
                  "asked to. A demo that asks 'which application?' has "
                  "already lost the room.",
        changed="Five demos that take NO input: pick a question, the "
                "comparison runs, the answer follows in words with the "
                "mechanism behind it. A check refuses any input call in the "
                "module body.",
        evidence="Every question has the answer no - not out of "
                 "contrarianism, but because a demonstration that things work "
                 "teaches that things work, which the audience already "
                 "assumed. What they do not know is where the intuition "
                 "breaks, and that is the only part worth taking their time "
                 "for.",
        affected="Demo Mode. No engine value changed.",
    ),
    Revision(
        version="3.90.0",
        observed="Two demos stated answers their own tables contradicted. The "
                 "dual demo said two engines are slower and showed them 12% "
                 "faster; the engine demo said the large one reverses and "
                 "showed it fastest of three.",
        suspected="Both were built on a configuration where preprocessing "
                  "runs on the ISP rather than the host, which is not where "
                  "the claims hold. I copied a reference without checking "
                  "that the finding travelled with it.",
        changed="Both moved to the host-preprocessed configuration, and every "
                "stated answer is now a check: the large engine must be "
                "slower than the medium, two engines must be slower than one, "
                "two node generations must move the time under one per cent "
                "while the power falls, and the quick design must fail at "
                "least three requirements including one that is a class "
                "rather than a number.",
        evidence="A demo whose answer contradicts its own table is worse than "
                 "no demo, because the audience is watching the numbers. This "
                 "is the same failure the lessons were checked against at "
                 "3.87.0, and it recurred within three releases in a "
                 "different module - which is why the check is per-claim and "
                 "not per-module.",
        affected="Two demo configurations and their verification. No engine "
                 "value changed.",
    ),
    Revision(
        version="3.89.0",
        observed="Challenge Mode pointed at the open-ended innovation flow: "
                 "change what you like and get a score. There was no stated "
                 "bar and no population behind the number.",
        suspected="'You scored 78' tells a student nothing - out of what, "
                  "against whom, and was 90 even possible? A score with no "
                  "population behind it is a number chosen by whoever wrote "
                  "the marking scheme, and students optimise the scheme "
                  "rather than the design.",
        changed="Three challenges, each with a situation, stated targets and "
                "a reason for every target. The population is COMPUTED: every "
                "design reachable with the allowed choices is evaluated, so a "
                "rank is a position among designs that exist and meet the "
                "requirements.",
        evidence="Six of 288 possible designs pass the inspection challenge, "
                 "14 of 288 the drone, 17 of 288 the camera. A student told "
                 "they are third of six is being told something true, and can "
                 "ask which design is first and get an answer.",
        affected="Challenge Mode. No engine value changed.",
    ),
    Revision(
        version="3.89.0",
        observed="The obvious implementation ranks every design and puts the "
                 "failures at the bottom.",
        suspected="That teaches requirements are a scale. They are not: a "
                  "design that misses one is not ninetieth of a hundred, it "
                  "is not in the race.",
        changed="Only passing designs are ranked. A failing one is told which "
                "requirement it missed and how many designs in the allowed "
                "set do meet all of them - so the answer is 'not yet' rather "
                "than 'badly'.",
        evidence="A mutation that ranks against the feasible set instead of "
                 "the passing one survived the first version of the check, "
                 "because the 'out of' figure is read from the population "
                 "directly and would still have said six. It is caught now by "
                 "requiring that a rank lie inside its own population - a "
                 "design cannot be fortieth of six.",
        affected="Verification and the scoring.",
    ),
    Revision(
        version="3.89.0",
        observed="A ranking needs a weighting, and a weighting is a "
                 "judgement.",
        suspected="Burying it is how a marking scheme becomes the thing being "
                  "optimised.",
        changed="The rank is total margin with every requirement weighted the "
                "same, and the report says so on screen: a design barely "
                "inside all three ranks below one comfortably inside all "
                "three.",
        evidence="The tool also declines to award anything for elegance, "
                 "effort or explanation. It cannot judge those, and putting a "
                 "number on a guess is worse than leaving it to the "
                 "instructor - which the separate rubric already does.",
        affected="Presentation only - no computed value changed. What changed "
                 "is that the weighting is on screen rather than in the "
                 "source.",
    ),
    Revision(
        version="3.88.0",
        observed="The framework - fourteen categories, ninety-six items - "
                 "existed as a description. Nothing connected it to the code.",
        suspected="A framework written down is a list of promises, and a "
                  "document notices nothing when one stops being kept or was "
                  "never kept. The item stays on the list, a reader assumes it "
                  "works, and the first person to find out otherwise is a "
                  "student in a lecture.",
        changed="The map lives in code. Every entry names a metric the engine "
                "reports or a function that exists, and a check refuses one "
                "that names neither. Three states: implemented, partial with "
                "its limit stated, and absent with its reason stated.",
        evidence="Nine of my own entries pointed at nothing on the first run - "
                 "'Accelerator area (mm2)', 'Memory cost (USD)', "
                 "'ppact.game.sweep_designs'. All plausible, all invented. "
                 "This is the third time in this project a declaration has "
                 "named something absent, after a boundary contract and a "
                 "coefficient registry, and the third time the fix was to "
                 "require that a declaration point at something.",
        affected="Documentation and two menu entries. No engine value "
                 "changed. The tally is 79 implemented, 6 partial, 11 not.",
    ),
    Revision(
        version="3.88.0",
        observed="Absent items had 'not implemented' as their whole "
                 "explanation.",
        suspected="A gap without a reason reads as an oversight rather than a "
                  "decision, and a reader cannot tell which it is.",
        changed="Every absent entry states what is missing and why, and a "
                "check enforces it. So does every partial one: 'partial' "
                "without a stated boundary is a word, not a status.",
        evidence="The gaps stay on the list. Removing them would make the map "
                 "agree with the code by forgetting what was promised, which "
                 "is the opposite of useful - the gap is the most informative "
                 "line on the page. A model that says what it cannot express "
                 "is more useful than one that quietly guesses.",
        affected="Documentation and verification.",
    ),
    Revision(
        version="3.87.0",
        observed="Education Mode pointed at the same tools as everything "
                 "else. A student was offered a design builder and left to "
                 "discover the principles by changing things.",
        suspected="Discovery works when a comparison isolates one cause. "
                  "Change the host, the memory, a second engine and the "
                  "process node together, get a system four times quicker, "
                  "and what has been learnt is that changing four things "
                  "makes a system faster - which is not a design principle "
                  "and is not even true.",
        changed="Six lessons, each with the shape reference, one change, "
                "result, reason. The module REFUSES to define a step that "
                "changes more than one thing, counting a DECISION rather "
                "than a field: choosing HBM sets both the memory and the "
                "stack count, and that is one choice a person makes.",
        evidence="Each lesson exists because its answer is no. A bigger "
                 "engine is not always faster - 64x64 loses to 32x32 here "
                 "and the limit moves to the memory. A faster memory buys "
                 "under 25% for six times the price on a design that was not "
                 "waiting. Two engines are SLOWER than one when they share a "
                 "bus. A course that only demonstrates things working teaches "
                 "that things work.",
        affected="Presentation and Education Mode. No engine value changed - "
                 "the lessons hold no numbers at all, and are checked not to.",
    ),
    Revision(
        version="3.87.0",
        observed="The lesson checks caught two of my own errors on the first "
                 "run.",
        suspected="Both were the kind that read as fine and fail in front of "
                  "a student.",
        changed="The tables rendered 80 columns wide and wrapped; the column "
                "widths are narrower and a check refuses a lesson whose table "
                "would wrap. And the final challenge was already satisfied by "
                "the design it starts from - all three targets met before the "
                "student touches anything.",
        evidence="A challenge already passed is not a challenge, and one that "
                 "meets nothing is one a student abandons. The targets are "
                 "now set so the starting design meets exactly one of three, "
                 "and six configurations in the library satisfy all three. "
                 "Both bounds are checked, so a later change to the library "
                 "cannot quietly make the challenge trivial or impossible.",
        affected="Verification and the three challenge targets. No engine "
                 "value changed.",
    ),
    Revision(
        version="3.87.0",
        observed="A lesson whose reasoning no longer matches its numbers "
                 "would be worse than no lesson.",
        suspected="Nothing yet - but the lessons make claims about direction "
                  "that a library change could silently break. 'The power "
                  "falls too' stops being true the day a coefficient moves.",
        changed="Every teaching claim is a check: the engine must be three "
                "times faster than the host alone AND lower power; the large "
                "engine must be slower than the medium one; the memory "
                "upgrade must buy under 25% for over three times the cost; "
                "two engines must be slower; the capable host must be twice "
                "as fast and draw more power.",
        evidence="These are the sentences a student is asked to believe. If "
                 "the model stops producing them the lesson is wrong, and the "
                 "suite should say so rather than the student finding out.",
        affected="Verification only - no computed value changed. What changed "
                 "is that a lesson can no longer drift away from its own "
                 "numbers unnoticed.",
    ),
    Revision(
        version="3.86.0",
        observed="The menu had grown to seventeen entries named after what "
                 "they do: 'Compare HBM3E and HBM4 on an LLM workload', "
                 "'Sweep the whole design space'. Every one is a good name "
                 "for someone who already knows what HBM is.",
        suspected="A first screen that demands vocabulary before it offers "
                  "anything teaches nothing. A student who cannot read the "
                  "menu picks at random or stops, and neither outcome is "
                  "visible to the person who wrote it.",
        changed="A mode screen in front: Quick Start, Education, Challenge, "
                "Research, Demo, Validation. Six entries, one line each, no "
                "technical word on any of them. The old menu is intact and "
                "reachable inside Research, where the audience has the "
                "vocabulary.",
        evidence="The first question is not WHICH FEATURE but WHAT FOR. The "
                 "same engine serves a student on their first day, a student "
                 "handing in an assignment, a researcher sweeping parameters, "
                 "someone presenting, and someone checking the model - five "
                 "programs sharing one set of numbers.",
        affected="Presentation only. The mode layer calls no engine function "
                 "and is checked not to: a screen that computed would give a "
                 "student different numbers from a researcher and neither "
                 "would know.",
    ),
    Revision(
        version="3.86.0",
        observed="Four design rules for the first screen, none of them "
                 "enforceable by reading.",
        suspected="A rule nobody checks erodes one release at a time. The "
                  "first version of the length check measured the description "
                  "alone and let a line print at 84 characters, because the "
                  "number, the dot and the padded title were not counted.",
        changed="The rules are checks: forbidden vocabulary, the RENDERED "
                "line width, no parameter on the first screen, and no engine "
                "call from the mode layer. Research is required to be the "
                "widest mode, so new capability has somewhere to go that is "
                "not the front door.",
        evidence="Both detectors were then shown deliberately bad input - a "
                 "description containing HBM and one long enough to wrap - "
                 "because neither had ever fired on the real modes. That is "
                 "the fifth detector in this project found in that state, and "
                 "the pattern is now the first thing checked when one is "
                 "added.",
        affected="Verification. The rendered mode lines are 62 to 77 "
                 "characters.",
    ),
    Revision(
        version="3.85.0",
        observed="A third failed run on the same machine. The folder held "
                 "certify.py from 3.84.0 and ppact/ from 3.82.0, and the "
                 "failure surfaced as TypeError: print_evidence_status() takes "
                 "0 positional arguments but 1 was given.",
        suspected="Extracting a new archive over an existing folder leaves a "
                  "mixture - new scripts calling old code. Every symptom it "
                  "produces looks like a defect in the model: a missing "
                  "module, a wrong argument count, a stale result. The layout "
                  "check asked whether the files existed and never whether "
                  "they came from the same release.",
        changed="certify.py carries the release it belongs to and compares it "
                "against ppact/__init__.py BEFORE importing anything, by "
                "reading the file rather than importing it - since importing "
                "a mismatched package is the thing that goes wrong. On a "
                "mismatch it names both versions and says to extract into a "
                "new, empty folder.",
        evidence="Three consecutive failed attempts on a second machine, none "
                 "of them about the model. Each was a way the script assumed "
                 "a clean starting state: a fresh interpreter, then a complete "
                 "extraction, now a single-release folder. The tool intended "
                 "to establish reproducibility was itself the least "
                 "reproducible part of the release.",
        affected="certify.py only. No model behaviour changes.",
    ),
    Revision(
        version="3.84.0",
        observed="A notebook run showed the evidence list and SystemExit: 1, "
                 "with the verdict nowhere on screen. Separately, the evidence "
                 "list reported second-machine reproduction as PENDING even "
                 "after a second-machine run had succeeded.",
        suspected="Two presentation defects with the same root: the report was "
                  "written to be read top to bottom in full, and nobody reads "
                  "that way. The verdict was printed before a forty-line "
                  "evidence list, so it scrolled away and the reader was left "
                  "interpreting an exit code. And the evidence list was "
                  "hardcoded, so it stated a claim about the world rather than "
                  "recording what had happened to it.",
        changed="The verdict is printed last, after the evidence list, with "
                "the level named in words. certify.py appends every run - "
                "reproduced or failed - to reproducibility/runs.csv, and the "
                "evidence list reads that file; a PENDING item can be cleared "
                "only by a recorded run, never by editing the list.",
        evidence="During this change the version was bumped without "
                 "regenerating the evidence package. The tool reported SOURCE "
                 "DIFFERENCE and refused to certify, which is what it is for; "
                 "the author was the one caught.",
        affected="Report presentation and the evidence list. No coefficient, "
                 "scenario, or numeric result changes.",
    ),
    Revision(
        version="3.83.0",
        observed="A run on Windows with Python 3.13 matched every substantive "
                 "check - source digest, coefficient digest, seed, "
                 "categorical results, numeric values, package hash - and the "
                 "report said NOT REPRODUCED.",
        suspected="The classifier counted an environment difference as a "
                  "failure. That is backwards: on a second machine the "
                  "environment is SUPPOSED to differ, and it is the condition "
                  "under which a reproduction is worth having. The same "
                  "numbers on a different operating system say something the "
                  "same numbers on the same machine cannot.",
        changed="Environment differences are reported separately and do not "
                "decide whether a run reproduced. The grade is COMPUTED from "
                "them instead: same platform R2, different machine or "
                "interpreter R3, different operating system R4.",
        evidence="Found by running it, not by reasoning about it. Every "
                 "internal check passed on the machine that wrote the code, "
                 "and the first run elsewhere found the defect in the first "
                 "minute - which is the argument for a second machine and not "
                 "for more tests.",
        affected="The reproducibility report and grading. No computed model "
                 "value changed. A substantive difference still grades R0 "
                 "whatever the platform: a different operating system does "
                 "not excuse a different answer.",
        independent=True),
]


def print_revisions() -> None:
    line = "=" * 78
    print(line)
    print(" MODEL REVISION LOG")
    print(line)
    print("  Parameters that moved, and what moved them. A change made only")
    print("  because a result was inconvenient is fitting the model to the")
    print("  answer, so the reason is recorded at the time rather than")
    print("  reconstructed later.\n")
    for r in REVISIONS:
        flag = "" if r.independent else "   [NO INDEPENDENT EVIDENCE]"
        print(f"  {r.version}{flag}")
        print(f"    observed  : {r.observed}")
        print(f"    suspected : {r.suspected}")
        print(f"    changed   : {r.changed}")
        print(f"    evidence  : {r.evidence}")
        print(f"    affected  : {r.affected}\n")
