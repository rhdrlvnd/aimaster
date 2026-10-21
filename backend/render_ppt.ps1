param([string]$SourcePath, [string]$OutputPath)
$ErrorActionPreference = 'Stop'
$app = $null
$deck = $null
$ownedApp = $false
$security = $null
try {
    $app = New-Object -ComObject PowerPoint.Application
    $ownedApp = $app.Presentations.Count -eq 0
    $security = $app.AutomationSecurity
    $app.AutomationSecurity = 3
    $deck = $app.Presentations.Open($SourcePath, -1, 0, 0)
    if ($deck.Slides.Count -gt 20) { throw 'Slide limit exceeded' }
    $height = [int](1600 * $deck.PageSetup.SlideHeight / $deck.PageSetup.SlideWidth)
    for ($i = 1; $i -le $deck.Slides.Count; $i++) {
        $deck.Slides.Item($i).Export((Join-Path $OutputPath "$i.png"), 'PNG', 1600, $height)
    }
} finally {
    if ($null -ne $deck) { $deck.Close() }
    if ($null -ne $app -and $null -ne $security) { $app.AutomationSecurity = $security }
    if ($null -ne $app -and $ownedApp -and $app.Presentations.Count -eq 0) { $app.Quit() }
}
