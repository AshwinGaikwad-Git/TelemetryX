# Cleanup report — 2026-11-16

Removed material with no current application, test, deployment, or maintenance use.

## Deleted files

| File | Reason |
| --- | --- |
| `frontend/lib/utils.ts` | Unreferenced `cn()` class-name helper. |
| `frontend/components.json` | Unused shadcn generator scaffold; no generated UI components use it. |
| `saved_models/.gitkeep` | Obsolete storage placeholder; configured model storage is `models/`. |
| `docs/.gitkeep` | Redundant placeholder in a populated directory. |
| `data/samples/.gitkeep` | Redundant placeholder in a populated directory. |

## Removed code and dependencies

- Removed five unused direct frontend dependencies: `@radix-ui/react-slot`, `@tanstack/react-query`, `class-variance-authority`, `clsx`, and `tailwind-merge`. Regenerated the pnpm lockfile, removing their unused dependency entries too.
- Removed nine unused icon imports: eight from the research page and `Settings2` from the industrial workspace.
- Removed unused research-page sidebar state and its setter.
- Removed unused API client methods `getExperiments`, `getPredictions`, and `getPrediction`. Their backend endpoints remain available as documented public API functionality.
- Removed six unused global CSS variables and the unused `telemetry-bg`, `glass-card`, `kaggle-card`, `glass-card-hover`, and `kaggle-card-hover` styles, including hover rules.
- Removed obsolete `saved_models` entries from Git and Docker ignore configuration.

## Retained after review

The industrial workspace and research demo both remain active routes. Backend services, schema models, migrations, workers, deployment configuration, tests, sample fixtures, their generator, database inspection/migration scripts, and project documentation still contribute to those workflows. No clearly unreferenced top-level backend functions or classes were found by the reference scan; this is not a proof that every execution path is used.

Local credentials, databases, backups, imported datasets, and trained artifacts were preserved because they may contain user data or recorded experiment evidence. Development dependencies and build outputs remain available for running and checking the project.

## Validation

- Backend: 45 tests passed.
- Frontend: 21 tests passed.
- TypeScript check with unused-local and unused-parameter detection passed.
- Next.js production build passed for `/` and `/demo`.
- `git diff --check` passed.

Changes are local and have not been committed or pushed.
