# -*- coding: utf-8 -*-
# Webshare Stream Cinema
# Uzivatelske rozhrani v Kodi: hledani (vysledky seskupene podle filmu/serialu),
# vyber varianty v dialogu, serialy (rada -> epizoda).
# License: AGPL v.3 https://www.gnu.org/licenses/agpl-3.0.html

import io
import os
import sys
import json
import time
import traceback
import uuid
from urllib.parse import urlencode, parse_qsl

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
from xbmcvfs import translatePath

import title_parser
import ws_api

CATEGORIES = ws_api.CATEGORIES
SORTS = ws_api.SORTS
SEARCH_HISTORY = 'search_history'
SEARCH_CACHE = 'search_cache.json'
CACHE_TTL = 1800        # vysledky hledani se drzi 30 minut
CACHE_MAX = 6           # kolik poslednich hledani se drzi
PAGE_SIZE = 100         # kolik souboru vraci server na jeden dotaz
QUALITY_RANK = {'2160p': 4, '1080p': 3, '720p': 2, '480p': 1}

_url = sys.argv[0]
_handle = int(sys.argv[1])
_addon = xbmcaddon.Addon()
_profile = translatePath(_addon.getAddonInfo('profile'))


def S(string_id):
    return _addon.getLocalizedString(string_id)


def get_url(**kwargs):
    return '{0}?{1}'.format(_url, urlencode(kwargs, 'utf-8'))


def popinfo(message, heading=_addon.getAddonInfo('name'), icon=xbmcgui.NOTIFICATION_INFO, time_ms=3000, sound=False):
    xbmcgui.Dialog().notification(heading, message, icon, time_ms, sound=sound)


def _client():
    return ws_api.WebshareClient(
        username=_addon.getSetting('wsuser'),
        password=_addon.getSetting('wspass'),
        token=_addon.getSetting('token'),
        on_token=lambda t: _addon.setSetting('token', t))


def _int_setting(key, default):
    try:
        return int(_addon.getSetting(key))
    except (TypeError, ValueError):
        return default


def ask(what=''):
    kb = xbmc.Keyboard(what or '', S(30007))
    kb.doModal()
    if kb.isConfirmed():
        return kb.getText().strip()
    return None


def _set_video_info(listitem, title, year=None, mediatype='movie', season=None,
                    episode=None, tvshowtitle=None):
    """Metadata polozky (Kodi 20+ pres InfoTagVideo, jinak starsi setInfo)."""
    try:
        tag = listitem.getVideoInfoTag()
        tag.setTitle(title)
        tag.setMediaType(mediatype)
        if year:
            tag.setYear(int(year))
        if season is not None:
            tag.setSeason(int(season))
        if episode is not None:
            tag.setEpisode(int(episode))
        if tvshowtitle:
            tag.setTvShowTitle(tvshowtitle)
    except AttributeError:
        info = {'title': title, 'mediatype': mediatype}
        if year:
            info['year'] = int(year)
        if season is not None:
            info['season'] = int(season)
        if episode is not None:
            info['episode'] = int(episode)
        if tvshowtitle:
            info['tvshowtitle'] = tvshowtitle
        listitem.setInfo('video', info)


# ---------- soubory v profilu: historie hledani a cache vysledku ----------

def _profile_path(name):
    return os.path.join(_profile, name)


def _read_json(name, default):
    try:
        with io.open(_profile_path(name), 'r', encoding='utf8') as fh:
            return json.load(fh)
    except IOError:
        return default
    except Exception:
        traceback.print_exc()
        return default


def _write_json(name, data):
    try:
        if not os.path.exists(_profile):
            os.makedirs(_profile)
        with io.open(_profile_path(name), 'w', encoding='utf8') as fh:
            fh.write(json.dumps(data, ensure_ascii=False))
    except Exception:
        traceback.print_exc()


def loadsearch():
    history = _read_json(SEARCH_HISTORY, [])
    return history if isinstance(history, list) else []


def storesearch(what):
    if what:
        size = _int_setting('shistory', 20)
        history = [what] + [h for h in loadsearch() if h != what]
        _write_json(SEARCH_HISTORY, history[:size])


def removesearch(what):
    history = loadsearch()
    if what in history:
        history.remove(what)
        _write_json(SEARCH_HISTORY, history)


