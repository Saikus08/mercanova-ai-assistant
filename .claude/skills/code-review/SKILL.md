---
name: code-review
description: Review a pull request against the project rules before merge. Use whenever reviewing a teammate's PR or AI-generated changes.
---

# Code review

Review the PR diff and the linked issue. Report findings as: **Blocking** (must fix), **Suggestion**, **Question**.

## Checklist

### Requirements
- [ ] The change does what the issue's acceptance criteria say (cite the RF/RNF).
- [ ] No scope creep outside the issue.

### Architecture (AGENTS.md)
- [ ] Price, stock and order data come from tools/DB, never from RAG or the prompt.
- [ ] Purchases still require explicit confirmation outside the LLM.
- [ ] Domain layer has no framework/adapter imports.
- [ ] Frontend uses design tokens; presentational components do not fetch.
- [ ] New decisions are backed by an ADR in `docs/decisions/`.

### Correctness and robustness
- [ ] Edge cases handled: not found, out of stock, invalid quantity, LLM unavailable.
- [ ] Errors mapped to clear messages; no raw stack traces to the user.
- [ ] Stock changes are transactional.

### Tests
- [ ] New behavior has tests; tests fail without the change.
- [ ] `make test` passes (output summarized in the PR).

### Hygiene
- [ ] No secrets, `.env` files or large generated files committed.
- [ ] New env vars added to `.env.example`.
- [ ] Conventional Commit messages; code and comments in English.
- [ ] The CI check is green.
- [ ] New or changed flows have their diagram in `docs/diagrams/`.
- [ ] PR title and description are in Spanish.

## AI-generated code

If the PR was produced with a coding agent, also verify the author understood it: ask them to explain one non-trivial part in the PR conversation. Record any change you rejected or corrected in the review — this evidence goes into the report's "Uso de Coding Agents" section.
