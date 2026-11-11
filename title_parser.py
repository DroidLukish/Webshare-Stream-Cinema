# -*- coding: utf-8 -*-
# Module: title_parser
# Rozbor nazvu souboru (titul, rok, rada/epizoda, kvalita, jazyk) a seskupovani
# vysledku hledani podle filmu / serialu. Nezavisi na Kodi ani na siti.
# License: AGPL v.3 https://www.gnu.org/licenses/agpl-3.0.html

import re
import unicodedata

VIDEO_EXT = {'mkv', 'avi', 'mp4', 'mpg', 'mpeg', 'm4v', 'mov', 'wmv', 'flv', 'ts', 'm2ts', 'iso', 'webm', 'divx'}

STOPWORDS = {'the', 'a', 'an', 'of', 'and', 'in', 'to', 'on', 'at', 'film', 'movie'}

# zanrova slova v nazvech souboru ("Matrix Akcni Thriller Sci-Fi ..."); pri porovnani titulu se ignoruji
NOISE = {
    'akcni', 'thriller', 'sci', 'fi', 'scifi', 'dobrodruzny', 'fantasy', 'komedie',
    'drama', 'animovany', 'horor', 'krimi', 'romanticky', 'rodinny', 'valecny',
    'dokument', 'csfd',
    # varianty vydani - patri ke stejnemu filmu
    'verze', 'rozsirena', 'rozsirene', 'prodlouzena', 'predlzena', 'edition',
    'special', 'directors', 'cut', 'ultimate',
    # "Star Wars Episode I" = "Star Wars 1"
    'episode', 'epizoda', 'episoda',
}

# rimske cislice v titulu -> cisla ("Star Wars III" = "Star Wars 3")
ROMAN_ALWAYS = {'ii': '2', 'iii': '3', 'iv': '4', 'vi': '6', 'vii': '7', 'viii': '8', 'ix': '9'}
# 'i' a 'v' jsou v cestine bezna slova ("v muzeu"), proto jen v kontextu
ROMAN_CONTEXT = {'i': '1', 'v': '5'}
CONTEXT_PREV = {'wars', 'episode', 'epizoda', 'episoda', 'part', 'volume', 'kapitola', 'dil', 'chapter'}

# --- slovniky znacek (porovnava se zlowercovany text bez diakritiky) ---
Q_2160 = {'2160p', '2160', '4k', 'uhd'}
Q_1080 = {'1080p', '1080i', '1080', 'fhd'}
Q_720 = {'720p', '720', 'hd'}
Q_480 = {'480p', '576p', '480', 'sd'}

SOURCES = {
    'bluray': 'BluRay', 'blu': 'BluRay', 'bdrip': 'BluRay', 'brrip': 'BluRay',
    'bd': 'BluRay', 'bdremux': 'BluRay', 'remux': 'BluRay',
    'web': 'WEB', 'webrip': 'WEB', 'webdl': 'WEB',
    'hdtv': 'HDTV', 'tvrip': 'HDTV', 'hdrip': 'HDRip',
    'dvd': 'DVD', 'dvdrip': 'DVD', 'dvdscr': 'DVD',
    'cam': 'CAM', 'hdcam': 'CAM',
}

LANG_CZ = {'cz', 'cs', 'cesky', 'czech', 'czdab'}
LANG_SK = {'sk', 'slo', 'slovensky', 'slovak'}
LANG_EN = {'en', 'eng', 'english'}
DUB = {'dab', 'dabing', 'dabovano', 'dub', 'dubbing', 'czdab'}
SUBS = {'tit', 'titulky', 'titulkami', 'subs', 'sub'}
HDR = {'hdr', 'hdr10', 'dv', 'dolby'}

# dalsi slova, ktera uz nepatri k nazvu (jen ukoncuji titul)
OTHER_MARKERS = {
    'x264', 'x265', 'h264', 'h265', 'hevc', 'xvid', 'divx', 'avc', 'aac', 'ac3',
    'dts', 'dd5', 'dd', 'dl', '10bit', '8bit', 'atmos', 'mp3', 'yify', 'rarbg',
    'proper', 'rerip', 'repack', 'internal', 'extended', 'uncut', 'remastered',
    'multi', 'dual', 'top', 'kvalita', 'novinka',
}

