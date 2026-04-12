---
apply: always
---

# Design source fidelity rules

## Primary rule
When the user provides a design reference from Figma, Pencil, or another connected design source, treat that design as the source of truth.

Implementation must follow the provided design exactly and must not invent, reinterpret, simplify, or “improve” the design unless the user explicitly asks for that.

## Source priority
When a design reference is available, prioritize it over assumptions, generic UI conventions, or the model's own design preferences.

Do not fill gaps with invented design decisions unless the source is genuinely incomplete and the user explicitly allows reasonable assumptions.

## No design hallucination
Do not:
- invent spacing, sizing, colors, typography, states, icons, or layout behavior;
- add extra UI elements not present in the design;
- remove UI elements shown in the design;
- merge or split blocks unless the design clearly implies it;
- apply “better UX” changes without explicit approval;
- introduce stylistic interpretation.

## Implementation behavior
When implementing from a design source:
1. Read the provided design reference first.
2. Extract the actual structure and visible behavior from the design.
3. Reproduce the hierarchy, layout, and UI elements as shown.
4. Keep implementation faithful to the design while matching the local project architecture.
5. If the design conflicts with the existing code structure, preserve design fidelity in UI and adapt only the internal implementation structure.

## Missing or unclear details
If some detail is genuinely missing or ambiguous in the design source:
- prefer existing design system tokens and local reusable UI primitives already present in the project;
- keep the smallest possible assumption;
- do not invent stylistic changes;
- clearly state what was inferred.

## Local architecture still applies
Design fidelity does not cancel project architecture rules.

This means:
- UI should still remain in components;
- business logic should still live in stores/services;
- styles/helpers/subcomponents should still be decomposed according to the local project structure.

Follow the design exactly in UI, but implement it using the project's existing architecture.

## Reusable UI primitives
Before creating a new UI primitive, check whether the project already has a matching component, token, or style primitive that can reproduce the design accurately.

Reuse existing project UI building blocks whenever possible, but do not let reuse reduce fidelity to the provided design.

## Interaction and states
If the design source includes visible interaction states or variants, implement only those that are explicitly shown or explicitly requested.

Do not invent additional states, transitions, or behaviors.

## Design reference over guesswork
When a design source is present, accuracy is more important than speed.
Matching the provided design is more important than producing a quick generic UI.
