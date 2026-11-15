# LibForeverThemes — design and migration guide

The Forever addons' themes (theme ids, each theme's identity, the theme colours, textures,
fonts and the drawing helpers) in one embedded library. Every themed Forever addon carries a
copy under `Libs/LibForeverThemes/`; at runtime the newest loaded copy wins; every addon keeps
working on its own (no required dependency). Phase 1 (this repository + the pilot Forever Group
Finder) is done; phase 2 migrates the other addons by the recipe below.

Repository: `~/Dokumente/ForeverThemes` (GitHub `StephanRosin/ForeverThemes`, public).

```
LibForeverThemes.lua      the library (one file)
Media/Themes/*.tga        backdrops, grey backdrops, bars, ornaments, Pitwall wedge
Media/Fonts/*.ttf         the theme fonts + OFL.txt + FONTS.txt
tools/make_themes.py      generates Media/Themes (moved from ForeverUnitFrames/tools)
tools/sync <repo> [...]   copies the library into an addon repo
tests/run                 the library's tests (Lua 5.1)
```

## 1. Inventory (state before the migration, 15.11.2026)

Themed: FUF, Quest Log (QL), Combat Meter (CM), Data Bar (DB), Group Finder (GF), Square
Minimap (SM), InfoPanel (IP, private). **Not themed:** Progress Bars, Consumables (no
`Themes.lua`, no registration) — out of scope.

| Aspect | FUF | QL | CM | DB | GF | SM | IP |
|---|---|---|---|---|---|---|---|
| Theme code | `Core/Themes.lua` 633 | `Themes.lua` 794 (draws its art itself, no ThemeArt) | `Themes.lua` 607 | `Themes.lua` 613 | `Themes.lua` 599 | `Themes.lua` 613 | `InfoPanel/Themes.lua` 617 |
| Art | `Elements/ThemeArt.lua` | in Themes.lua (`DrawArt`) | `ThemeArt.lua` 183 | `ThemeArt.lua` 223 | `ThemeArt.lua` 173 | `ThemeArt.lua` 141 | `ThemeArt.lua` 171 + `Skins/` |
| `REVISION` | 13 | 11 | 15 | 10 | 10 | 8 | 10 |
| IDS | `Settings.THEMES` | `Settings.THEMES` | `Settings.THEMES` | literal | literal | literal | `Settings.THEMES` |
| Colour data shape | `colour()` + `COMIC_PAPER` | inline + `YELLOW_ACCENT`… | inline + `YELLOW_ACCENT`… | `colour()` + `COMIC_PAINT` (no `dark`) | `colour()` + `COMIC_PAINT` | `colour()` + `COMIC_PAPER` | inline + `YELLOW_ACCENT`… |
| Pitwall colour field | `accent` | `ornament` | `ornament` | `wedge` | `wedge` | `wedge` | `ornament` |
| `GREY_MEAN` keys | `WoodBack`… | `Wood`… | `Wood`… | `WoodBack`… | `WoodBack`… | `WoodBack`… | `Wood`… |
| Helpers | Accent, Rim, Back, Tint, Font, CellLook | BackColor, Accent, Rim, Icons, Ink, OnPaper, TitleIndent, DrawArt | Backdrop, DarkPaper, Accent, Rim, Ornament, IconAccent | Back, Tint, TitleFont, Accent, Rim, WedgeColor, IconColor | Back, Tint, Accent, RingColor, WedgeColor, IconTones, DarkInk | Rim, OrnamentColor, Back, Tint | ForeignFont, FontsElsewhere, BackColor, Accent, Rim, Wedge, IconColor, OnPaper |
| Media/Themes | all 34 | all 34 | 30 (no Console/Pitwall bar, PitwallBack) | 33 (no PitwallBack) | 22 (no bars) | 21 (no bars, no wedge) | 23 |
| Media/Fonts | all 14 | all 14 | all 14 | 10 | 10 | 12 | all 14 |
| `_G.ForeverThemes` + ApplyToAll | own copy | own copy | own copy | own copy | own copy | own copy | registers + `ThemePicker.lua` reads it, plus Blizzard/Bartender/Platynator entries |
| Tests | `test_themes*.lua`, `test_theme_backgrounds.lua` (reads siblings) | `tests/` | `tests/` | `tests/` | `tests/themes.lua` | `tests/` | `tests/InfoPanel/` |

Every texture and font file that exists in several addons is **md5-identical** (FONTS.txt
differs: each lists its subset). No addon ships LibStub; CM/DB/GF use LibStub only to find an
optional LibSharedMedia / LibDataBroker someone else loaded.

