---
apply: by file patterns
patterns: **/*.tsx
---

# React and React Native rules

## UI-only components
Top-level React and React Native components should mostly contain UI composition.

A component may contain:
- rendering;
- small memoized render helpers;
- small callbacks for UI events;
- lifecycle glue for screen/component initialization;
- store wiring.

A component should not contain core business logic.

## Business logic placement
Business logic belongs in:
- MobX stores;
- services;
- pure helpers when truly stateless.

Do not place in components:
- request orchestration;
- feature state transitions;
- business rule branching;
- reusable domain logic;
- large transformation logic with feature meaning.

## Function components only
Use function components only.
Do not introduce class components.

## Component decomposition
Components should stay visually small and readable.

If a component grows:
- extract subcomponents;
- extract helper functions;
- move business logic to store/service;
- keep the entry component clean.

The codebase prefers deep decomposition over oversized component files.

## File-level composition
A screen/component is often a coordinator for:
- subcomponents;
- store state;
- wrapper composition;
- refresh controls;
- existing UI building blocks.

That is the preferred style.

## Hooks policy
Hooks are allowed, but they are not the architectural center of the application.

Hooks may be used for:
- lifecycle glue;
- navigation/focus integration;
- memoization and stable callbacks;
- theme and localization integration;
- small UI-local behavior;
- platform integration.

Do not use hooks as the main place for business logic, feature orchestration, or domain behavior.

Custom hooks are acceptable only when they solve a real UI/platform integration need and fit the local codebase style.
Do not replace stores/services with custom hooks.

## Store wrappers
Use `withStores`, `parentStore`, and local store wrappers when that is how the feature is already structured.

Do not replace these with ad hoc alternatives.

## Lists and render helpers
For list-heavy UI:
- keep `renderItem`, `keyExtractor`, empty/footer/header rendering compact;
- memoize/callback where it matches existing local style;
- keep list configuration readable.

Follow existing patterns from nearby list components.

## Screen behavior
For screens:
- initialization and refresh triggers may be wired in the component;
- navigation options may be configured in the component;
- actual feature behavior still belongs in the store.

This matches local project style and should be preserved.

## Styling
Keep styling separate in colocated style files.
Use the project's existing styling pattern.

## Existing local structure wins
When there is a choice between generic React best practice and the style already present in this project, follow the project style.

## Memo wrapper exports
When using `memo()` on a component, do not wrap it inline in the export.

Instead, create a named wrapper variable:

```tsx
const MyComponentMemo = memo(MyComponent);

export default MyComponentMemo;
```

Do not write:
```tsx
export default memo(MyComponent);
```

## Compound components
Complex UI components may expose sub-components as static properties:

```tsx
Comments.Header = CommentsHeader;
Comments.Input = CommentsInput;
```

When using `withStores`, preserve compound component types:

```tsx
const Wrapper = withStores(Component, stores);

type TWrapper = typeof Wrapper & ICompoundComponents;

export default Wrapper as TWrapper;
```

## Component comment requirements
Inside React and React Native components, all methods and callbacks must have block comments.

This includes:
- event handlers;
- press handlers;
- submit handlers;
- useCallback functions;
- useMemo computations;
- render helpers (renderItem, keyExtractor, etc.).

Use block comments:

/**
 * Comment text
 */

Do not leave component-local logic undocumented.
