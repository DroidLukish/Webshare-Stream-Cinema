# -*- coding: utf-8 -*-
"""
Sestavi instalacni zip pluginu pro Kodi (jen soubory, ktere plugin potrebuje).

    python tools/build_zip.py [cilova_slozka]

Vychozi cilova slozka je Plocha. Vznikne plugin.video.webshare.streamcinema-<verze>.zip
s korenovou slozkou plugin.video.webshare.streamcinema (lomitka v ceste jsou spravne pro Kodi).
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


def addon_version(addon_xml_path):
    with open(addon_xml_path, encoding='utf-8') as fh:
        return re.search(r'<addon[^>]*\sversion="([^"]+)"', fh.read()).group(1)


def build_addon_zip(target_dir):
    """Sestavi zip hlavniho doplnku do target_dir, vrati (cesta, verze)."""
    version = addon_version(os.path.join(ROOT, 'addon.xml'))
    os.makedirs(target_dir, exist_ok=True)
    out = os.path.join(target_dir, '%s-%s.zip' % (ADDON_ID, version))

    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name in FILES:
            zf.write(os.path.join(ROOT, name), '%s/%s' % (ADDON_ID, name))
        for folder in DIRS:
            for base, _dirs, names in os.walk(os.path.join(ROOT, folder)):
                for name in names:
                    full = os.path.join(base, name)
                    rel = os.path.relpath(full, ROOT).replace(os.sep, '/')
                    zf.write(full, '%s/%s' % (ADDON_ID, rel))
    return out, version


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser('~'), 'Desktop')
    out, _version = build_addon_zip(target)
    print('Vytvoreno: ' + out)


if __name__ == '__main__':
    main()
