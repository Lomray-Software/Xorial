---
apply: by file patterns
patterns: **/*.store.ts, **/*.store.tsx, **/*Store.ts, **/*Store.tsx
---

# MobX and @lomray/react-mobx-manager rules

## Primary state architecture
This project uses MobX with `@lomray/@lomray/react-mobx-manager` as the primary architecture for feature state and business logic.

Respect this architecture.
Do not replace it with hooks-based state management or generic React patterns.

## Hard rule — business logic belongs in stores

Business logic must not live in React components. This is a hard constraint, not a preference.

Every time you write or review a component, ask: does this belong in the store? If yes — move it.

The only exceptions are values that physically cannot leave the component:
- Reanimated shared values and animated styles
- Gesture handlers that are tightly coupled to animation state

Everything else — async calls, derived state, conditions, orchestration — goes in the store.

## Store interface — IRelativeStore vs IGlobalStore

When a store uses lifecycle methods (`init`, `onDestroy`, `onComponentPropsUpdate`), it must implement the appropriate interface from `@lomray/react-mobx-manager`:

- **`IRelativeStore`** — component-scoped store, tied to a component's lifecycle.
- **`IGlobalStore`** — app-wide singleton, shared across the entire app. Must also declare `public static isGlobal = true`.

```ts
import type { IRelativeStore } from '@lomray/react-mobx-manager';

class SomeFeatureStore implements IRelativeStore { ... }
```

```ts
import type { IGlobalStore } from '@lomray/react-mobx-manager';

class UserStore implements IGlobalStore {
    public static isGlobal = true;
    ...
}
```

Do not add `implements IRelativeStore` or `implements IGlobalStore` to a store that has no lifecycle methods — there is nothing to declare.

## Store lifecycle methods

Both interfaces inherit `IStoreLifecycle`, which provides three lifecycle hooks:

- **`init(): void | (() => void)`** — called by the manager after the store is created. Use it for: initial data fetching, setting up MobX reactions/subscriptions. If it returns a function, that function is called as a disposer when the store is destroyed.
- **`onDestroy(): void`** — called when the store is unmounted/destroyed. Use it for explicit cleanup that isn't covered by the `init` disposer.
- **`onComponentPropsUpdate(props): void`** — called when the parent component's props change. Use it to sync store state with incoming prop updates.

```ts
public init(): () => void {
    const unsubscribe = reaction(
        () => this.queryParams,
        () => { void this.fetchData(); }
    );

    return () => {
        this.debouncedFetch.cancel();
        unsubscribe();
    };
}
```

Do not put initialization logic (reactions, first fetches, subscriptions) in the constructor — put it in `init()`.

## Store responsibilities
Stores are the primary place for:
- feature state;
- async requests;
- derived/computed state;
- actions and state transitions;
- orchestration logic;
- integration with services;
- request lifecycle state.

UI components should consume store state and delegate behavior to the store.

## Store construction style
Stores are class-based.

Preferred store structure:
- public observable fields first;
- refs as public fields when needed;
- private/protected service dependencies next;
- constructor after fields;
- `makeFetching(...)` in constructor when used;
- `makeObservable(...)` in constructor;
- public methods after constructor;
- private helpers after public methods.

Keep the structure visually strict and consistent.

## Constructor behavior
When a store receives dependencies from `@lomray/react-mobx-manager`, keep the style consistent with local code:
- extract `getStore`, `endpoints`, `componentProps` from constructor params;
- initialize dependent stores/services in constructor;
- merge config from component props carefully;
- keep constructor readable and ordered.

Do not over-abstract constructor setup.

## MobX usage
Use MobX primitives in the same style as the existing codebase:
- `observable`
- `computed`
- `action.bound`
- `reaction`
- `runInAction`
- `makeObservable`

Prefer explicit MobX declarations over hidden magic.

## Async operations and loading state

Async requests live in stores.