_RE_YEAR = re.compile(r'(19[3-9]\d|20[0-3]\d)$')
_RE_SXXEXX = re.compile(r's(\d{1,2})e(\d{1,3})(?:e\d{1,3})?$')
_RE_S_ONLY = re.compile(r's(\d{1,2})$')
_RE_E_ONLY = re.compile(r'e(\d{1,3})$')
_RE_NXNN = re.compile(r'(\d{1,2})x(\d{2,3})$')
_RE_RES = re.compile(r'(\d{3,4})x(\d{3,4})$')
_SEASON_WORDS = {'season', 'serie', 'series', 'rada', 'sezona'}
_SEP = re.compile(r"[._\-+,;:~=/\\]+")


def _fold_char(c):
    return unicodedata.normalize('NFKD', c)[0]


def fold(text):
    """Maly pismena bez diakritiky; delka retezce se nemeni."""
    return ''.join(_fold_char(c) for c in text).lower()


def _tokenize(stem):
    s = stem.replace('(', ' | ').replace('[', ' | ').replace('{', ' | ')
    s = s.replace(')', ' | ').replace(']', ' | ').replace('}', ' | ')
    s = _SEP.sub(' ', s)
    return s.split()


def _strip_ext(name):
    name = name.strip()
    m = re.search(r'\.([A-Za-z0-9]{2,5})\s*$', name)
    if m and m.group(1).lower() in VIDEO_EXT:
        return name[:m.start()]
    return name


class ParsedName(object):
    __slots__ = ('title', 'tokens', 'year', 'season', 'episode', 'quality',
                 'source', 'hdr', 'langs', 'dub', 'subs')

    def __init__(self):
        self.title = ''
        self.tokens = frozenset()
        self.year = None
        self.season = None
        self.episode = None
        self.quality = None
        self.source = None
        self.hdr = False
        self.langs = []
        self.dub = False
        self.subs = False

    def __repr__(self):
        return ('ParsedName(title=%r, year=%r, S%rE%r, %r, %r, langs=%r, dub=%r)' % (
            self.title, self.year, self.season, self.episode, self.quality,
            self.source, self.langs, self.dub))


def _quality_of(token):
    if len(token) > 1 and token[0] == 'm' and token[1].isdigit():
        token = token[1:]  # 'm720p' -> '720p'
    if token in Q_2160:
        return '2160p'
    if token in Q_1080:
        return '1080p'
    if token in Q_720:
        return '720p'
    if token in Q_480:
        return '480p'
    m = _RE_RES.match(token)
    if m:
        width = int(m.group(1))
        if width >= 3000:
            return '2160p'
        if width >= 1800:
            return '1080p'
        if width >= 1200:
            return '720p'
        if width >= 600:
            return '480p'
    return None


def _is_marker(tok, nxt):
    """Je tento token zacatek technicke casti nazvu (uz nepatri k titulu)?"""
    if tok == '|':
        return True
    if _RE_YEAR.match(tok):
        return True
    if (_RE_SXXEXX.match(tok) or _RE_S_ONLY.match(tok) or _RE_E_ONLY.match(tok)
            or _RE_NXNN.match(tok)):
        return True
    if tok in _SEASON_WORDS and nxt is not None and nxt.isdigit():
        return True
    if tok == 'full' and nxt == 'hd':
        return True
    if _quality_of(tok) or tok in SOURCES:
        return True
    if (tok in LANG_CZ or tok in LANG_SK or tok in LANG_EN or tok in DUB
            or tok in SUBS or tok in HDR or tok in OTHER_MARKERS):
        return True
    return False


def _collapse_repeat(words):
    """'Matrix The Matrix' -> 'Matrix' (titul zopakovany v druhem jazyce/podobe)."""
    folded = [fold(w) for w in words]
    for s in range(1, len(words)):
        right = folded[s:]
        if right and right[0] in STOPWORDS:
            right = right[1:]
        if right and folded[:s] == right:
            return words[:s]
    return words


def _merge_series_brackets(raw, low):
    """'Star Wars (DROIDS) S01 E01' -> zavorka je soucasti nazvu serialu, kdyz za ni
    hned nasleduje znacka rady/epizody a uvnitr neni rok, jazyk ani kvalita."""
    for i, tok in enumerate(low):
        if tok != '|' or i == 0:
            continue
        try:
            j = low.index('|', i + 1)
        except ValueError:
            return raw, low
        inside = low[i + 1:j]
        after = low[j + 1] if j + 1 < len(low) else None
        if (inside and after is not None
                and not any(_is_marker(t, None) for t in inside)
                and (_RE_SXXEXX.match(after) or _RE_S_ONLY.match(after) or _RE_NXNN.match(after))):
            keep = [k for k in range(len(low)) if k not in (i, j)]
            return [raw[k] for k in keep], [low[k] for k in keep]
        return raw, low  # posuzuje se jen prvni zavorka za titulem
    return raw, low


