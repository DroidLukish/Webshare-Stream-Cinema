# -*- coding: utf-8 -*-
"""
Sonda c. 2: hleda titulky (.srt) k videim z predchozi sondy. Jen cteni.

Pro kazde z nekolika videi z nejnovejsiho probe_*.json zkusi:
  A) dotaz = nazev souboru bez pripony (titulky casto nesou nazev vydani),
  B) dotaz = "<zkraceny titul> cz srt"
oba BEZ kategorie (kategorie 'video' titulky nenajde) a nechá jen soubory typu srt/sub.
Vysledek: tools/probe_output/subs_<cas>.json + prehled na obrazovce.

Spusteni:  python probe_subtitles.py
"""
import getpass
import glob
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from probe_webshare import login, search, ascii_fold  # noqa: E402

PER_TITLE = 4          # kolik videi na titul
SUB_TYPES = ('srt', 'sub', 'ass', 'ssa', 'txt')


def stem(name):
    return re.sub(r'\.[A-Za-z0-9]{2,4}\s*$', '', name)


def short_title(name):
    s = ascii_fold(stem(name))
    s = re.split(r'[\(\[]|\b(19|20)\d\d\b', s)[0]
    s = re.sub(r'[._\-]+', ' ', s)
    return ' '.join(s.split()[:4]).strip()


def subs_only(res):
    return [f for f in res.get('files', []) if (f.get('type') or '').strip().lower() in SUB_TYPES]


def main():
    probes = sorted(glob.glob(os.path.join(HERE, 'probe_output', 'probe_*.json')))
    if not probes:
        raise SystemExit('Nejdriv spust probe_webshare.py')
    data = json.load(open(probes[-1], encoding='utf-8'))

    user = os.environ.get('WS_USER') or input('Webshare uzivatel: ').strip()
    password = os.environ.get('WS_PASS') or getpass.getpass('Webshare heslo (nezobrazuje se): ')
    token = login(user, password)
    del password
    print('Prihlaseno.')

    out = {'created': time.strftime('%Y-%m-%d %H:%M:%S'), 'items': []}
    for title, entry in data['titles'].items():
        base = next((s for s in entry['searches'] if s['variant'] == 'puvodni'), None)
        videos, seen = [], set()
        for f in (base or {}).get('files', []):
            if f['name'] not in seen and (f.get('type') or '').strip().lower() in ('mkv', 'avi', 'mp4'):
                seen.add(f['name'])
                videos.append(f)
            if len(videos) >= PER_TITLE:
                break
        print('\n=== %s ===' % title)
        for v in videos:
            qa = stem(v['name'])
            qb = short_title(v['name']) + ' cz srt'
            ra = search(token, qa, category='')
            rb = search(token, qb, category='')
            sa, sb = subs_only(ra), subs_only(rb)
            print('- %s' % v['name'][:80])
            print('    A (nazev vydani): srt=%d z %d  | prvni: %s' % (
                len(sa), len(ra.get('files', [])), [f['name'][:50] for f in sa[:3]]))
            print('    B ("%s"): srt=%d z %d  | prvni: %s' % (
                qb, len(sb), len(rb.get('files', [])), [f['name'][:50] for f in sb[:3]]))
            out['items'].append({'video': v['name'], 'query_a': qa, 'query_b': qb,
                                 'subs_a': sa, 'subs_b': sb,
                                 'total_a': ra.get('total'), 'total_b': rb.get('total')})

    path = os.path.join(HERE, 'probe_output', 'subs_%s.json' % time.strftime('%Y%m%d_%H%M%S'))
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print('\nUlozeno: ' + path)


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    main()
