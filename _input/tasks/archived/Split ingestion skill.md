---
title: "Split Ingestion Skill into Two Phases (Draft Review & Approved Compilation)"
type: "task"
status: "done"
created: 2026-11-01
updated: 2026-11-01
deliverable: "[[_input/drafts/Two-Phase Ingestion Skill Architecture Proposal]]"
---

I want to split the ingestion skill into two phases:
Phase 1: run the steps until the source is created in wiki/sources in status draft
The source should have a property: draft or approved
That can be changed after review
Phase 2: In status approved the processing should continue to create and update the wiki entities and subsequent steps to update the database

Deliverable: Create an implementation proposal in _input/drafts_