**Do not manually flip boolean loading flags** (`isLoading = true` / `isLoading = false`) inside async methods. Use `makeFetching` instead — it wraps the method automatically.

```ts
import makeFetching from '@lomray/react-mobx-manager';

class SomeStore {
    public isSaving = false;
    public isDeleting = false;

    constructor() {
        makeFetching(this, {
            save: 'isSaving',
            delete: 'isDeleting',
        });
        makeObservable(this, {
            isSaving: observable,
            isDeleting: observable,
        });
    }

    public save = async () => { ... };   // isSaving is true while this runs
    public delete = async () => { ... }; // isDeleting is true while this runs
}
```

`makeFetching` call goes in the constructor, before `makeObservable`.
Multiple methods can map to the same flag or to different flags.

This is a hard rule. Any code that manually sets a loading boolean inside an async method is wrong and must be replaced with `makeFetching`.

## Reactions and listeners
When a feature needs reactive listeners, prefer the existing store pattern:
- dedicated method like `addListeners`
- explicit cleanup return function
- colocated reaction logic in the store

Do not scatter reactive business behavior across UI components.

## Computed values
Use computed getters for derived state.
Examples of the local pattern:
- visibility flags;
- filtered entities;
- ownership/permission checks;
- derived loading states.

Do not compute meaningful business state repeatedly inside components if it belongs in the store.

## Refs
When list/modal/navigation refs are required by the feature, it is acceptable to store them inside the store if that matches the existing feature pattern.

Examples of accepted local style:
- `flashListRef`
- `actionMenuModalRef`

## Public method naming
Prefer clear method names that read like feature actions:
- `getCharacter`
- `refreshCharacter`
- `changePage`
- `setStoreProps`
- `resetAllFilters`

Avoid vague or overly abstract names.

## Private helpers
Keep private helpers in the store for internal feature behavior:
- visibility filtering;
- error registration;
- small local orchestration helpers;
- debounced request wrappers.

If a helper becomes reusable across features, move it to a colocated helper module or shared helper according to existing project conventions.

## Store destructuring in components

When a store is connected to a component, always destructure its fields before use — do not access them inline via the store reference.

```tsx
// ✓
const { items, isLoading, fetchItems } = store;

return isLoading ? <Spinner /> : <List data={items} onRefresh={fetchItems} />;

// ✗
return store.isLoading ? <Spinner /> : <List data={store.items} onRefresh={store.fetchItems} />;
```

This keeps template code clean and makes observable dependencies explicit.

## Store methods in hook dependencies

Do not include store methods in dependency arrays of `useEffect`, `useCallback`, or `useMemo`. MobX store methods are stable — they never change between renders.

```tsx
// ✓
useEffect(() => {
    void fetchItems();
}, [id]);

// ✗
useEffect(() => {
    void fetchItems();
}, [id, fetchItems]);
```

Adding store methods to deps is noise and can cause unnecessary re-runs if the linter forces re-creation of the function reference.

## UI integration
Components may use small glue hooks such as:
- `useEffect`
- `useMemo`
- `useCallback`
- `useFocusEffect`

But these must remain UI integration glue, not business logic containers.

Do not move store responsibilities into React hooks.

## Parent store pattern
If a child component uses `parentStore(...)`, follow that pattern.
Do not rewire it into prop drilling or unrelated abstractions unless explicitly requested.

## Existing local MobX conventions have priority
When nearby files show a more specific MobX style, follow the nearby style first.

## Store versus component decision
When deciding where logic belongs:
- store for feature behavior, async flows, derived business state, and actions;
- component for rendering and thin integration glue;
- helper for pure local transformation;
- service for reusable operational/integration behavior.

Default to store when logic clearly belongs to feature state or workflow.

## Keep stores readable
Stores should be decomposed as well.
If a store grows too large, consider:
- extracting pure mapping/helpers;
- moving reusable integrations into services;
- splitting local responsibilities when the feature architecture supports it.

Do not dump every concern into one giant store.
