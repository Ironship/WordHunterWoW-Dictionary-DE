-- Real Lua 5.1 load/count/guard checks. Run once per client case to bound memory.
local root, edition = assert(arg[1], "addon root"), assert(arg[2], "client case")
local cases = {
  tbc = { "classic", "2.5.6" }, wrath = { "classic", "3.4.3" },
  cata = { "classic", "4.4.2" }, ["mop-classic"] = { "classic", "5.5.2" },
  retail = { "retail", "12.0.1" }, forever = { "forever", "1.60.0" },
  era = { "classic", "1.15.7" }, sod = { "sod", "1.15.7" },
  ["retail-major-two"] = { "retail", "2.0.0" },
  unknown = { nil, "2.5.6" }, ["unknown-flavor"] = { "unknown", "2.5.6" },
  ["numeric-flavor"] = { 2, "2.5.6" }, ["numeric-version"] = { "classic", 2 },
  ["malformed-version"] = { "classic", "not-a-version" },
  ["malformed-major"] = { "classic", "2.bad" },
}
local case = cases[edition]
if case then
  WordHunterWoW_Addon = { Compat = { GameFlavor = function() return case[1] end } }
  GetBuildInfo = function() return case[2], "test", "date", 0 end
else
  assert(edition == "unavailable", "unknown client case")
end
local dictionary, items, nativeQuests, saved = {}, {}, {}, {}
WordHunterWoW_Dictionary_DE, WordHunterWoW_ENNames_Item = dictionary, items
WordHunterWoW_QuestData, WordHunterWoW_DB = nativeQuests, saved
local upstreamItems, upstreamNpcs, upstreamSpells = {}, {}, {}
MultiLanguageItemData, MultiLanguageNpcData, MultiLanguageSpellData = upstreamItems, upstreamNpcs, upstreamSpells
for _, path in ipairs(dofile(root .. "/EntityData/tests/load-order.lua")) do
  assert(loadfile(root .. "/" .. path))()
end
local expected = cases[edition] and ({ tbc = true, wrath = true, cata = true, ["mop-classic"] = true, retail = true, forever = true })[edition] and ("multilanguage-" .. edition)
if edition == "retail-major-two" then expected = "multilanguage-retail" end
local buckets = 0
for key, ref in pairs(WordHunterWoW_EntityDataBySource) do
  buckets = buckets + 1
  assert(key == "multilanguage-classic" or key == expected, "wrong client namespace loaded: " .. key)
  assert(ref.referenceOnly and ref.schemaVersion == 1)
  for kind, maps in pairs(ref.kinds) do
    for locale, rows in pairs(maps) do
      local actual = { records = 0, text = 0, role = 0, unresolvedValues = 0 }
      for id, row in pairs(rows) do
        assert(type(id) == "number" and id > 0 and id % 1 == 0)
        assert(type(row.name) == "string" and row.name ~= "")
        actual.records = actual.records + 1
        for _, field in ipairs({ "text", "role", "unresolvedValues" }) do
          if row[field] then actual[field] = actual[field] + 1 end
        end
        for _, field in ipairs({ "name", "text", "role" }) do
          local text = row[field]
          if text then
            assert(type(text) == "string" and text ~= "")
            assert(not text:find("%[q%d*%]") and not text:find("%$[%w_]+"), "source formatting survived")
            local tokensRemoved = text:gsub("{name}", ""):gsub("{race}", ""):gsub("{class}", "")
            assert(not tokensRemoved:find("[{}]"), "source column braces survived")
          end
        end
      end
      for field, count in pairs(actual) do
        assert(count == ref.counts[kind][locale][field], key .. "/" .. kind .. "/" .. locale .. "/" .. field)
      end
      local count = ref.counts[kind][locale]
      assert(count.sourceRecords == count.records + count.excludedDeveloperRecords + count.omittedEmptyNames)
    end
    local paired, deOnly, enOnly, pairedText, pairedRoles = 0, 0, 0, 0, 0
    for id, de in pairs(maps.deDE) do
      local en = maps.enUS[id]
      if en then
        paired = paired + 1
        if de.text and en.text then pairedText = pairedText + 1 end
        if de.role and en.role then pairedRoles = pairedRoles + 1 end
      else deOnly = deOnly + 1 end
    end
    for id in pairs(maps.enUS) do if not maps.deDE[id] then enOnly = enOnly + 1 end end
    local expectedCoverage = ref.counts[kind].coverage
    assert(paired == expectedCoverage.pairedNames and deOnly == expectedCoverage.deOnly and enOnly == expectedCoverage.enOnly)
    assert(pairedText == expectedCoverage.pairedText and pairedRoles == expectedCoverage.pairedRoles)
  end
end
assert(buckets == (expected and 2 or 1), "missing/extra source bucket")
local classic = WordHunterWoW_EntityDataBySource["multilanguage-classic"]
assert(classic.kinds.item.deDE[6948].name == "Ruhestein")
if expected then
  local ref = assert(WordHunterWoW_EntityDataBySource[expected])
  assert(ref.kinds.item.enUS[6948].name == "Hearthstone")
  assert(ref.kinds.item.enUS[6948] ~= classic.kinds.item.enUS[6948], "same IDs share mutable source rows")
  assert(ref.provenance.locales.enUS.commit and ref.viewLabel)
  assert(ref.kinds.item.deDE[6948].name == "Ruhestein")
  assert(ref.provenance.locales.deDE.commit)
  if edition == "wrath" then
    assert(ref.provenance.locales.deDE.commit == "a0a5e66931a7f13f06e4f73d1dd472215c5da5a9")
    assert(ref.provenance.locales.deDE.interface == "30403")
  end
  if expected == "multilanguage-retail" then
    local mail, boots = ref.kinds.item.enUS[198998], ref.kinds.item.enUS[198999]
    assert(mail.name == "Hornstrider's Chainmail" and boots.name == "Hornstrider's Boots")
    assert(mail.text == "Binds when equipped\nChest Mail\n20 Armor\n+9 [Agility or Intellect]\n+14 Stamina\nDurability 115 / 115\nSell Price:", "later itemsFour duplicate must win")
    assert(boots.text == "Binds when equipped\nFeet Mail\n13 Armor\n+7 [Agility or Intellect]\n+10 Stamina\nDurability 55 / 55\nSell Price:", "later itemsFour duplicate must win")
    assert(not ref.kinds.npc.enUS[1], "explicit GM-only waypoint must not become learning data")
  end
end
assert(WordHunterWoW_Dictionary_DE == dictionary and WordHunterWoW_ENNames_Item == items)
assert(WordHunterWoW_QuestData == nativeQuests and WordHunterWoW_DB == saved)
assert(MultiLanguageItemData == upstreamItems and MultiLanguageNpcData == upstreamNpcs and MultiLanguageSpellData == upstreamSpells)
print("ENTITY_VARIANTS_OK " .. edition)
