#!/usr/bin/env python3
"""Merge questions into data/me.json (and solutions into data/me-exp.json).

Usage: python3 tools/import.py questions.json

questions.json is a list of objects:
  year     2024                      (required)
  set      1                         (optional, for multi-session years)
  n        12                        question number in the paper (required)
  marks    1 or 2
  type     "mcq" | "msq" | "nat"
  subject  subject name or id from data/me.json   (required)
  topic    topic name or id under that subject    (required)
  q        question text; HTML allowed, maths as \\( ... \\) or \\[ ... \\]
  options  ["...", "...", "...", "..."]            (mcq / msq)
  answer   "B" | ["A","C"] | [min, max] | number | null
  solution optional worked solution (HTML / LaTeX)
Images go in img/ and are referenced as <img src="img/name.webp">.
Re-importing a question with the same year/set/number replaces it.
"""
import json, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
slug = lambda s: re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")

def main(src):
    data = json.loads((ROOT / "data/me.json").read_text())
    exp = json.loads((ROOT / "data/me-exp.json").read_text())
    subs = {s["id"]: s for s in data["subjects"]}
    qs = {q["id"]: q for q in data["questions"]}
    for i, r in enumerate(json.loads(pathlib.Path(src).read_text())):
        where = f"item {i} ({r.get('year')} Q{r.get('n')})"
        s = subs.get(slug(r["subject"])) or sys.exit(f"{where}: unknown subject {r['subject']!r}")
        tid = slug(r["topic"])
        if tid not in {t["id"] for t in s["topics"]}:
            sys.exit(f"{where}: unknown topic {r['topic']!r} in {s['name']}")
        key = f"{r['year']}-{r['set']}" if r.get("set") else str(r["year"])
        t = r.get("type", "mcq")
        a = r.get("answer")
        if t == "nat" and a is not None:
            a = [[float(a), float(a)]] if not isinstance(a, list) else [[float(a[0]), float(a[-1])]]
        if t in ("mcq", "msq") and len(r.get("options") or []) < 2:
            sys.exit(f"{where}: {t} needs options")
        q = {"id": f"me-{key}-{r['n']}", "p": key, "n": r["n"], "m": r.get("marks", 1), "t": t,
             "s": s["id"], "tp": tid, "q": r["q"], "a": a}
        if a is None:
            q["nt"] = "Answer not available"
        if r.get("options"):
            q["o"] = r["options"]
        qs[q["id"]] = q
        if r.get("solution"):
            exp[q["id"]] = r["solution"]
    data["questions"] = sorted(qs.values(), key=lambda q: (-int(q["p"][:4]), q["p"], q["n"]))
    papers = {}
    for q in data["questions"]:
        y, _, st = q["p"].partition("-")
        p = papers.setdefault(q["p"], {"key": q["p"], "title": f"GATE ME {y}" + (f" Set {st}" if st else ""),
                                       "kind": "paper", "year": int(y), "set": int(st) if st else None, "count": 0})
        p["count"] += 1
    data["papers"] = list(papers.values())
    (ROOT / "data/me.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    (ROOT / "data/me-exp.json").write_text(json.dumps(exp, ensure_ascii=False, separators=(",", ":")))
    print(f"{len(data['questions'])} questions in {len(data['papers'])} papers")

if __name__ == "__main__":
    main(sys.argv[1]) if len(sys.argv) == 2 else sys.exit(__doc__)