def _roman_to_digits(words):
    out = []
    for i, w in enumerate(words):
        if i > 0 and w in ROMAN_ALWAYS:
            out.append(ROMAN_ALWAYS[w])
        elif (i > 0 and w in ROMAN_CONTEXT
              and (i == len(words) - 1 or words[i - 1] in CONTEXT_PREV)):
            out.append(ROMAN_CONTEXT[w])
        else:
            out.append(w)
    return out


def parse_name(name):
    """Z nazvu souboru vytahne titul, rok, radu/epizodu, kvalitu a jazyk."""
    p = ParsedName()
    stem = _strip_ext(name)
    # uvodni zavorky typu "[www.web.cz] Film" nejsou soucasti titulu
    stem = re.sub(r'^(\s*[\[(][^\])]*[\])])+\s*', '', stem)
    # poradove cislo na zacatku: "01. Pribeh hracek 1" -> "Pribeh hracek 1"
    stem = re.sub(r'^\s*\d{1,3}\s*[.)]\s+', '', stem)
    # epizoda na zacatku: "01x11 Nazev" nebo "S01E11 Nazev"
    pre = None
    m = re.match(r'^\s*(?:(\d{1,2})x(\d{2,3})|[sS](\d{1,2})[eE](\d{1,3}))[\s._-]+(?=\S)', stem)
    if m:
        pre = (int(m.group(1) or m.group(3)), int(m.group(2) or m.group(4)))
        stem = stem[m.end():]
    raw = _tokenize(stem)
    low = [fold(t) for t in raw]
    raw, low = _merge_series_brackets(raw, low)
    n = len(low)

    # --- konec titulu: prvni znacka (ne na zacatku) ---
    cut = n
    for i, tok in enumerate(low):
        nxt = low[i + 1] if i + 1 < n else None
        if i > 0 and _is_marker(tok, nxt):
            cut = i
            break
    # '|' na zacatku zahodit
    title_idx = [i for i in range(cut) if low[i] != '|']
    title_words = [raw[i] for i in title_idx]
    title_low = [low[i] for i in title_idx]

    # --- vlastnosti z celeho nazvu ---
    for i, tok in enumerate(low):
        nxt = low[i + 1] if i + 1 < n else None
        if p.year is None and i > 0 and _RE_YEAR.match(tok):
            p.year = int(tok)
        m = _RE_SXXEXX.match(tok)
        if m and p.episode is None:
            p.season, p.episode = int(m.group(1)), int(m.group(2))
            continue
        m = _RE_S_ONLY.match(tok)
        if m and p.season is None:
            p.season = int(m.group(1))
            m2 = _RE_E_ONLY.match(nxt) if nxt else None
            if m2:
                p.episode = int(m2.group(1))
            continue
        m = _RE_E_ONLY.match(tok)
        if m and p.episode is None and i >= cut:
            p.episode = int(m.group(1))
            if p.season is None:
                p.season = 1
            continue
        m = _RE_NXNN.match(tok)
        if m and p.episode is None:
            p.season, p.episode = int(m.group(1)), int(m.group(2))
            continue
        if tok in _SEASON_WORDS and nxt is not None and nxt.isdigit() and p.season is None:
            p.season = int(nxt)
            continue
        if i >= cut or tok == 'hd':
            q = _quality_of(tok)
            if q and (p.quality is None or p.quality == '720p' and q != '720p'):
                p.quality = q
        if tok == 'full' and nxt == 'hd':
            p.quality = '1080p'
        if i >= cut and tok in SOURCES and p.source is None:
            p.source = SOURCES[tok]
        if i >= cut and tok in HDR:
            p.hdr = True
        if i >= cut:
            for lang, group in (('CZ', LANG_CZ), ('SK', LANG_SK), ('EN', LANG_EN)):
                if tok in group and lang not in p.langs:
                    p.langs.append(lang)
            if tok in DUB:
                p.dub = True
            if tok in SUBS:
                p.subs = True
    if p.dub and not p.langs:
        p.langs.append('CZ')
    if p.episode is None and pre is not None:
        p.season, p.episode = pre

    # --- titul ---
    words = _collapse_repeat(title_words)
    if words and all(w.isupper() or not w.isalpha() for w in words):
        words = [w.title() if w.isalpha() and len(w) > 1 else w for w in words]
    p.title = ' '.join(words).strip()
    p.tokens = frozenset(t for t in _roman_to_digits(title_low)
                         if t and t not in STOPWORDS and t not in NOISE)
    return p


