## Branching Strategy

The SOCIALIZER repository follows a protected trunk-based branching workflow with long-lived integration branches for staged deployments.

### Branches

- **main**: Production-ready code. Protected by required reviews, status checks, and linear history.
- **staging**: Candidate releases that mirror the staging environment. Receives merges from `develop` once feature toggles are validated.
- **develop**: Default branch for day-to-day development. Feature branches branch off here and merge back through pull requests.
- **feature/\***: Short-lived branches scoped to a single task or user story. Rebased onto `develop` prior to merge.
- **hotfix/\***: Emergency fixes branched from `main` and merged back into both `main` and `develop`.

### Protection Rules

The following protection rules should be configured in GitHub:

1. **main**
   - Require pull request reviews (minimum 2 approvers).
   - Require status checks to pass: unit tests, lint, type checks.
   - Require branches to be up to date before merging.
   - Restrict who can push to administrators and CI.
2. **staging**
   - Require pull request review (minimum 1 approver).
   - Require CI checks (integration tests, e2e smoke tests).
   - Disallow force pushes and deletions.
3. **develop**
   - Require passing CI pipeline (lint, unit tests).
   - Encourage squash merges to keep history clean.

### Workflow

1. Create a feature branch: `git checkout -b feature/INFRA-005-env-config`.
2. Develop the change, commit, and push to remote.
3. Open a pull request targeting `develop`.
4. Ensure automated checks pass and request review.
5. Once approved, squash merge into `develop`.
6. Promote to `staging` via pull request when ready for QA.
7. After QA sign-off, merge `staging` into `main` for production release.

### Release Cadence

- **Develop → Staging**: As features reach QA readiness (multiple times per week).
- **Staging → Main**: On successful staging validation (weekly or as needed).

### Additional Policies

- Enforce commit message convention (Conventional Commits) through linting hooks.
- Tag releases from `main` using semantic versioning (e.g., `v1.0.0`).
- Use GitHub Actions to enforce automated checks on pull requests.
