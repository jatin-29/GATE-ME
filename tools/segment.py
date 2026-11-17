#!/usr/bin/env python3
"""Cut an official GATE question-paper PDF into one image per question.

Usage: python3 tools/segment.py paper.pdf out_dir prefix

Finds the "Q.12" / "Q.No. 12" labels in the left margin (from the PDF text layer, or by OCR
when a page is a scan), crops the region between consecutive labels, trims white space and
stacks the pieces of a question that runs over a page break. A question number going back to 1
starts a new set. Writes <out_dir>/<prefix>-s<set>-q<n>.webp and <out_dir>/<prefix>.json with the
text of every question (text layer or OCR) for search and topic tagging.
"""
import json, re, subprocess, sys, tempfile, pathlib, io
import numpy as np
import pymupdf
from PIL import Image

ZOOM = 1.9          # render scale for the saved crops (72 dpi * 1.9)
OCR_ZOOM = 2.8

def ocr_words(img, psm="4"):
    """[(x0, y0, x1, y1, text)] in pixel units of img, via tesseract."""
    with tempfile.NamedTemporaryFile(suffix=".png") as f:
        img.save(f.name)
        out = subprocess.run(["tesseract", f.name, "-", "--psm", psm, "tsv"], capture_output=True, text=True).stdout
    words = []
    for line in out.splitlines()[1:]:
        c = line.split("\t")
        if len(c) == 12 and c[11].strip() and float(c[10]) >= 0:
            x, y, w, h = map(int, c[6:10])
            words.append((x, y, x + w, y + h, c[11].strip()))
    return words

def render(page, zoom):
    pm = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    return Image.frombytes("RGB", (pm.width, pm.height), pm.samples)

def table_labels(img):
    """Scans that set every question in a ruled table: find each table (a long vertical rule in
    the left third of the page) and OCR its top-left cell on its own. -> words in pixel units."""
    a = np.asarray(img.convert("L")) < 140
    H, W = a.shape
    sums = a[:, : int(0.3 * W)].sum(0)
    strong = np.where(sums >= 0.5 * sums.max())[0]
    if not len(strong) or sums.max() < 0.06 * H:
        return []
    xl, xr = int(strong[0]), int(strong[-1])   # table border(s) / label-column rule
    col = a[:, max(xl - 2, 0) : xr + 3].any(1)
    def read(box):
        cell = img.crop(box).convert("L").point(lambda v: 0 if v < 120 else 255)
        if cell.width < 8 or cell.height < 8:
            return None
        cell = cell.resize((cell.width * 2, cell.height * 2))
        with tempfile.NamedTemporaryFile(suffix=".png") as f:
            cell.save(f.name)
            t = subprocess.run(["tesseract", f.name, "-", "--psm", "7"], capture_output=True, text=True).stdout
        m = re.search(r"Q\.? ?[\dlI|OoSs]{1,2}", t)
        return m.group(0).replace(" ", "") if m else None
    out, start = [], None
    for y in range(H + 1):
        on = y < H and col[y]
        if on and start is None:
            start = y
        if not on and start is not None:
            if y - start > 40 * OCR_ZOOM / 2.8:
                y1 = start + int(24 * OCR_ZOOM)
                # the label cell is right of the outer border, or left of the label-column rule
                label = read((xl + 4, start + 5, xl + int(40 * OCR_ZOOM), y1)) or read((max(xl - int(48 * OCR_ZOOM), 0), start + 5, xl - 4, y1))
                # an unreadable cell is kept as "Q?": it is a question start only if a number is missing
                out.append((10, start, 40, start + 20, label or "Q?"))
            start = None
    return out

NUM = r"(\d{1,2})"
def find_events(words, width):
    """Question labels and 'carry N marks' headers on a page: [(y, kind, n)]."""
    words = sorted(words, key=lambda w: (round(w[1] / 4), w[0]))
    ev = []
    for i, w in enumerate(words):
        if w[0] > 0.2 * width:
            continue
        t = w[4].rstrip("_.,:;")
        line = [v for v in words if abs(v[1] - w[1]) < 6]
        nxt = [v for v in line if v[0] > w[0]]
        nxt.sort(key=lambda v: v[0])
        n = None
        fix = lambda d: int(d.translate(str.maketrans("lI|OoSs", "1110055")))
        m = re.fullmatch(r"[QO0]\.? ?" + NUM, t) or re.fullmatch(r"Q[.,]? ?([\dlI|OoSs]{1,2})", t)
        if m:
            n = fix(m.group(1))
        elif re.fullmatch(r"Q|Q\.?(No)?", t.rstrip(".")) and nxt and nxt[0][0] - w[2] < 40:
            m = re.fullmatch(r"([\dlI|OoSs]{1,2})", nxt[0][4].rstrip("_.,:;"))
            if m:
                n = fix(m.group(1))
        if w[4] == "Q?":
            ev.append((w[1], "q", -1)); continue
        if n is None:
            continue
        text = " ".join(v[4] for v in line)
        if len(re.findall(r"\bQ\.? ?\d{1,2}", text)) >= 2 or re.search(r"carr(y|ies)\b.{0,25}mark", text, re.I) or re.search(r"Q\.? ?\d+\s*[-–—to]+\s*Q", text):
            ev.append((w[1], "header", 0))
        else:
            ev.append((w[1], "q", n))
    return ev

