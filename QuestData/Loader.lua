-- OptionalDeps ensures ENPanel's chunks are loaded before this alias.
local function selectFlavor()
    local addon = WordHunterWoW_Addon
    local compat = addon and addon.Compat
    local flavor = compat and compat.GameFlavor and compat.GameFlavor()
    if flavor ~= "classic" and flavor ~= "forever" then return end
    local data = WordHunterWoW_QuestDataByFlavor[flavor]
    if data and data.enUS then WordHunterWoW_QuestEN = data.enUS end
end
selectFlavor()
-- The base resolves season/client flavor again at login.
local events = CreateFrame("Frame")
events:RegisterEvent("PLAYER_LOGIN")
events:SetScript("OnEvent", selectFlavor)
