-- 1.12 passes a file no arguments, so the name is written out rather than read.
local addonName = "WordHunterWoW-Dictionary-DE"

local function importDictionary()
  local addon = WordHunterWoW_Addon
  if not addon or not addon.RegisterDictionaryProvider or type(WordHunterWoW_Dictionary_DE) ~= "table" then return end
  addon.RegisterDictionaryProvider("deDE", addonName, WordHunterWoW_Dictionary_DE)
end

-- 1.12 hands a script handler no arguments at all: the event name is the global
-- `event` and its payload is `arg1`.
local events = CreateFrame("Frame")
events:RegisterEvent("ADDON_LOADED")
events:SetScript("OnEvent", function()
  if arg1 == addonName then importDictionary() end
end)

-- WordHunterWoW is a required dependency, so its provider API is already available.
-- Register immediately as well as on ADDON_LOADED to avoid load-order edge cases.
importDictionary()
