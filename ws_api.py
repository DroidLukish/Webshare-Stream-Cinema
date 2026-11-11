# -*- coding: utf-8 -*-
# Module: ws_api
# Tenka vrstva nad Webshare API. Nezavisi na Kodi (zadne importy xbmc*),
# takze ji lze zkouset i mimo Kodi.
# License: AGPL v.3 https://www.gnu.org/licenses/agpl-3.0.html

import hashlib
import xml.etree.ElementTree as ET

import requests

from md5crypt import md5crypt

BASE = 'https://webshare.cz'
API = BASE + '/api/'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36')
HEADERS = {'User-Agent': UA, 'Referer': BASE}
REALM = ':Webshare:'

CATEGORIES = ['', 'video', 'images', 'audio', 'archives', 'docs', 'adult']
SORTS = ['', 'recent', 'rating', 'largest', 'smallest']

DEFAULT_TIMEOUT = 20


class WebshareError(Exception):
    """Chyba site, odpovedi serveru nebo API."""

    def __init__(self, message, code=None):
        Exception.__init__(self, message)
        self.code = code


class AuthError(WebshareError):
    """Chybi udaje nebo prihlaseni selhalo."""


class SearchPage(object):
    __slots__ = ('total', 'files')

    def __init__(self, total, files):
        self.total = total
        self.files = files


def is_ok(root):
    status = root.find('status')
    return status is not None and status.text == 'OK'


def todict(xml, skip=()):
    """XML element -> dict. Opakujici se tagy se slouci do seznamu."""
    result = {}
    for e in xml:
        if e.tag in skip:
            continue
        value = e.text if len(list(e)) == 0 else todict(e, skip)
        if e.tag in result:
            if isinstance(result[e.tag], list):
                result[e.tag].append(value)
            else:
                result[e.tag] = [result[e.tag], value]
        else:
            result[e.tag] = value
    return result


def _error_text(root):
    msg = root.find('message')
    code = root.find('code')
    return (msg.text if msg is not None and msg.text else 'Chyba serveru',
            code.text if code is not None else None)


class WebshareClient(object):
    """
    Klient API. Token se pouziva bez dalsiho overovani; teprve kdyz server
    vrati chybu, overi se token (user_data) a pripadne se znovu prihlasi.
    Diky tomu odpada jeden dotaz navic pri kazdem kliknuti v pluginu.
    """

    def __init__(self, username='', password='', token='', on_token=None,
                 session=None, timeout=DEFAULT_TIMEOUT):
        self.username = username or ''
        self.password = password or ''
        self.token = token or ''
        self.on_token = on_token
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)

    # ---- nizka uroven ----
    def _raw(self, fn, data):
        try:
            response = self.session.post(API + fn + '/', data=data, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as e:
            raise WebshareError('Chyba site: %s' % e)
        try:
            return ET.fromstring(response.content)
        except ET.ParseError:
            raise WebshareError('Neplatna odpoved serveru (%s)' % fn)

    def _fail(self, root):
        text, code = _error_text(root)
        raise WebshareError(text, code)

    def login(self):
        if not self.username or not self.password:
            raise AuthError('Chybi prihlasovaci udaje')
        root = self._raw('salt', {'username_or_email': self.username})
        if not is_ok(root):
            raise AuthError('Prihlaseni selhalo')
        salt = root.find('salt').text
        encrypted = hashlib.sha1(
            md5crypt(self.password.encode('utf-8'), salt.encode('utf-8')).encode('utf-8')
        ).hexdigest()
        digest = hashlib.md5(
            (self.username + REALM + encrypted).encode('utf-8')).hexdigest()
        root = self._raw('login', {'username_or_email': self.username,
                                   'password': encrypted, 'digest': digest,
                                   'keep_logged_in': 1})
        if not is_ok(root):
            raise AuthError('Prihlaseni selhalo')
        self.token = root.find('token').text
        if self.on_token:
            self.on_token(self.token)
        return self.token

    def _token_valid(self):
        if not self.token:
            return False
        return is_ok(self._raw('user_data', {'wst': self.token}))

    def _call(self, fn, data=None):
        """Volani s tokenem. Vraci XML korene i pri chybe API (rozhodne volajici)."""
        data = dict(data or {})
        if not self.token:
            self.login()
        data['wst'] = self.token
        root = self._raw(fn, data)
        if is_ok(root):
            return root
        if self._token_valid():
            return root  # token je v poradku, jde o skutecnou chybu API
        self.login()
        data['wst'] = self.token
        return self._raw(fn, data)

    def _call_ok(self, fn, data=None):
        root = self._call(fn, data)
        if not is_ok(root):
            self._fail(root)
        return root

    # ---- ucet ----
    def user_data(self):
        return todict(self._call_ok('user_data'))

    # ---- hledani ----
    def search(self, what, sort='', category='video', limit=100, offset=0):
        root = self._call_ok('search', {'what': what, 'sort': sort,
                                        'category': category,
                                        'limit': limit, 'offset': offset})
        try:
            total = int(root.find('total').text)
        except (AttributeError, TypeError, ValueError):
            total = 0
        return SearchPage(total, [todict(f) for f in root.iter('file')])

    # ---- soubory ----
    def file_info(self, ident):
        root = self._call('file_info', {'ident': ident})
        if not is_ok(root):
            root = self._call('file_info', {'ident': ident, 'maybe_removed': 1})
        if not is_ok(root):
            self._fail(root)
        return todict(root)

    def file_link(self, ident, download_type='video_stream', device_uuid=None):
        data = {'ident': ident, 'download_type': download_type}
        if device_uuid:
            data['device_uuid'] = device_uuid
        return self._call_ok('file_link', data).find('link').text

    # ---- fronta a historie ----
    def queue_list(self):
        return [todict(f) for f in self._call_ok('queue').iter('file')]

    def queue_add(self, ident):
        self._call_ok('queue_file', {'ident': ident})

    def queue_remove(self, ident):
        self._call_ok('dequeue_file', {'ident': ident})

    def history_list(self):
        """Seznam souboru vcetne download_id (potreba pro mazani)."""
        return [todict(f) for f in self._call_ok('history').iter('file')]

    def history_remove(self, ident):
        ids = [f['download_id'] for f in self.history_list()
               if f.get('ident') == ident and f.get('download_id')]
        if ids:
            self._call_ok('clear_history', {'ids[]': ids})
        return len(ids)

    def play_headers(self):
        """Hlavicky pro prehravac (Kodi: odkaz|hlavicky). Nemeni sdilenou session."""
        headers = dict(HEADERS)
        headers['Cookie'] = 'wst=' + self.token
        return headers
