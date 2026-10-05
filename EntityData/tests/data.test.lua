-- Run with Lua 5.1; the root is the containing WordHunterWoW-Dictionary-DE folder.
local root = assert(arg[1], "provide addon root")
local oldItems = { [25] = "already present English item" }
WordHunterWoW_ENNames_Item = oldItems
local oldDictionary = { unchanged = { translation = "dictionary sentinel" } }
WordHunterWoW_Dictionary_DE = oldDictionary
local nativeQuest = { [1] = { title = "native quest sentinel" } }
WordHunterWoW_QuestData = nativeQuest

for _,path in ipairs(dofile(root .. "/EntityData/tests/load-order.lua")) do
  assert(loadfile(root .. "/" .. path))()
end
local ref = assert(WordHunterWoW_EntityDataBySource["multilanguage-classic"])
assert(ref.referenceOnly == true and ref.schemaVersion == 1)
assert(ref.provenance.commit == "c51dc2e5141f070f5b92de190521d79e8dccaeab")
assert(WordHunterWoW_ENNames_Item == oldItems and oldItems[25] == "already present English item")
assert(WordHunterWoW_Dictionary_DE == oldDictionary and oldDictionary.unchanged.translation == "dictionary sentinel")
assert(WordHunterWoW_QuestData == nativeQuest and nativeQuest[1].title == "native quest sentinel")

local function counts(rows)
  local out = { records = 0, text = 0, role = 0, unresolvedValues = 0 }
  for id,row in pairs(rows) do
    assert(type(id) == "number" and id > 0 and id % 1 == 0)
    assert(type(row.name) == "string" and row.name ~= "")
    out.records = out.records + 1
    for _,field in ipairs({"text","role","unresolvedValues"}) do
      if row[field] then out[field] = out[field] + 1 end
    end
    for _,field in ipairs({"name","text","role"}) do
      local text = row[field]
      if text then
        assert(type(text) == "string" and text ~= "")
        assert(not text:find("%[q%d*%]"), "source quality token survived")
        assert(not text:find("%$[%w_]+"), "source macro survived")
        assert(not text:find("%[%s*[%d%.%s%+%-%*%/]+%]"), "unevaluated formula survived")
        assert(not text:find("{[^{}]+}%s*{"), "column braces survived")
      end
    end
  end
  return out
end

for kind,maps in pairs(ref.kinds) do
  for locale,rows in pairs(maps) do
    local actual = counts(rows)
    for field,value in pairs(actual) do
      assert(value == ref.counts[kind][locale][field], kind .. "/" .. locale .. "/" .. field)
    end
  end
  local paired,deOnly,enOnly,pairedText,pairedRoles = 0,0,0,0,0
  for id,de in pairs(maps.deDE) do
    local en = maps.enUS[id]
    if en then
      paired = paired + 1
      if de.text and en.text then pairedText = pairedText + 1 end
      if de.role and en.role then pairedRoles = pairedRoles + 1 end
    else deOnly = deOnly + 1 end
  end
  for id in pairs(maps.enUS) do if not maps.deDE[id] then enOnly = enOnly + 1 end end
  local expected = ref.counts[kind].coverage
  assert(paired == expected.pairedNames and deOnly == expected.deOnly and enOnly == expected.enOnly)
  assert(pairedText == expected.pairedText and pairedRoles == expected.pairedRoles)
end

assert(ref.kinds.item.deDE[6948].name == "Ruhestein")
assert(ref.kinds.item.deDE[6948].text:find("ändern",1,true))
assert(ref.kinds.npc.deDE[295].role == "Gastwirt" and ref.kinds.npc.enUS[295].role == "Innkeeper")
assert(ref.kinds.spell.deDE[133].name == "Feuerball" and ref.kinds.spell.enUS[133].name == "Fireball")
assert(ref.kinds.spell.deDE[10].unresolvedValues and ref.kinds.spell.deDE[10].text:find("[Quellwert]",1,true))
assert(ref.kinds.spell.enUS[10].unresolvedValues and ref.kinds.spell.enUS[10].text:find("[source value]",1,true))
assert(ref.kinds.npc.enUS[765] and not ref.kinds.npc.deDE[765], "English-only record dropped")
assert(ref.kinds.spell.deDE[348779].text == "Sofort", "useful text around null macros must survive")
assert(not ref.kinds.item.deDE[143] and not ref.kinds.item.enUS[143], "NPC equipment developer record must be excluded")
assert(ref.kinds.spell.deDE[1235320].name and not ref.kinds.spell.deDE[1235320].text, "copied English prose must not be editable German text")
assert(ref.kinds.spell.enUS[1235320].text:find("The Crimson Cleaver",1,true), "English source prose remains available in English")
print("ENTITY_REFERENCE_DATA_OK")
