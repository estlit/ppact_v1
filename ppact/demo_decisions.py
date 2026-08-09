"""ppact.demo_decisions - the choice behind each demo, and what follows

A demo that changes two configuration fields has not necessarily changed
two things. Choosing HBM3E over LPDDR5 changes the package count too,
because one stack replaces two packages - the designer picked a memory,
not a package count.

    Engineering decision  ->  Derived configuration  ->  Measured result

Counting changed fields would call eight of the fifteen demos
multi-variable and put a disclaimer on designs that made one choice. What
matters is whether the CONCLUSION can be attributed to a decision, and
that needs the decision named.

Editorial, not computed. Nothing in the demo data distinguishes a chosen
field from one that came with it: `memory` and `memory_devices` simply
differ. One entry per demo, written where it can be argued with.

"""
DECISIONS = {
    "memory": dict(
        decision="Change the memory technology",
        derived=["memory_devices"],
        why="One HBM3E stack replaces two LPDDR5 packages. Package count "
             "follows from the technology; a designer picks the memory, "
             "not the package count independently."),
    "engine": dict(
        decision="Change the accelerator class", derived=[],
        why="A single choice with no derived configuration."),
    "dual": dict(
        decision="Add a second accelerator",
        derived=["execution_mode"],
        why="Two engines only run in parallel. Sequential execution of a "
             "pair would be a different design, not this one."),
    "node": dict(
        decision="Change the process node",
        derived=["accel_node"],
        why="A node choice applies to the whole SoC. Fabricating the CPU "
             "and accelerator on different nodes is a separate decision "
             "this demonstration does not make."),
    "order": dict(
        decision="Move the preprocessing off the host", derived=[],
        why="A single choice."),
    "finest": dict(
        decision="Change the process node", derived=["accel_node"],
        why="As Demo 004."),
    "together": dict(
        decision="Widen the memory AND add a second accelerator",
        derived=["execution_mode"],
        why="TWO engineering decisions, deliberately. The question is "
             "about the ORDER of two purchases, so both must be present "
             "and the result cannot be attributed to either alone."),
    "shipping": dict(
        decision="Take the quickest configuration available",
        derived=["memory_devices"],
        why="Not a single-variable change and not meant to be: the "
             "question is whether the fastest design ships, so the "
             "comparison design is chosen for speed and everything else "
             "follows."),
    "host": dict(
        decision="Change the host processor", derived=[],
        why="A single choice."),
    "offload": dict(
        decision="Move the preprocessing to fixed logic", derived=[],
        why="A single choice."),
    "capacity": dict(
        decision="Change how many memory packages are fitted",
        derived=[],
        why="A single choice. Bandwidth follows from package count in "
             "this model, which is the demonstration's subject."),
    "fit": dict(
        decision="Change how many memory packages are fitted",
        derived=[],
        why="A single choice. Capacity follows from package count."),
    "cheaper": dict(
        decision="Change the memory technology", derived=[],
        why="A single choice at the same package count."),
    "split": dict(
        decision="Add a second, smaller accelerator and divide the work",
        derived=["execution_mode"],
        why="As Demo 003."),
    "nodecost": dict(
        decision="Change the process node", derived=["accel_node"],
        why="As Demo 004."),
}
