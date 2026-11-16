"""Write translated CSV cells back into ETC.BIN tables, touching only translated cells.

The CSVs are spreadsheet exports (Shift-JIS, CRLF, RFC-4180 quoting). A span-aware tokenizer
records each cell's byte range; translated cells are replaced in place (quoted when they
contain a comma, quote or line break) and every other byte stays identical.

Translations: work/translation/en/csv/<FILE>.json entries {id: "FILE.CSV:row:col", en}.
Budget: English bytes must not exceed the column's longest original value ('max'), which is
what the game's fixed-size fields were sized for. Over-budget cells are reported and skipped.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import textcodec

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(ROOT, 'work', 'source', 'arc', 'ETC')
TR = os.path.join(ROOT, 'work', 'translation', 'en', 'csv')


def spans(t):
    """Yield (row, col, start, end) of every cell in text t (end exclusive, quotes included)."""
    i, n, row, col = 0, len(t), 0, 0
    while i <= n:
        start = i
        if i < n and t[i] == '"':
            i += 1
            while i < n:
                if t[i] == '"':
                    if i + 1 < n and t[i + 1] == '"':
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            while i < n and t[i] not in ',\r\n':
                i += 1
        else:
            while i < n and t[i] not in ',\r\n':
                i += 1
        yield row, col, start, i
        if i >= n:
            break
        if t[i] == ',':
            col += 1
            i += 1
        else:
            if t[i] == '\r' and i + 1 < n and t[i + 1] == '\n':
                i += 2
            else:
                i += 1
            row += 1
            col = 0
            if i >= n:
                break


# The game's CSV reader does not follow RFC-4180: its line reader drops every '"' (it only uses them to
# join quoted multi-line cells) and its cell splitter cuts at every ',' -- even inside quotes. Some
# original designer columns rely on that split (PLACE_NM col 2), so the reader is left as it is.
# English commas and quote marks are written as 0x1F / 0x1E instead; the cell copy routine
# (patches.csv_text, 0x08909B44) turns them back. Cells are then quoted only for line breaks.
COMMA, QUOTE, NEWLINE = '\x1f', '\x1e', '\x1d'

# The line reader also drops line breaks inside cells, so the Japanese description boxes were laid out
# by byte count. These columns are now word-wrapped by pixel width in the game (vwf.apply_wrap); a line
# break kept as NEWLINE (0x1D, stored as 0x0A by the cell copy) starts a new row. Breaks that only copy
# the Japanese line layout (mid-sentence) become spaces; a blank line, a break after sentence-ending
# punctuation and a break after a recipe line ('A x B') are kept. Other columns: every break is a space.
WRAP_COLS = {('EVENT_TEXT.CSV', 6), ('EVENT_TEXT.CSV', 7), ('EVENT_TEXT.CSV', 8), ('RENKIN_TXT.CSV', 3),
             ('MON_TEXT.CSV', 1), ('ITEM_TEXT.CSV', 1)}
BREAK_AFTER = tuple('.!?:\'"~)-')
RECIPE = re.compile(r'\S x \S')


def flow(s, keep):
    if not keep:
        return re.sub(r' *\n+ *', ' ', s)
    # restricted lore entries (MON_TEXT 315-331) open with 'Not for loan:' and a '------.---' line: one row
    s = s.replace('Not for loan:\n------.---', 'Not for loan: ------.---')
    paras = []
    for p in re.split(r' *\n\s*\n *', s):
        lines = [l.strip() for l in p.split('\n')]
        acc = lines[0]
        for prev, nxt in zip(lines, lines[1:]):
            acc += (NEWLINE if prev.endswith(BREAK_AFTER) or RECIPE.search(prev) else ' ') + nxt
        paras.append(acc)
    return (NEWLINE * 2).join(paras)


def quote(s):
    s = s.replace(',', COMMA).replace('"', QUOTE)
    if any(c in s for c in '\r\n'):
        return '"' + s + '"'
    return s


def prepare(en):
    for k, v in textcodec.FIX.items():
        en = en.replace(k, v)
    return en


def build_file(fname, entries, report):
    raw = open(os.path.join(SRC, fname), 'rb').read()
    t = raw.decode('cp932')
    tr = {}
    for e in entries:
        en = (e.get('en') or '').strip('\n')
        if not en:
            continue
        _, r, c = e['id'].rsplit(':', 2)
        en = flow(prepare(en), (fname, int(c)) in WRAP_COLS)
        if len(en.encode('cp932', 'replace')) > e['max']:
            report.append('%s: %d bytes > column max %d' % (e['id'], len(en.encode('cp932')), e['max']))
            continue
        tr[(int(r), int(c))] = en
    if not tr:
        return None, 0
    out, pos, n = [], 0, 0
    for r, c, a, b in spans(t):
        if (r, c) in tr:
            out.append(t[pos:a])
            out.append(quote(tr[(r, c)]).replace('\n', '\r\n'))
            pos = b
            n += 1
    out.append(t[pos:])
    return ''.join(out).encode('cp932'), n


def apply(info, report=None):
    report = [] if report is None else report
    files = {}
    total = 0
    for f in sorted(os.listdir(SRC)):
        if not f.endswith('.CSV'):
            continue
        p = os.path.join(TR, f.replace('.CSV', '.json'))
        if not os.path.exists(p):
            continue
        data, n = build_file(f, json.load(open(p, encoding='utf-8')), report)
        if data is not None:
            files[f] = data
            total += n
    if files:
        info['archives'].setdefault('ETC', {}).update(files)
    print('  csv: %d cells in %d files, %d over budget' % (total, len(files), len(report)))
    for line in report[:20]:
        print('   ', line)
    return report


if __name__ == '__main__':
    # self-test: tokenizer reproduces cell values of the stdlib csv reader
    import csv, io
    bad = 0
    for f in sorted(os.listdir(SRC)):
        if not f.endswith('.CSV'):
            continue
        t = open(os.path.join(SRC, f), 'rb').read().decode('cp932')
        ref = list(csv.reader(io.StringIO(t, newline='')))
        mine = {}
        for r, c, a, b in spans(t):
            v = t[a:b]
            if v.startswith('"'):
                v = v[1:v.rindex('"')].replace('""', '"')
            mine[(r, c)] = v
        for r, row in enumerate(ref):
            for c, v in enumerate(row):
                if mine.get((r, c)) != v:
                    bad += 1
                    if bad < 5:
                        print('mismatch', f, r, c)
    print('tokenizer mismatches:', bad)
