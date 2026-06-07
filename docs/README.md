# BasketGuard Documentation

This folder contains the kickoff documentation pack for BasketGuard. These documents define the initial product scope, technical architecture, data model, and implementation order.

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

## Build Order

The recommended implementation sequence starts in [Codex workplan](11_CODEX_WORKPLAN.md):

1. Keep this repo scaffold minimal.
2. Add database migrations.
3. Add product normalisation utilities.
4. Add analytics functions.
5. Add fixtures and report generation.
6. Add ingestion contracts before any live crawling.
