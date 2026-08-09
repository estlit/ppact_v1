# Deferred to v1.1 and beyond

Work that is understood, wanted, and deliberately NOT in v1.0.

The list exists because a deferral nobody wrote down is indistinguishable
from an oversight, and because the reason for deferring is usually more
useful than the item itself.

## Structural — changes the analytical model

These add a term to the timing decomposition, which is verified to zero
residue across 180 configurations. Adding a term means re-verifying all of
it, and shipping that alongside a library change would make the first
failure impossible to attribute.

| Item | Why it is not in v1.0 |
|---|---|
| Host interconnect | A card on PCIe or a stick on USB is a separate die from its host. The link has no term in the model, so it cannot become the bottleneck. `host_connection` is already declared and informational for this reason. |
| Deployment models | Standalone SoC, host-attached, module, appliance, multi-card, rack. Seven of eight declared deployment classes are not expressible. Follows the interconnect term. |
| Chiplet and multi-die | Changes the timing and the cost model together: per-die yield, assembly, die-to-die links. |
| Rack scale | A design here is one device. A rack is eight accelerators, a host, a chassis budget and a rack budget, and none of the four is expressible. |
| Structured sparsity | Work becomes data-dependent. The model is deterministic; that is a different kind of model, not a coefficient. |
| Multi-partition execution | Needs a notion of isolation the model does not have. |
| Mixed precision within one engine | Precision is a property of the engine, fixed at design time. One part running seven formats at different rates is not expressible. |

## Presentation

| Item | Why it is not in v1.0 |
|---|---|
| Balance chart normalization | The log scale compresses a 6x cost increase into about 24 points, which is a real educational weakness. Changing the formula while the chart's ROLE was being moved would make it impossible to attribute what a reader is seeing. One change at a time. |
| Pareto front | Not implemented. Recorded in the capability map. |
| Heat map | A two-parameter sweep is printed as rows rather than shaded. |
| Timeline view | The runtime reports station busy time as numbers, not drawn. |

## Library

| Item | Why it is not in v1.0 |
|---|---|
| Training-domain class | The registry reports the domain as empty rather than filling it with an inference class wearing a different label. |
| Cloud inference and training separated | One entry serves both. They are different classes in industry. |
| Host cache hierarchy, big.LITTLE, DVFS | The host is modelled as cycles and bytes. |
| Security block area and power | Named by every industrial profile reviewed and absent from the model. |
| Safety grade cost and area | An application can require automotive grade; grades are not distinguished. |

## Validation

| Item | Why it is not in v1.0 |
|---|---|
| Educational effectiveness | Needs students, a control, and the same people with and without the tool. See `EDUCATIONAL_VALIDATION.md`. It is a protocol, not a result. |
| Independent external holdout | Needs a predictor who does not run the engine. |
| Measured hardware comparison | Needs measured hardware. No amount of internal work raises this. |
| Second-machine reproduction at this release | R4 evidence exists for engine 3.82.0. Reproduction certifies the release that was run, so this release carries its own grade until somebody runs it elsewhere. |

## Framework extraction

Four things built for PPACT Studio are not specific to it:

| Component | What it governs |
|---|---|
| Question Registry | every user-facing prompt: wording, options, defaults, help, refusal |
| Terminology Registry | one concept, one name, one definition, and why the aliases are wrong |
| Language and Philosophy Audit | that the wording and the philosophy do not drift back |
| Validation Framework | the three layers, mutation testing, the evidence package |

They belong to a shared framework, and a second Studio product would want
them unchanged.

**Not extracted in v1.0**, and the reason is not effort. Extraction means
choosing an interface, and an interface chosen against ONE product is an
interface shaped like that product. The registries have been used by one
program for one release; a second product will find the joints, and moving
them before it does would be guessing where the joints are.

What has been done instead is to keep them separable, and the claim is
checked rather than asserted: neither registry imports the engine at module
level. The terminology registry touches it nowhere at all. The question
registry reaches it in eight places, all inside option builders — the points
where a prompt has to know what the library contains — which is the seam a
second product would replace. Extraction should therefore be a move plus
eight builders, not a rewrite.

## Unified launcher and Streamlit

