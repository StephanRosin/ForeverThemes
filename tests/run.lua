-- Tests for LibForeverThemes. Run with tests/run (Lua 5.1, as in WoW).
local LIB = LIBDIR .. "/LibForeverThemes.lua"

-- The little of the client the library touches.
local locale = "enUS"
function GetLocale() return locale end
local fontsSet = {}
function CreateFrame()
    return { Hide = function() end, CreateFontString = function()
        return { SetFont = function(_, path) fontsSet[#fontsSet + 1] = path end }
    end }
end
local errors = {}
function geterrorhandler() return function(msg) errors[#errors + 1] = msg end end
local lsmFonts = {}
function LibStub(name, silent)
    assert(name == "LibSharedMedia-3.0" and silent)
    return { Fetch = function(_, kind, font, noDefault)
        assert(noDefault)
        return kind == "font" and lsmFonts[font] and "Own\\" .. font or nil
    end }
end
StaticPopupDialogs, OKAY = {}, "Okay"
local shown
function StaticPopup_Show(which) shown = which; return which end

local pass, fail = 0, 0
local function check(label, got, want)
    if got == want then
        pass = pass + 1
    else
        fail = fail + 1
        print(("  FAIL %-58s -> %s   (want: %s)"):format(label, tostring(got), tostring(want)))
    end
end
local function section(name) print(name) end
local function rgb(c) return c and table.concat({ c[1], c[2], c[3], c[4] }, ",") or "nil" end
local function exists(path)
    local h = io.open(path)
    if h then h:close() end
    return h ~= nil
end

-- The library file as one addon's copy, its MINOR replaced by minor, and
-- edit(src) applied when given.
local function loadCopy(folder, minor, edit)
    local src = assert(io.open(LIB)):read("*a")
    if minor then src = src:gsub("local MINOR = %d+", "local MINOR = " .. minor, 1) end
    if edit then src = edit(src) end
    local chunk = assert(loadstring(src, "LibForeverThemes.lua"))
    return pcall(chunk, folder, {})
end

section("Newest copy wins")
loadCopy("AddonA")
local Lib = LibForeverThemes
check("loaded: the global", type(Lib), "table")
check("loaded: its folder", Lib.FOLDER, "AddonA")
check("texture in its own folder", Lib.Texture("WoodBack"),
    "Interface\\AddOns\\AddonA\\Libs\\LibForeverThemes\\Media\\Themes\\WoodBack")
check("fonts preloaded", #fontsSet, #Lib.FONTS)
Lib.stale = true
local MINOR = Lib.MINOR
loadCopy("AddonB", MINOR + 1)
check("newer: the same table", LibForeverThemes, Lib)
check("newer: its folder", Lib.FOLDER, "AddonB")
check("newer: its media", Lib.FontPath("VT323"),
    "Interface\\AddOns\\AddonB\\Libs\\LibForeverThemes\\Media\\Fonts\\VT323-Regular.ttf")
check("newer: nothing of the old left", Lib.stale, nil)
loadCopy("AddonC", MINOR)
check("older after it: ignored", Lib.FOLDER, "AddonB")
check("older after it: version kept", Lib.MINOR, MINOR + 1)
local ok = loadCopy("Broken", MINOR + 2, function(src)
    return (src:gsub("lib.HUB_URL = ", "error('half way') lib.HUB_URL = ", 1))
end)
check("throwing newer copy: it fails", ok, false)
check("throwing newer copy: the loaded one stays", Lib.FOLDER, "AddonB")
check("throwing newer copy: its version stays", Lib.MINOR, MINOR + 1)
check("throwing newer copy: its helpers stay", type(Lib.ShowHubLink), "function")
fontsSet = {}
loadCopy("AddonD", MINOR + 2)
check("after it a good copy still loads", Lib.FOLDER, "AddonD")
check("its functions read the shared table", Lib.FontPath("VT323"),
    "Interface\\AddOns\\AddonD\\Libs\\LibForeverThemes\\Media\\Fonts\\VT323-Regular.ttf")
check("fonts preloaded at the end, its own", fontsSet[1], Lib.FONTS[1].path)

section("MINOR raised with every change")
-- LibForeverThemes.lua and Media/ as they are must equal the commit that
-- last changed the `local MINOR` line, or that line must be changed now.
local function sh(cmd)
    local h = io.popen("cd '" .. LIBDIR .. "' && " .. cmd .. " 2>/dev/null")
    local out = h:read("*a")
    h:close()
    return (out:gsub("%s+$", ""))
end
if sh("git rev-parse --is-inside-work-tree") ~= "true" then
    print("  (skipped: not a git work tree)")
else
    local paths = "-- LibForeverThemes.lua Media"
    local minorNow = sh("git diff -U0 HEAD -- LibForeverThemes.lua | grep -c '^+local MINOR = '")
    local base = sh("git log -1 --format=%H -G'^local MINOR = ' -- LibForeverThemes.lua")
    local changed = sh("git diff --name-only " .. base .. " " .. paths)
        .. sh("git ls-files --others --exclude-standard " .. paths)
    check("changed since the last MINOR: none, or MINOR raised now ("
        .. changed:gsub("\n", " ") .. ")", changed == "" or minorNow ~= "0", true)
end

section("Media")
for _, f in ipairs(Lib.FONTS) do
    local file = f.path:match("([^\\]+)$")
    check("font file there: " .. f.name, exists(LIBDIR .. "/Media/Fonts/" .. file), true)
end
check("font alias", Lib.FontPath("IBM Plex Sans Condensed"), Lib.FontPath("IBM Plex Sans Condensed Bold"))
check("font alias: its name", Lib.FontName("Titillium Web"), "Titillium Web SemiBold")
check("other font: not ours", Lib.FontPath("Friz Quadrata"), nil)
lsmFonts["Titillium Web"] = true
check("alias: a shared font of that name is not swapped", Lib.FontName("Titillium Web"), "Titillium Web")
check("alias: nor its path", Lib.FontPath("Titillium Web"), nil)
check("alias: a full name stays ours", Lib.FontPath("Titillium Web SemiBold") ~= nil, true)
lsmFonts = {}
local function texture(name) return exists(LIBDIR .. "/Media/Themes/" .. name .. ".tga") end
for _, id in ipairs(Lib.IDS) do
    local t = Lib.THEMES[id]
    check(id .. ": has an identity", type(t), "table")
    for _, key in ipairs({ "back", "ornament", "wedge" }) do
        if t[key] then check(id .. ": " .. key .. " file", texture(t[key]), true) end
    end
    for _, c in ipairs(Lib.COLORS[id] or {}) do
        if c.texture then check(id .. " " .. c.id .. ": HD file", texture(c.texture), true) end
        if c.back then
            check(id .. " " .. c.id .. ": grey file", texture(t.back .. "Grey"), true)
            check(id .. " " .. c.id .. ": grey mean known", type(Lib.GREY_MEAN[t.back]), "number")
        end
    end
    local fonts = { t.font, t.bodyFont }
    for _, name in ipairs(fonts) do
        local known = Lib.FontPath(name) ~= nil or name == "Friz Quadrata" or name == "Morpheus"
        check(id .. ": font known: " .. name, known, true)
    end
end

section("Colours")
for _, id in ipairs(Lib.IDS) do
    local seen = {}
    for _, c in ipairs(Lib.COLORS[id] or {}) do
        check(id .. " " .. c.id .. ": once", seen[c.id], nil)
        seen[c.id] = true
    end
    check(id .. ": colours unless classic", (Lib.COLORS[id] ~= nil), id ~= "CLASSIC")
end
check("colour ids", table.concat(Lib.Colors("SWISS"), " "), "RED BLUE YELLOW WHITE")
check("classic: none", #Lib.Colors("CLASSIC"), 0)
check("unknown stored reads first", Lib.ValidColor("PIXEL", "NOPE"), "NAVY")
check("known stays", Lib.ValidColor("PIXEL", "TEAL"), "TEAL")
check("classic: no colour", Lib.ValidColor("CLASSIC", "TEAL"), nil)
check("first colour: no paint", Lib.Paint("WOOD", "OAK"), nil)

section("Drawing helpers")
local specs = Lib.Specs({ WOOD = { look = { x = 1 }, art = { padding = 5 } }, GLASS = { bodyFont = false } })
local wood = specs.WOOD
check("spec: own look", wood.look.x, 1)
check("spec: own art", wood.art.padding, 5)
check("spec: shared art", wood.art.back, "WoodBack")
check("spec: shared font", wood.font, "Cinzel")
check("spec: false drops a shared field", specs.GLASS.bodyFont, false)
check("spec: a theme without own part has none", specs.TECH, nil)
check("spec: classic always", type(specs.CLASSIC), "table")
check("spec ids: classic and own, in order", table.concat(Lib.SpecIds(specs), " "), "CLASSIC WOOD GLASS")
check("spec: classic has no art", specs.CLASSIC.art, nil)
Lib.THEMES.WOOD.font = "Changed"
check("spec: a newer library's data is seen", wood.font, "Changed")
Lib.THEMES.WOOD.font = "Cinzel"
local art = specs.WOOD.art
check("back: own look", Lib.Back(art, "WOOD", "OAK"), "WoodBack")
check("back: a colour takes the grey", Lib.Back(art, "WOOD", "EBONY"), "WoodBackGrey")
check("tint: own look", rgb(Lib.Tint(art, "WOOD", "OAK")), "0.5,0.5,0.5,1")
check("tint: grey to the colour", rgb(Lib.Tint(art, "WOOD", "WALNUT")), "0.1875,0.1125,0.075,1")
specs = Lib.Specs({ FROST = {}, TECH = {}, COMIC = {}, SWISS = {}, PITWALL = {}, WOOD = { art = { padding = 5 } } })
check("tint: frost keeps its alpha", Lib.Tint(specs.FROST.art, "FROST", "DEEP")[4], 0.85)
check("tint: tech without one", Lib.Tint(specs.TECH.art, "TECH", "CYAN"), nil)
check("tint: comic grey paper", rgb(Lib.Tint(specs.COMIC.art, "COMIC", "GREY")), "0.7,0.7,0.7,1")
check("tint: comic white paper", rgb(Lib.Tint(specs.COMIC.art, "COMIC", "WHITE")), "1,1,1,1")
check("tint: swiss blue keeps its black", Lib.Back(specs.SWISS.art, "SWISS", "BLUE"), "SwissBack")
check("back: none (false) under a colour", Lib.Back({ back = false }, "WOOD", "EBONY"), false)
check("tint: none (false) under a colour", Lib.Tint({ back = false }, "WOOD", "EBONY"), nil)
check("back: a foreign back without grey keeps it", Lib.Back({ back = "Own" }, "WOOD", "EBONY"), "Own")
check("tint: a foreign back keeps its tint", rgb(Lib.Tint({ back = "Own", tint = { 1, 1, 1, 1 } }, "WOOD", "EBONY")),
    "1,1,1,1")
check("grey tint: as the backdrop's", rgb(Lib.GreyTint("WoodBack", { 0.15, 0.09, 0.06 })), "0.1875,0.1125,0.075")
check("grey tint: capped at 1", Lib.GreyTint("TechBack", { 1, 1, 1 })[1], 1)
check("grey tint: unknown back", Lib.GreyTint("Own", { 1, 1, 1 }), nil)
Lib.Tint(art, "WOOD", "OAK")[1] = 9
Lib.Accent("COMIC", "YELLOW")[1] = 9
Lib.Rim("CONSOLE", "AMBER")[1] = 9
Lib.WedgeColor(specs.PITWALL.art, "PITWALL", "RED")[1] = 9
check("returned colours are copies: tint", Lib.THEMES.WOOD.tint[1], 0.5)
check("returned colours are copies: accent", Lib.COLORS.COMIC[4].accent[1], 0.15)
check("returned colours are copies: rim", Lib.COLORS.CONSOLE[2].rim[1], 1)
check("returned colours are copies: wedge", Lib.THEMES.PITWALL.wedgeColor[1], 0.882)
section("HD themes")
local hdSpecs = Lib.Specs({ WOOD = { look = { x = { 1 } }, art = { padding = 5, back = "OwnBack" } }, COMIC = {} }, true)
check("hd: from its base's part", hdSpecs.WOOD_HD.look.x[1], 1)
check("hd: a copy, not the base's table", hdSpecs.WOOD_HD.look.x ~= hdSpecs.WOOD.look.x, true)
check("hd: base's geometry", hdSpecs.WOOD_HD.art.padding, 5)
check("hd: its own backdrop, not the base's", hdSpecs.WOOD_HD.art.back, "WoodHDEbony")
for id, want in pairs({ WOOD_HD = "EBONY", TECH_HD = "CARBON", PARCHMENT_HD = "ASH", RUNESTONE_HD = "SLATE",
    GLASS_HD = "RUBY", COMIC_HD = "NOIR", FROST_HD = "ICE" }) do
    check("hd default " .. id, Lib.ValidColor(id, nil), want)
    check("hd default backdrop " .. id, Lib.THEMES[id].back, Lib.COLORS[id][1].texture)
end
check("hd: the default keeps its accent", Lib.Accent("RUNESTONE_HD", "SLATE") ~= nil, true)
check("hd: noir by default is dark", Lib.DarkPaper("COMIC_HD", Lib.ValidColor("COMIC_HD", nil)), true)
check("non-HD first colour stays the own look", Lib.Paint("WOOD", "OAK"), nil)
check("hd: base's font", hdSpecs.WOOD_HD.font, "Cinzel")
check("hd: only where the base is", hdSpecs.TECH_HD, nil)
check("hd: spec ids", table.concat(Lib.SpecIds(hdSpecs), " "), "CLASSIC WOOD COMIC WOOD_HD COMIC_HD")
check("hd: not without asking", Lib.Specs({ WOOD = {} }).WOOD_HD, nil)
check("hd: base theme", Lib.BaseTheme("COMIC_HD"), "COMIC")
check("hd: base of a base", Lib.BaseTheme("COMIC"), "COMIC")
check("hd: back first colour", Lib.Back(hdSpecs.WOOD_HD.art, "WOOD_HD", "OAK"), "WoodHDOak")
check("hd: back other colour", Lib.Back(hdSpecs.WOOD_HD.art, "WOOD_HD", "EBONY"), "WoodHDEbony")
check("hd: tint white", rgb(Lib.Tint(hdSpecs.WOOD_HD.art, "WOOD_HD", "EBONY")), "1,1,1,1")
check("hd: frost keeps its alpha", Lib.THEMES.FROST_HD.tint[4], 0.85)
check("hd: tile", Lib.THEMES.GLASS_HD.tile, Lib.TILE_HD)
check("hd: back none (false) stays none", Lib.Back({ back = false }, "WOOD_HD", "EBONY"), false)
check("hd: comic noir is dark", Lib.DarkPaper("COMIC_HD", "NOIR"), true)
check("hd: comic newsprint is light", Lib.DarkPaper("COMIC_HD", "NEWSPRINT"), false)
check("hd: comic tint is not the paper's", rgb(Lib.Tint(hdSpecs.COMIC_HD.art, "COMIC_HD", "POP")), "1,1,1,1")
check("hd: base themes unchanged", Lib.THEMES.WOOD.back, "WoodBack")

check("accent: comic yellow", rgb(Lib.Accent("COMIC", "YELLOW")), "0.15,0.45,0.95")
check("accent: none for the first", Lib.Accent("TECH", "CYAN"), nil)
check("rim: console amber", rgb(Lib.Rim("CONSOLE", "AMBER")), "1,0.69,0,1")
check("rim: none elsewhere", Lib.Rim("TECH", "GREEN"), nil)
check("wedge: own", rgb(Lib.WedgeColor(specs.PITWALL.art, "PITWALL", "RED")), "0.882,0.024,0,1")
check("wedge: teal", rgb(Lib.WedgeColor(specs.PITWALL.art, "PITWALL", "TEAL")), "0,0.631,0.612,1")
check("dark paper: black", Lib.DarkPaper("COMIC", "BLACK"), true)
check("dark paper: grey", Lib.DarkPaper("COMIC", "GREY"), false)
check("dark paper: not the comic", Lib.DarkPaper("PIXEL", "BLACK"), false)
check("icons: pitwall in the wedge's colour", rgb(Lib.IconColor(specs.PITWALL, "PITWALL", "ORANGE", { 1, 1, 1 })),
    "1,0.541,0,1")
check("icons: the accent", rgb(Lib.IconColor(specs.TECH, "TECH", "AMBER", { 1, 1, 1 })), "1,0.75,0.2")
check("icons: else the title", rgb(Lib.IconColor(specs.WOOD, "WOOD", "OAK", { 1, 0, 0 })), "1,0,0")
check("icons: comic has its ink", Lib.IconColor(specs.COMIC, "COMIC", "GREY", { 1, 1, 1 }), nil)
check("icons: none under classic", Lib.IconColor(specs.CLASSIC, "CLASSIC", nil, { 1, 1, 1 }), nil)
local tones = Lib.IconTones({ 0.2, 0.4, 0.6 })
check("tones: hover half to white", rgb(tones.hover), "0.6,0.7,0.8")
check("tones: off 40 % darker", rgb(tones.off), "0.12,0.24,0.36")
check("wedge reach", Lib.WedgeReach(24, 12), 19)
check("foreign font: frost's body", Lib.ForeignFont(specs.FROST), "Julius Sans One")
check("foreign font: friz body gives the title font", Lib.ForeignFont(specs.WOOD), "Cinzel")
check("foreign font: none gives the title font", Lib.ForeignFont(specs.TECH), "Space Grotesk")
locale = "ruRU"
check("latin client: no", Lib.LatinClient(), false)
locale = "deDE"
check("latin client: yes", Lib.LatinClient(), true)

section("Cross-addon menu")
local log = {}
local function entry(name, themes, colours)
    return { title = name, Current = function() return "CLASSIC" end,
        Switch = function(id) if themes[id] then log[#log + 1] = name .. ">" .. id; return true end return nil, "UNKNOWN" end,
        Colors = colours and function(id) return colours[id] or {} end,
        SetColor = colours and function(c, id) log[#log + 1] = name .. ":" .. c .. "/" .. id; return true end }
end
Lib.Register("Me", entry("Me", { PIXEL = true }))
-- An addon without the library writes its entry itself, without colours.
_G.ForeverThemes.Old = entry("Old", { PIXEL = true })
Lib.Register("New", entry("New", { PIXEL = true }, { PIXEL = { "NAVY", "TEAL" } }))
_G.ForeverThemes.Junk = "not an entry"
check("others: not myself, not junk", #Lib.Others("Me"), 2)
check("apply: both switched", Lib.ApplyToAll("Me", "PIXEL", "TEAL"), 2)
table.sort(log)
check("apply: colour only where it exists", table.concat(log, " "), "New:TEAL/PIXEL New>PIXEL Old>PIXEL")
log = {}
check("apply: a theme they lack is skipped", Lib.ApplyToAll("Me", "WOOD", "OAK"), 0)
_G.ForeverThemes.Pseudo = { title = "Pseudo", Switch = function() error("not an addon") end }
check("others: an entry without Current is none", #Lib.Others("Me"), 2)
_G.ForeverThemes.Pseudo = nil
_G.ForeverThemes.Bad = { title = "Bad Addon", Current = function() end, Switch = function() error("boom") end }
local n, failed = Lib.ApplyToAll("Me", "PIXEL", "TEAL")
check("apply: an erroring addon stops none", n, 2)
check("apply: it is named", table.concat(failed, ","), "Bad Addon")
check("apply: its error is reported", errors[1] and errors[1]:find("Bad Addon: ", 1, true) ~= nil, true)
_G.ForeverThemes.Bad = nil

section("Hub")
check("no hub: nil", Lib.Hub(), nil)
local hub = { Follows = function(folder) return folder == "New" end }
Lib.SetHub(hub)
check("hub: the one set", Lib.Hub(), hub)
loadCopy("AddonZ", 99)
check("hub: survives a newer copy", Lib.Hub(), hub)
check("hub: follows", Lib.Hub().Follows("New"), true)
check("follows: through the library", Lib.Follows("New"), true)
check("follows: not another", Lib.Follows("Old"), false)
log = {}
check("apply: a follower is the hub's", Lib.ApplyToAll("Me", "PIXEL", "TEAL"), 1)
check("apply: only the other switched", table.concat(log, " "), "Old>PIXEL")
Lib.HubSync()   -- a hub without Sync: nothing
local synced = 0
hub.Sync = function() synced = synced + 1 end
Lib.HubSync()
check("hub sync: called", synced, 1)
Lib.SetHub(nil)
check("follows: no hub", Lib.Follows("New"), false)
Lib.HubSync()
check("hub sync: no hub, nothing", synced, 1)

section("Hub texts and link")
locale = "koKR"
check("text: korean", Lib.Text("HUB_LINK"), "다운로드 링크")
locale = "esMX"
check("text: mexican spanish", Lib.Text("HUB_OPEN"), "Abrir Forever Themes")
locale = "ruRU"
check("text: else english", Lib.Text("HUB_COPY"), "Copy the link (Ctrl+C) and open it in your browser:")
check("text: own locale over the client's", Lib.Text("HUB_FOLLOWS", "deDE"), "Folgt Forever Themes")
check("text: own mexican spanish", Lib.Text("HUB_OPEN", "esMX"), "Abrir Forever Themes")
locale = "frFR"
check("text: unknown own locale, client's", Lib.Text("HUB_FOLLOWS", "auto"), "Suit Forever Themes")
check("text: no own locale, client's", Lib.Text("HUB_FOLLOWS"), "Suit Forever Themes")
Lib.ShowHubLink(nil, "deDE")
check("link: prompt in own locale", StaticPopupDialogs[shown].text, "Link kopieren (Strg+C) und im Browser öffnen:")
locale = "ruRU"
check("link: shown", Lib.ShowHubLink(), "LIBFOREVERTHEMES_HUB_LINK")
local dialog = StaticPopupDialogs[shown]
check("link: its prompt", dialog.text, Lib.Text("HUB_COPY"))
local box = { SetText = function(b, t) b.text = t end, HighlightText = function() end, SetFocus = function() end }
dialog.OnShow({ GetEditBox = function() return box end })
check("link: the url in the box", box.text, "https://www.curseforge.com/wow/addons/forever-themes")
Lib.ShowHubLink("Own text")
check("link: an own prompt", StaticPopupDialogs[shown].text, "Own text")

section("Seed revision")
local sets = {}
check("reseed: new sets", Lib.NeedsReseed(sets, 10), true)
Lib.MarkSeeded(sets, 10)
check("reseed: marked", Lib.NeedsReseed(sets, 10), false)
check("reseed: sets of before MINOR 3 (revision only)", Lib.NeedsReseed({ revision = 10 }, 10), false)
check("reseed: own revision raised", Lib.NeedsReseed(sets, 11), true)
Lib.SEED_REVISION = 2
check("reseed: library seed raised, read at call", Lib.NeedsReseed(sets, 10), true)
Lib.MarkSeeded(sets, 10)
Lib.SEED_REVISION = 1
check("reseed: an older copy winning does not reseed", Lib.NeedsReseed(sets, 10), false)

print(("%d passed, %d failed"):format(pass, fail))
os.exit(fail == 0 and 0 or 1)
