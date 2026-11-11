# -*- coding: utf-8 -*-
"""
Udela totez co plugin pri hledani (az N stran po 100 souborech, seskupeni) a vse
ulozi do textoveho souboru. Jen cteni, nic nestahuje.

    python search_like_plugin.py "star wars"          (3 strany jako plugin)
    python search_like_plugin.py "star wars" 10       (10 stran = az 1000 souboru)
    python search_like_plugin.py "star wars" 10 offline   (znovu seskupi ulozena data, bez prihlaseni)

Vystup: tools/probe_output/search_<dotaz>.txt (skupiny + nazvy) a .json (surova data ze serveru)
"""
import getpass
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from probe_webshare import login, search  # noqa: E402
import title_parser as tp  # noqa: E402

PAGE = 100


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    if len(sys.argv) < 2:
        raise SystemExit('Pouziti: python search_like_plugin.py "dotaz" [pocet_stran]')
    query = sys.argv[1]
    pages = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    safe = re.sub(r'[^\w]+', '_', query.lower()).strip('_')
    out_dir = os.path.join(HERE, 'probe_output')
    os.makedirs(out_dir, exist_ok=True)
    raw_path = os.path.join(out_dir, 'search_%s.json' % safe)
    offline = len(sys.argv) > 3 and sys.argv[3] == 'offline'

    files, total = [], 0
    if offline:
        with open(raw_path, encoding='utf-8') as fh:
            saved = json.load(fh)
        files, total = saved['files'], saved['total']
        print('Nacteno z %s (%d souboru)' % (raw_path, len(files)))
    else:
        user = os.environ.get('WS_USER') or input('Webshare uzivatel: ').strip()
        password = os.environ.get('WS_PASS') or getpass.getpass('Webshare heslo (nezobrazuje se): ')
        token = login(user, password)
        del password
        for page in range(pages):
            res = search(token, query, sort='', limit=PAGE, offset=page * PAGE, category='video')
            if res.get('status') != 'OK':
                print('Chyba serveru na strane %d: %s' % (page + 1, res.get('raw', '')[:200]))
                break
            total = res['total']
            files.extend(res['files'])
            print('strana %d: %d souboru (celkem na serveru %s)' % (page + 1, len(res['files']), total))
            if not res['files'] or (page + 1) * PAGE >= total:
                break
        with open(raw_path, 'w', encoding='utf-8') as fh:
            json.dump({'query': query, 'total': total, 'files': files}, fh, ensure_ascii=False)

    unique = tp.dedupe(files)
    groups = tp.group_files(files)
    lines = ['Dotaz: %s | na serveru: %s | nacteno: %d | po dedupu: %d | skupin: %d' % (
        query, total, len(files), len(unique), len(groups)), '']
    for g in groups:
        head = '[%s] %s%s - %d souboru' % (g.kind, g.title or '(ostatni)',
                                          ' (%s)' % g.year if g.year else '', len(g.items))
        lines.append(head)
        if g.kind == 'series':
            for season, eps in sorted(g.seasons().items()):
                lines.append('    rada %s: epizody %s' % (season, sorted(e for e in eps if e is not None)))
        for it in g.items:
            lines.append('    %s' % it.name)
        lines.append('')
    lines.append('--- soubory, jejichz nazev obsahuje episod/epizod/star wars ---')
    for f in unique:
        if re.search(r'episod|epizod|star.?wars', f.get('name') or '', re.I):
            lines.append(f.get('name') or '')

    path = os.path.join(out_dir, 'search_%s.txt' % safe)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines))
    print('\nSkupin: %d. Ulozeno: %s' % (len(groups), path))


if __name__ == '__main__':
    main()
