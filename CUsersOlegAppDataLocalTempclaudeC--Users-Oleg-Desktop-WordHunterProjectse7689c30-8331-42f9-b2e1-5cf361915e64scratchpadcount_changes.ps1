$inputFile = "C:\Users\Oleg\Desktop\WordHunterProjects\WordHunterWoW-Dictionary-DE\Data\cache\audit_work\in\batch_00.jsonl"
$outputFile = "C:\Users\Oleg\Desktop\WordHunterProjects\WordHunterWoW-Dictionary-DE\Data\cache\audit_work\out\batch_00.jsonl"

$inLines = @(Get-Content $inputFile | ConvertFrom-Json)
$outLines = @(Get-Content $outputFile | ConvertFrom-Json)

$translationChanges = 0
$notesWritten = 0
$noEmptyTranslations = 0

for ($i = 0; $i -lt $inLines.Count; $i++) {
    $inTrans = $inLines[$i].current
    $outTrans = $outLines[$i].translation
    $outNote = $outLines[$i].note
    
    if ($outTrans -ne $inTrans) {
        $translationChanges++
    }
    
    if ($outNote -and $outNote -ne "") {
        $notesWritten++
    }
    
    if ($outTrans -and $outTrans -ne "") {
        $noEmptyTranslations++
    }
}

Write-Host "Translation changes: $translationChanges"
Write-Host "Notes written: $notesWritten"
Write-Host "No empty translations: $noEmptyTranslations / 150"