### Identical everywhere → in the library

Theme ids and order; `LATIN_CLIENTS`; the colour sets (ids, order, backs, accents, comic papers);
`GREY_MEAN`; backdrop tints (Wood 0.5, Parchment 0.45, Runestone 0.55, Comic 0.7, Frost 0.55 at
0.85); ornament files, corners and the rune colour; the ring colour per theme (Rahmen-Regel);
title font and `fontSizeAdd`; Comic's ink; Pitwall wedge geometry (0.53, 8, `0.98·h − 0.36·y`);
icon tones (hover ½ to white, off 40 % darker); the "apply to all" code; the media files.

### Different by accident → unified in the library

| What | Values seen | Library |
|---|---|---|
| Swiss blue / white accent | 0.18 vs 0.176; 0.95 vs 0.949 | 0.176 / 0.949 (exact #2D6BFF / #F2F2F2) |
| Swiss ring, red title | 0.16 vs 0.165; {1,0.18,0.13} vs {1,0.176,0.125} | 0.165, {1,0.176,0.125} |
| Pitwall wedge red | {0.88,0.02,0} vs {0.882,0.024,0} | {0.882,0.024,0} (#E10600) |
| Pitwall orange/teal/silver | 0.54/0.63,0.61/0.79,0.81,0.84 vs 0.541/0.631,0.612/0.788,0.808,0.839 | the 3-digit (exact hex) values |
| Handheld accent | 3 or 4 components | 3 (`rim` has 4) |
| Console rim per colour | missing in FUF (derived from accent) | `rim` on every Console colour |
| Pitwall colour field name | `wedge` / `ornament` / `accent` | `wedge` |
| `GREY_MEAN` keys | `Wood` vs `WoodBack` | keyed by the back file (`WoodBack`) |
| Font names | `IBM Plex Sans Condensed` vs `… Bold`; `Titillium Web` vs `… SemiBold` | longer names; the short ones are aliases (§2.4) |
| Media subsets, FONTS.txt subsets | per addon | the full set in every copy |

### Genuinely addon-specific → stays in the addon (own part of the spec)

- `look`: the addon's settings keys (border style/size, body colour, header flag/colour,
  shadow…). Header colours differ per addon on purpose (QL zone headers, CM names).
- Geometry: `padding`, `ornamentSize`, `ornamentInset`, `header = false`, DB `track`/`rimSize`/
  `bar`, CM `line`, QL `shade`/`shadeInset`, IP `shine`/`contentShade`, FUF `hardShadow`.
- Body font choice: GF keeps the list fonts except Frost (`bodyFont = false`); CM Console rows
  narrow (IBM Plex Sans Condensed Bold); FUF/DB have one font (they use the body face as `font`).
- Theme sets, `REVISION`, seeding, switching, placement copy (FUF scopes, CM windows), saved
  variables, the options UI, GF's dark-ink tones (`DARK_INK`), SM's missing wedge.

## 2. Design

### 2.1 Name and loading

- Lua global **`LibForeverThemes`** (a table). Not `ForeverThemes`: `_G.ForeverThemes` is the
  existing cross-addon menu registry and stays exactly as it is.
- No LibStub (no addon ships it; one file with its own version check is enough).
- Every embedding addon lists `Libs\LibForeverThemes\LibForeverThemes.lua` as the **first file**
  of its TOC.
- Version: `local MINOR = n` in the file. A copy loads only if no copy with `MINOR >= n` has
  loaded. A newer copy **empties the existing table and refills it in place**, so an addon that
  did `local Lib = LibForeverThemes` before uses the newest code and data. An older copy loading
  later returns at once.
- A change that breaks an existing caller is not allowed under the same name: add, never remove
  or change meaning; if that is ever impossible, a new global (`LibForeverThemes2`).
- **Every change to `LibForeverThemes.lua` or `Media/` raises `MINOR`** (also media-only changes:
  the newest copy's folder is where textures are read from). The lib test does not enforce this.

### 2.2 Media paths

The file's `...` is the folder of the addon whose TOC loaded it; the winning copy builds its paths
from that: `Interface\AddOns\<folder>\Libs\LibForeverThemes\Media\…`. Each copy ships the
**complete** media, so the winner's folder always has every file. `Lib.Texture(name)` and
`Lib.FONTS[i].path` / `Lib.FontPath(name)` give full paths; addons never build theme paths
themselves. Paths are read at use (not cached at load), because a newer copy may win later in
the loading phase.

The winning copy preloads all its fonts at load (the first-use font trap); addons drop their own
preload of theme fonts.

### 2.3 Specs

```lua
local Lib, T = LibForeverThemes, LibForeverThemes.THEMES
Themes.SPECS = Lib.Specs({
    WOOD = { bodyFont = false, look = { ... }, art = { padding = 5, ornamentSize = 9 } },
    ...
})
```

`Lib.THEMES[id]` is the identity: `back`, `tint`, `ornament`, `corners`, `ornamentColor`,
`rule`/`ruleSize` (Swiss), `strip`/`wedge`/`wedgeColor` (Pitwall), `rim` (ring colour), `font`,
`fontSizeAdd`, `bodyFont`, `iconColor`/`iconHoverColor` (Comic). `Lib.Specs(own)` returns a spec
per id in `Lib.IDS`: the addon's table, with `__index` falling back to the identity, and the
same for `spec.art`. Rules:

- Write only what differs from the identity. An addon value overrides; `false` removes an
  identity field (e.g. `bodyFont = false`).
- Lookups are live (newest copy). `pairs(spec)` / `pairs(spec.art)` list only the addon's own
  fields — iterate `look`, never `art`, when seeding.
- Ring colour in `look` (a setting): reference it, `borderColor = T.TECH.rim`. Seeding copies it.
- Old addon field names map onto library names: `band = {color, height}` → `rule`/`ruleSize`;
  `darkTitle`/`titleStrip`/`title` → `strip`; `titleWedge`/`titleWedgeColor` → `wedge`/
  `wedgeColor`; Pitwall colour `ornament`/`accent` → `wedge`. Rename in the addon's art code, or
  keep the addon's own key as an override where its meaning differs.

### 2.4 Fonts

`Lib.FONTS` = `{ name, path }` for the 14 font files. Names are stored in saved variables and
never change. `Lib.FontName(name)` maps the old aliases (`IBM Plex Sans Condensed` → `… Bold`,
`Titillium Web` → `Titillium Web SemiBold`); `Lib.FontPath(name)` resolves both; addons resolve
font names through `Lib.FontName` in `Media.Path`, and their font dropdown shows
`Lib.FontName(value)` so an old value still shows as selected. New seeds store the long names.
`Friz Quadrata` and `Morpheus` are the client's (not in `Lib.FONTS`).
LibSharedMedia registration is **not** done (open question).

### 2.5 Colours and helpers

All stateless; the addon passes the current theme and the chosen colour id (stored per addon,
account wide, as today):

| Function | Returns |
|---|---|
| `Lib.Colors(theme)` | colour ids in order (`{}` for CLASSIC) |
| `Lib.Colour(theme, id)` / `Lib.ValidColor(theme, id)` | entry or nil / the id, unknown → first |
| `Lib.Paint(theme, id)` | the entry unless it is the theme's first |
| `Lib.Back(art, theme, id)` | backdrop file name (`<back>Grey` under a tinting colour) |
| `Lib.Tint(art, theme, id)` | `{r,g,b,a}` or nil: comic paper, or grey tinted `back/GREY_MEAN` at `art.tint` alpha |
| `Lib.Accent / Lib.Rim(theme, id)` | the colour's accent / ring, nil = the addon's own |
| `Lib.WedgeColor(art, theme, id)` | the colour's wedge, else `art.wedgeColor` |
| `Lib.DarkPaper(theme, id)` | Comic on a dark paper |
| `Lib.IconColor(spec, theme, id, title)` | icon colour: wedge (Pitwall) / accent / title; nil for CLASSIC and Comic |
| `Lib.IconTones(c)` | `{idle, on, hover, off}` |
| `Lib.WEDGE_PART`, `Lib.TITLE_GAP`, `Lib.WedgeReach(h, y)` | Pitwall wedge geometry |
| `Lib.ForeignFont(spec)` | face for Blizzard/other addons' texts |
| `Lib.LatinClient()` | theme fonts usable on this client |

Addons keep their public helper names as thin wrappers (`Themes.Tint(art)` →
`Lib.Tint(art, Themes.Current(), Themes.Color())`), so call sites and tests stay.

### 2.6 Cross-addon menu

`Lib.Register(folder, entry)` writes `_G.ForeverThemes[folder] = entry` — the same table shape
as before (`title, Current, Switch, Colors, Color, SetColor`). `Lib.Others(folder)` and
`Lib.ApplyToAll(folder, theme, color)` replace each addon's copy. Old (unmigrated) addons and
migrated ones read and write the same registry, so mixed installs interoperate (lib test
"Cross-addon menu" covers an entry without colours). The InfoPanel picker needs no change.

### 2.7 REVISION and seeding

Theme sets, seeding and `Themes.Upgrade` stay in each addon. Seeding copies values that now come
from the library (fonts, `fontSizeAdd`, ring colour), so the library has `SEED_REVISION` (now 0):

```lua
local OWN_REVISION = 10   -- the addon's number as before; raise it for the addon's own looks
Themes.REVISION = OWN_REVISION + Lib.SEED_REVISION * Lib.SEED_STEP   -- SEED_STEP = 1000
```

With `SEED_REVISION = 0` the stored revision is unchanged, so migrating reseeds nothing. Raise
`SEED_REVISION` only when a seeded value in `THEMES` changes. Known edge: removing the addon with
the newest copy can lower the effective revision → one reseed (acceptable).

Drawing-time values (tints, colours, textures) need no revision; that is why the unified roundings
show at once and the font-name change only reaches new seeds.

### 2.8 Saved variables

Unchanged and per addon (`themeSets`, `themeColors`, `theme`). The library stores nothing.

### 2.9 Copies, sync and checks

- The copy is **committed** in each addon repo (`Libs/LibForeverThemes/`: `LibForeverThemes.lua`
  + `Media/`). Never edit it there; edit here, raise `MINOR`, run `tools/sync <repo>…`.
- Each addon test suite has a section "Embedded LibForeverThemes": when `../ForeverThemes` sits
  next to the repo, `diff -rq` copy vs. source must be empty; and `LibForeverThemes.FOLDER` equals
  the addon (the copy really loaded).
- `ForeverUnitFrames/tests/test_theme_backgrounds.lua` loads an addon's embedded copy before its
  `Themes.lua` automatically (`Libs/…` next to Themes.lua or one folder up) — no per-addon edit.
- Textures: `python3 tools/make_themes.py` (deterministic, reproduces the files md5-identical);
  the `*BackGrey.tga` are not generated by any script (kept as files; `GREY_MEAN` = their means).
  FUF's `tools/make_themes.py` is removed when FUF migrates.

### 2.10 Packaging and CurseForge

`install` copies the TOC's files (which includes the library file) and then
`Libs/LibForeverThemes/Media`; `tools/package` zips what `install` produced, so the zip has the
library. CurseForge: each project could list "LibForeverThemes" as an *Embedded Library* relation
only if the library becomes its own CurseForge project — not done, not needed (note only).
**New files in the TOC → a full game restart, `/reload` is not enough.**

### 2.11 Testing

1. `tests/run` here (newest-wins, paths, media files exist, colours, helpers, specs, registry).
2. The addon's suite, all green, with the "Embedded LibForeverThemes" section.
3. FUF `tests/run theme_backgrounds`.
4. `forever-render` before/after: every theme × colour of a scenario that **shows the themed
   window** (GF: `options`, which runs `/fgf`; `classic`/`full` draw nothing because the window is
   closed). Compare with all four channels — `ImageChops.difference(...).getbbox()` on RGBA looks
   only at alpha and reports false "identical".

### 2.12 The hub (addon "Forever Themes")

Optional addon `ForeverThemes` (repo `~/Dokumente/Forever-Themes`, MINOR ≥ 2): one central theme
and colour that it applies to every registered addon through `_G.ForeverThemes` (the same
`Switch`/`SetColor` calls as "Apply to all"), per addon "follow" (default) or "own theme". It
announces itself with `Lib.SetHub(api)`; addons ask `Lib.Hub()`:

| `Lib.Hub()` | nil without the hub, else the table below |
|---|---|
| `Follows(folder)` | true while the hub sets that addon's theme (show "Following Forever Themes") |
| `Theme()`, `Color()` | the central theme id, colour id (nil for a theme without colours) |
| `OpenMenu(anchor)` | the theme/colour menu at a frame (Data Bar "Theme" element) |
| `OpenOptions()` | the hub's options window |

The api lives in `_G.ForeverThemesHub`, not in the library table (a newer copy loading after the
hub empties that). **Texts hand-off:** while `Lib.Hub()` is non-nil the hub owns the theme font
on Blizzard's texts (cast bar, buff timers, Cooldown Manager, error line, damage numbers) and on
Platynator; FUF's `BlizzardFonts`/`PlatynatorFonts` and InfoPanel's bridges stand down (check at
PLAYER_LOGIN or later: every addon is loaded by then). Call guarded (`Lib.Hub and Lib.Hub()`)
only in a copy that may be older than MINOR 2.

## 3. Migration recipe (one addon)

Run tests only as `flock /tmp/claude-1000/forever-tests.lock tests/run` (FUF: `tests/run -j 4`).

1. **Baseline renders** of the addon's themed scenario in every theme × colour (ids from
   `Lib.COLORS`), `FOREVER_THEME=… FOREVER_COLOR=… ./forever-render <Addon>/<scn> -o before/…`.
2. `~/Dokumente/ForeverThemes/tools/sync ~/Dokumente/<Addon>`.
3. TOC: `Libs\LibForeverThemes\LibForeverThemes.lua` as the first file.
4. `install`: replace the copy of `Media/Themes` and `Media/Fonts` with
   `cp -r "$HERE/Libs/LibForeverThemes/Media" "$TARGET/Libs/LibForeverThemes/"`.
5. `Media.lua`: theme fonts from the library —
   `Media.OWN = setmetatable({ background = {}, statusbar = {} }, { __index = function(_, k) if k == "font" then return Lib.FONTS end end })`
   (statusbar textures from `Lib.Texture("<Name>Bar")` the same way where the addon offers them);
   `if kind == "font" then name = Lib.FontName(name) end` at the top of `Media.Path`; delete the
   font preload block. QL/IP: their backdrop textures are Media *background* entries — point
   them at `Lib.Texture`.
6. Font dropdown `get`: `kind == "font" and LibForeverThemes.FontName(S(key)) or S(key)`.
7. `Themes.lua`:
   - `Themes.CLASSIC = Lib.CLASSIC`, `Themes.IDS = Lib.IDS` (or keep `Settings.THEMES` if the
     settings enum needs it — then assert it equals `Lib.IDS` in a test).
   - `REVISION` per §2.7, `OWN_REVISION` = the current number.
   - `SPECS = Lib.Specs({...})`: drop every identity field equal to the library's; keep
     differences as overrides with a one-line why; `borderColor = T.<ID>.rim` in `look`.
   - `Themes.COLORS = Lib.COLORS`; delete `GREY_MEAN`, comic paint tables, accent constants,
     `colour()`, `LATIN_CLIENTS` (use `Lib.LatinClient()`), mixing code.
   - Helpers become wrappers over §2.5, keeping their names and return shapes (CM `Backdrop`
     returns `Lib.Back(...), Lib.Tint(...)`; `Accent(color)` → `Lib.Accent(...) or color`).
   - `Lib.Register(ADDON, {...})`; `HasOthers`/`ApplyToAll` over `Lib.Others`/`Lib.ApplyToAll`.
8. Art: `PATH .. x` → `Lib.Texture(x)`; wedge constants → `Lib.WEDGE_PART`, `Lib.TITLE_GAP`,
   `Lib.WedgeReach`.
9. `git rm -r Media/Themes Media/Fonts` once `grep -rn 'Media\\\\Themes\|Media\\\\Fonts'` finds no
   user outside `Libs/`.
10. Tests: hard-coded texture paths → `…\Libs\LibForeverThemes\Media\Themes\`; expected values to
    the unified roundings (§1); add the "Embedded LibForeverThemes" section (copy from GF
    `tests/run.lua`, wrap in `do … end` if the main chunk hits 200 locals). Suite green.
11. After renders; every difference must be one of the unified values (expect ≤ 2/255 on Swiss
    and Pitwall accents/rings/wedges), anything else is a bug.
12. README licence note → the library (as GF's). Commit with explicit paths; `.git/hooks/pre-push
    </dev/null`; no push, no release. Install; new TOC file → full game restart.

## 4. Risks

- **Mixed versions in one install:** a stale copy in some addon with a higher `MINOR` than the
  source would win — only if someone edits a copy. The copy-equals-source test prevents it.
- **Partial media in a copy** would break every addon when that copy wins: copies are synced as a
  whole (`rsync --delete`), and the tests diff them.
- **Load order:** data is read live (metatables, `Lib.FONTS` at use); code that caches lib tables
  at load (e.g. `local FONTS = Lib.FONTS`) would keep an older copy's paths — don't.
- **Font first use:** paths change when another copy wins; the winner preloads its own files.
- **REVISION:** forgetting `SEED_REVISION` after changing a seeded field leaves old sets; changing
  it reseeds the active theme of every migrated addon from Classic (theme tweaks lost).
- **InfoPanel:** private, uncommitted foreign changes in `InfoPanel.lua`, `Locales/*.lua`,
  `tests/InfoPanel/run.lua`, `tests/InfoPanel/wowmock.lua` — the test section belongs in
  `run.lua`, so InfoPanel waits until those are committed. Its Skins move to "Forever Skins"
  (embeds the library) later.
- Release order does not matter (mixed old/new interoperate), but each migrated addon grows to
  the full media set (~2.7 MB uncompressed).
