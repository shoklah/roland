# Plan pairs

The plan pairs measure asks whether `xhigh` is worth its extra tokens in plan writing: each Full design gets two plans from the same spec, one at `medium` and one at `xhigh`, and only one is built. Read this file at design approval while the measure runs.

- **When:**
  - Every Full design in every project takes part, until 10 records carry `plan_pair` or 2026-12-20, whichever comes first. The design seat stays at `medium`.
  - A design the owner exempts in words writes no `plan_pair`, and the next slot does not move.
  - `--brief`'s `Trial:` line shows `paired plans N/10 by 2026-12-20`, ending with `CHECKPOINT` from 6 pairs on, and once the end date has passed.
- **Slot:** at design approval, `n` is the count of records in `~/.claude/workflow-log.jsonl` that carry `plan_pair`, read from `--brief`'s `paired plans N`. The built level is `xhigh` when `n` is even, else `medium`. Write it in the ledger before dispatching the writers.
- **Writers:** two `plan-writer` dispatches in one message, on the stage's design-and-plan model (pass `model: opus` in stages 2, 3 and Out), one with `effort: medium` and one with `effort: xhigh`.
  - Each gets only the spec path, the repo and its own output path. The built level's writer writes to the usual plan path under `docs/superpowers/plans/`. The other writes to `~/.claude/workflow-archive/<date>-<branch>-plan-<level>.md`, outside every repo, so it is never committed or exported.
  - Neither writer is told which plan is built or that another plan exists.
- **Spec gaps:** a writer that stops with `NEEDS_CONTEXT` lists its questions. Answer each one in the spec, as a short addition committed before either writer goes on, then send both writers the same `SendMessage` with the new lines, even the one that didn't ask. The ledger gets one line per question, naming the level of the writer that asked it.
- **Checks:** in the order simplify A, review A, simplify B, review B, where A is the built plan: one `plan-simplifier`, then one fresh `plan-reviewer`, per plan.
  - Each writer applies its own plan's simplify findings, resumed with `SendMessage`, and the session rules on declines as today.
  - Only the built plan's review findings are acted on, sent to its writer as today.
  - Give every finding of both plans a severity and validity. The other plan's review findings take outcome `not_built` and are never applied.
  - The dispatch hook refuses a second review that has no simplify after the first, so two reviews in one message, or both simplifies before either review, are refused.
- **Approval:** the owner approves the built plan as today (cuts, declined findings with reasons, spec flags), plus one line naming the other plan's path and its counts. The owner never chooses between them: the slot already chose.
- **Record:** the plan record carries `plan_pair` and each `plan_simplify` and `plan_review` step's `plan_effort`, as `--schema` prints them, with `plan` the built plan's path.
  - `plan_pair` holds `built` and `plans`, one per level, each with `effort`, `path`, `agent_id` (the writer's first dispatch), `lines`, `tasks` and `questions`, that writer's spec-gap count.
  - `plan_effort` names the plan each step checked. The implementation session starts from the built plan's path only.
- **End:**
  - **The early stop:** at the first `CHECKPOINT` from 6 pairs, the session that sees it proposes the analysis (`effort.py --pairs`, outside every repo) once, and logs that in its ledger. Pairing goes on unless the analysis finds the early stop holds and the owner ends the measure.
  - **The full stop:** at 10 pairs or past the end date, the analysis runs again. A later change ends the measure: it removes the pointer sentence and this file, and adds a `CHANGES` row.
