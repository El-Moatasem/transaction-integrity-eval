# T04: Out-of-order payment webhook state machine

This candidate tests financial correctness under the documented task-specific conditions.

- Agent-visible: `instruction.md` and `environment/service.py`.
- Withheld: `solution/`, `tests/`, `mutants/`.
- Oracle: `harbor run -p tasks/T04_webhook-ordering -a oracle`.
- No-op: `harbor run -p tasks/T04_webhook-ordering -a nop`.
- Cross-model comparison: freeze task, tests, environment, timeouts and agent framework before running.

**Status:** locally control-validated; Harbor/Docker end-to-end not run in this build environment. No model trials are included.