def _slim(f):
    return {k: f.get(k) for k in ('ident', 'name', 'size', 'positive_votes',
                                  'negative_votes', 'password', 'img')}


def get_results(client, what, category, sort, pages):
    """Soubory pro dotaz (z cache nebo ze serveru, az 'pages' stran po 100)."""
    key = json.dumps([what, category, sort, pages], ensure_ascii=False)
    cache = _read_json(SEARCH_CACHE, {})
    entry = cache.get(key)
    now = time.time()
    if entry and now - entry.get('ts', 0) < CACHE_TTL:
        return entry['files'], entry['total']

    files, total = [], 0
    for page in range(pages):
        result = client.search(what, sort=sort, category=category,
                               limit=PAGE_SIZE, offset=page * PAGE_SIZE)
        total = result.total
        files.extend(_slim(f) for f in result.files)
        if not result.files or (page + 1) * PAGE_SIZE >= total:
            break

    cache[key] = {'ts': now, 'total': total, 'files': files}
    if len(cache) > CACHE_MAX:
        newest = sorted(cache.items(), key=lambda kv: kv[1].get('ts', 0), reverse=True)[:CACHE_MAX]
        cache = dict(newest)
    _write_json(SEARCH_CACHE, cache)
    return files, total


def _query_params(params):
    category = params.get('c')
    if category is None:
        category = CATEGORIES[_int_setting('scategory', 1)]
    sort = params.get('s')
    if sort is None:
        sort = SORTS[_int_setting('ssort', 0)]
    return params['q'], category, sort


def _groups(client, params):
    what, category, sort = _query_params(params)
    files, _total = get_results(client, what, category, sort, max(1, _int_setting('spages', 3)))
    return files, title_parser.group_files(files)


def _find_group(groups, params):
    """Skupina podle poradi; kdyz se mezitim zmenila data, podle titulu."""
    title = params.get('t', '')
    try:
        group = groups[int(params.get('g', -1))]
        if group.title == title:
            return group
    except (ValueError, IndexError):
        pass
    for group in groups:
        if group.title == title:
            return group
    raise ws_api.WebshareError(S(30225))


# ---------- popisky a vyber varianty ----------

def _group_label(group):
    return '%s (%d)' % (group.title, group.year) if group.year else group.title


def _variant_key(item):
    p = item.parsed
    czech = 2 if (p.dub and 'CZ' in p.langs) else (1 if 'CZ' in p.langs else 0)
    return (-czech, -QUALITY_RANK.get(p.quality, 0), -item.votes, -item.size)


def choose_variant(items, heading):
    """Dialog s variantami; vraci vybranou polozku nebo None.
    Ukazuje se vzdy, i pri jedine verzi, aby bylo videt, co se pousti."""
    ordered = sorted(items, key=_variant_key)
    listitems = []
    for it in ordered:
        label = title_parser.variant_label(it)
        if it.password:
            label += ' · ' + S(30227)
        listitems.append(xbmcgui.ListItem(label=label, label2=it.name))
    index = xbmcgui.Dialog().select(heading, listitems, useDetails=True)
    return ordered[index] if index >= 0 else None


def _group_context(params_base):
    return [(S(30228), 'RunPlugin(' + get_url(mode='info', action='pick', **params_base) + ')')]


# ---------- hledani ----------

