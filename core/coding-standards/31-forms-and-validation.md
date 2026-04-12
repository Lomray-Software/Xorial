---
apply: always
---

# Forms and validation rules

## Form architecture
Forms in this codebase are structured, colocated, and explicit.

Preferred form structure:
- form component for UI composition;
- validation schema in a nearby `*.validation.tsx` file when needed;
- store near the form if the form has non-trivial business logic;
- shared field/input abstractions reused from existing form infrastructure.

## Existing form infrastructure
Before creating any new form primitives, inspect whether the project already has:
- Formik wrapper;
- submit button;
- field components;
- input components;
- validation utilities;
- helper text and error text components.

Reuse them.

## Validation
Validation should be explicit and colocated.

Prefer nearby validation schema files for form-specific validation instead of embedding large validation logic into the form component.

Do not mix large validation schemas into UI component files if the local module already uses separate validation files.

## Submit flow
Submit logic may be connected in the form component, but business behavior should still live in the store/service when the operation is non-trivial.

The form component should orchestrate submission, not become the business-logic owner.

## Form comments and readability
Keep forms visually compact and easy to scan.
Avoid noisy inline logic inside JSX.
