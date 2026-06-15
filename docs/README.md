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
15. [Backend pipeline pack](backend/00_BACKEND_PIPELINE_INDEX.md)

## Progress Tracking

The original scaffold workplan is retained in [Codex workplan](11_CODEX_WORKPLAN.md)
as a completed/legacy checkpoint. Current progress is tracked by milestone tags
and the "Delivered Milestones" table in that file.

To assess project status:

1. Check delivered tags with `git tag --list "milestone-*"`.
2. Compare them with [Codex workplan](11_CODEX_WORKPLAN.md).
3. Use [backend implementation checklist](backend/10_IMPLEMENTATION_CHECKLIST.md)
   for capability-level detail.
4. Use [backend MVP roadmap](backend/08_MVP_DELIVERY_ROADMAP.md) for the next
   planned milestone.
5. Verify with `python -m unittest discover -s tests -v`.

The active next milestone is recorded in [Codex workplan](11_CODEX_WORKPLAN.md)
under "Active Next Prompt".
