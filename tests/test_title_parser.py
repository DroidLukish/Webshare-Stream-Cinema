# -*- coding: utf-8 -*-
"""
Testy parseru nazvu. Bezi mimo Kodi i bez site:

    python -m unittest discover -s tests -v        (ze slozky projektu)
"""
import glob
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import title_parser as tp  # noqa: E402


def f(ident, name, size='1000', pos=0, neg=0):
    return {'ident': ident, 'name': name, 'size': size,
            'positive_votes': pos, 'negative_votes': neg, 'password': '0'}


class ParseNameTests(unittest.TestCase):
    def test_film_s_rokem_a_znackami(self):
        p = tp.parse_name('Matrix - The Matrix (1999)(CZ,EN)[2160p][HDR-DV].mkv')
        self.assertEqual(p.title, 'Matrix')
        self.assertEqual(p.year, 1999)
        self.assertEqual(p.quality, '2160p')
        self.assertTrue(p.hdr)
        self.assertEqual(p.langs, ['CZ', 'EN'])
        self.assertIsNone(p.episode)

    def test_serial_sxxexx(self):
        p = tp.parse_name('Red Dwarf  S01E02 Cerveny trpaslik CZ.mkv')
        self.assertEqual(p.title, 'Red Dwarf')
        self.assertEqual((p.season, p.episode), (1, 2))
        self.assertEqual(p.langs, ['CZ'])
        self.assertFalse(p.dub)

    def test_serial_s1_e1_a_cislo_dilu(self):
        p = tp.parse_name(u'Črvený.Trpaslík_Red.Dwarf_01. Konec (s1 e1).mkv')
        self.assertEqual((p.season, p.episode), (1, 1))
        self.assertIn('red', p.tokens)
        self.assertIn('dwarf', p.tokens)

    def test_rok_v_zavorce_a_hd(self):
        p = tp.parse_name(u'Příběh hraček 4 (2019) Hbo Hd cz.avi')
        self.assertEqual(p.year, 2019)
        self.assertEqual(p.title, u'Příběh hraček 4')
        self.assertEqual(p.quality, '720p')

    def test_m720p_zdroj_a_poradi_jazyku(self):
        p = tp.parse_name(u'Pan-prstenů-Společenstvo-prstenu.2001.m720p.BDRip.x264.DD5.1.ENG.CZ.SK.mkv')
        self.assertEqual(p.year, 2001)
        self.assertEqual(p.quality, '720p')
        self.assertEqual(p.source, 'BluRay')
        self.assertEqual(p.langs, ['EN', 'CZ', 'SK'])

    def test_rozliseni_1920x800_neni_epizoda(self):
        p = tp.parse_name(u'Pán prstenu - Společenstvo 1920x800 2001 CZ dabing.mkv')
        self.assertIsNone(p.episode)
        self.assertEqual(p.quality, '1080p')
        self.assertTrue(p.dub)
        self.assertEqual(p.langs, ['CZ'])

    def test_bez_roku(self):
        p = tp.parse_name('Matrix 1(1).avi')
        self.assertEqual(p.title, 'Matrix 1')
        self.assertIsNone(p.year)

    def test_uvodni_zavorka_neni_titul(self):
        p = tp.parse_name('[www.nejaky-web.cz] Matrix 1999 CZ.mkv')
        self.assertEqual(p.title, 'Matrix')
        self.assertEqual(p.year, 1999)


class ParseNameExtraTests(unittest.TestCase):
    def test_poradove_cislo_na_zacatku(self):
        p = tp.parse_name(u'01. Příběh Hraček 1.mkv')
        self.assertEqual(p.title, u'Příběh Hraček 1')
        self.assertEqual(p.tokens, frozenset(['pribeh', 'hracek', '1']))

    def test_epizoda_na_zacatku(self):
        p = tp.parse_name(u'01x11 Příběh hraček-Toy story.avi')
        self.assertEqual((p.season, p.episode), (1, 11))
        self.assertEqual(p.title, u'Příběh hraček Toy story')


