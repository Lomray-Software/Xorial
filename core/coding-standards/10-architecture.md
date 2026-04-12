---
apply: always
---

# Architecture and decomposition rules

## General architecture
This codebase prefers strict decomposition, isolation of responsibilities, and removable/self-contained modules.

The target architecture is modular and destructured:
- UI lives in components;
- business logic lives outside UI;
- reusable pure helpers live in helper/utility modules;
- services and stores encapsulate behavior;
- modules should be removable with minimal cleanup in unrelated places.

A component or feature should be as self-contained as possible.
If a component is removed, the cleanup required outside its own module should be minimal.

## React / React Native architecture
For UI layers:
- components should contain UI only;
- business logic must not live inside React components;
- complex decisions, actions, state transitions, and orchestration must live in stores/services;
- components may consume stores, but should not implement business workflows.

If a component becomes large:
- split it into smaller subcomponents;
- move logic into a store/service/helper;
- keep the top-level component visually small and readable.

## Store-driven architecture
MobX and MobX Store Manager are the preferred source of business logic and state orchestration.

Use stores for:
- state;
- computed values;
- user interaction handling when it affects business behavior;
- async workflows;
- domain-related orchestration;
- derived UI state that is meaningfully connected to business logic.

Do not move business logic into hooks or component-local ad hoc solutions if a store-based solution is appropriate.

## Hooks
Avoid custom hooks as a business-logic abstraction.
Do not introduce hook-heavy architecture.

Hooks are acceptable only for:
- unavoidable React integration points;
- platform lifecycle glue;
- small UI-local behavior that is not business logic.

Do not use hooks as a replacement for stores/services.

## Services and helpers
Use services/classes for structured behavior.
Use helpers/utilities only for:
- pure transformations;
- formatting;
- isolated stateless helpers;
- reusable logic that does not belong to a store or service.

Do not dump unrelated logic into generic helper files.

## Class preferences
Classes are preferred for:
- stores;
- services;
- structured domain behavior.

Functional style is acceptable mainly for:
- helpers;
- utility functions;
- simple pure transformations.

## File responsibility
A component file should ideally contain:
- one exported default component;
- its props interface/type if needed;
- minimal UI-related composition only.

Move everything else out when possible:
- business logic → store/service;
- reusable logic → helper/utility;
- large fragments → subcomponents;
- API interaction → dedicated API/service layer.

## Ordering and structure
Prefer consistent, pedantic member ordering.

For classes, the default order is:
1. Class comment
2. Properties
3. Constructor
4. Computed accessors / getters
5. Public methods
6. Protected/private helpers

For component files, the default order is:
1. Imports
2. Local types/interfaces
3. Local constants
4. Comment for component
5. Component implementation
6. Export default

## Domain boundaries
For backend/domain code:
- keep domain separate from transport;
- keep DTOs separate from domain models;
- keep controller/service/repository boundaries explicit.

## Reuse over reinvention
Before creating a new abstraction, first check whether:
- the project already has a service for that;
- the project already has a helper for that;
- the project already has an API layer pattern for that;
- the project already has an established store pattern.

Prefer alignment with the existing project over idealized generic architecture.

## Feature locality
Prefer colocated feature architecture.

When adding logic for a feature:
- keep feature-specific helpers near the feature;
- keep feature-specific types near the feature;
- keep feature-specific subcomponents inside the feature module;
- avoid pushing local logic into global shared folders without clear reuse value.

The codebase prefers feature locality over premature global sharing.