def search(params):
    xbmcplugin.setPluginCategory(_handle, _addon.getAddonInfo('name') + " \\ " + S(30201))
    what = params.get('what')
    if what is None:
        what = ask('')
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        if what:
            storesearch(what)
            xbmc.executebuiltin('Container.Update(%s,replace)' % get_url(action='search', what=what))
        return
    storesearch(what)

    client = _client()
    _q, category, sort = _query_params({'q': what, 'c': params.get('c'), 's': params.get('s')})
    base = {'q': what, 'c': category, 's': sort}
    files, _total = get_results(client, what, category, sort, max(1, _int_setting('spages', 3)))
    groups = title_parser.group_files(files)
    imgs = {f['ident']: f.get('img') for f in files}

    xbmcplugin.setContent(_handle, 'movies')
    xbmcplugin.addSortMethod(_handle, xbmcplugin.SORT_METHOD_NONE)
    if not groups:
        popinfo(S(30225), icon=xbmcgui.NOTIFICATION_WARNING)

    for gid, group in enumerate(groups):
        ref = dict(base, g=gid, t=group.title)
        if group.kind == 'other':
            listitem = xbmcgui.ListItem(label=S(30232), label2=str(len(group.items)))
            listitem.setArt({'icon': 'DefaultFolder.png'})
            xbmcplugin.addDirectoryItem(_handle, get_url(action='other', **dict(base, g=gid, t='')), listitem, True)
            continue

        count = len(group.items)
        label2 = '%d %s' % (count, S(30224)) if count > 1 else ''
        listitem = xbmcgui.ListItem(label=_group_label(group), label2=label2)
        thumb = imgs.get(group.items[0].ident)
        if thumb:
            listitem.setArt({'thumb': thumb})
        if group.kind == 'series':
            _set_video_info(listitem, group.title, mediatype='tvshow')
            listitem.setArt({'icon': 'DefaultTVShows.png'})
            xbmcplugin.addDirectoryItem(_handle, get_url(action='series', **ref), listitem, True)
        else:
            _set_video_info(listitem, group.title, year=group.year)
            listitem.setProperty('IsPlayable', 'true')
            listitem.addContextMenuItems(_group_context(ref))
            xbmcplugin.addDirectoryItem(_handle, get_url(action='pick', mode='play', **ref), listitem, False)
    xbmcplugin.endOfDirectory(_handle)


def other(params):
    """Soubory, ktere se nepodarilo zaradit k zadnemu filmu/serialu."""
    xbmcplugin.setPluginCategory(_handle, _addon.getAddonInfo('name') + " \\ " + S(30232))
    client = _client()
    _files, groups = _groups(client, params)
    for group in groups:
        if group.kind != 'other':
            continue
        for item in sorted(group.items, key=_variant_key):
            label = '%s · %s' % (item.name, title_parser.variant_label(item))
            listitem = xbmcgui.ListItem(label=label)
            listitem.setProperty('IsPlayable', 'true')
            listitem.addContextMenuItems([(S(30211), 'RunPlugin(' + get_url(action='info', ident=item.ident) + ')')])
            xbmcplugin.addDirectoryItem(_handle, get_url(action='play', ident=item.ident, name=item.name), listitem, False)
    xbmcplugin.endOfDirectory(_handle)


def forget(params):
    removesearch(params.get('what', ''))
    xbmc.executebuiltin('Container.Refresh')


# ---------- serialy ----------

def _episode_items(group, season, episode):
    items = []
    for it in group.items:
        s = it.parsed.season if it.parsed.season is not None else 1
        if s == season and it.parsed.episode == episode:
            items.append(it)
    return items


def series(params):
    xbmcplugin.setPluginCategory(_handle, _addon.getAddonInfo('name') + " \\ " + params.get('t', ''))
    client = _client()
    _files, groups = _groups(client, params)
    group = _find_group(groups, params)
    seasons = group.seasons()
    if len(seasons) == 1:
        _list_episodes(group, params, next(iter(seasons)))
        return
    xbmcplugin.setContent(_handle, 'seasons')
    xbmcplugin.addSortMethod(_handle, xbmcplugin.SORT_METHOD_NONE)
    for number in sorted(seasons):
        count = len(seasons[number])
        listitem = xbmcgui.ListItem(label='%s %d' % (S(30222), number), label2='%d %s' % (count, S(30226)))
        listitem.setArt({'icon': 'DefaultFolder.png'})
        _set_video_info(listitem, '%s %d' % (S(30222), number), mediatype='season',
                        season=number, tvshowtitle=group.title)
        xbmcplugin.addDirectoryItem(_handle, get_url(action='season', n=number, **_keep(params)), listitem, True)
    xbmcplugin.endOfDirectory(_handle)


def _keep(params):
    return {k: params[k] for k in ('q', 'c', 's', 'g', 't') if k in params}


def season(params):
    xbmcplugin.setPluginCategory(_handle, _addon.getAddonInfo('name') + " \\ " + params.get('t', ''))
    client = _client()
    _files, groups = _groups(client, params)
    group = _find_group(groups, params)
    _list_episodes(group, params, int(params['n']))