class GroupTests(unittest.TestCase):
    def test_dedupe(self):
        files = [f('1', 'A 2000.mkv', '10'), f('2', 'A 2000.mkv', '10'), f('3', 'A 2000.mkv', '11')]
        self.assertEqual(len(tp.dedupe(files)), 2)

    def test_filmy_se_slucuji_podle_titulu_a_roku(self):
        files = [
            f('1', 'Matrix - The Matrix (1999)(CZ,EN)[2160p].mkv', '100'),
            f('2', 'Matrix 1999 CZ dab.avi', '50'),
            f('3', 'Matrix Reloaded (2003).mkv', '60'),
            f('4', 'Matrix 1(1).avi', '70'),
            f('5', 'Matrix 1999 CZ dab.avi', '50'),  # duplicita
        ]
        groups = tp.group_files(files)
        self.assertEqual([g.kind for g in groups], ['movie', 'movie'])
        self.assertEqual((groups[0].title, groups[0].year, len(groups[0].items)), ('Matrix', 1999, 3))
        self.assertEqual((groups[1].title, groups[1].year, len(groups[1].items)), ('Matrix Reloaded', 2003, 1))

    def test_serial_ma_rady_a_epizody(self):
        files = [
            f('1', 'Red Dwarf S01E01 CZ.mkv', '1'),
            f('2', 'Red Dwarf S01E02 CZ.mkv', '2'),
            f('3', 'Red Dwarf S02E01 CZ.mkv', '3'),
            f('4', 'Red Dwarf S01E01 1080p BluRay.mkv', '4'),
        ]
        groups = tp.group_files(files)
        self.assertEqual(len(groups), 1)
        g = groups[0]
        self.assertEqual((g.kind, g.title), ('series', 'Red Dwarf'))
        seasons = g.seasons()
        self.assertEqual(sorted(seasons), [1, 2])
        self.assertEqual(sorted(seasons[1]), [1, 2])
        self.assertEqual(len(seasons[1][1]), 2)  # dve varianty 1. epizody

    def test_nejednoznacne_jde_do_ostatni(self):
        files = [
            f('1', 'Matrix Reloaded (2003).mkv', '1'),
            f('2', 'Matrix Revolutions (2003).mkv', '2'),
            f('3', 'Matrix 2003.mkv', '3'),
        ]
        groups = tp.group_files(files)
        self.assertEqual(groups[-1].kind, 'other')
        self.assertEqual([i.ident for i in groups[-1].items], ['3'])

    def test_popisek_varianty(self):
        item = tp.Item(0, f('1', 'Matrix (1999) 1080p BluRay CZ dabing.mkv', str(int(4.2 * 1024 ** 3))))
        self.assertEqual(tp.variant_label(item), u'1080p · BluRay · CZ dabing · 4,2 GB')


class GroupExtraTests(unittest.TestCase):
    def test_premosteni_ceskeho_a_puvodniho_nazvu(self):
        files = [
            f('1', 'Toy Story 4 (2019).mkv', '1'),
            f('2', u'Příběh hraček 4 (2019).mkv', '2'),
            f('3', u'Toy Story 4 - Příběh hraček (2019).mkv', '3'),
        ]
        groups = tp.group_files(files)
        self.assertEqual(len(groups), 1)
        self.assertEqual((groups[0].kind, groups[0].year, len(groups[0].items)), ('movie', 2019, 3))

    def test_bez_roku_s_cizimi_slovy_je_samostatny_film(self):
        files = [
            f('1', 'Matrix (1999).mkv', '1'),
            f('2', 'Matrix jeff who lives at home.avi', '2'),
        ]
        self.assertEqual(len(tp.group_files(files)), 2)

    def test_bez_roku_pripadne_k_dominantnimu_filmu(self):
        files = [
            f('1', 'Matrix (1999) CZ.mkv', '1'),
            f('2', 'Matrix (1999) EN.mkv', '2'),
            f('3', 'Matrix (1999) 1080p.mkv', '3'),
            f('4', 'Matrix (2022).mkv', '4'),
            f('5', 'Matrix 1.avi', '5'),
        ]
        groups = tp.group_files(files)
        by_year = {g.year: g for g in groups if g.kind == 'movie'}
        self.assertEqual(len(by_year[1999].items), 4)
        self.assertEqual(len(by_year[2022].items), 1)

    def test_popisek_bez_kvality(self):
        item = tp.Item(0, f('1', 'Matrix CZ dabing.avi', str(700 * 1024 ** 2)))
        self.assertEqual(tp.variant_label(item), u'CZ dabing · 700 MB')


