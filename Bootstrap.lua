local addonName = ...
local base = WordHunterWoW_Addon
if not base then return end
local loaded, job = {}, nil
local function descriptors() return WordHunterWoW_Dictionary_DataModules or {} end

local function active(module)
  if module.kind == "native" then
    return not (base.Compat and base.Compat.GameFlavor() == "retail")
  end
  return module.kind == "entity" or WordHunterWoW_QuestSources and WordHunterWoW_QuestSources[module.source] ~= nil
end

local function loadModule(module)
  if loaded[module.name] then return true end
  local load = C_AddOns and C_AddOns.LoadAddOn or LoadAddOn
  local errorKey = module.kind == "entity" and "dictionaryEntityDataError" or "dictionaryDataError"
  if type(load) ~= "function" then base[errorKey] = "UNAVAILABLE"; return false end
  local ok, success, reason = pcall(load, module.name)
  if not ok or not success then
    base[errorKey] = reason or (not ok and success) or "UNAVAILABLE"
    return false
  end
  loaded[module.name] = true
  base[errorKey] = nil
  if module.kind == "native" then
    local data = WordHunterWoW_QuestDataByFlavor
    local flavor = base.Compat and base.Compat.GameFlavor()
    -- SeedForever has finished; native lookups use only the current game.
    if type(data) == "table" then
      if flavor == "forever" then data.classic = nil
      elseif flavor == "classic" or flavor == "sod" then data.forever = nil end
    end
  end
  return true
end

local function nativeQuests()
  for _, module in ipairs(descriptors()) do
    if module.kind == "native" and active(module) and not loadModule(module) then return false end
  end
  return true
end

local function questData(id, source)
  if base.IsSecretValue and base.IsSecretValue(id) then return false end
  if id ~= nil then id = tonumber(id); if not id then return false end end
  if not id and not nativeQuests() then return false end
  for _, module in ipairs(descriptors()) do
    if module.kind == "quest" and active(module) and (not source or source == module.source)
        and (not id or id >= module.first and id <= module.last) then
      if not loadModule(module) then return false end
    end
  end
  return true
end

local function entityData()
  for _, module in ipairs(descriptors()) do
    if module.kind == "entity" and not loadModule(module) then return false end
  end
  return true
end

local function requestCatalog(callback)
  if job then return false end
  if base.dictionaryDataError then return true end
  local pending = {}
  for _, module in ipairs(descriptors()) do
    if module.kind ~= "entity" and active(module) and not loaded[module.name] then
      pending[#pending + 1] = module
    end
  end
  if #pending == 0 then return true end
  if not (C_Timer and C_Timer.NewTimer) then return questData() end
  local current = { index = 1 }
  job = current
  local function step()
    if job ~= current then return end
    local frame = base.questsFrame
    if frame and (not frame:IsShown() or frame.tab == "words") then job = nil; return end
    local success = loadModule(pending[current.index])
    current.index = current.index + 1
    if not success or current.index > #pending then
      job = nil
      callback()
    else
      C_Timer.NewTimer(.01, step)
    end
  end
  C_Timer.NewTimer(.01, step)
  return job == nil
end

if base then
  base.EnsureDictionaryNativeQuestData = nativeQuests
  base.EnsureDictionaryQuestData = questData
  base.EnsureDictionaryEntityData = entityData
  base.RequestDictionaryQuestCatalog = requestCatalog
  base.CanLoadDictionaryQuestSource = function(source)
    for _, module in ipairs(descriptors()) do
      if module.kind == "quest" and module.source == source and active(module) then return true end
    end
    return false
  end
end

local function importDictionary()
  if base and base.RegisterDictionaryProvider and type(WordHunterWoW_Dictionary_DE) == "table" then
    base.RegisterDictionaryProvider("deDE", addonName, WordHunterWoW_Dictionary_DE)
  end
end

local events = CreateFrame("Frame")
events:RegisterEvent("ADDON_LOADED")
events:RegisterEvent("PLAYER_LOGIN")
events:SetScript("OnEvent", function(_, event, name)
  if event == "ADDON_LOADED" and name == addonName then
    base.dictionaryDataError = nil
    importDictionary()
  end
  if event == "PLAYER_LOGIN" and not base.SupportsDictionaryDataModules then questData(); entityData() end
end)
importDictionary()
