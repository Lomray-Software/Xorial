---
apply: always
---

# File placement and feature locality rules

## Primary rule
Place code where this codebase would naturally expect it.

Do not create random shared abstractions or generic folders unless the logic is clearly cross-feature and reusable.

## Feature locality
Prefer colocated feature architecture.

When adding functionality for a feature or screen, place it near that feature:
- feature-specific UI -> inside the feature/component `components/` tree;
- feature-specific store -> near the feature entry file;
- feature-specific styles -> near the component/screen;
- feature-specific validation -> near the form/component;
- feature-specific helpers/constants/types -> inside the same feature/module.

## Shared code
Move code into shared/global folders only when at least one of these is true:
- it is reused across multiple unrelated features;
- it is truly foundational infrastructure;
- the project already has an established shared location for that concern.

Do not move local feature logic into shared folders prematurely.

## File naming
Prefer existing local naming conventions:
- `FeatureName.tsx`
- `FeatureName.store.ts`
- `FeatureName.styles.ts`
- `FeatureName.validation.tsx`
- `FeatureName.types.ts`
- `constants/...`
- `helpers/...`

Child components should usually live in:
- `components/ChildComponent/ChildComponent.tsx`
- with colocated `ChildComponent.styles.ts` when needed.

## Component files
A component file should remain focused.
Do not keep unrelated helpers, validation, store logic, or large constants inside the component file when local colocated files are more appropriate.

## Shared components import boundary

Files inside `src/components/` are global/shared. They must not import from `src/features/`.

This rule applies to both `apps/frontend` and `apps/mobile`.

Allowed imports from `src/components/**`:
- other files within `src/components/`
- `src/services/`, `src/stores/`, `src/helpers/`, `src/hooks/`, `src/constants/`, `src/types/`, `src/utils/`, `src/theme/`, `src/styles/`
- external packages

Not allowed:
```ts
// inside src/components/SomeShared/SomeShared.tsx
import Something from '@/features/Chat/...' // ✗ — feature import in shared component
import Something from '@/features/Character/...' // ✗
```

If a shared component needs behavior that currently lives in a feature, extract that behavior to a shared location (`src/services/`, `src/helpers/`, etc.) first — then import from there.

A component that imports from `src/features/` belongs inside that feature, not in `src/components/`.

## New files
When adding a new file, match the local feature naming and placement pattern before inventing a new structure.