Deferred to RC4, as a new feature rather than a fix.

```
python run_ppact.py
        |
   runtime detection
        |
Terminal   Jupyter   Colab   Streamlit
```

RC3 includes `run_jupyter.py` and `run_colab.py`. There is no runtime
detection and no Streamlit path.

It is deferred rather than attempted because RC3 is a release that freezes
what has been verified, and a launcher written now would be released on the
same day it was written. What RC4 has to demonstrate is not that the code
exists but that three runtimes produce the same figures from the same
ReviewAnalysis, that Streamlit reruns do not duplicate figures, and that
no file outside the launcher changes digest.

## Host memory demand model, then memory arbitration

Deferred because the order was wrong, not because the work is large.

    Host demand model  ->  memory arbitration

The arbitration rule was going to be replaced first. It cannot be: the
input it arbitrates on is derived from the compute time it is supposed to
influence, so any rule built on it is circular. See MEM-ARB-000 in
METHODOLOGY.

What RC4 has to produce is a host memory demand defined the same way the
accelerator's is - a rate the host would draw if nothing stopped it - and
only then a sharing rule. Two attempts at the arbitration alone have
already failed in opposite directions, and this was the third.

## MEM-ARB-001: host memory demand and arbitration

```
old policy    accelerator-priority residual allocation
problem       3.2% aggregate over-demand cuts host bandwidth by 50%
observed      a faster accelerator makes the design 59% slower
attempted     demand-proportional fair sharing
reverted      its input is not a demand
blocked on    a host memory demand model
```

The order was wrong. Arbitration was to be fixed first; the investigation
showed the quantity being arbitrated has to be defined first, because
`host_demand` today is back-computed from compute time. Two agents' demands
must mean the same physical thing before they can be divided fairly.

Affected once fixed: latency, throughput, host transfer time, deployment
margins, bottleneck diagnosis, and every sensitivity figure.

## CO-BOUNDARY-001: logic die cost declares a block it does not include

```
declared    accelerator, secondary accelerator, host cpu, ISP
computed    accelerator, secondary accelerator, host cpu
difference  0.2489 USD on industrial_vision / npu_32x32 / LPDDR5 x2
```

The boundary declaration for `Logic die cost` lists `isp` among its
includes; the expression does not add it. Whether the declaration or the
expression carries the intent is not recoverable from either, so neither is
changed.

Found by trying to recover the component costs from the libraries: the
recovered sum was 1.1996 against the engine's 0.9507, and the gap is
exactly the ISP.

`System cost` is unaffected - it adds the ISP term directly - so the Cost
track is built on it rather than on the logic die subtotal.

## WF-WIDTH-001: eighteen tasks print past the column limit

```
task_memory        218 chars    three memory technologies as columns
task_designs       253 chars
task_rubric        185 chars
task_sweep         114 chars
15 others           80-103 chars
```

Eighteen of thirty menu tasks emit at least one line wider than 78
columns. The column rule exists so a terminal shows a line whole; past
about 80 the line wraps and a table becomes unreadable rather than merely
untidy.

**Found by the workflow suite, which measures every task.** The contract
suite checked the column limit on `task_system_flow` alone, so the other
twenty-nine were never measured - the rule was enforced on one screen and
described as a rule for all of them.

Two different problems sit under one number:

```
80-114 chars    a line or two past the limit; a wrap, not a break
185-253 chars   a comparison table with one column per option, which
                wraps into nonsense
```

The wide tables need transposing - options as rows rather than columns -
and that is a renderer change per task rather than a formatting fix.

**Not fixed here.** Eighteen tasks touched at once could not be checked
individually, and a batch edit across screens nobody re-read is how the
wrong thing gets fixed quietly.

## DEP-PY-001: the hosted Python version is not observed

```
verified      Python 3.12.3, Linux x86_64
pinned        runtime.txt -> python-3.12
not observed  any hosted environment
```

The three deployment libraries are pinned and the combination has been
run here. What has not been run is a hosted build: Streamlit Community
Cloud resolves its own interpreter, and whether `numpy==2.4.4` and
`matplotlib==3.10.8` install against it is the one thing about a
deployment nobody in this project has watched.