# ------------------------------------------------------------------
# Polozka (soubor z vyhledavani) a seskupovani
# ------------------------------------------------------------------

class Item(object):
    __slots__ = ('index', 'ident', 'name', 'size', 'votes', 'password', 'parsed')

    def __init__(self, index, f):
        self.index = index
        self.ident = f.get('ident')
        self.name = (f.get('name') or '').strip()
        try:
            self.size = int(f.get('size') or 0)
        except (TypeError, ValueError):
            self.size = 0
        try:
            self.votes = int(f.get('positive_votes') or 0) - int(f.get('negative_votes') or 0)
        except (TypeError, ValueError):
            self.votes = 0
        self.password = str(f.get('password') or '0') == '1'
        self.parsed = parse_name(self.name)


class Group(object):
    """kind: 'movie' | 'series' | 'other'"""

    def __init__(self, kind, title, year, items):
        self.kind = kind
        self.title = title
        self.year = year
        self.items = items

    @property
    def first_index(self):
        return min(i.index for i in self.items) if self.items else 0

    def seasons(self):
        """{rada: {epizoda: [Item, ...]}} (jen pro serialy; epizoda None = cele rady)."""
        out = {}
        for it in self.items:
            s = it.parsed.season if it.parsed.season is not None else 1
            out.setdefault(s, {}).setdefault(it.parsed.episode, []).append(it)
        return out


def dedupe(files):
    """Odstrani stejne soubory (stejny nazev a velikost, jine ident)."""
    seen, out = set(), []
    for f in files:
        key = (fold((f.get('name') or '').strip()), str(f.get('size')))
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def _nums(tokens):
    return {t for t in tokens if t.isdigit()}


class _Cluster(object):
    """Shluk souboru, ktere patri k jednomu filmu/serialu. Pamatuje si vsechny
    podpisy (mnoziny slov titulu), ktere se v nem vyskytly (cesky i puvodni nazev)."""

    def __init__(self, year, item):
        self.year = year
        self.sigs = {item.parsed.tokens}
        self.items = [item]

    def add(self, item):
        self.items.append(item)
        self.sigs.add(item.parsed.tokens)

    def merge(self, other):
        self.items.extend(other.items)
        self.sigs |= other.sigs

    def display_title(self):
        """Nejcastejsi podoba titulu ve shluku (pri shode ta podrobnejsi)."""
        counts = {}
        for it in self.items:
            if it.parsed.title:
                counts[it.parsed.tokens] = counts.get(it.parsed.tokens, 0) + 1
        if not counts:
            return '?'
        best = max(counts, key=lambda sig: (counts[sig], len(sig)))
        return min((it.parsed.title for it in self.items
                    if it.parsed.tokens == best and it.parsed.title), key=len)


def _score(cluster, toks, strict, symmetric=False):
    """Jak dobre polozka sedi do shluku: (obsazuje_podpis, shoda_cisel, specificnost)
    nebo None, kdyz nesedi. strict: slova navic u polozky smi byt jen cisla;
    symmetric: totez i pro slova navic u shluku (rozlisi "Star Wars Rebels" od "Star Wars")."""
    best = None
    nt = _nums(toks)
    for s in cluster.sigs:
        ns = _nums(s)
        if ns and nt and ns != nt:
            continue
        if s <= toks:
            if strict and not all(t.isdigit() for t in toks - s):
                continue
            if strict and not ns and nt and nt != {'1'}:
                continue  # "Star Wars 6" nepatri k "Star Wars (1977)"; jen "1" smi
            sc = (1, 1 if ns == nt else 0, len(s))
        elif toks <= s:
            if symmetric and not all(t.isdigit() for t in s - toks):
                continue
            sc = (0, 1 if ns == nt else 0, -len(s))
        else:
            continue
        if best is None or sc > best:
            best = sc
    return best


