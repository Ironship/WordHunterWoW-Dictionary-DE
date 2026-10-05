-- Lua 5.1: lua5.1 QuestData/Tools/test_multilanguage_references.lua QUESTDATA FILE_LIST
local root, fileList = assert(arg[1]), assert(arg[2])
local files = {}
local list = assert(io.open(fileList))
for line in list:lines() do files[#files + 1] = line:gsub("\r$", "") end
list:close()
assert(files[1] == "ReferenceMetadata.lua" and #files == 472)
local counts = {
    ["multilanguage-classic-master"] = {deDE = 5281, enUS = 5310},
    ["multilanguage-tbc"] = {deDE = 6655, enUS = 6652},
    ["multilanguage-retail"] = {deDE = 45322, enUS = 47662},
}
local function count(table)
    local result = 0
    for _ in pairs(table) do result = result + 1 end
    return result
end
for _, case in ipairs({
    {name = "Classic", flavor = "classic", version = "1.15.9", master = true},
    {name = "Forever", flavor = "forever", version = "1.60.1", master = true},
    {name = "SoD", flavor = "sod", version = "1.15.9", master = true},
    {name = "Retail", flavor = "retail", version = "12.0.5", retail = true},
    {name = "TBC", flavor = "classic", version = "2.6.0", master = true, tbc = true},
    {name = "Unknown"},
}) do
    local native, alias, saved = {nativeSentinel = true}, {retailAliasSentinel = true}, {userSentinel = true}
    local env = {type = type, pairs = pairs, ipairs = ipairs,
        WordHunterWoW_Addon = {Compat = {GameFlavor = function() return case.flavor end}},
        GetBuildInfo = function() return case.version end,
        WordHunterWoW_QuestDataByFlavor = native, WordHunterWoW_QuestEN = alias,
        WordHunterWoW_DB = saved,
    }
    for _, file in ipairs(files) do
        local chunk = assert(loadfile(root .. "/" .. file))
        setfenv(chunk, env)
        chunk()
    end
    assert(env.WordHunterWoW_QuestDataByFlavor == native and count(native) == 1,
        "references must not alter native/default catalogs")
    assert(env.WordHunterWoW_QuestEN == alias and count(alias) == 1,
        "references must not alter the English alias")
    assert(env.WordHunterWoW_DB == saved and count(saved) == 1,
        "references must not copy material into SavedVariables")
    local sources = assert(env.WordHunterWoW_QuestSources)
    local allowed = { ["multilanguage-classic-master"] = case.master,
                      ["multilanguage-tbc"] = case.tbc, ["multilanguage-retail"] = case.retail }
    for key, expected in pairs(counts) do
        local library = sources[key]
        if not allowed[key] then
            assert(library == nil, "foreign source metadata/bucket must be absent: " .. key)
        else
            assert(library.loaded and library.sourceVersionUnverified and not library.bilingualPairVerified)
            assert(library.voiceUnavailable)
            for locale, amount in pairs(expected) do
                assert(count(library.locales[locale]) == amount, "retained source count mismatch")
                for id, record in pairs(library.locales[locale]) do
                    assert(id == record.id and record.locale == locale and record.flavor == "source-reference")
                    assert(record.sourceFlavor == library.sourceFlavor and record.sourceVersionUnverified)
                    assert(record.sourceRevision == library.localeSources[locale].revision)
                    assert(record.bilingualPairVerified == false and record.voiceUnavailable)
                    if record.sourceObjective then
                        assert(record.sourceObjectiveStatus == "unverified-source-field")
                    end
                    if record.objectives then
                        assert(record.objectivesStatus == "corroborated by independent bundled same-flavor locale corpus")
                    end
                    for _, field in ipairs({"title", "description", "objectives", "sourceObjective", "progress", "completion"}) do
                        local text = record[field]
                        if text then
                            assert(not text:find("\194\160", 1, true), "source NBSP must not glue words")
                            assert(not text:find("\226\128\175", 1, true), "source narrow NBSP must not glue words")
                        end
                    end
                end
            end
        end
    end
    if case.master then
        local de = sources["multilanguage-classic-master"].locales.deDE
        assert(de[1] == nil, "the known Chow debug quest must not enter a study library")
        assert(de[1149] and de[1150], "legitimate Test of Faith/Endurance quests must survive")
        assert(de[8517].completion:find("erfährt. Gebt", 1, true))
        assert(de[9002].completion:find("{name}. Ich", 1, true))
    end
    if case.tbc then
        assert(sources["multilanguage-tbc"].locales.deDE[1] == nil,
            "the known Alexander craft developer quest must not enter a study library")
    end
    if case.retail then
        local library = sources["multilanguage-retail"]
        assert(library.locales.deDE[7] and library.locales.deDE[7].title == nil,
            "captured numeric German title must not replace usable German passages")
        assert(library.locales.deDE[783].description:find("Abtei hinter mir", 1, true))
        assert(library.locales.enUS[783].description:find("Deathwing", 1, true),
            "different DE/EN source variants must be retained independently, not silently rewritten")
        assert(library.locales.deDE[1] and library.locales.deDE[1].title == "Kanrethads Quest",
            "an ID blacklist must not drop a different usable historical Retail variant")
    end
    print(case.name .. ": source counts, client guards, native/SV isolation and provenance PASS")
    env = nil
    collectgarbage("collect")
end
