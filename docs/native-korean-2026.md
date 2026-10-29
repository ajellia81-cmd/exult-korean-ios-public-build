# Native Korean packs (BG + SI)

This engine supports the per-font CP949 .FNT files from the installed 2026 Korean pack. It reads them at runtime; no game, translation or font data is included in this repository.

## iOS installation

Copy these directories from the supplied pack into the app's Documents folder:

- root `patch` -> `Documents/patch` (FONT*.FNT and EXULTMSG.TXT)
- `blackgate/STATIC` -> `Documents/game/blackgate/static`
- `blackgate/PATCH` -> `Documents/game/blackgate/patch`
- `serpentisle/STATIC` -> `Documents/game/serpentisle/static`
- `serpentisle/PATCH` -> `Documents/game/serpentisle/patch`
- optional audio `data` -> `Documents/data`

Use lowercase directory and file names throughout. The loader accepts uppercase FONT filenames too, but game asset lookup also needs correctly cased paths. Do not use the Windows exult.cfg, executables, DLLs, temporary files or its included GAMEDAT folders on iOS. The old korean.fnt is unnecessary when native fonts are installed.

Keep a backup of existing saves. Start a new game for this new translation baseline; do not assume old saves are compatible with the replaced USECODE/INITGAME data. New saves remain in Documents/save/blackgate and Documents/save/serpentisle. The app display name remains Ultima VII.

## Design and provenance

The format and source/index mapping were checked against wonst719/exult branch feature_korean_v1.12.x at 4c884fc721d1b84831395f9c9228bb6cc2ff4f1b. The supplied Windows log references 5cb47a350e63195d32c3e81f3dfd8876fa23de03, which is not publicly retrievable. We do not substitute that branch wholesale for the modern iOS engine.

The native parser validates both 0x11223344 and 0x11223345 formats, lengths, dimensions, duplicate codes and signed offsets. Native glyph colors, shadows, bearings and advances are preserved. ASCII is used from the native face when supplied for mixed text, with original game glyphs as fallback. CP949 extension syllables are consumed as whole code units. Missing curly quotes and ellipsis fall back to ordinary quotes and three periods.

Existing iOS fixes remain: launcher native aspect, DOS scenes 4:3, lifecycle pause, keyboard automatic activation/native dismissal, notebook position, immediate menu-layer release, touch menu bounds, text ink bounds/pagination, and checkmark touch regions/stock BG coordinate corrections.

All compiler/sanitizer checks and IPA builds run on GitHub Actions with synthetic font data. Actual game assets and translations stay outside the repository and Actions artifacts. Physical-device gameplay verification is still required.
