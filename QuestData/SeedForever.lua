-- Classic texts are an explicit compatibility fallback on Forever.
-- Native Forever records below replace these copies without touching Classic.
local data = WordHunterWoW_QuestDataByFlavor
data.forever = data.forever or {}
for _, locale in ipairs({"deDE", "enUS"}) do
    data.forever[locale] = data.forever[locale] or {}
    for id, record in pairs(data.classic[locale]) do
        if not data.forever[locale][id] then
            local copy = {}
            for key, value in pairs(record) do copy[key] = value end
            copy.flavor = "forever"
            copy.originFlavor = "classic"
            copy.compatibleClassic = true
            data.forever[locale][id] = copy
        end
    end
end
