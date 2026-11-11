# -*- coding: utf-8 -*-
"""
Vygeneruje obsah Kodi repozitare ve slozce repo/ (pro hostovani na GitHubu):

    repo/addons.xml
    repo/addons.xml.md5
    repo/zips/<id>/<id>-<verze>.zip        (doplnek i repozitarovy doplnek)
    repo/zips/<id>/resources/icon.png      (ikona doplnku; repozitar: icon.png)

Spusteni po kazde zmene verze v addon.xml:

    python tools/make_repo.py

Pak: git add -A, git commit, git push. Kodi si novou verzi stahne samo (verze musi byt vyssi).
"""
import hashlib
import os
import re
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_zip  # noqa: E402

ROOT = build_zip.ROOT
REPO_DIR = os.path.join(ROOT, 'repo')
ZIPS_DIR = os.path.join(REPO_DIR, 'zips')
REPO_ADDON_DIR = os.path.join(ROOT, 'repository.webshare.streamcinema')
REPO_ADDON_ID = 'repository.webshare.streamcinema'
ICON = os.path.join(ROOT, 'resources', 'icon.png')


def read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def build_repository_zip():
    version = build_zip.addon_version(os.path.join(REPO_ADDON_DIR, 'addon.xml'))
    target = os.path.join(ZIPS_DIR, REPO_ADDON_ID)
    os.makedirs(target, exist_ok=True)
    out = os.path.join(target, '%s-%s.zip' % (REPO_ADDON_ID, version))
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(os.path.join(REPO_ADDON_DIR, 'addon.xml'), '%s/addon.xml' % REPO_ADDON_ID)
        zf.write(ICON, '%s/icon.png' % REPO_ADDON_ID)
    shutil.copyfile(ICON, os.path.join(target, 'icon.png'))
    return out, version


def build_main_zip():
    target = os.path.join(ZIPS_DIR, build_zip.ADDON_ID)
    out, version = build_zip.build_addon_zip(target)
    icon_dir = os.path.join(target, 'resources')
    os.makedirs(icon_dir, exist_ok=True)
    shutil.copyfile(ICON, os.path.join(icon_dir, 'icon.png'))
    return out, version


def write_addons_xml():
    parts = []
    for path in (os.path.join(ROOT, 'addon.xml'), os.path.join(REPO_ADDON_DIR, 'addon.xml')):
        text = read(path).replace('\r\n', '\n').strip()
        text = re.sub(r'^<\?xml[^>]*\?>\s*', '', text)
        parts.append(text)
    xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n%s\n</addons>\n' % '\n'.join(parts)
    data = xml.encode('utf-8')
    os.makedirs(REPO_DIR, exist_ok=True)
    with open(os.path.join(REPO_DIR, 'addons.xml'), 'wb') as fh:
        fh.write(data)
    with open(os.path.join(REPO_DIR, 'addons.xml.md5'), 'w', encoding='ascii', newline='') as fh:
        fh.write(hashlib.md5(data).hexdigest())


def main():
    main_zip, main_version = build_main_zip()
    repo_zip, repo_version = build_repository_zip()
    write_addons_xml()
    print('Doplnek    %s: %s' % (main_version, main_zip))
    print('Repozitar  %s: %s' % (repo_version, repo_zip))
    print('addons.xml a addons.xml.md5 ve slozce: ' + REPO_DIR)
    print('\nPrvni instalace v Kodi: nainstalujte ze zipu jen soubor\n  ' + repo_zip)


if __name__ == '__main__':
    main()
