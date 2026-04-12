# Skill: Compact Implementation

**Applies to**: implementer

Before writing any code, ask: **what is the minimum amount of code that correctly solves this?**

Rules:
- Prefer editing an existing function over adding a new one.
- Prefer a simple conditional over a new abstraction.
- If two implementations are equally correct, choose the shorter one.
- Do not create helpers, wrappers, or utilities for one-time use.
- Do not add parameters, options, or config keys that the spec does not require.
- Do not design for hypothetical future requirements — solve what is asked, nothing more.
- Three similar lines of code are better than a premature abstraction.
- If you find yourself writing boilerplate, stop and look for an existing utility or a simpler path.

After finishing, review your diff:
- Can any new function be inlined?
- Can any new file be avoided by extending an existing one?
- Is every added line load-bearing, or is some of it defensive fluff?

The goal is not cleverness — it is the smallest correct delta between the current codebase and the required behavior.
