# Fish S2 Pro — niemieckie słowa: raport końcowy

Generacja zakończona 2026-10-13 o 15:39:42. Weryfikacja zakończona o 15:45:39.

- Plan: 122 049 haseł.
- Baza: 122 049 rekordów.
- Pliki: 122 049 nagrań.
- Brak brakujących lub dodatkowych rekordów i plików.
- Każdy plik: zgodny hash tekstu i konfiguracji, rozmiar i SHA256; pełne dekodowanie bez błędu, dane skończone i niesilentne.
- Format: OGG Vorbis, mono, 24 000 Hz.
- Rozmiar audio: 1 209 380 145 bajtów (około 1,21 GB).
- Głos: ten sam zatwierdzony kobiecy głos referencyjny; model lokalny fishaudio/s2-pro.
- Tymczasowy scheduler wyłączony po pozytywnej weryfikacji.

Nagrania znajdują się w sounds/w w głównym katalogu repozytorium Dictionary-DE. Ten raport opisuje weryfikację mastera przed publikacją. Podczas generacji nie podmieniono instalacji addona.

## Jakość i ograniczenia

51 różnych nagrań wymaga odsłuchu: 39 oznaczonych jako zbyt krótkie i 12 jako zbyt długie. Jedno z długich osiągnęło także limit tokenów. Flagi są heurystyką, a nie potwierdzonym błędem wymowy. Kontrola techniczna nie zastępuje audytu wymowy całego zbioru.

W historii zapisano jeden błąd PermissionError podczas podmiany progress.json. Dodano krótkie ponawianie operacji i wznowiono proces. Nagranie Todesblickiris jest obecne i przeszło końcową weryfikację.

## Pliki raportów

- verification-report.json: pełny wynik kontroli.
- verification-flags.json: hasła, ścieżki, flagi i długości.
- verification.log: przebieg weryfikacji.
- generation.sqlite: metadane i sumy nagrań.

## Nagrania do odsłuchu

- AAAARRRRRGGGHHHHH — 4.087 s; too_long; sounds/w/96/967252c0fae4500b.ogg
- as — 0.186 s; too_short; sounds/w/5e/5e25208dbfbb1f6c.ogg
- aufs — 0.186 s; too_short; sounds/w/7e/7e62165ca8654fe9.ogg
- Chub — 0.186 s; too_short; sounds/w/80/8069d93971f27ac4.ogg
- dacht — 0.186 s; too_short; sounds/w/a1/a108a5e319c1991c.ogg
- das — 0.093 s; too_short; sounds/w/da/da4f123fc9a465b8.ogg
- dasss — 0.186 s; too_short; sounds/w/d8/d8bf09754b86fdc6.ogg
- dem — 0.186 s; too_short; sounds/w/d0/d0598fddb7ad43be.ogg
- des — 0.093 s; too_short; sounds/w/d2/d2599303c1ad537c.ogg
- dick — 0.186 s; too_short; sounds/w/65/6537d094b9be7091.ogg
- Diem — 0.186 s; too_short; sounds/w/5f/5f3349f4dfcdb6ed.ogg
- ebbt — 0.186 s; too_short; sounds/w/7c/7cc6046879c1812d.ogg
- es — 0.186 s; too_short; sounds/w/46/461a6d69c7b09ea8.ogg
- Gebr — 0.139 s; too_short; sounds/w/6d/6d0da4e9cb1cf0d8.ogg
- giiibt — 0.139 s; too_short; sounds/w/12/127fa8992faee0b0.ogg
- Grlrlrglrmg — 2.508 s; too_long; sounds/w/bf/bf091b1bb0155cc0.ogg
- HARRRRR — 3.947 s; too_long; sounds/w/2c/2ceed68851e2801f.ogg
- He — 0.093 s; too_short; sounds/w/5c/5c3ae3b6b9a3bcab.ogg
- Hick — 0.139 s; too_short; sounds/w/52/52d34db08475d0cd.ogg
- Hm — 0.186 s; too_short; sounds/w/64/643af04eb1a3b013.ogg
- Hmph — 0.186 s; too_short; sounds/w/9f/9f269ff6c8f847a3.ogg
- Ick — 0.093 s; too_short; sounds/w/80/80e10e8a91a95ced.ogg
- Ik — 0.093 s; too_short; sounds/w/46/4638827dd7a62a7c.ogg
- im — 0.186 s; too_short; sounds/w/40/4038790bd5a62756.ogg
- in'n — 0.093 s; too_short; sounds/w/30/3018a8cf1ffb8ba6.ogg
- ins — 0.186 s; too_short; sounds/w/98/98e98317718d5410.ogg
- it — 0.093 s; too_short; sounds/w/47/47388410cea61c51.ogg
- Jup — 0.186 s; too_short; sounds/w/d3/d3bc1b38e757aecf.ogg
- kann — 0.186 s; too_short; sounds/w/29/29d348f98fe89978.ogg
- kickt — 0.139 s; too_short; sounds/w/49/49329171baa6b9ba.ogg
- Krick — 0.186 s; too_short; sounds/w/ed/edc2c6c106fd409a.ogg
- Krieg — 0.139 s; too_short; sounds/w/c9/c9d1989fdaedf0cc.ogg
- kriegt — 0.139 s; too_short; sounds/w/9f/9ff3b9f15c91f1a8.ogg
- litt — 0.139 s; too_short; sounds/w/fa/faf48066d0247a3b.ogg
- lrglgllmrrglm — 3.715 s; too_long; sounds/w/2d/2d062b2e4b0990ad.ogg
- lrlgllrlm — 11.099 s; token_limit, too_long; sounds/w/c9/c963ccc74e7a87a8.ogg
- mglgrgrlm — 6.502 s; too_long; sounds/w/4b/4bb47eccc9e8cb07.ogg
- mgrlmlgr — 3.576 s; too_long; sounds/w/55/5589ddb764e7e3ea.ogg
- mlrmglrgr — 2.508 s; too_long; sounds/w/86/862209d16464f2f2.ogg
- Mmm — 0.186 s; too_short; sounds/w/ca/ca99d446dd6d31b5.ogg
- Mmmrrrgggllls — 3.437 s; too_long; sounds/w/a6/a6e54e621d45c261.ogg
- mrlglmrgm — 3.019 s; too_long; sounds/w/dc/dceda57afbe87f25.ogg
- Na — 0.093 s; too_short; sounds/w/54/543659f0b19f32e5.ogg
- Nr — 0.093 s; too_short; sounds/w/47/47364579be9f475c.ogg
- Psst — 0.139 s; too_short; sounds/w/62/62d3d803c3bff8c2.ogg
- rlmgr — 3.437 s; too_long; sounds/w/35/35860097f7e92354.ogg
- rmglrgmlr — 3.437 s; too_long; sounds/w/b9/b9e59d0d2dc4aff6.ogg
- rum — 0.186 s; too_short; sounds/w/29/29cd4d372eba5230.ogg
- tsss — 0.093 s; too_short; sounds/w/f8/f8a087fe08c78c5f.ogg
- up — 0.093 s; too_short; sounds/w/43/43430b20cad7b2d1.ogg
- zsch — 0.093 s; too_short; sounds/w/e5/e5c42b4906b17578.ogg
