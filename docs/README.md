# BasketGuard Documentation

This folder contains the BasketGuard documentation pack. These documents define the product scope, technical architecture, data model, implementation order, and backend pipeline.

## Core Documents

1. [Product brief](00_PRODUCT_BRIEF.md)
2. [Problem and goals](01_PROBLEM_AND_GOALS.md)
3. [MVP scope](02_MVP_SCOPE.md)
4. [Data ingestion](03_DATA_INGESTION.md)
5. [Product normalisation and equivalence](04_PRODUCT_NORMALISATION_AND_EQUIVALENCE.md)
6. [Price analytics and offender score](05_PRICE_ANALYTICS_AND_OFFENDER_SCORE.md)
7. [Technical architecture](06_TECHNICAL_ARCHITECTURE.md)
8. [Database schema](07_DATABASE_SCHEMA.md)
9. [Reporting and UX](08_REPORTING_AND_UX.md)
10. [Risks, legal and trust](09_RISKS_LEGAL_TRUST.md)
11. [Roadmap](10_ROADMAP.md)
12. [Codex workplan](11_CODEX_WORKPLAN.md)
13. [Grouping catalogue draft](12_GROUPING_CATALOGUE_DRAFT.md)
14. [Git workflow](13_GIT_WORKFLOW.md)
15. [UI professionalisation plan](14_UI_PROFESSIONALISATION_PLAN.md)
16. [Delivery governance](15_DELIVERY_GOVERNANCE.md)
17. [Commercial UI finish plan](16_COMMERCIAL_UI_FINISH_PLAN.md)
18. [Backend pipeline pack](backend/00_BACKEND_PIPELINE_INDEX.md)

## Progress Tracking

Linear is the single source of truth for planned work, current issue status,
priority, ownership and delivery sequencing. GitHub manages change control
through branches, pull requests, CI evidence, merge history and tags. Repository
docs are durable product and engineering references, not the live backlog.

Use [Delivery governance](15_DELIVERY_GOVERNANCE.md) for the operating model.

To assess project state:

1. Check the BasketGuard project and issues in Linear for active and upcoming work.
2. Check GitHub branches, pull requests and CI for change-control status.
3. Check delivered tags with `git tag --list "milestone-*"` when historical
   delivery evidence is needed.
4. Use [Codex workplan](11_CODEX_WORKPLAN.md) only as a historical milestone ledger.
5. Use [backend implementation checklist](backend/10_IMPLEMENTATION_CHECKLIST.md)
   for capability-level detail.
6. Verify with `python -m unittest discover -s tests -v`.

If Linear and repository docs disagree about what is next, use Linear and update
the docs through the normal GitHub change-control process.
