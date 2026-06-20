# Delivery Governance

## Purpose

This document defines how BasketGuard tracks work, accepts changes and keeps repository documentation aligned with delivery reality.

## Source of truth order

Use these systems for different kinds of truth:

1. **Linear** is the single source of truth for planned work, current status, ownership, priority, dependencies and delivery sequencing.
2. **GitHub** is the source of truth for change control: branches, pull requests, code review, CI evidence, merge history and release or milestone tags.
3. **Repository docs** are product, architecture, implementation and operating references. They should explain how the system works and what standards apply, but they should not duplicate live backlog state.

## Linear responsibilities

Linear owns:

- active and upcoming work;
- issue status such as Backlog, In Progress, In Review, Done or Blocked;
- parent/child task breakdowns;
- priorities, labels, dependencies and assignments;
- acceptance criteria and implementation scope for the current delivery slice.

When a repository doc and Linear disagree about what is next, use Linear and open or update a documentation task to reconcile the repo.

## GitHub responsibilities

GitHub owns:

- branch creation for each coherent change;
- pull request review and approval;
- CI/test evidence;
- merged change history;
- milestone or release tags;
- audit trail for what changed and when.

Substantial changes should move through a branch and pull request. Direct commits to `main` should be limited to explicitly approved trivial documentation fixes.

## Repository documentation responsibilities

Repo docs should:

- describe product intent, technical decisions, schema vocabulary and implementation guardrails;
- link to Linear issue identifiers for traceability where useful;
- avoid claiming an issue's live status unless the status is explicitly marked as a point-in-time snapshot;
- mark historical roadmaps, prompts and milestone ledgers as historical when they are not the live queue;
- be updated in the same GitHub pull request when a change invalidates architecture, schema, API or operating guidance.

## Delivery workflow

1. Select the next task in Linear.
2. Create or switch to an appropriate Git branch.
3. Implement the smallest coherent change.
4. Update repo docs only where the implementation changes durable product, architecture, API, schema or operating guidance.
5. Run relevant tests and capture screenshots for UI changes.
6. Open a GitHub pull request with summary, tests, risks and screenshots or migration notes when relevant.
7. Move the Linear issue through review and completion based on the accepted GitHub change.

## Historical documents

Some existing docs contain scaffold-era prompts, roadmap phases or milestone ledgers. Keep them for context, but do not treat them as the active backlog unless a matching Linear issue is selected.
