# Předání práce: Webshare Stream Cinema (Kodi doplněk)

Stav k 12. 11. 2026. Tento soubor slouží k pokračování v nové session. Není commitnutý v gitu (jen lokální poznámka).

## Cíl projektu

Kodi doplněk pro Webshare.cz. Uživatel v 99 % případů jen vyhledá film nebo seriál podle názvu a pustí ho. Žádné přehledy novinek, správce seriálů ani stahování. Původní doplněk (YAWsP) byl přepracován do vlastní verze.

## Pracovní dohody s uživatelem

- Komunikace česky.
- **Skripty a testy v Kodi spouští uživatel sám.** Dávat mu příkazy s cestou přes `$env:USERPROFILE` (spustitelné odkudkoli) a čekat na „hotovo“. Já ověřuji jen syntaxi (`py_compile`) a čtu výstupní soubory.
- **Nikde nesmí být jméno uživatele, firma ani e-mail.** Poskytovatel doplňku, název i autor commitů je jen „Webshare Stream Cinema“. Commity: `Webshare Stream Cinema <noreply@webshare-stream-cinema.invalid>` (nastaveno lokálně v repozitáři projektu) a na konci zprávy řádek `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Přezdívka `DroidLukish` je jen v adrese GitHub repozitáře.
- **Push na GitHub jen na výslovný pokyn** („commit a push“).
- V doplňku se nesmí objevit slovo „yawsp“ ani jméno původního autora. Licence AGPL a `LICENSE.txt` zůstávají.
- Cesta k projektu: `<slozka-projektu>` (složka s tímto souborem). Skript `build_zip.py` ukládá zip na Plochu v uživatelském profilu (`%USERPROFILE%\Desktop`).
- Pozor: domovský adresář uživatele ve Windows může být sám git repozitář. Repozitář projektu je samostatný ve složce projektu (vnořený).

## Architektura

| Soubor | Role |
|---|---|
| `main.py` | vstup, volá `streamcinema.router` |
| `streamcinema.py` | UI v Kodi: menu, hledání, dialog s verzemi, seriály, přehrání |
| `ws_api.py` | klient Webshare API (bez Kodi závislostí): timeouty, token se ověřuje až při chybě |
| `title_parser.py` | rozbor názvu souboru (titul, rok, řada/epizoda, kvalita, zdroj, jazyk) a seskupení výsledků |
| `md5crypt.py` | pomocné pro přihlášení (beze změny) |
| `resources/` | `settings.xml`, jazyky cs/en/sk (`strings.po`), `icon.png` (logo Webshare, 512×512) |
| `repository.webshare.streamcinema/addon.xml` | repozitářový doplněk pro automatické aktualizace |
| `repo/` | generované: `addons.xml`, `addons.xml.md5`, `zips/…` (verzuje se v gitu) |
| `tests/test_title_parser.py` | 28 testů parseru, procházejí |
| `tools/` | `build_zip.py`, `make_repo.py`, `probe_webshare.py`, `probe_subtitles.py`, `search_like_plugin.py`, `show_groups.py`; výstupy v `tools/probe_output/` (v `.gitignore`) |
| `_backup_original/`, `plugin/` | původní verze a původní zip, jen lokálně (v `.gitignore`) |

ID doplňku: `plugin.video.webshare.streamcinema`, verze `1.00` (v `addon.xml`), repozitářový doplněk `repository.webshare.streamcinema` `1.0.0`. Vyžaduje Kodi 19+.

## Co doplněk dnes dělá

- Hlavní menu: **Nové hledání, Historie hledání, Nastavení** (Chci si stáhnout, Historie stahování, stahování, Backup DB a správce seriálů byly odstraněny).
- Hledání: až `spages` stran po 100 souborech (nastavení, výchozí 3), cache výsledků 30 min v profilu (`search_cache.json`), odstranění duplicit, seskupení podle filmu/seriálu. Skupina „Ostatní soubory“ jen pro nejednoznačné případy.
- Klik na film: **dialog s verzemi se ukazuje vždy**, i při jedné (řádek: kvalita · zdroj · jazyk · velikost, pod ním název souboru; řazení: česká verze, kvalita, hodnocení, velikost). Kontextové menu: Informace o souboru.
- Seriály: složka seriálu, řady, epizody, výběr verze.
- Přehrání předává titul, rok, řadu a epizodu (pro doplňky s titulky).
- Titulky: **varianta A**, tedy přes doplněk titulků v Kodi. Varianta B (titulky z Webshare) byla zkoumána a zamítnuta: `similar_files` titulky nevrací a hledání `.srt` dává šum.

## Poznatky o serveru Webshare

- `search` bere `what`, `sort` (recent, rating, largest, smallest), `category`, `limit`, `offset`; **maximum 1000 výsledků** na dotaz (strop serveru).
- Diakritika a tečky v dotazu nehrají roli. Řazení probíhá před oříznutím na limit (jiná sada výsledků, ne jen jiné pořadí).
- Stejný soubor se vrací víckrát s různými `ident` (nutný dedup).
- Kategorie `video` titulky nenajde. Bez kategorie ano, ale s volnou shodou.
- Název souborů je velmi nepravidelný (tečky, pomlčky, římské číslice, „Epizoda I“, české i anglické jméno).

## Kde jsme (ověřeno × neověřeno)

Ověřeno:
- Všech 28 testů prochází, seskupení „star wars“ nad uloženými daty vypadá dobře (111 skupin, seriály se nemíchají, původní filmy mají vlastní skupiny).
- Instalace přes repozitář z GitHubu v Kodi proběhla v pořádku.
- Dialog s verzemi funguje v Kodi (starší sestavení, film SpongeBob).

**Neověřeno v Kodi** (po poslední sérii změn): nové menu se třemi položkami, Historie hledání, dialog při jediném souboru, seriály (řada → epizoda), titulky z Kodi doplňku, automatická aktualizace na vyšší verzi.

Dříve hlášené „Test nedopadl dobře“: příčina se nejspíš shodovala s tím, že na TV byl starší zip (nový název, ale staré menu). Přesně se to nepotvrdilo.

## Otevřené body

1. **Ověřit automatickou aktualizaci**: zvýšit `version` v `addon.xml`, spustit `tools\make_repo.py`, commit, push, v Kodi Aktualizovat.
2. **Řazení skupin ve výsledcích**: uživatel zatím neodpověděl na návrh „filmy před seriály a výpisy z her“. Teď platí pořadí podle serveru.
3. **Výrazná změna vzhledu** (uživatel to chce): možnosti probrané v chatu: (1) plakáty, popisy, pozadí z TMDB (potřebuje API klíč, cache), (2) vlastní okno `WindowXML`, (3) jiný skin a plakátový pohled, (4) drobné barvy a ikony. Doporučeno 1 + 3. **Čekáme, co přesně uživatele na vzhledu ruší.**
4. **Levý pruh v Estuary** (velká ikona): jde z pohledu skinu. Řešení: v Možnostech zvolit „Široký seznam“, nebo vynutit pohled příkazem `Container.SetViewMode` (u Estuary číslo 55; křehké u jiných skinů). Nerozhodnuto.
5. Drobnosti: české a anglické jméno téhož seriálu zůstává ve dvou skupinách; překlepy v názvech souborů se nespojí; nepoužívané metody fronty a historie v `ws_api.py`; nepoužité řetězce v `strings.po` (30040 až 30044, 30208 až 30212, 30301 až 30304 a další).

## Postup vydání nové verze

1. Zvýšit `version` v `addon.xml` (a případně poznámky `<news>`).
2. `python "<slozka-projektu>\tools\make_repo.py"` (generuje `repo/`).
3. Commit a push (jen na pokyn uživatele).
4. V Kodi: Doplňky, Moje doplňky, Aktualizovat (jinak se kontroluje asi jednou za den; GitHub cachuje několik minut).

Samostatný zip bez repozitáře: `tools\build_zip.py` (uloží na Plochu).

Testy: `python -m unittest discover -s "<slozka-projektu>\tests" -v`

Seskupení nad uloženými daty bez přihlášení: `tools\search_like_plugin.py "star wars" 10 offline` (výstup `tools\probe_output\search_star_wars.txt`).

## GitHub

Repozitář (veřejný): <https://github.com/DroidLukish/Webshare-Stream-Cinema>, větev `main`, poslední commit `6dd7174` („Kodi repozitar pro automaticke aktualizace“). Instalace v Kodi: nejdřív zip repozitářového doplňku `repo/zips/repository.webshare.streamcinema/repository.webshare.streamcinema-1.0.0.zip`, pak Instalovat z repozitáře, Webshare Stream Cinema Repository, Doplňky videa, Webshare Stream Cinema.

Poznámka: `HANDOFF.md` je nový nesledovaný soubor. Pokud ho uživatel chce mít na GitHubu, commitnout ho jen na jeho pokyn.