`runtime.txt` pins the major-minor line to the one that was verified.
That does not establish that the build succeeds; it establishes that a
failure is a version conflict printed at install time rather than a
silent substitution.

**Not resolvable here.** This container is not a hosted environment, and
running the app locally proves the packages work locally. The evidence
that closes this is a build log from a deployment.

## UX-BLIND-001: no reader outside this project has been observed

```
Instrument verification     PASS
Study protocol              FROZEN candidate at 1.0
Freeze record               NOT YET SIGNED
Pilot infrastructure        READY
Pilot results               NOT ESTABLISHED
Main-study results          NOT ESTABLISHED
Human effectiveness claim   NOT ESTABLISHED
```

The claim this tool makes for itself is that the System Flow and
Bottleneck Map helps an engineer reach a correct design judgement. Every
check written so far establishes that the screen says what the engine
computed, which is a different thing: a screen can be faithful and still
be misread.

The instrument to test it exists - eight stimulus cases each verified to
produce the condition it claims, three arms differing in one treatment
each, timing from render-complete, and a scorer that raises rather than
returning zeros for an empty study. What does not exist is a
participant.

**Not resolvable here.** This needs people, and recruiting them is
outside what this container can do. The protocol is
`RC4_USER_VALIDATION.md`; the evidence that closes this is a set of
sessions under `study/main/`.

Until then, no claim about what a reader understands from this interface
is supported. `tests_streamlit` passing is not a finding about people.

## PERF-SEM-001: what "Performance" means on the benchmark chart

```
Demo 002, small accelerator -> large accelerator

  Pipeline capacity    106.34 -> 59.76    down
  Single-job rate       48.10 -> 54.58    up
```

The benchmark spider - the one drawn after the constraint gate, on the
designs that passed it - scores `Performance` from the single-job rate,
which is one over the latency. The other axes on that chart read
absolute quantities: total silicon across every die, the whole bill of
materials. Nothing there is measured against a requirement.

Delivered throughput cannot be the axis: the chart plots survivors, a
survivor has met its target by definition, and the delivered figure is
capped at that target. Three different designs read 60.00, 60.00,
60.00.

That leaves two, and they disagree. A larger accelerator can shorten
one job while lowering the rate the pipeline sustains, so the chart
concludes the opposite thing depending on which is chosen. This is not
a rename and not a defect: it is a decision about whether the benchmark
answers "how quickly does this machine finish one job" or "how much
work can this machine sustain".

The anchor's own rationale says `Throughput on the selected
application, not peak TOPS`, which rules out the headline number and
does not choose between these two. That sentence needs settling with
the metric.

**Open.** `_AXIS_METRIC["Performance"]` now names the canonical key for
the value it already used; the value did not change and the baseline
holds. What it should name is unresolved.

## P2-L1: the legacy throughput alias is still read in nine modules

`system.py` keeps `"Throughput (inf/s)"` as an alias for the single-job
rate and says so:

> retained as an alias for the single-job rate so that older callers
> keep working, but nothing new should read it

`_AXIS_METRIC` stopped reading it. These still do:

```
interpret.py     runtime.py       crossval.py
migration.py     gold.py          industry.py
game.py          memory_sweep.py  innovation.py
```

**No global replace.** Each site has to be read for what it meant to
ask for, because the alias and the canonical key hold the same number
today and a blind substitution would look correct while changing what a
later caller believes it requested. Per site:

```
VALID LEGACY COMPATIBILITY
SHOULD USE SINGLE-JOB RATE
SHOULD USE PIPELINE CAPACITY
SHOULD USE DELIVERED THROUGHPUT
AMBIGUOUS
```

Lower priority than PERF-SEM-001: this one is about which name the code
asks for, and that one is about which figure the chart should show.

## Not planned

| Item | Why |
|---|---|
| A catalogue of commercial products | The Studio models architectural design spaces. Products validate the library and never become entries in it. |
| A single "library quality" score | It would let a gap in one domain be paid for by an entry in another, and they are not exchangeable. |
| Coverage percentages | A percentage needs a denominator, and the denominator implied by "industrial coverage" is the whole industry. Counts are reported instead. |
