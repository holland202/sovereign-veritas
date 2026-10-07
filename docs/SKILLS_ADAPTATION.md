# What this repository takes from anthropics/skills (studied at `683bc88`, 2026-10-07)

Source: a local clone of `github.com/anthropics/skills`, including `spec/agent-skills-spec.md`. That Anthropic publishes a
pattern is not evidence that the pattern works. Each row below says why it is or is not used here, and whether anything
was measured. Written by Claude (Opus 5.5), **self-tested**.

**Decision.** One project skill, `.claude/skills/test-vacuity-audit/`, kept or dropped by a registered with-and-without
trial (`docs/SK1_PREREG.md`). **Result (`docs/SK1_RESULTS.md`):** the agent without the skill found the same defect,
with executed evidence (S2 refuted). By the decision rule fixed in advance, the skill shows no measurable value on that
task and is kept only as a pointer to the tool, and says so. No other project skill. The repository's other repeatable
procedure is register → build → anti-vacuity → run → failures-first results. It is already covered by the user-level
`experiment-first` skill and by the definition of done in `docs/PRODUCTION_GAP_ANALYSIS.md`, and a second copy would drift.

| Anthropic pattern / skill | What it does | Relevant? | Why / why not | Proposed adaptation |
|---|---|---|---|---|
| Agent Skills spec: `name` and `description` frontmatter; progressive disclosure (body on trigger; `scripts/`, `references/`, `assets/` on demand) | lets an agent find a procedure by its description and load details only when needed | yes | this repository's procedures reach agents through sessions like this one | adopted: a 50-line `SKILL.md` that **points to** `tools/test_vacuity_audit.py` instead of copying it |
| spec: no notion of tests, versions or provenance | a skill is only a document | yes, as a gap | a skill can drift from the tool it names, or claim value it never showed | the skill names the tool by path; the tool has its own tests (`tests/test_test_vacuity_audit.py`); the skill's value is measured (SK-1), not assumed |
| `skill-creator`: the same task with and without the skill | measures whether a skill changes outcomes | yes | the user's instruction: test skills as artifacts | adopted as SK-1; **n = 1 per arm, same vendor, labelled as a demonstration**. Outcome: no measurable value on that task |
| `skill-creator` grader: "A passing grade on a weak assertion is worse than useless"; it critiques the evals too | stops weak assertions from producing confidence | yes | the same principle as this repository's anti-vacuity rule (M3) | adopted: SK-1's key assertion (G1) is one the baseline can plausibly fail; criteria fixed before the runs |
| `skill-creator` analyzer: finds non-discriminating assertions | flags assertions that pass with and without the skill | yes | an assertion both arms pass says nothing about the skill | adopted in SK-1's decision rule: if both arms pass G1 and G2, the skill gets no credit |
| `skill-creator` blind comparator | a separate agent compares outputs without knowing which arm produced them | partly | SK-1 is graded by the skill's author, mechanically | the final evaluation of this work uses a blind agent (task #7); SK-1 states the author-grader limit |
| `skill-creator` description optimization with a 60% train / 40% held-out split | tunes the trigger description without overfitting | not now | one skill, one task: nothing to optimize, and no held-out set | EXPERIMENT FIRST if skills multiply |
| `skill-creator/scripts/quick_validate.py` | checks frontmatter fields, kebab-case name, length | yes | a cheap format check | used (`Skill is valid!`); a CI step is DOCUMENT ONLY (it needs PyYAML, which this repository does not depend on) |
| `webapp-testing`: scripts as black boxes, run `--help` first | keeps the agent from re-deriving tool logic | yes | the same reason the skill calls the tool instead of describing its internals | adopted |
| `webapp-testing`: server lifecycle helpers, Playwright | test a running web app | no | there is no web app here | — |
| `discernment-nudge` | after a substantive answer, adds 2–3 questions that help the user check it | partly | its aim (users checking AI output) is this repository's aim, but here it is met by artifacts: failures first, the claims matrix, raw outputs | not adopted as a project skill |
| `doc-coauthoring` | a staged workflow for writing documents with a user | no | results documents follow this repository's registration and results conventions | — |
| `mcp-builder` (including evaluation creation) | builds MCP servers and question sets to test them | no | there is no MCP server here | — |
| `claude-api` | API usage across languages | no | the kernel makes no model calls (one exploratory NVIDIA tool aside) | — |
| `docx`, `pdf`, `pptx`, `xlsx` | file-format tooling with validation scripts | no | deliverables here are Markdown and JSON in the repository | — |
| `algorithmic-art`, `canvas-design`, `brand-guidelines`, `theme-factory`, `frontend-design`, `web-artifacts-builder`, `slack-gif-creator`, `internal-comms` | creative and communication tooling | no | unrelated to verification | — |
| `academy-guide` | points users to learning material | no | product guidance, not engineering procedure | — |
| `template/` and a LICENSE per skill | a skeleton and license clarity | yes, lightly | reuse needs a license | adopted: `license: MIT`, as the repository |
