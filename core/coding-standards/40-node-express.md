---
apply: by file patterns
patterns: **/server/**/*.ts, **/backend/**/*.ts, **/api/**/*.ts
---

# Node.js and Express backend rules

## Backend direction
Backend code should remain explicit, layered, and maintainable.

Preferred structure:
- controller
- service
- repository
- DTOs
- domain models
- infrastructure integrations

Keep boundaries explicit.

## Framework preference
Express is preferred.
Do not introduce unnecessary framework magic.

## Controllers
Controllers should:
- validate/parse input according to project conventions;
- delegate business behavior to services;
- remain thin.

Do not place business logic in controllers.

## Services
Services are the primary place for backend business behavior and orchestration.

Prefer class-based services when aligned with the codebase.

## Repositories
Repositories handle persistence concerns.
Do not leak persistence details into controllers or transport-facing layers.

## DTOs and domain models
Keep DTOs separate from domain models.
Do not conflate transport contracts with domain entities.

## Database
TypeORM is preferred where already used.
Migrations are mandatory for schema changes.

If a database change is required:
- update the relevant entities/models;
- create or update migrations;
- preserve backward compatibility where possible.

## API contracts
Do not silently break public API contracts.
Call out contract changes explicitly.

When changing request/response shapes:
- keep DTOs explicit;
- follow existing versioning or compatibility patterns;
- mention the impact clearly.

## Dependencies
Do not add backend dependencies unless necessary and justified.
Reuse existing infrastructure, utilities, and patterns first.

## Logging and errors
Prefer project logging/reporting infrastructure over console logging.
Do not swallow errors silently.
