#!/usr/bin/env python3
"""Build the Story DNA static site from markdown cards and reports."""
import json, re, html
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
OUT = ROOT / "site"

def md_inline(s):
    s = html.escape(s)
    s = re.sub(r'\[([^\]]+)\]\((https?://[^\s)]+)\)', r'<a href="\2">\1</a>', s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', s)
    return s

def render_md(text):
    """Minimal markdown -> HTML for our controlled content."""
    out, in_list = [], False
    for block in re.split(r'\n\n+', text.strip()):
        if not block.strip():
            continue
        lines = block.splitlines()
        if block.startswith('# '):
            out.append(f'<h1>{md_inline(block[2:])}</h1>'); continue
        if block.startswith('## '):
            out.append(f'<h2>{md_inline(block[3:])}</h2>'); continue
        if block.startswith('### '):
            out.append(f'<h3>{md_inline(block[4:])}</h3>'); continue
        if all(re.match(r'^- ', l) for l in lines):
            items = ''.join(f'<li>{md_inline(l[2:])}</li>' for l in lines)
            out.append(f'<ul>{items}</ul>'); continue
        if all(re.match(r'^\d+\. ', l) for l in lines):
            items = ''.join(f'<li>{md_inline(re.sub(chr(94)+"\\\\d+\\\\. ","",l))}</li>' for l in lines)
            out.append(f'<ol>{items}</ol>'); continue
        out.append(f'<p>{md_inline(" ".join(lines))}</p>')
    return '\n'.join(out)

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Story DNA</title>
<meta name="description" content="{desc}">
<link rel="stylesheet" href="{root}assets/style.css?v=3">
<link rel="icon" href="data:,">
</head>
<body>
<header class="site-header">
  <a class="brand" href="{root}index.html">Story DNA</a>
  <nav>
    <a href="{root}index.html">Library</a>
    <a href="{root}reports/worldbuilding.html">Worldbuilding</a>
    <a href="{root}reports/characters.html">Characters</a>
    <a href="{root}reports/storytelling.html">Storytelling</a>
  </nav>
</header>
<main class="wrap">
{body}
</main>
<footer class="site-footer">
  <p>41 favorite works · narrative DNA · analysis is interpretation, personal appeal sections are hypotheses</p>
</footer>
</body>
</html>
"""

def page(title, desc, body, root=""):
    return PAGE.format(title=html.escape(title), desc=html.escape(desc), body=body, root=root)

def card_sections(text):
    """Split a card markdown into (title, dict of sections)."""
    m = re.match(r'^## ([^\n]+)\n+(.*)', text.strip(), re.S)
    title, body = m.group(1), m.group(2)
    sections = []
    cur_label, cur_lines = None, []
    for line in body.splitlines():
        lm = re.match(r'\*\*(.+?)(?::|\.)?\*\*\s*(.*)', line)
        if lm:
            if cur_label:
                sections.append((cur_label, cur_lines))
            cur_label = lm.group(1).rstrip('.:')
            cur_lines = [lm.group(2)]
        elif line.strip():
            cur_lines.append(line.strip())
    if cur_label:
        sections.append((cur_label, cur_lines))
    return title, sections

def build():
    (OUT / "works").mkdir(parents=True, exist_ok=True)
    (OUT / "reports").mkdir(parents=True, exist_ok=True)
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    (OUT / "assets" / "style.css").write_text((ROOT / "style.css").read_text())

    order = json.loads((CONTENT / "works-order.json").read_text())
    cards = []
    for entry in order:
        f = CONTENT / "works" / f"{entry['slug']}.md"
        if not f.exists():
            raise SystemExit(f"missing card: {f}")
        title, sections = card_sections(f.read_text())
        dna = next((v for k, v in sections if k == 'DNA sentence'), [''])
        tags = next((v for k, v in sections if k.lower().startswith('tags')), [])
        search_blob = ' '.join([entry['title'], title] + dna + tags).lower()
        cats = entry.get('cats', [])
        cards.append({**entry, 'display': title, 'sections': sections,
                      'dna': ' '.join(dna), 'tags': tags, 'search': search_blob, 'cats': cats})

    # individual work pages
    for c in cards:
        parts = [f'<nav class="crumbs"><a href="../index.html">Library</a> / {html.escape(c["display"])}</nav>',
                 f'<h1>{html.escape(c["display"])}</h1>',
                 f'<p class="dna">{md_inline(c["dna"])}</p>']
        for label, lines in c['sections']:
            if label == 'DNA sentence':
                continue
            if any(l.startswith('- ') for l in lines):
                items = ''.join(f'<li>{md_inline(l[2:])}</li>' for l in lines if l.strip())
                body_html = f'<ul>{items}</ul>'
            else:
                body_html = f'<p>{md_inline(" ".join(lines))}</p>'
            cls = 'note' if 'Why it may matter' in label else 'sec'
            parts.append(f'<section class="{cls}"><h2>{html.escape(label)}</h2>{body_html}</section>')
        (OUT / "works" / f"{c['slug']}.html").write_text(
            page(c['display'], c['dna'][:150], '\n'.join(parts), root="../"))

    # index
    all_cats = sorted({c for c2 in cards for c in c2['cats']})
    chips = ''.join(
        f'<button class="chip" data-cat="{html.escape(c)}">{html.escape(c)}</button>'
        for c in all_cats)
    lis = []
    for i, c in enumerate(cards, 1):
        lis.append(f'''<a class="card" href="works/{c['slug']}.html" data-cats="{html.escape(' '.join(c['cats']))}" data-search="{html.escape(c['search'])}">
  <span class="num">{i:02d}</span>
  <span class="t">{html.escape(c['display'])}</span>
  <span class="cats">{' '.join(html.escape(x) for x in c['cats'])}</span>
  <span class="d">{md_inline(c['dna'])}</span>
</a>''')
    idx = f'''<h1>Story DNA</h1>
<p class="lede">A reference library of {len(cards)} favorite works — what makes each of them tick, and what they teach about worldbuilding, characters, and storytelling.</p>
<p class="lede small">Each card is a critical reading. The "why it may matter to you" sections are hypotheses, not claims.</p>
<div class="filters">
  <input id="search" type="search" placeholder="Search works, DNA, tags…" autocomplete="off">
  <div class="chips"><button class="chip active" data-cat="">All</button>{chips}</div>
</div>
<div class="grid" id="grid">{''.join(lis)}</div>
<p class="lede small" id="empty" style="display:none">No works match — try a different search or category.</p>
<script>
(function () {{
  var q = document.getElementById('search');
  var grid = document.getElementById('grid');
  var empty = document.getElementById('empty');
  var cards = Array.prototype.slice.call(grid.children);
  var cat = '';
  var chips = Array.prototype.slice.call(document.querySelectorAll('.chip'));
  chips.forEach(function (ch) {{
    ch.addEventListener('click', function () {{
      cat = ch.dataset.cat;
      chips.forEach(function (x) {{ x.classList.toggle('active', x === ch); }});
      apply();
    }});
  }});
  function apply() {{
    var needle = q.value.trim().toLowerCase();
    var shown = 0;
    cards.forEach(function (card) {{
      var okCat = !cat || (card.dataset.cats || '').split(' ').indexOf(cat) !== -1;
      var okQ = !needle || (card.dataset.search || '').indexOf(needle) !== -1;
      var show = okCat && okQ;
      card.style.display = show ? '' : 'none';
      if (show) shown++;
    }});
    empty.style.display = shown ? 'none' : '';
  }}
  q.addEventListener('input', apply);
}})();
</script>'''
    (OUT / "index.html").write_text(page("Story DNA · Library", "Narrative DNA of 41 favorite works", idx))

    # retired slugs: emit redirect pages so old links keep working
    for retired, target in {'space-jam': 'time-jam'}.items():
        (OUT / "works" / f"{retired}.html").write_text(
            f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            f'<meta http-equiv="refresh" content="0; url={target}.html">'
            f'<link rel="canonical" href="{target}.html">'
            f'<title>Moved · Story DNA</title></head><body>'
            f'<p>Renamed — see <a href="{target}.html">{target}</a>.</p></body></html>')
    for slug, title in [("worldbuilding", "Worldbuilding Report"),
                        ("characters", "Character Building & Development"),
                        ("storytelling", "Storytelling Report")]:
        f = CONTENT / "reports" / f"{slug}.md"
        body = render_md(f.read_text())
        (OUT / "reports" / f"{slug}.html").write_text(
            page(title, title, f'<nav class="crumbs"><a href="../index.html">Library</a> / Reports</nav>\n{body}', root="../"))

    print(f"built {len(cards)} work pages + index + 3 reports")

if __name__ == "__main__":
    build()
