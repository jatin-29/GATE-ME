#!/usr/bin/env python3
"""Assemble data/me.json from the official papers.

Inputs (all under tools/official/):
  seg/me<year>.json  questions cut out by tools/segment.py (image name, size, text)
  keys.json          official answer keys: year -> sets -> question -> {t, key, m}
  topics.txt         subject/topic tag of every technical question
  solutions/*.json   optional worked solutions {"<paper>-<n>": "html"}
Question images are expected in img/q/.
"""
import json, re, html, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OFF = ROOT / "tools/official"
SPLIT = {2019, 2020, 2021}            # GA numbered 1-10 and ME 1-55 separately in these years
SRC = "https://gate2026.iitg.ac.in/doc/download/"
PDF = {2019: "2019/me_2019.pdf", 2020: "2020/me_2020.pdf", 2021: "2021/me_2021.pdf", 2022: "2022/me_2022.pdf",
       2023: "2023/me_2023.pdf", 2024: "2024/ME24S2.pdf", 2025: "2025/ME2025.pdf", 2026: "2026/QPs/ME.pdf"}

data = json.loads((ROOT / "data/me.json").read_text())
subjects = data["subjects"]
keys = json.loads((OFF / "keys.json").read_text())

topics = {}
for line in (OFF / "topics.txt").read_text().splitlines():
    if line.startswith("#") or ":" not in line:
        continue
    paper, rest = line.split(":", 1)
    for item in rest.split():
        n, st = item.split("=")
        s, t = map(int, st.split("."))
        topics[(paper.strip(), int(n))] = (subjects[s]["id"], subjects[s]["topics"][t]["id"])

def ga_topic(text):
    t = text.lower()
    if re.search(r"fold|unfold|mirror|rotat|cube|dice|paper is|pattern|shape|figure|tile|triangle|square|circle|polygon|view", t) and re.search(r"fold|mirror|rotat|pattern|tile|dice|view|shape", t):
        return "spatial-aptitude"
    if re.search(r"statement|conclusion|infer|inference|argument|assum|passage|logic|seating|arrang|sequence of|order of|true\b", t):
        return "logical-reasoning"
    if re.search(r"\d", t) and re.search(r"ratio|percent|%|average|probab|speed|area|sum|number|value|cost|price|time|distance|interest|profit|equation|graph|chart|how many", t):
        return "numerical-ability"
    return "verbal-ability"

def answer(typ, key):
    if key == "MTA":
        return None, "Marks to all in the official key"
    if typ == "nat":
        return [[float(a), float(b)] for a, b in (p.split(" to ") for p in key.split(" OR "))], None
    alts = [a.split(",") for a in key.split("OR")]
    if typ == "msq":
        return alts[0], ("Official key also accepts: " + " or ".join(", ".join(a) for a in alts[1:])) if len(alts) > 1 else None
    return (alts[0][0] if len(alts) == 1 else [a[0] for a in alts]), None

def safe_html(h):
    """Escape any '<' that does not start one of the simple tags solutions use (maths like a<b)."""
    return re.sub(r"<(?!/?(p|b|i|br|sub|sup|span|strong|em)\b)", "&lt;", h)

solutions = {}
for f in sorted((OFF / "solutions").glob("*.json")) if (OFF / "solutions").exists() else []:
    solutions.update(json.loads(f.read_text()))

questions, papers, exp, untagged = [], [], {}, []
for year in sorted(PDF, reverse=True):
    seg = json.loads((OFF / f"seg/me{year}.json").read_text())
    nsets = len(keys[str(year)])
    for s in range(1, nsets + 1):
        pkey = f"{year}-{s}" if nsets > 1 else str(year)
        count = 0
        for q in seg:
            if year in SPLIT:
                if (q["set"] + 1) // 2 != s:
                    continue
                n = q["n"] + (10 if q["set"] % 2 == 0 else 0)
            else:
                if q["set"] != s:
                    continue
                n = q["n"]
            k = keys[str(year)][s - 1][str(n)]
            a, note = answer(k["t"], k["key"])
            if n <= 10:
                sub, top = "general-aptitude", ga_topic(q["text"])
            elif (pkey, n) in topics:
                sub, top = topics[(pkey, n)]
            else:
                untagged.append((pkey, n)); continue
            text = re.sub(r"\s+", " ", q["text"]).strip()
            img = f'<img class="qimg" src="img/q/{q["img"]}" width="{q["w"]}" height="{q["h"]}" loading="lazy" alt="GATE ME {year} question {n}" style="width:min(100%,{round(q["w"] * 0.74)}px);height:auto">'
            item = {"id": f"me-{pkey}-{n}", "p": pkey, "n": n, "m": k["m"], "t": k["t"], "s": sub, "tp": top,
                    "q": img + f'<span hidden> {html.escape(text)}</span>', "a": a}
            if k["t"] != "nat":
                item["o"] = ["", "", "", ""]
            if note:
                item["nt"] = note
            questions.append(item)
            count += 1
            sol = solutions.get(f"{pkey}-{n}")
            if sol:
                exp[item["id"]] = safe_html(sol)
        papers.append({"key": pkey, "title": f"GATE ME {year}" + (f" Set {s}" if nsets > 1 else ""), "kind": "paper",
                       "year": year, "set": s if nsets > 1 else None, "count": count, "src": SRC + PDF[year]})

data["papers"], data["questions"] = papers, questions
(ROOT / "data/me.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
(ROOT / "data/me-exp.json").write_text(json.dumps(exp, ensure_ascii=False, separators=(",", ":")))
print(f"{len(questions)} questions, {len(papers)} papers, {len(exp)} solutions; untagged: {untagged}")
