# -*- coding: utf-8 -*-
"""
Sestavi instalacni zip pluginu pro Kodi (jen soubory, ktere plugin potrebuje).

    python tools/build_zip.py [cilova_slozka]

Vychozi cilova slozka je Plocha. Vznikne plugin.video.webshare.streamcinema-<verze>.zip
s koreno vou slozkou plugin.video.webshare.streamcinema (lomitka v ceste jsou spravne pro Kodi).
"""
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON_ID = 'plugin.video.webshare.streamcinema'
FILES = ['addon.xml', 'main.py', 'streamcinema.py', 'ws_api.py', 'title_parser.py',
         'md5crypt.py', 'LICENSE.txt']
DIRS = ['resources']


def main():
    with open(os.path.join(ROOT, 'addon.xml'), encoding='utf-8') as fh:
        version = re.search(r'<addon[^>]*\sversion="([^"]+)"', fh.read()).group(1)
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser('~'), 'Desktop')
    out = os.path.join(target, '%s-%s.zip' % (ADDON_ID, version))

    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name in FILES:
            zf.write(os.path.join(ROOT, name), '%s/%s' % (ADDON_ID, name))
        for folder in DIRS:
            for base, _dirs, names in os.walk(os.path.join(ROOT, folder)):
                for name in names:
                    full = os.path.join(base, name)
                    rel = os.path.relpath(full, ROOT).replace(os.sep, '/')
                    zf.write(full, '%s/%s' % (ADDON_ID, rel))
    print('Vytvoreno: ' + out)


if __name__ == '__main__':
    main()
