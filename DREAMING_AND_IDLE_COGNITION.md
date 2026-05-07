# GAIA Dreaming and Idle Cognition

Dreaming and idle cognition are internal-only simulation modes for memory consolidation, plan improvement, creative association, and problem replay. They must never execute external actions.

## Allowed Behaviors

Dreaming mode may:

- analyze completed tasks
- simulate alternative plans
- summarize memory
- consolidate notes
- generate internal-only scenarios
- rehearse goals
- replay problems for insight
- write a dream journal entry

## Forbidden Behaviors

Dreaming mode must not:

- run shell commands
- modify external files
- install packages
- push Git changes
- call external APIs
- send messages
- schedule autonomous external work
- alter GAIA code directly

## Implemented Foundation

The `NoActionGuard` blocks external-action attempts. Dream engine modules are designed for notes and reports only. Future idle schedulers must call the guard before any action-like operation.

## Roadmap

1. Add workspace-scoped dream journals.
2. Add memory consolidation reports with provenance.
3. Add idle scheduler windows that are disabled by default.
4. Add tests for every forbidden action type.
