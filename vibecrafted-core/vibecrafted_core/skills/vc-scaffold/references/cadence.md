# VC-ship read/write cadence

Scaffold is the WRITE entry of VC-ship: end-to-end delivery of a clearly-defined idea/feature,
**injected at Scaffold, delivered at Release**. The operator runs a PREP phase that must be perfect
to **zero questions**, because through the cycle **no one is available** — the operator sees only
intermediate artifacts. The middle is alternating read-write cycles: the **read/write cadence**.

## The order (canonical)

```
Scaffold(W) → Implement(W) → Review(R) → Workflow(W) → Follow-up(R)
→ Marbles/chaos(W) → Audit(R) → Polarize/order(W) → Dou(R) → Hydrate(W) → Release(W) → Fanfary
```

- **WRITE** (create, leaves an artifact): Scaffold · Implement · Workflow · Marbles · Polarize · Hydrate · Release
- **READ** (verify, falsifies an artifact): Review · Follow-up · Audit · Dou
- **Cadence invariant:** no WRITE advances until the next READ verifies it. Review verifies Implement;
  Follow-up verifies Workflow; Audit verifies Marbles; Dou verifies Polarize. This is the measure-core
  invariant lifted from the plan unit to the orchestration layer.

## Handoff: scaffold ↔ operator

- **Scaffold OWNS brainstorm→plan (WRITE).** It writes the plan with a `state` column and a `Vector`
  per cut.
- **vc-operator READS the `state` column → trigger/stop (dispatch).** The lighthouse writes; the fleet
  sails. Handoff artifact = the plan (e.g. `EMIL.md` / `SCAFFOLD.md`) with its `state` column.

## Four planning rules (why scaffold must be armored)

1. **Front-load to scaffold, not mid-flight.** All decision-making moves forward; no one answers in
   flight. Architecture, scope, cuts (single/multiple/project), acceptance, dispatch shape — all here.
2. **Every artifact self-sufficient + falsifiable by the next READ.** The brief assumes no human on the
   other side; the READ phase (review/audit/dou) must be able to refute it without the operator.
3. **Research-first / anti-memory is safety-critical, not polish.** In an autonomous pipeline, an agent
   composing from memory is silent drift the operator cannot catch live. The orientation gate is the
   bezpiecznik (see SKILL.md → Canonical Orientation Gate).
4. **Shape plans around the cadence, not around "one dispatch".** Each cut declares which read-write
   phase it lives in and what artifact it leaves for the next. The tracker is visibility-through-artifacts.
