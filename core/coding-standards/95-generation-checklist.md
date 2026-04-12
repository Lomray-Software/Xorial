---
apply: always
---

# Generation checklist

Before writing code, always check:

1. Is this logic UI-only, store logic, service logic, helper logic, validation logic, or styles?
2. Is there already a nearby file/module where this naturally belongs?
3. Does the project already have an existing abstraction/service/component for this?
4. Can this change be implemented with a smaller diff?
5. Should this UI be decomposed into subcomponents?
6. Is business logic leaking into the component?
7. Is this becoming a generic shared abstraction too early?
8. Does the naming and placement match surrounding files?
9. Are comments written in the local block-comment style?
10. Are unrelated files left untouched?

If project context is visible, match the surrounding local style exactly.
