param(
  [int]$StartOffset = 960,
  [int]$WaveSize = 960,
  [int]$BatchSize = 60,
  [int]$MuseParallel = 3,
  [int]$MimoParallel = 3,
  [string]$MuseModel = "opencode-go/muse-spark-1.2-contributor",
  [string]$MimoModel = "opencode-go/mimo-v2.5"
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

$translations = "Data/cache/translations_de_en.jsonl"
$curated = "Data/CuratedDE.jsonl"
$total = (Get-Content $translations | Measure-Object -Line).Lines
$curatedCount = (Get-Content $curated | Where-Object { $_.Trim() -ne "" } | Measure-Object -Line).Lines
$remaining = $total - $curatedCount
Write-Host "total=$total curated=$curatedCount remaining=$remaining startOffset=$StartOffset waveSize=$WaveSize" -ForegroundColor Cyan

$kilo = Get-ChildItem "$env:USERPROFILE/.vscode/extensions/kilocode.kilo-code-*-win32-x64/bin/kilo.exe" | Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
if (-not $kilo) { throw "Kilo CLI not found" }
Write-Host "kilo=$kilo muse=$MuseModel mimo=$MimoModel" -ForegroundColor Cyan

function Invoke-MuseBatch([int]$batchIndex) {
  $batchName = "batch_{0:D2}.jsonl" -f $batchIndex
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
  & $kilo run -m $MuseModel --auto $prompt
  return $LASTEXITCODE
}

function Invoke-MimoBatch([int]$batchIndex) {
  $batchName = "batch_{0:D2}.jsonl" -f $batchIndex
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
  & $kilo run -m $MimoModel --auto $prompt
  return $LASTEXITCODE
}

$waveIndex = 0
for ($offset = $StartOffset; $offset -lt $total; $offset += $WaveSize) {
  $waveIndex++
  $limit = [Math]::Min($WaveSize, $total - $offset)
  Write-Host "`n=== WAVE $waveIndex offset=$offset limit=$limit ===" -ForegroundColor Yellow

  # Prepare
  python Tools/prepare_polysemy_audit.py --offset $offset --limit $limit --batch-size $BatchSize
  if ($LASTEXITCODE -ne 0) { throw "prepare failed wave $waveIndex" }

  $batches = (Get-ChildItem "Data/cache/polysemy_batches" -Filter "batch_*.jsonl" | Measure-Object).Count
  if ($batches -eq 0) { Write-Host "No batches at offset $offset - done" ; break }

  # Muse waves in parallel groups
  $batchIndices = 0..($batches-1)
  for ($i = 0; $i -lt $batchIndices.Count; $i += $MuseParallel) {
    $group = $batchIndices[$i..[Math]::Min($i+$MuseParallel-1, $batchIndices.Count-1)]
    Write-Host "Muse group $($group -join ',') wave $waveIndex" -ForegroundColor Cyan
    $jobs = @()
    foreach ($b in $group) {
      $jobs += Start-Job -ScriptBlock {
        param($b,$root,$muse)
        Set-Location $root
        $kilo = Get-ChildItem "$env:USERPROFILE/.vscode/extensions/kilocode.kilo-code-*-win32-x64/bin/kilo.exe" | Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
        $batchName = "batch_{0:D2}.jsonl" -f $b
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
        & $kilo run -m $muse --auto $prompt 2>&1 | Out-String
        return $LASTEXITCODE
      } -ArgumentList $b,$root,$MuseModel
    }
    $jobs | Wait-Job | Out-Null
    foreach ($j in $jobs) {
      $out = Receive-Job $j
      Write-Host $out
      if ($j.State -eq "Failed" -or $j.ChildJobs[0].JobStateInfo.Reason) { throw "Muse batch failed" }
      Remove-Job $j
    }
    # validate group produced expected files
    foreach ($b in $group) {
      $p = "Data/cache/polysemy_muse/batch_{0:D2}.jsonl" -f $b
      if (-not (Test-Path $p)) { throw "Missing $p after Muse group" }
    }
  }

  # Collect for Mimo
  python Tools/collect_polysemy_proposals.py
  if ($LASTEXITCODE -ne 0) { Write-Host "No proposals for wave $waveIndex - skipping Mimo"; continue }
  $mimoBatches = (Get-ChildItem "Data/cache/polysemy_mimo_batches" -Filter "batch_*.jsonl" | Measure-Object).Count
  if ($mimoBatches -eq 0) { Write-Host "No mimo batches wave $waveIndex"; continue }

  # Mimo waves in parallel groups
  $mimoIndices = 0..($mimoBatches-1)
  for ($i = 0; $i -lt $mimoIndices.Count; $i += $MimoParallel) {
    $group = $mimoIndices[$i..[Math]::Min($i+$MimoParallel-1, $mimoIndices.Count-1)]
    Write-Host "Mimo group $($group -join ',') wave $waveIndex" -ForegroundColor Magenta
    $jobs = @()
    foreach ($b in $group) {
      $jobs += Start-Job -ScriptBlock {
        param($b,$root,$mimo)
        Set-Location $root
        $kilo = Get-ChildItem "$env:USERPROFILE/.vscode/extensions/kilocode.kilo-code-*-win32-x64/bin/kilo.exe" | Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
        $batchName = "batch_{0:D2}.jsonl" -f $b
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
        & $kilo run -m $mimo --auto $prompt 2>&1 | Out-String
        return $LASTEXITCODE
      } -ArgumentList $b,$root,$MimoModel
    }
    $jobs | Wait-Job | Out-Null
    foreach ($j in $jobs) {
      $out = Receive-Job $j
      Write-Host $out
      if ($j.State -eq "Failed") { throw "Mimo batch failed" }
      Remove-Job $j
    }
    foreach ($b in $group) {
      $p = "Data/cache/polysemy_mimo/batch_{0:D2}.jsonl" -f $b
      if (-not (Test-Path $p)) { throw "Missing $p after Mimo group" }
    }
  }

  # Apply consensus
  python Tools/apply_polysemy_consensus.py --apply
  if ($LASTEXITCODE -ne 0) { throw "apply failed wave $waveIndex" }

  # Optional checkpoint commit every 5 waves
  if ($waveIndex % 5 -eq 0) {
    $curatedLines = (Get-Content $curated | Measure-Object -Line).Lines
    Write-Host "Checkpoint wave $waveIndex curated=$curatedLines" -ForegroundColor Green
    git add $curated "Tools/prepare_polysemy_audit.py" "Tools/build_dictionary_lua.py"
    git commit -m "Wave $waveIndex offset $offset: curated $curatedLines" --allow-empty | Out-Null
    git push origin feat/german-full-audit | Out-Null
  }
}

Write-Host "`nALL WAVES COMPLETE" -ForegroundColor Green