def trim(img, pad=6):
    a = np.asarray(img.convert("L"))
    ink = a < 215
    rows = np.where(ink.sum(1) > 0)[0]
    cols = np.where(ink.sum(0) > 0)[0]
    if not len(rows):
        return None
    return img.crop((max(cols[0] - pad, 0), max(rows[0] - pad, 0), min(cols[-1] + pad, img.width), min(rows[-1] + pad, img.height)))

def strip_rules(img):
    """Drop a header/footer rule line sitting at the top or bottom edge of a crop."""
    a = np.asarray(img.convert("L")) < 160
    frac = a.sum(1) / a.shape[1]
    top, bot = 0, a.shape[0]
    for y in range(min(14, bot)):
        if frac[y] > 0.45:
            top = y + 1
    for y in range(bot - 1, max(bot - 15, 0), -1):
        if frac[y] > 0.45:
            bot = y
    if bot - top < 4:
        return img
    return img.crop((0, top, img.width, bot)) if (top or bot != a.shape[0]) else img

def main(pdf, out_dir, prefix):
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(pdf)
    pages = []  # per page: words (in points), events, used_ocr
    cache_file = out / f"{prefix}.ocr.json"
    ocr_cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    for page in doc:
        W = page.rect.width
        words = [(w[0], w[1], w[2], w[3], w[4]) for w in page.get_text("words")]
        ev = find_events(words, W)
        ocr = False
        if not any(k == "q" for _, k, _ in ev):
            key = str(page.number)
            if key not in ocr_cache:
                img = render(page, OCR_ZOOM)
                blank = np.asarray(img.convert("L")).min() >= 200
                ocr_cache[key] = [] if blank else [(a / OCR_ZOOM, b / OCR_ZOOM, c / OCR_ZOOM, d / OCR_ZOOM, t) for a, b, c, d, t in ocr_words(img)]
                cache_file.write_text(json.dumps(ocr_cache))
            ow = [tuple(w) for w in ocr_cache[key]]
            if ow and key + "m" not in ocr_cache:
                # labels set small in a table cell are often missed: read the left margin on its own
                img = render(page, OCR_ZOOM)
                strip = img.crop((0, 0, int(0.24 * img.width), img.height))
                ocr_cache[key + "m"] = [(a / OCR_ZOOM, b / OCR_ZOOM, c / OCR_ZOOM, d / OCR_ZOOM, t) for a, b, c, d, t in ocr_words(strip, "11")]
                cache_file.write_text(json.dumps(ocr_cache))
            if ow and key + "t" not in ocr_cache:
                ocr_cache[key + "t"] = [(a / OCR_ZOOM, b / OCR_ZOOM, c / OCR_ZOOM, d / OCR_ZOOM, t) for a, b, c, d, t in table_labels(render(page, OCR_ZOOM))]
                cache_file.write_text(json.dumps(ocr_cache))
            if ow:
                oe = find_events(ow, W)
                seen = {n for _, k, n in oe if k == "q"}
                for extra in ("t", "m"):
                    oe += [e for e in find_events([tuple(w) for w in ocr_cache[key + extra]], W)
                           if e[1] == "q" and (e[2] < 0 or e[2] not in {n for _, k, n in oe if k == "q"}) and not any(abs(e[0] - y) < 12 for y, _, _ in oe)]
                if len(ow) > len(words):
                    words, ev, ocr = ow, oe, True
        # an answer-key table printed after the questions is not part of the last question
        if sum(w[4] in ("MCQ", "NAT", "MSQ") for w in words) >= 5:
            ev = [(0, "header", 0)]
        pages.append({"words": words, "ev": ev, "ocr": ocr, "H": page.rect.height, "W": W})
        print(f"page {page.number + 1}: {'ocr ' if ocr else ''}{[n for _, k, n in sorted(ev) if k == 'q']}", file=sys.stderr)

    # header / footer bands: words that repeat at the same height on many pages
    def band(sel):
        from collections import Counter
        c = Counter()
        for p in pages:
            qy = [y for y, k, _ in p["ev"]]
            for key in {(round(w[1] / 5), re.sub(r"\d+", "#", w[4])) for w in p["words"] if sel(w, p) and not any(abs(w[1] - y) < 8 for y in qy)}:
                c[key] += 1
        return {k for k, v in c.items() if v >= max(4, 0.4 * len(pages))}
    tops = band(lambda w, p: w[3] < 0.13 * p["H"])
    bots = band(lambda w, p: w[1] > 0.88 * p["H"])
    for p in pages:
        key = lambda w: (round(w[1] / 5), re.sub(r"\d+", "#", w[4]))
        qy = [y for y, k, _ in p["ev"]]
        ok = lambda w: not any(abs(w[1] - y) < 8 for y in qy)
        t = [w[3] for w in p["words"] if w[3] < 0.13 * p["H"] and key(w) in tops and ok(w)]
        b = [w[1] for w in p["words"] if w[1] > 0.88 * p["H"] and key(w) in bots and ok(w)]
        p["top"] = max(t) + 3 if t else 0
        p["bot"] = min(b) - 3 if b else p["H"]

    # reading-order list of events, then one region per question
    seq = [(i, y, k, n) for i, p in enumerate(pages) for y, k, n in sorted(p["ev"]) if k != "q" or p["top"] <= y + 6 and y <= p["bot"]]
    cache = {}
    def page_img(i):
        if i not in cache:
            cache.clear(); cache[i] = render(doc[i], ZOOM)
        return cache[i]
    result, cur_set, last = [], 1, 0
    for j, (pi, y, kind, n) in enumerate(seq):
        if kind != "q":
            continue
        if 0 < n <= last and n <= 2 and last > 5:   # numbering restarted → next set (or GA → subject section)
            cur_set += 1
        elif not last < n <= last + 4:
            # unreadable or misread label on a scan: it is the next question if exactly one number
            # is missing before the next readable label, or if its units digit fits
            nxt = next((m for (_, _, k, m) in seq[j + 1:] if k == "q" and m > 0), None)
            if not pages[pi]["ocr"]:
                continue
            if n > 0:
                guess = [c for c in range(last + 1, last + 5) if c % 10 == n % 10]
                n = guess[0] if guess else last + 1   # a readable label is a question start; trust the order
            elif nxt == last + 2:
                n = last + 1
            else:
                continue
            if n != last + 1:
                print(f"!! set {cur_set}: Q{n} follows Q{last} (page {pi + 1})", file=sys.stderr)
        elif n != last + 1:
            print(f"!! set {cur_set}: Q{n} follows Q{last} (page {pi + 1})", file=sys.stderr)
        last = n
        end = seq[j + 1] if j + 1 < len(seq) else (len(pages) - 1, pages[-1]["bot"], "end", 0)
        pieces, text = [], []
        for i in range(pi, end[0] + 1):
            p = pages[i]
            y0 = y - 4 if i == pi else p["top"]
            y1 = end[1] - 3 if i == end[0] else p["bot"]
            if y1 - y0 < 4:
                continue
            im = page_img(i)
            c = trim(im.crop((0, int(y0 * ZOOM), im.width, int(y1 * ZOOM))))
            if c is not None:
                c = trim(strip_rules(c))
            if c is not None and c.height > 6:
                pieces.append(c)
            text += [w[4] for w in sorted(p["words"], key=lambda w: (round(w[1] / 4), w[0])) if y0 - 2 <= w[1] < y1]
        if not pieces:
            print(f"!! set {cur_set} Q{n}: empty", file=sys.stderr); continue
        Wd = max(c.width for c in pieces)
        canvas = Image.new("RGB", (Wd, sum(c.height for c in pieces) + 10 * (len(pieces) - 1)), "white")
        yy = 0
        for c in pieces:
            canvas.paste(c, (0, yy)); yy += c.height + 10
        txt = " ".join(text)
        if len(txt) < 60:   # image-only question body: OCR the crop for search / tagging
            big = canvas.resize((int(canvas.width * 1.5), int(canvas.height * 1.5)))
            txt = " ".join(w[4] for w in ocr_words(big))
        name = f"{prefix}-s{cur_set}-q{n}.webp"
        canvas.save(out / name, "WEBP", quality=72, method=6)
        result.append({"set": cur_set, "n": n, "img": name, "w": canvas.width, "h": canvas.height, "text": txt})
    (out / f"{prefix}.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))
    from collections import Counter
    print(prefix, dict(Counter(r["set"] for r in result)))

if __name__ == "__main__":
    main(*sys.argv[1:4])
