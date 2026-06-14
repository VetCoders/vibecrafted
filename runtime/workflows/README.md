# Workflow Runtime Packages

`runtime/workflows/<workflow>/` owns executable workflow defaults and runtime
assets. `skills/<workflow>/` owns interactive doctrine and reference material.

The Python launcher reads this tree through `vibecrafted_core.workflows.registry`
so runtime defaults do not live in `SKILL.md` files or in generic launcher glue.

This tree is the future home for lifecycle nodes in the read-write cadence:
read workflows discover and falsify, write workflows deliver and converge, and
the runner/supervisor layer moves the baton between them.
