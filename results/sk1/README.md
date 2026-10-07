# SK-1 raw results (`docs/SK1_PREREG.md`, `docs/SK1_RESULTS.md`)

- `skill_arm/REPORT.md` and `baseline_arm/REPORT.md`: each agent's final report, verbatim, as handed back to the session
  that ran the trial.
- `skill_arm/`: the agent's tool outputs (`audit*.txt`, `audit*.json`), runner and mutant outputs, and repository
  snapshots, copied from its scratch area `/home/user/sk1_skill_out`. Its mutant copies of skn are not kept.
- `baseline_arm/`: the agent's `logs/` and `env.sh`, copied from `/home/user/sk1_base_out`. Its working copy and mutant
  copies of skn are not kept.
- Scripts the agents wrote are stored as `*.py.txt`, so that scanners and pytest in this repository do not treat them as
  repository code. Run them with `python3 <file>.py.txt`. They contain the agents' absolute paths.
