param([Parameter(Mandatory = $true)][int]$Batch)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$batchName = "batch_{0:D2}.jsonl" -f $Batch
$kilo = Get-ChildItem "$env:USERPROFILE/.vscode/extensions/kilocode.kilo-code-*-win32-x64/bin/kilo.exe" |
  Sort-Object FullName -Descending |
  Select-Object -First 1 -ExpandProperty FullName
if (-not $kilo) { throw "Kilo/OpenCode-compatible CLI not found" }

$prompt = @"
You are the second-pass reviewer for a German-English learner dictionary used with World of Warcraft quests.
Read Data/cache/polysemy_mimo_batches/$batchName. Each item includes the current gloss, one real quest context, frequency, and a Muse proposal.
Write Data/cache/polysemy_mimo/$batchName, creating the parent folder. Output exactly one JSON object per input line, same order:
{"key":"...","action":"accept"|"reject"|"revise","translation":"...","note":"...","reason":"...","confidence":"high"|"medium"|"low"}
Rules:
- Be conservative. Reject unnecessary notes, obscure dictionary senses, capitalization-only edits, and proposals unsupported by common German usage.
- Accept only changes that materially help an English-speaking learner understand the surface word.
- For revise, provide the final concise gloss and note. For accept, copy the Muse translation/note. For reject, copy the current translation/note.
- Preserve important distinctions such as noun/verb homographs, separable verbs, pronoun case, passive/future auxiliaries, and colloquial spellings.
- Gloss should normally contain at most 3 common senses separated by semicolons. Note max 100 characters. Reason max 120 characters.
- Write valid UTF-8 JSONL, no extra or missing keys. Do not edit any other file.
When complete, report counts only.
"@

& $kilo run -m "opencode-go/mimo-v2.5" --auto $prompt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