class StarWarsRegressionTests(unittest.TestCase):
    def test_ruzne_serialy_se_stejnym_zacatkem_nejsou_jedna_skupina(self):
        files = [
            f('1', 'Star Wars Rebels S01E01 CZ.mkv', '1'),
            f('2', 'Star Wars Droids S01E01 CZ.mkv', '2'),
            f('3', 'Star Wars S01E01 Padawan.mp4', '3'),
            f('4', 'Star Wars Rebels 01x01 Spark.mp4', '4'),
        ]
        groups = tp.group_files(files)
        self.assertEqual(len(groups), 3)
        titles = sorted(g.title for g in groups)
        self.assertEqual(titles, ['Star Wars', 'Star Wars Droids', 'Star Wars Rebels'])
        rebels = [g for g in groups if g.title == 'Star Wars Rebels'][0]
        self.assertEqual(len(rebels.items), 2)

    def test_rimske_cislice_a_slovo_epizoda(self):
        a = tp.parse_name(u'Star Wars III - Pomsta Sithů (2005).mkv')
        self.assertIn('3', a.tokens)
        b = tp.parse_name(u'Star Wars Episode I - Skrytá hrozba (1999).mkv')
        self.assertEqual(b.tokens, frozenset(['star', 'wars', '1', 'skryta', 'hrozba']))
        c = tp.parse_name('Star Wars Epizoda 1 (1999).mkv')
        self.assertEqual(c.tokens, frozenset(['star', 'wars', '1']))

    def test_epizoda_i_a_epizoda_1_jsou_jeden_film(self):
        files = [
            f('1', u'Star Wars Episode I - Skrytá hrozba (1999).mkv', '1'),
            f('2', 'Star Wars Epizoda 1 (1999).mkv', '2'),
            f('3', u'Star Wars II Klony útočí (2002).mkv', '3'),
        ]
        groups = tp.group_files(files)
        self.assertEqual(sorted(len(g.items) for g in groups), [1, 2])

    def test_zavorka_za_nazvem_serialu(self):
        p = tp.parse_name('Star Wars (DROIDS) - S01 E01 - The White Witch (1080p - DSNP Web-DL).mp4')
        self.assertEqual(p.tokens, frozenset(['star', 'wars', 'droids']))
        self.assertEqual((p.season, p.episode), (1, 1))
        q = tp.parse_name('Star Wars Rebels (2014) - S01E03 - Droids (1080p).mp4')
        self.assertEqual(q.tokens, frozenset(['star', 'wars', 'rebels']))

    def test_serialy_se_zavorkou_se_deli(self):
        files = [
            f('1', 'Star Wars (DROIDS) - S01 E01 - A.mp4', '1'),
            f('2', 'Star Wars Droids S01E02 CZ.mkv', '2'),
            f('3', 'Star Wars (EWOKS) - S01 E01 - B.mp4', '3'),
        ]
        groups = tp.group_files(files)
        self.assertEqual(sorted(len(g.items) for g in groups), [1, 2])

    def test_cislo_vetsi_nez_jedna_nepatri_k_filmu_bez_cisla(self):
        files = [
            f('1', 'Star Wars (1977).mkv', '1'),
            f('2', 'Star Wars 6.avi', '2'),
            f('3', u'Star Wars VI - Návrat Jediho 1983.mkv', '3'),
        ]
        groups = tp.group_files(files)
        by_year = {g.year: g for g in groups}
        self.assertEqual(len(by_year[1977].items), 1)
        self.assertEqual(len(by_year[1983].items), 2)

    def test_serial_s_nazvem_epizody_se_pripoji_k_vetsimu(self):
        files = [
            f('1', u'Star Wars Příběhy z podsvětí S01E01 CZ.mkv', '1'),
            f('2', u'Star Wars Příběhy z podsvětí S01E02 CZ.mkv', '2'),
            f('3', u'Star Wars Příběhy z podsvětí S01E03 CZ.mkv', '3'),
            f('4', u'Star Wars Tales Of The Underworld Příběhy z podsvětí Dobrý život S01E04 CZ.mkv', '4'),
        ]
        groups = tp.group_files(files)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0].items), 4)

    def test_cesky_v_neni_rimska_petka(self):
        p = tp.parse_name('Noc v muzeu (2006).mkv')
        self.assertNotIn('5', p.tokens)


class ProbeDataSmokeTest(unittest.TestCase):
    """Na realnych datech ze sondy: nic nespadne a zadna polozka se neztrati."""

    def test_vsechna_data_ze_sondy(self):
        paths = sorted(glob.glob(os.path.join(ROOT, 'tools', 'probe_output', 'probe_*.json')))
        if not paths:
            self.skipTest('chybi tools/probe_output/probe_*.json')
        with open(paths[-1], encoding='utf-8') as fh:
            data = json.load(fh)
        checked = 0
        for title, entry in data['titles'].items():
            for search in entry['searches']:
                files = search.get('files') or []
                if not files:
                    continue
                groups = tp.group_files(files)
                self.assertEqual(sum(len(g.items) for g in groups), len(tp.dedupe(files)),
                                 '%s / %s' % (title, search['variant']))
                checked += 1
        self.assertGreater(checked, 0)


if __name__ == '__main__':
    unittest.main()
