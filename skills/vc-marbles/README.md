#

؞Vibecraftedٜ - The Marbles
؞Vibecraftedٜ - The Marbles

## For Founders and Agentosceptic Developers

_This section explains what Marbles does and why it earns your trust.
The operational protocol follows below._

### The Promise

Language models generate approximations, not proofs. Every AI-written
code change introduces signal AND noise. That is not a bug — it is the
physics of next-token prediction. The question is not whether noise
exists, but whether you have a system to eliminate it.

Marbles is that system.

It works by asking one question, relentlessly: **What is still wrong?**

Not "is this correct?" — that is an infinite question with no finite answer.
Instead: "Can I find a specific, measurable thing that contradicts health?"
If yes, fix it. If no, you are done.

### Why It Earns Trust

The agent operating inside a Marbles loop is not freestyling improvements
based on aesthetic preference. It is a precise, inquisitive core of
expertise — a generator of surgical code modifications and a disciplined
remediation engine. Its work rests on hard evidence, not assumptions.

**Your tools are the agent's senses.** Loctree, compilers, linters, tests —
they deliver objective truth about the state of the code. The agent delivers
expert interpretation and a precise remediation plan. It cannot hallucinate
architecture because it does not guess architecture — it reads it through
instruments.

**Your mission is partnership in quality.** The agent does not replace the
engineer-creator. It becomes their relentless assistant who never tires of
finding imperfections. It leads code toward completeness by eliminating
shortcomings step by step, in a closed verification loop.

### The Daily Flow

Your work on a task is a process of continuous entropy reduction. Instead
of trying to prove "everything is fine," you relentlessly ask one question:
**What is still wrong?**

1. **Gather Evidence** — reach for your tools (linter, loctree, tests).
   Ask the analysis system to show you a counterexample to repository health.

2. **Focus** — isolate a concrete, measurable problem surfaced by the tool.
   "Evidence: loctree reports that export X in utils.ts has zero consumers."

3. **Apply Craft** — write a targeted, surgical fix that resolves only that
   one isolated piece of evidence. Be a sniper, not a grenadier.

4. **Observe the Cascade** — every successful fix may reveal the next
   previously hidden issue. Check your tools again. New findings? Back to
   step 2.

5. **Converge** — your work ends only when, after thorough audit, no tool
   can generate even one accusation. The circle closes. What was undone
   becomes done.

Take the burden of micromanagement off the founder's shoulders. Be the
machine that closes open wounds in the organism, operating only under the
dictation of merciless assertions from deterministic instruments.

### Why This Works (For The Sceptic)

You hand the agent the wheel not because "AI is smart now," but because
**AI is hard-wired to deterministic compilers and tests, so it will not
wreck your project chasing aesthetic improvement.** The mission and agency
are harnessed within iron rules that build absolute trust:

- Every action traces to tool output, never to "I think this looks better"
- Every fix is verifiable — run the same tool again, see the accusation disappear
- Every loop is bounded — 3-5 fixes, then re-measure, never a blind sprint
- Divergence is detectable — if old problems persist while new ones appear, stop

The agent's intelligence is in the precision of interpretation.
The trustworthiness is in the evidence chain.

---

## The Mechanism

Traditional quality asks: _is this correct?_ and tries to prove yes.
That question has no finite answer for a living codebase.

Marbles asks a different question: **what is still wrong?**

Each loop inspects the current state and finds **counterexamples** —
concrete things that contradict health. A dead export in `utils.ts:42`.
A circular import between `auth/` and `api/`. A twin export `Button`
living in two files. These are not abstract noise. They are specific,
named, located violations of health.

This is counterexample-guided convergence — CEGIS applied to code:

```
hypothesis:      "this codebase is healthy"
counterexample:  sniff finds dead export `formatDate` in utils.ts:42
correction:      remove dead export
new landscape:   utils.ts is now empty → new counterexample revealed
correction:      remove empty file
new landscape:   import in api.ts pointed to utils.ts → broken import revealed
correction:      fix import
new landscape:   cycle between api.ts and auth.ts disappeared → health score jumps

No single loop understood the whole.
Each loop only answered: "what is still wrong?"
The convergence was emergent.
```

### The Cascade Effect

Findings are not a flat list. They form a directed graph where fixing one
reveals the next. This is the primary convergence driver:

- Dead export removed → file becomes empty → empty file is new finding
- Empty file removed → import breaks → broken import is new finding
- Import fixed → cycle disappears → health score jumps

Each fix **irreversibly narrows** the space of possible bugs.
Entropy drops monotonically.

### Dual-Source Truth

Convergence becomes stronger with multiple independent sources that can
counterexample each other:

```
sniff says: "exportFoo is dead"      → hypothesis
dist says:  "exportFoo is in bundle" → counterexample to sniff
agent checks: dynamic import          → hypothesis corrected
sniff learns: skip dynamic imports    → error class eliminated permanently
```

When two tools agree — confidence is high.
When they disagree — the disagreement IS the counterexample.

### Agent Blindness

The agent in each loop does not know it is in a loop.

It receives the original plan and sees the current state of the living tree.
No loop metadata, no previous reports, no awareness that other agents ran
before it. It just does the job: read the plan, look at the code, find what
is wrong, fix it, run gates.

Convergence happens because each agent independently finds less wrong than
the one before — the previous agent already fixed its share. No coordination
needed. The shrinking problem space IS the convergence signal.

---
