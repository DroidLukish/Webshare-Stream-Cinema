# -*- coding: utf-8 -*-
"""
Jednorazova sonda pro Webshare API (jen cteni, nic nestahuje ani nemeni).

Co dela:
  1) prihlasi se (heslo se pta pres getpass, nikam se neuklada),
  2) pro kazdy titul zkusi vice variant dotazu (s diakritikou, bez, s teckami),
  3) pro prvni nalezene soubory zavola similar_files,
  4) vse ulozi do tools/probe_output/probe_<cas>.json (token se NEUKLADA).

Spusteni (z teto slozky, Python 3.8+, bez dalsich knihoven):
  python probe_webshare.py
nebo s vlastnimi tituly:
  python probe_webshare.py "Matrix" "Red Dwarf"
"""
import getpass
import hashlib
import json
import os
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # kvuli md5crypt.py v koreni projektu
from md5crypt import md5crypt  # noqa: E402

API = 'https://webshare.cz/api/'
REALM = ':Webshare:'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36')
DEFAULT_TITLES = ['Matrix', 'Red Dwarf', 'Příběh hraček', 'Pán prstenů']
PAUSE = 0.6  # pauza mezi dotazy, at server nezatezujeme


def call(fn, data):
    body = urllib.parse.urlencode(data).encode('utf-8')
    req = urllib.request.Request(API + fn + '/', data=body, headers={
        'User-Agent': UA, 'Referer': 'https://webshare.cz',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    time.sleep(PAUSE)
    return raw


def todict(el):
    out = {}
    for e in el:
        out[e.tag] = e.text if len(list(e)) == 0 else todict(e)
    return out


def login(user, password):
    xml = ET.fromstring(call('salt', {'username_or_email': user}))
    if xml.find('status').text != 'OK':
        raise SystemExit('salt selhal')
    salt = xml.find('salt').text
    enc = hashlib.sha1(md5crypt(password.encode('utf-8'), salt.encode('utf-8')).encode('utf-8')).hexdigest()
    digest = hashlib.md5((user + REALM + enc).encode('utf-8')).hexdigest()
    xml = ET.fromstring(call('login', {'username_or_email': user, 'password': enc,
                                       'digest': digest, 'keep_logged_in': 1}))
    if xml.find('status').text != 'OK':
        raise SystemExit('Prihlaseni selhalo (spatne jmeno/heslo?)')
    return xml.find('token').text


def ascii_fold(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def variants(title):
    a = ascii_fold(title)
    v = [('puvodni', title)]
    if a != title:
        v.append(('bez_diakritiky', a))
    v.append(('s_teckami', a.replace(' ', '.')))
    v.append(('s_s01e01', a + ' s01e01'))
    # unikatni, zachovat poradi
    seen, out = set(), []
    for label, q in v:
        if q not in seen:
            seen.add(q)
            out.append((label, q))
    return out


def search(token, what, sort='', limit=100, offset=0, category='video', fn='search'):
    raw = call(fn, {'what': what, 'sort': sort, 'limit': limit, 'offset': offset,
                    'category': category, 'wst': token})
    xml = ET.fromstring(raw)
    status = xml.find('status').text
    res = {'status': status, 'query': what, 'sort': sort, 'category': category}
    if status != 'OK':
        res['raw'] = raw.decode('utf-8', 'replace')
        return res
    t = xml.find('total')
    res['total'] = int(t.text) if t is not None and t.text else 0
    if fn == 'search':
        res['files'] = [todict(f) for f in xml.iter('file')]
    else:
        for part in ('subtitles', 'next_episode', 'similar'):
            node = xml.find(part)
            res[part] = [todict(f) for f in node.iter('file')] if node is not None else None
    return res


def main():
    titles = sys.argv[1:] or DEFAULT_TITLES
    user = os.environ.get('WS_USER') or input('Webshare uzivatel: ').strip()
    password = os.environ.get('WS_PASS') or getpass.getpass('Webshare heslo (nezobrazuje se): ')
    token = login(user, password)
    del password
    print('Prihlaseno.')

    out = {'created': time.strftime('%Y-%m-%d %H:%M:%S'), 'titles': {}}
    for title in titles:
        print('\n=== %s ===' % title)
        entry = {'searches': [], 'similar': []}
        vs = variants(title)
        for label, q in vs:
            r = search(token, q)
            r['variant'] = label
            entry['searches'].append(r)
            print('  %-15s %-30s status=%s total=%s vraceno=%s' % (
                label, q, r['status'], r.get('total'), len(r.get('files', []))))
        # dalsi razeni jen pro prvni variantu
        for sort in ('rating', 'largest', 'recent'):
            r = search(token, vs[0][1], sort=sort)
            r['variant'] = 'razeni_' + sort
            entry['searches'].append(r)
            print('  razeni %-8s total=%s vraceno=%s' % (sort, r.get('total'), len(r.get('files', []))))

        # similar_files pro 3 nalezene soubory (podle nazvu souboru)
        base = next((s for s in entry['searches'] if s.get('files')), None)
        if base:
            for f in base['files'][:3]:
                sim = search(token, f['name'], fn='similar_files')
                sim['from_file'] = f['name']
                entry['similar'].append(sim)
                print('  similar_files pro "%s": titulky=%s dalsi_epizoda=%s podobne=%s' % (
                    f['name'][:60],
                    None if sim.get('subtitles') is None else len(sim['subtitles']),
                    None if sim.get('next_episode') is None else len(sim['next_episode']),
                    None if sim.get('similar') is None else len(sim['similar'])))
        out['titles'][title] = entry

    outdir = os.path.join(HERE, 'probe_output')
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, 'probe_%s.json' % time.strftime('%Y%m%d_%H%M%S'))
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print('\nUlozeno: ' + path)


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    main()
