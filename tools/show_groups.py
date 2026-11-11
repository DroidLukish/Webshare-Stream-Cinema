# -*- coding: utf-8 -*-
"""
Vypise, jak parser seskupil vysledky ze sondy (jen cteni lokalniho souboru, bez site).

    python tools/show_groups.py                 -> vsechny tituly z posledni sondy
    python tools/show_groups.py "Matrix"        -> jen jeden titul
Vystup se ulozi i do tools/probe_output/groups.txt
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import title_parser as tp  # noqa: E402


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    paths = sorted(glob.glob(os.path.join(HERE, 'probe_output', 'probe_*.json')))
    if not paths:
        raise SystemExit('Chybi probe_output/probe_*.json')
    data = json.load(open(paths[-1], encoding='utf-8'))
    wanted = sys.argv[1:]
    lines = []
    for title, entry in data['titles'].items():
        if wanted and title not in wanted:
            continue
        base = next(s for s in entry['searches'] if s['variant'] == 'puvodni')
        files = base['files']
        groups = tp.group_files(files)
        lines.append('=== %s: %d souboru -> %d po dedupu -> %d skupin' % (
            title, len(files), len(tp.dedupe(files)), len(groups)))
        for g in groups:
            if g.kind == 'other':
                lines.append('  [OSTATNI] %d polozek' % len(g.items))
                for it in g.items[:15]:
                    lines.append('      ' + it.name)
                continue
            head = '%s%s [%s] %d souboru' % (g.title, ' (%s)' % g.year if g.year else '', g.kind, len(g.items))
            lines.append('  ' + head)
            if g.kind == 'series':
                for season, eps in sorted(g.seasons().items()):
                    lines.append('      rada %s: epizody %s' % (season, sorted(e for e in eps if e is not None)))
            for it in g.items[:4]:
                lines.append('      %s   <- %s' % (tp.variant_label(it), it.name[:70]))
    text = '\n'.join(lines)
    print(text)
    with open(os.path.join(HERE, 'probe_output', 'groups.txt'), 'w', encoding='utf-8') as fh:
        fh.write(text)


if __name__ == '__main__':
    main()
