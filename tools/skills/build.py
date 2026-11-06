#!/usr/bin/env python3
"""Build the 18 research skills from one source, or check that the built copies have not drifted.

    python tools/skills/build.py           # write .claude/skills/<name>/SKILL.md from tools/skills/
    python tools/skills/build.py --check   # exit 1 if any SKILL.md differs from what the source builds
    python tools/skills/build.py --extract # one-off: create the source from existing SKILL.md files

The source is `contract.md` (the operating contract shared by every skill, written once) and `skills.json`
(each skill's frontmatter and procedure). Standard library only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SKILLS = ROOT / ".claude" / "skills"
HEADING = "## Operating contract — binding for this invocation\n"
RESPONSE = ("## Response contract\n"
            "Report **observed facts**, **uncertainties**, **constraints**, **action taken**, **verification state**, "
            "and **next owner decision** as applicable. Do not invent measured results. Keep claims bounded to "
            "observed evidence.\n")


def render(skill: dict, contract: str) -> str:
    lines = ["---", f"name: {skill['name']}", f"description: {skill['description']}",
             f"argument-hint: {skill['argument_hint']}", "disable-model-invocation: true", "---", "",
             f"# /{skill['name']} — Sovereign Research Skill", "", HEADING + contract.rstrip("\n"), "",
             "## Procedure"]
    lines += [f"{i}. {step}" for i, step in enumerate(skill["procedure"], 1)]
    return "\n".join(lines) + "\n\n" + RESPONSE


def load() -> tuple[str, list[dict]]:
    contract = (HERE / "contract.md").read_text(encoding="utf-8")
    skills = json.loads((HERE / "skills.json").read_text(encoding="utf-8"))
    names = [s["name"] for s in skills]
    if len(names) != len(set(names)) or not all(re.fullmatch(r"[a-z][a-z0-9-]{0,63}", n) for n in names):
        raise SystemExit("skills.json: names must be unique lowercase identifiers")
    return contract, skills


def extract() -> None:
    contract, skills = None, []
    for path in sorted(SKILLS.glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        fm = dict(line.split(": ", 1) for line in text.split("---\n")[1].strip().splitlines())
        block = text.split(HEADING, 1)[1].split("\n\n## Procedure", 1)[0] + "\n"
        if contract is None:
            contract = block
        elif block != contract:
            raise SystemExit(f"{path}: operating contract differs from the others; reconcile before extracting")
        procedure = re.findall(r"^\d+\. (.*)$", text.split("## Procedure\n", 1)[1].split("\n\n## ", 1)[0], re.M)
        skills.append({"name": fm["name"], "description": fm["description"],
                       "argument_hint": fm["argument-hint"], "procedure": procedure})
    (HERE / "contract.md").write_text(contract, encoding="utf-8")
    (HERE / "skills.json").write_text(json.dumps(skills, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"extracted {len(skills)} skills")


def main(argv: list[str]) -> int:
    if "--extract" in argv:
        extract()
        return 0
    contract, skills = load()
    expected = {s["name"]: render(s, contract) for s in skills}
    present = {p.name for p in SKILLS.iterdir() if p.is_dir()} if SKILLS.exists() else set()
    if "--check" in argv:
        problems = [f"extra skill folder: {n}" for n in sorted(present - set(expected))]
        for name, text in expected.items():
            path = SKILLS / name / "SKILL.md"
            if not path.exists():
                problems.append(f"missing: {path.relative_to(ROOT)}")
            elif path.read_text(encoding="utf-8") != text:
                problems.append(f"differs from source: {path.relative_to(ROOT)}")
        for p in problems:
            print("DRIFT " + p)
        print(f"skills check: {len(expected)} expected, {len(problems)} problem(s)")
        return 1 if problems else 0
    for name, text in expected.items():
        (SKILLS / name).mkdir(parents=True, exist_ok=True)
        (SKILLS / name / "SKILL.md").write_text(text, encoding="utf-8", newline="\n")
    print(f"built {len(expected)} skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
