# Agent Board tray buddy for Windows: a tiny character in the taskbar tray (next to the clock).
#   amber and waving  = an agent needs you
#   blue and bobbing  = agents are working
#   teal, eyes closed = all quiet        grey = the board isn't running
# Left-click opens the board. Right-click lists agents (click one to open it), shows plan usage,
# and switches between the Work and Personal spaces. It only talks to the board on this computer.
#
# Started hidden at sign-in by setup.py:
#   powershell -NoProfile -STA -WindowStyle Hidden -ExecutionPolicy Bypass -File tray.ps1
# (Keep this file plain ASCII: Windows PowerShell 5.1 misreads other characters without a BOM.)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$Board = 'http://127.0.0.1:4317/'

# Only one tray buddy at a time.
$created = $false
$script:mutex = New-Object System.Threading.Mutex($true, 'AgentBoardTrayBuddy', [ref]$created)
if (-not $created) { exit }

function New-BuddyIcon([System.Drawing.Color]$Color, [bool]$EyesOpen, [int]$Bob, [int]$Arm) {
    $bmp = New-Object System.Drawing.Bitmap 32, 32
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.Clear([System.Drawing.Color]::Transparent)
    $body = New-Object System.Drawing.SolidBrush $Color
    $g.FillEllipse($body, 3, (7 - $Bob), 24, 22)
    if ($Arm -ne 0) {
        $state = $g.Save()
        $g.TranslateTransform(25, (15 - $Bob))
        $g.RotateTransform($Arm)
        $g.FillEllipse($body, -3, -12, 6, 13)
        $g.Restore($state)
    }
    $white = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::White)
    $dark = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(19, 24, 39))
    foreach ($x in @(9, 17)) {
        if ($EyesOpen) {
            $g.FillEllipse($white, $x, (13 - $Bob), 6, 7)
            $g.FillEllipse($dark, ($x + 2), (15 - $Bob), 3, 3)
        } else {
            $g.FillRectangle($white, $x, (16 - $Bob), 6, 2)
        }
    }
    $g.Dispose()
    return [System.Drawing.Icon]::FromHandle($bmp.GetHicon())
}

$amber = [System.Drawing.Color]::FromArgb(255, 154, 31)
$blue = [System.Drawing.Color]::FromArgb(47, 140, 255)
$teal = [System.Drawing.Color]::FromArgb(35, 191, 176)
$grey = [System.Drawing.Color]::FromArgb(150, 156, 170)
$Icons = @{
    'need0'   = New-BuddyIcon $amber $true 0 (-15)
    'need1'   = New-BuddyIcon $amber $true 0 30
    'work0'   = New-BuddyIcon $blue $true 0 0
    'work1'   = New-BuddyIcon $blue $true 2 0
    'quiet0'  = New-BuddyIcon $teal $false 0 0
    'offline0' = New-BuddyIcon $grey $false 0 0
}

$script:summary = $null
$script:frame = 0

$tray = New-Object System.Windows.Forms.NotifyIcon
$tray.Icon = $Icons['offline0']
$tray.Text = 'Agent Board'
$tray.Visible = $true
$menu = New-Object System.Windows.Forms.ContextMenuStrip
$tray.ContextMenuStrip = $menu

function Get-Mood {
    if ($null -eq $script:summary) { return 'offline' }
    if (@($script:summary.need).Count -gt 0) { return 'need' }
    if (@($script:summary.work).Count -gt 0) { return 'work' }
    return 'quiet'
}

function Set-Tip([string]$Text) {
    if ($Text.Length -gt 63) { $Text = $Text.Substring(0, 63) }   # Windows limit for tray tooltips
    $tray.Text = $Text
}

function Update-Look {
    $m = Get-Mood
    switch ($m) {
        'need'    { $tray.Icon = $Icons["need$($script:frame)"]; Set-Tip ("Agent Board - " + @($script:summary.need).Count + " need you") }
        'work'    { $tray.Icon = $Icons["work$($script:frame)"]; Set-Tip ("Agent Board - " + @($script:summary.work).Count + " working") }
        'quiet'   { $tray.Icon = $Icons['quiet0']; Set-Tip 'Agent Board - all quiet' }
        default   { $tray.Icon = $Icons['offline0']; Set-Tip "Agent Board isn't running" }
    }
}

