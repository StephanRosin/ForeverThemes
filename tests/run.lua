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

-- The library file as one addon's copy, its MINOR replaced by minor.
local function loadCopy(folder, minor)
    local src = assert(io.open(LIB)):read("*a")
    if minor then src = src:gsub("local MINOR = %d+", "local MINOR = " .. minor, 1) end
    local chunk = assert(loadstring(src, "LibForeverThemes.lua"))
    chunk(folder, {})
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

section("Media")
for _, f in ipairs(Lib.FONTS) do
    local file = f.path:match("([^\\]+)$")
    check("font file there: " .. f.name, exists(LIBDIR .. "/Media/Fonts/" .. file), true)
end
check("font alias", Lib.FontPath("IBM Plex Sans Condensed"), Lib.FontPath("IBM Plex Sans Condensed Bold"))
check("font alias: its name", Lib.FontName("Titillium Web"), "Titillium Web SemiBold")
check("other font: not ours", Lib.FontPath("Friz Quadrata"), nil)
local function texture(name) return exists(LIBDIR .. "/Media/Themes/" .. name .. ".tga") end
for _, id in ipairs(Lib.IDS) do
    local t = Lib.THEMES[id]
    check(id .. ": has an identity", type(t), "table")
    for _, key in ipairs({ "back", "ornament", "wedge" }) do
        if t[key] then check(id .. ": " .. key .. " file", texture(t[key]), true) end
    end
    for _, c in ipairs(Lib.COLORS[id] or {}) do
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
check("spec: a theme without own part", specs.TECH.art.back, "TechBack")
check("spec: classic has no art", specs.CLASSIC.art, nil)
Lib.THEMES.WOOD.font = "Changed"
check("spec: a newer library's data is seen", wood.font, "Changed")
Lib.THEMES.WOOD.font = "Cinzel"
local art = specs.WOOD.art
check("back: own look", Lib.Back(art, "WOOD", "OAK"), "WoodBack")
check("back: a colour takes the grey", Lib.Back(art, "WOOD", "EBONY"), "WoodBackGrey")
check("tint: own look", rgb(Lib.Tint(art, "WOOD", "OAK")), "0.5,0.5,0.5,1")
check("tint: grey to the colour", rgb(Lib.Tint(art, "WOOD", "WALNUT")), "0.1875,0.1125,0.075,1")
check("tint: frost keeps its alpha", Lib.Tint(specs.FROST.art, "FROST", "DEEP")[4], 0.85)
check("tint: tech without one", Lib.Tint(specs.TECH.art, "TECH", "CYAN"), nil)
check("tint: comic grey paper", rgb(Lib.Tint(specs.COMIC.art, "COMIC", "GREY")), "0.7,0.7,0.7,1")
check("tint: comic white paper", rgb(Lib.Tint(specs.COMIC.art, "COMIC", "WHITE")), "1,1,1,1")
check("tint: swiss blue keeps its black", Lib.Back(specs.SWISS.art, "SWISS", "BLUE"), "SwissBack")
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
    return { title = name,
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

print(("%d passed, %d failed"):format(pass, fail))
os.exit(fail == 0 and 0 or 1)
