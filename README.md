# Webshare Stream Cinema

Kodi plugin pro přehrávání obsahu ze služby Webshare.cz. Cíl: vyhledat film nebo seriál podle názvu a pustit ho, nic navíc.

Vyžaduje Kodi 19 (Matrix) nebo novější a účet na Webshare.

## Co plugin umí

- vyhledávání podle názvu, seznam předchozích hledání (Historie hledání)
- přehrávání videí s výběrem verze
- informace o souboru (kontextové menu)

Hlavní menu: Nové hledání, Historie hledání, Nastavení.

Odebráno oproti předchozí verzi: správce seriálů, stahování souborů, Backup DB, přehledy novinek a seznamy Chci si stáhnout / Historie stahování.

## Stav přepracování

| Krok | Stav |
|---|---|
| Úklid a odstranění nepotřebných funkcí | hotovo |
| API vrstva `ws_api.py` (časový limit, bez zbytečného ověřování tokenu) | hotovo |
| Parser názvů a seskupování `title_parser.py` | hotovo, testy procházejí |
| Nové hledání (výsledky seskupené podle filmu, výběr varianty v dialogu) | napsáno, čeká na vyzkoušení v Kodi |
| Seriály (řada, epizoda, výběr varianty) v novém hledání | napsáno, čeká na vyzkoušení v Kodi |

Dosavadní verze před přepracováním je uložena v `_backup_original/`.

## Titulky

Plugin titulky nehledá sám. Nainstalujte v Kodi doplněk pro titulky (např. Titulky.com nebo OpenSubtitles) a v Nastavení, Přehrávač, Jazyk zvolte službu a jazyk. Plugin přehrávači předá titul, rok, řadu a epizodu.

## Soubory

| Soubor | Role |
|---|---|
| `main.py` | vstupní bod |
| `streamcinema.py` | uživatelské rozhraní v Kodi a router |
| `ws_api.py` | komunikace s API Webshare (nezávislé na Kodi) |
| `title_parser.py` | rozbor názvů souborů a seskupování (nezávislé na Kodi) |
| `tests/` | testy parseru: `python -m unittest discover -s tests -v` |
| `tools/` | jednorázové sondy a prohlížeč seskupení nad uloženými daty |

## Instalace a automatické aktualizace

Doplněk se do Kodi dostane přes repozitář na GitHubu, takže se nové verze stahují samy.

**Jednorázově v Kodi** (Nastavení, Doplňky, Instalovat z archivu ZIP): nainstalujte soubor
`repo/zips/repository.webshare.streamcinema/repository.webshare.streamcinema-1.0.0.zip`
(stáhněte ho z GitHubu). Pak: Doplňky, Instalovat z repozitáře, Webshare Stream Cinema Repository,
Doplňky videa, Webshare Stream Cinema. Kodi bude od té chvíle kontrolovat nové verze samo.

**Nové vydání** (vývojář):

1. zvýšit `version` v `addon.xml` (např. `1.00` na `1.01`),
2. `python tools/make_repo.py` (vytvoří zip, `repo/addons.xml` a kontrolní součet),
3. `git add -A`, `git commit`, `git push`.

Samostatný zip bez repozitáře vytvoří `python tools/build_zip.py`.

## Varování

Plugin neposkytuje žádný obsah, je to jen simulace prohlížeče veřejně dostupné webové stránky. Nejsem zodpovědný za obsah, který tato stránka poskytuje.
