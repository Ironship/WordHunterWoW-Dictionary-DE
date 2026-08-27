$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
python Tools/fetch_quests.py --workers 6 --interval 0.25
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python Tools/build_wordlist.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python Tools/translate_google.py --workers 4 --interval 0.25
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python Tools/build_dictionary_lua.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Dictionary-DE data complete"