def _absorb_subseries(clusters):
    """Serial, jehoz nazev je delsi podoba nazvu vetsiho serialu (ke jmenu pribyl nazev
    epizody nebo anglicky titul), se pripoji k tomu vetsimu. Sdileny nazev musi mit
    aspon 4 slova, aby se nespojily ruzne serialy ("Star Wars Rebels" vs "Star Wars")."""
    ordered = sorted(clusters, key=lambda c: len(c.items), reverse=True)
    result = []
    for c in ordered:
        target = None
        for b in result:
            if len(b.items) > len(c.items) and any(
                    len(bs) >= 4 and bs < cs for bs in b.sigs for cs in c.sigs):
                target = b
                break
        if target is not None:
            target.merge(c)
        else:
            result.append(c)
    return result


def group_files(files):
    """
    files: seznam dictu z API (ident, name, size, positive_votes, ...).
    Vraci seznam Group; poradi podle prvniho vyskytu (= relevance serveru),
    skupina 'other' na konci.
    """
    items = [Item(i, f) for i, f in enumerate(dedupe(files))]
    movie_clusters, series_clusters = [], []
    other = []

    series_items = [it for it in items if it.parsed.episode is not None or it.parsed.season is not None]
    yeared = [it for it in items if it not in series_items and it.parsed.year]
    yearless = [it for it in items if it not in series_items and not it.parsed.year]

    def place(clusters, item, year, any_year, strict, symmetric=False):
        toks = item.parsed.tokens
        if not toks:
            other.append(item)
            return
        scored = []
        for c in clusters:
            if not any_year and c.year != year:
                continue
            sc = _score(c, toks, strict, symmetric)
            if sc is not None:
                scored.append((sc, c))
        if not scored:
            clusters.append(_Cluster(year, item))
            return
        # premostujici polozka (s rokem): obsahuje podpisy vice shluku stejneho roku
        # (napr. "Toy Story 4 - Pribeh hracek (2019)" spoji "Toy Story 4" a "Pribeh hracek 4")
        if year is not None:
            bridge = [c for sc, c in scored
                      if sc[0] == 1 and any(len(s) >= 2 and s <= toks for s in c.sigs)]
            if len(bridge) >= 2:
                base = bridge[0]
                for o in bridge[1:]:
                    base.merge(o)
                    clusters.remove(o)
                base.add(item)
                return
        top = max(sc for sc, _ in scored)
        pool = [c for sc, c in scored if sc == top]
        if len(pool) == 1:
            pool[0].add(item)
            return
        pool.sort(key=lambda c: len(c.items), reverse=True)
        if len(pool[0].items) >= 3 * len(pool[1].items):
            pool[0].add(item)  # jasne dominantni shluk (napr. puvodni film vs. remake)
            return
        other.append(item)

    for it in yeared:
        place(movie_clusters, it, it.parsed.year, False, False)
    for it in series_items:
        place(series_clusters, it, None, True, True, True)
    for it in yearless:
        place(movie_clusters, it, None, True, True)

    series_clusters = _absorb_subseries(series_clusters)

    groups = []
    for c in movie_clusters:
        groups.append(Group('movie', c.display_title(), c.year, sorted(c.items, key=lambda i: i.index)))
    for c in series_clusters:
        groups.append(Group('series', c.display_title(), None, sorted(
            c.items, key=lambda i: (i.parsed.season or 1, i.parsed.episode or 0, i.index))))
    groups.sort(key=lambda g: g.first_index)
    if other:
        groups.append(Group('other', '', None, sorted(other, key=lambda i: i.index)))
    return groups


# ------------------------------------------------------------------
# Popisky variant
# ------------------------------------------------------------------

def format_size(size):
    if not size:
        return '?'
    gb = size / (1024.0 ** 3)
    if gb >= 1:
        return ('%.1f GB' % gb).replace('.', ',')
    return '%d MB' % round(size / (1024.0 ** 2))


def language_label(parsed):
    if parsed.dub and 'CZ' in parsed.langs:
        label = 'CZ dabing'
        rest = [l for l in parsed.langs if l != 'CZ']
        return label + (' + ' + '/'.join(rest) if rest else '')
    if parsed.langs:
        label = '/'.join(parsed.langs)
        return label + (' tit.' if parsed.subs else '')
    return 'tit.' if parsed.subs else ''


def variant_label(item):
    """Napr. '1080p · BluRay · CZ dabing · 4,2 GB'."""
    p = item.parsed
    parts = []
    if p.quality:
        parts.append(p.quality)
    if p.source:
        parts.append(p.source)
    if p.hdr:
        parts.append('HDR')
    lang = language_label(p)
    if lang:
        parts.append(lang)
    parts.append(format_size(item.size))
    return ' · '.join(parts)