def _list_episodes(group, params, number):
    episodes = group.seasons().get(number, {})
    xbmcplugin.setContent(_handle, 'episodes')
    xbmcplugin.addSortMethod(_handle, xbmcplugin.SORT_METHOD_NONE)
    ref = _keep(params)
    for ep in sorted(e for e in episodes if e is not None):
        count = len(episodes[ep])
        label2 = '%d %s' % (count, S(30224)) if count > 1 else ''
        listitem = xbmcgui.ListItem(label='%s %d' % (S(30223), ep), label2=label2)
        listitem.setProperty('IsPlayable', 'true')
        _set_video_info(listitem, '%s %d' % (S(30223), ep), mediatype='episode',
                        season=number, episode=ep, tvshowtitle=group.title)
        item_ref = dict(ref, n=number, e=ep)
        listitem.addContextMenuItems(_group_context(item_ref))
        xbmcplugin.addDirectoryItem(_handle, get_url(action='pick', mode='play', **item_ref), listitem, False)
    for item in episodes.get(None, []):  # baliky cele rady
        listitem = xbmcgui.ListItem(label='%s · %s' % (item.name, title_parser.variant_label(item)))
        listitem.setProperty('IsPlayable', 'true')
        listitem.addContextMenuItems([(S(30211), 'RunPlugin(' + get_url(action='info', ident=item.ident) + ')')])
        xbmcplugin.addDirectoryItem(_handle, get_url(action='play', ident=item.ident, name=item.name), listitem, False)
    xbmcplugin.endOfDirectory(_handle)


# ---------- vyber varianty -> prehrat / info / fronta ----------

def pick(params):
    mode = params.get('mode', 'play')
    client = _client()
    _files, groups = _groups(client, params)
    group = _find_group(groups, params)

    if 'e' in params:
        number, episode = int(params['n']), int(params['e'])
        items = _episode_items(group, number, episode)
        heading = '%s · %s %d' % (group.title, S(30223), episode)
    else:
        number = episode = None
        items = group.items
        heading = _group_label(group)

    item = choose_variant(items, '%s · %s' % (heading, S(30221))) if items else None
    if item is None:
        if mode == 'play':
            xbmcplugin.setResolvedUrl(_handle, False, xbmcgui.ListItem())
        return

    if mode == 'info':
        info({'ident': item.ident})
    else:
        play({'ident': item.ident, 'name': item.name, 'title': group.title,
              'year': group.year or '', 'n': '' if number is None else number,
              'e': '' if episode is None else episode})


def settings(params):
    _addon.openSettings()
    xbmcplugin.setResolvedUrl(_handle, False, xbmcgui.ListItem())


# ---------- informace o souboru ----------

def sizelize(txtsize, units=('B', 'KB', 'MB', 'GB')):
    if txtsize:
        size = float(txtsize)
        if size < 1024:
            return str(size) + units[0]
        size = size / 1024
        if size < 1024:
            return str(int(round(size))) + units[1]
        size = size / 1024
        if size < 1024:
            return str(round(size, 2)) + units[2]
        return str(round(size / 1024, 2)) + units[3]
    return str(txtsize)


def infonize(data, key, process=str, showkey=True, prefix='', suffix='\n'):
    if key in data:
        return prefix + (key.capitalize() + ': ' if showkey else '') + process(data[key]) + suffix
    return ''


def fpsize(fps):
    x = round(float(fps), 3)
    return str(int(x)) if int(x) == x else str(x)


def _bitrate(x):
    return sizelize(x, ['bps', 'Kbps', 'Mbps', 'Gbps'])


def _streams(info_data, kind):
    if kind in info_data and isinstance(info_data[kind], dict) and 'stream' in info_data[kind]:
        streams = info_data[kind]['stream']
        return [streams] if isinstance(streams, dict) else streams
    return []


def info(params):
    data = _client().file_info(params['ident'])
    text = ''
    text += infonize(data, 'name')
    text += infonize(data, 'size', sizelize)
    text += infonize(data, 'type')
    text += infonize(data, 'width')
    text += infonize(data, 'height')
    text += infonize(data, 'format')
    text += infonize(data, 'fps', fpsize)
    text += infonize(data, 'bitrate', _bitrate)
    for stream in _streams(data, 'video'):
        text += 'Video stream: '
        text += infonize(stream, 'width', showkey=False, suffix='')
        text += infonize(stream, 'height', showkey=False, prefix='x', suffix='')
        text += infonize(stream, 'format', showkey=False, prefix=', ', suffix='')
        text += infonize(stream, 'fps', fpsize, showkey=False, prefix=', ', suffix='')
        text += '\n'
    for stream in _streams(data, 'audio'):
        text += 'Audio stream: '
        text += infonize(stream, 'format', showkey=False, suffix='')
        text += infonize(stream, 'channels', prefix=', ', showkey=False, suffix='')
        text += infonize(stream, 'bitrate', _bitrate, prefix=', ', showkey=False, suffix='')
        text += '\n'
    text += infonize(data, 'removed', lambda x: 'Yes' if x == '1' else 'No')
    xbmcgui.Dialog().textviewer(_addon.getAddonInfo('name'), text)


