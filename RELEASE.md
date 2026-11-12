# Vydání nové verze doplňku

Postup, jak nahrát novou verzi Webshare Stream Cinema na GitHub, aby si ji Kodi stáhlo samo.

Jak to funguje: Kodi má nainstalovaný repozitářový doplněk, který ukazuje na soubor `repo/addons.xml` na GitHubu. Kodi si ho pravidelně stahuje a porovnává verze. Pokud je tam **vyšší verze** doplňku než nainstalovaná, stáhne zip z `repo/zips/` a doplněk aktualizuje.

## Rychlý postup

1. **Dokončete změny** v kódu a ověřte je (viz Kontrola před vydáním níže).
2. **Zvyšte verzi** v souboru `addon.xml` (atribut `version` u prvního řádku `<addon ...>`), například z `1.00` na `1.0.1`.
3. **Doplňte poznámky k verzi** v `addon.xml` v bloku `<news>` (nahoře přidejte `[B]1.0.1[/B]` a pár odrážek).
4. **Vygenerujte repozitář** (ve složce projektu):

   ```bash
   python tools/make_repo.py
   ```

   Skript vytvoří nový zip `repo/zips/plugin.video.webshare.streamcinema/plugin.video.webshare.streamcinema-<verze>.zip`, přepíše `repo/addons.xml` a `repo/addons.xml.md5`.
5. **Commit a push:**

   ```bash
   git add -A
   git commit -m "Verze 1.0.1: stručný popis změn"
   git push origin main
   ```
6. **Počkejte pár minut** (GitHub si soubory na chvíli ukládá do mezipaměti) a v Kodi spusťte kontrolu aktualizací (viz Ověření v Kodi).

## Pravidla pro verzi

- Kodi aktualizuje jen tehdy, když je nová verze **číselně vyšší**. Porovnává se po částech oddělených tečkou: `1.0.1` je vyšší než `1.00`, `1.1.0` je vyšší než `1.0.9`.
- Doporučené schéma od teď: tři čísla (`1.0.1`, `1.0.2`, `1.1.0`, `2.0.0`).
  - poslední číslo: oprava chyby,
  - prostřední: nová funkce,
  - první: velká změna.
- **Nikdy verzi nevracejte zpět ani nepřepisujte zip se stejným číslem.** Kodi by změnu nepoznalo.
- Nová verze musí být v `addon.xml` v hlavním adresáři projektu. `repo/addons.xml` se **needituje ručně**, vždy ho generuje `make_repo.py`.

## Kontrola před vydáním

Před zvýšením verze doporučuji:

```bash
python -m unittest discover -s tests -v
```

Všechny testy musí projít. Ve složce projektu pak ještě zkontrolujte:

- `git status`: v seznamu změn jsou jen soubory, které čekáte,
- v `addon.xml` se nezměnilo ID doplňku (`plugin.video.webshare.streamcinema`) ani název,
- `README.md` odpovídá novým funkcím.

## Co skript vygeneruje a co se nahraje

| Soubor | Význam |
|---|---|
| `repo/addons.xml` | seznam doplňků a jejich verzí (doplněk i repozitářový doplněk) |
| `repo/addons.xml.md5` | kontrolní součet `addons.xml` (Kodi ho kontroluje před stažením) |
| `repo/zips/plugin.video.webshare.streamcinema/…-<verze>.zip` | zip nové verze |
| `repo/zips/repository.webshare.streamcinema/…-1.0.0.zip` | zip repozitářového doplňku (nemění se) |
| `repo/zips/…/resources/icon.png`, `icon.png` | ikony zobrazené v Kodi |

Starší zipy v `repo/zips/` můžete nechat (slouží jako archiv) nebo je smazat. Kodi stahuje jen verzi uvedenou v `addons.xml`.

## Ověření v Kodi

1. Doplňky, Moje doplňky, Doplňky videa, Webshare Stream Cinema. U doplňku by se měla ukázat nová verze, případně nabídka aktualizace.
2. Ruční kontrola: Doplňky, Moje doplňky, vpravo nahoře (nebo klávesa pro možnosti) a Aktualizovat. Nebo restartujte Kodi, při startu kontroluje aktualizace.
3. Ověřte: Informace o doplňku, číslo verze odpovídá tomu, co jste nahráli.
4. Vyzkoušejte hlavní funkce (hledání, přehrání filmu, seriál).

Automatické aktualizace se zapínají v Nastavení, Systém, Doplňky, Aktualizace: musí být „Instalovat aktualizace automaticky“. Jinak se jen zobrazí upozornění.

## Když to nefunguje

| Příznak | Příčina a řešení |
|---|---|
| Kodi novou verzi nenabízí | Mezipaměť GitHubu (počkejte 5 až 10 minut) nebo Kodi ještě nekontrolovalo. Zkuste ruční Aktualizovat. |
| Verze se nezměnila ani po delší době | Verze v `addon.xml` není vyšší než nainstalovaná. Zvyšte ji a vygenerujte znovu. |
| Kodi hlásí chybu při stahování repozitáře | Zkontrolujte, že repozitář je **veřejný** a že soubory `repo/addons.xml` a `repo/addons.xml.md5` jsou na GitHubu ve větvi `main`. |
| Kontrolní součet nesouhlasí | `addons.xml` a `.md5` se nahrály z různých běhů skriptu, nebo Git změnil konce řádků. Spusťte `make_repo.py` znovu a commitujte oba soubory najednou. Soubor `.gitattributes` drží správné konce řádků. |
| Zip je ve složce, ale Kodi ho nestáhne | Zkontrolujte, že zip prošel gitem (`git ls-files repo/zips`). Zipy ve složce `repo/zips/` mají v `.gitignore` výjimku. |
| Po aktualizaci doplněk spadne | Chybu najdete v `kodi.log` (řádky s `streamcinema` nebo `Traceback`). Opravte kód, zvyšte verzi o další číslo a vydejte znovu (starou verzi nepřepisujte). |

## Návrat k předchozí verzi

Přepsat vydanou verzi nejde (viz pravidla výše). Pokud je nová verze špatná:

1. Opravte kód (nebo vraťte změny přes `git revert <commit>`),
2. **zvyšte verzi** na další číslo (např. `1.0.2`),
3. vydejte stejným postupem.

Uživatelé tak dostanou opravenou verzi i tehdy, když už stihli stáhnout špatnou.

## Kdy je potřeba zvlášť řešit repozitářový doplněk

Jen když se změní adresa repozitáře (jiný účet nebo jiný název na GitHubu). Upravte adresy v `repository.webshare.streamcinema/addon.xml`, zvyšte jeho verzi (např. na `1.0.1`), spusťte `make_repo.py` a vydejte. Uživatelé pak musí repozitářový doplněk nainstalovat znovu ze zipu, protože staré adresy už nefungují.

## Samostatný zip (bez repozitáře)

Pro ruční instalaci nebo odeslání někomu bez repozitáře:

```bash
python tools/build_zip.py
```

Zip se uloží na Plochu v uživatelském profilu. Instaluje se v Kodi přes Doplňky, Instalovat z archivu ZIP.
