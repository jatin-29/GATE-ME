# GATE ME PYQ

Topic-wise practice site for GATE Mechanical Engineering previous-year questions. Static site, no build step; progress is stored in the browser.

- `index.html`, `js/`, `css/` — the app (same frontend as the GATE EC site)
- `data/me.json` — subjects, topics, papers and questions; `data/me-exp.json` — solutions keyed by question id
- `img/` — figures referenced by questions
- `tools/import.py` — merges a list of questions into the data files (format in the script's docstring)

Run locally:

```bash
python3 -m http.server 8000
```

Add questions:

```bash
python3 tools/import.py questions.json
```

Deployment: `.github/workflows/pages.yml` publishes the repository to GitHub Pages on every push (Settings → Pages → Source must be "GitHub Actions").