# ---------- prehravani ----------

def play(params):
    client = _client()
    duuid = _addon.getSetting('duuid')
    if not duuid:
        duuid = str(uuid.uuid4())
        _addon.setSetting('duuid', duuid)
    link = client.file_link(params['ident'], 'video_stream', duuid)
    link = link + '|' + urlencode(client.play_headers())

    name = params.get('name', '')
    parsed = title_parser.parse_name(name)
    title = params.get('title') or parsed.title or name
    year = params.get('year') or parsed.year
    season_no = params.get('n') if params.get('n') not in (None, '') else parsed.season
    episode_no = params.get('e') if params.get('e') not in (None, '') else parsed.episode

    listitem = xbmcgui.ListItem(label=name, path=link)
    listitem.setProperty('mimetype', 'application/octet-stream')
    # titul, rok, rada a epizoda: podle nich hledaji titulky doplnky v Kodi
    if episode_no is not None:
        _set_video_info(listitem, title, mediatype='episode', season=season_no,
                        episode=episode_no, tvshowtitle=title)
    else:
        _set_video_info(listitem, title, year=year)
    xbmcplugin.setResolvedUrl(_handle, True, listitem)


# ---------- menu a router ----------

def searches(params):
    """Historie hledani (ulozena v profilu)."""
    xbmcplugin.setPluginCategory(_handle, _addon.getAddonInfo('name') + " \\ " + S(30234))
    xbmcplugin.addSortMethod(_handle, xbmcplugin.SORT_METHOD_NONE)
    for entry in loadsearch():
        listitem = xbmcgui.ListItem(label=entry)
        listitem.setArt({'icon': 'DefaultAddonsSearch.png'})
        listitem.addContextMenuItems([(S(30213), 'RunPlugin(' + get_url(action='forget', what=entry) + ')')])
        xbmcplugin.addDirectoryItem(_handle, get_url(action='search', what=entry), listitem, True)
    xbmcplugin.endOfDirectory(_handle)


def menu():
    xbmcplugin.setPluginCategory(_handle, _addon.getAddonInfo('name'))
    for label_id, icon, action, folder in (
            (30205, 'DefaultAddSource.png', 'search', True),
            (30234, 'DefaultAddonsSearch.png', 'searches', True),
            (30204, 'DefaultAddonService.png', 'settings', False)):
        listitem = xbmcgui.ListItem(label=S(label_id))
        listitem.setArt({'icon': icon})
        xbmcplugin.addDirectoryItem(_handle, get_url(action=action), listitem, folder)
    xbmcplugin.endOfDirectory(_handle)


ACTIONS = {
    'search': search,
    'searches': searches,
    'other': other,
    'forget': forget,
    'series': series,
    'season': season,
    'pick': pick,
    'settings': settings,
    'info': info,
    'play': play,
}
DIRECTORY_ACTIONS = ('search', 'searches', 'other', 'series', 'season')


def _fail(params, error):
    """Zobrazi chybu a korektne ukonci aktualni akci."""
    traceback.print_exc()
    if isinstance(error, ws_api.AuthError):
        popinfo(S(30102), icon=xbmcgui.NOTIFICATION_ERROR, sound=True)
        _addon.openSettings()
    else:
        popinfo(str(error) or S(30107), icon=xbmcgui.NOTIFICATION_WARNING)
    action = params.get('action')
    resolving = action == 'play' or (action == 'pick' and params.get('mode', 'play') == 'play')
    if resolving:
        xbmcplugin.setResolvedUrl(_handle, False, xbmcgui.ListItem())
    elif action in DIRECTORY_ACTIONS:
        xbmcplugin.endOfDirectory(_handle, succeeded=False)


def router(paramstring):
    params = dict(parse_qsl(paramstring))
    handler = ACTIONS.get(params.get('action'))
    if handler is None:
        menu()
        return
    try:
        handler(params)
    except ws_api.WebshareError as e:
        _fail(params, e)
