param(
  [Parameter(Mandatory = $true)][int]$Batch,
  [string]$Model = "opencode-go/muse-spark-1.2-contributor"
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$batchName = "batch_{0:D2}.jsonl" -f $Batch
$kilo = Get-ChildItem "$env:USERPROFILE/.vscode/extensions/kilocode.kilo-code-*-win32-x64/bin/kilo.exe" |
  Sort-Object FullName -Descending |
  Select-Object -First 1 -ExpandProperty FullName
if (-not $kilo) { throw "Kilo/OpenCode-compatible CLI not found" }

$prompt = @"
Act as a careful German-English lexicographer for a World of Warcraft vocabulary addon.
Read Data/cache/polysemy_batches/$batchName. Each line has key, surface word, current English gloss, frequency, and one quest context.
Write Data/cache/polysemy_muse/$batchName, creating the parent folder if needed. Write exactly one JSON object per input line, same order:
{"key":"...","action":"keep"|"fix","translation":"...","note":"...","confidence":"high"|"medium"|"low"}
Rules:
- Preserve action=keep unless a correction or genuinely useful polysemy/grammar note is justified.
- For fix, use a concise learner gloss (usually 1-4 meanings separated by semicolons).
- note is only for context-sensitive grammar, idioms, misleading forms, or important alternate senses; max 100 characters.
- Distinguish forms such as wurde vs würde. Do not invent meanings from a single context.
- Proper names and straightforward content words normally stay unchanged.
- Do not edit any other file. Do not omit or add keys.
When complete, report only counts keep/fix.
"@

& $kilo run -m $Model --auto $prompt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