function Find-Browser {
    foreach ($base in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:LOCALAPPDATA)) {
        if (-not $base) { continue }
        foreach ($rel in @('Google\Chrome\Application\chrome.exe', 'Microsoft\Edge\Application\msedge.exe')) {
            $p = Join-Path $base $rel
            if (Test-Path $p) { return $p }
        }
    }
    return $null
}
$script:browser = Find-Browser

function Open-Board([string]$Hash) {
    $url = $Board + $Hash
    if ($script:browser) { Start-Process -FilePath $script:browser -ArgumentList "--app=$url" }
    else { Start-Process $url }
}

function Refresh {
    try { $script:summary = Invoke-RestMethod -Uri ($Board + 'api/summary') -TimeoutSec 3 }
    catch { $script:summary = $null }
    Update-Look
}

function Add-Item([string]$Text, [bool]$Enabled) {
    $item = $menu.Items.Add($Text)
    $item.Enabled = $Enabled
    return $item
}

function Add-Agents([string]$Title, $Agents) {
    $list = @($Agents)
    if ($list.Count -eq 0) { return }
    [void](Add-Item "$Title ($($list.Count))" $false)
    foreach ($a in ($list | Select-Object -First 8)) {
        $label = [string]$a.title
        if ($label.Length -gt 50) { $label = $label.Substring(0, 49) + '...' }
        $item = Add-Item ("    " + $label) $true
        $item.Tag = '#s=' + $a.id
        $item.Add_Click({ param($sender, $e) Open-Board $sender.Tag })
    }
    [void]$menu.Items.Add('-')
}

# Build the menu fresh every time it opens.
$menu.Add_Opening({
    param($sender, $e)
    $menu.Items.Clear()
    $s = $script:summary
    if ($null -eq $s) {
        [void](Add-Item "Agent Board isn't running" $false)
    } else {
        $personal = ($s.space.space -eq 'personal')
        [void](Add-Item ($(if ($personal) { 'Personal space' } else { 'Work space' })) $false)
        $switch = Add-Item ($(if ($personal) { 'Switch to Work' } else { 'Switch to Personal' })) $true
        $target = if ($personal) { 'work' } else { 'personal' }
        if ($s.space.auto -eq $target) { $target = 'auto' }   # going back to the time-based space
        $switch.Tag = $target
        $switch.Add_Click({
            param($sender, $e)
            try {
                Invoke-RestMethod -Method Post -Uri ($Board + 'api/space') -ContentType 'application/json' `
                    -Body (@{ space = $sender.Tag } | ConvertTo-Json) -TimeoutSec 3 | Out-Null
            } catch {}
            Refresh
        })
        [void]$menu.Items.Add('-')
        Add-Agents 'Needs you' $s.need
        Add-Agents 'Working' $s.work
        $line = @()
        if ($s.done -gt 0) { $line += "$($s.done) done" }
        if ($s.tired -gt 0) { $line += "$($s.tired) to restart" }
        if ($s.asleep -gt 0) { $line += "$($s.asleep) asleep" }
        if ($line.Count -gt 0) { [void](Add-Item ($line -join ' | ') $false) }
        foreach ($p in @($s.plan)) {
            if ($null -eq $p) { continue }
            $who = ([string]$p.account).Split('@')[0]
            $five = if ($null -ne $p.five) { "$($p.five)%" } else { '-' }
            $week = if ($null -ne $p.week) { "$($p.week)%" } else { '-' }
            [void](Add-Item "${who}: 5h $five | week $week" $false)
        }
    }
    [void]$menu.Items.Add('-')
    $open = Add-Item 'Open Agent Board' $true
    $open.Add_Click({ Open-Board '' })
    $quit = Add-Item 'Quit tray buddy' $true
    $quit.Add_Click({
        $tray.Visible = $false
        $tray.Dispose()
        [System.Windows.Forms.Application]::Exit()
    })
    $e.Cancel = $false
})

$tray.Add_MouseClick({
    param($sender, $e)
    if ($e.Button -eq [System.Windows.Forms.MouseButtons]::Left) { Open-Board '' }
})

# Check the board every 6 seconds; animate only when something is happening.
$poll = New-Object System.Windows.Forms.Timer
$poll.Interval = 6000
$poll.Add_Tick({ Refresh })
$poll.Start()

$anim = New-Object System.Windows.Forms.Timer
$anim.Interval = 450
$anim.Add_Tick({
    $m = Get-Mood
    if ($m -eq 'need' -or $m -eq 'work') {
        $script:frame = 1 - $script:frame
        Update-Look
    }
})
$anim.Start()

Refresh
[System.Windows.Forms.Application]::Run()
