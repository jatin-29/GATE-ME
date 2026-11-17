# GATE ME PYQ

Topic-wise practice site for GATE Mechanical Engineering previous-year questions. Static site, no build step; progress is stored in the browser.

- `index.html`, `js/`, `css/` — the app (same frontend as the GATE EC site)
- `data/me.json` — subjects, topics, papers and questions; `data/me-exp.json` — solutions keyed by question id
- `img/` — figures referenced by questions
- `img/q/` — one image per question, cut from the official question papers
- `tools/segment.py` — cuts an official question-paper PDF into one image per question (needs PyMuPDF, Pillow, numpy and, for scanned papers, tesseract)
- `tools/build.py` — assembles `data/me.json` from `tools/official/` (question list, official answer keys, topic tags, solutions)
- `tools/import.py` — merges a hand-written list of text questions into the data files (format in the script's docstring)

## Source of the questions

Questions and answer keys come from the official GATE Mechanical Engineering papers for 2019–2026 (two sets in 2019–2022), as published on the GATE 2026 site: https://gate2026.iitg.ac.in/download.html. Each question is shown as an image of the official paper; the answer checked is the official key (including "marks to all" questions, which have no single answer). Topic tags were assigned by hand from the question text.

Run locally:

```bash
python3 -m http.server 8000
```

Rebuild the data after changing anything in `tools/official/`:

```bash
python3 tools/build.py
```

Deployment: `.github/workflows/pages.yml` publishes the repository to GitHub Pages on every push (Settings → Pages → Source must be "GitHub Actions").
