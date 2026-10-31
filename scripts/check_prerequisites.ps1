# scripts/check_prerequisites.ps1
# Diagnostic probe for Windows environments (PowerShell 5.1+ / PowerShell Core 7+)
# Verifies installation of all prerequisite tools for the LLM-Wiki stack.

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "LLM-Wiki Prerequisite Diagnostic"

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  LLM-Wiki & Knowledge Lab Prerequisite Diagnostic    " -ForegroundColor Cyan
Write-Host "  Target OS: Microsoft Windows ($([System.Environment]::OSVersion.Version))" -ForegroundColor Cyan
Write-Host "======================================================`n" -ForegroundColor Cyan

$MissingCritical = 0
$MissingOptional = 0

function Check-Tool {
    param(
        [string]$CommandName,
        [string]$DisplayName,
        [string]$InstallHint,
        [bool]$IsCritical = $true
    )

    $cmd = Get-Command $CommandName -ErrorAction SilentlyContinue
    if ($cmd) {
        $version = ""
        try {
            switch ($CommandName) {
                "node" { $version = (& node --version 2>&1).Trim() }
                "python" { $version = (& python --version 2>&1).Trim() }
                "uv" { $version = (& uv --version 2>&1).Trim() }
                "git" { $version = (& git --version 2>&1).Trim() }
                "gh" { $version = (& gh --version 2>&1).Trim() }
                "docker" { $version = (& docker --version 2>&1).Trim() }
                "podman" { $version = (& podman --version 2>&1).Trim() }
                "agy" { $version = (& agy --version 2>&1).Trim() }
                default { $version = "Installed (PATH detected)" }
            }
        } catch {
            $version = "Installed"
        }
        Write-Host "  [✓] " -ForegroundColor Green -NoNewline
        Write-Host "$DisplayName ($CommandName): " -ForegroundColor White -NoNewline
        Write-Host "$version" -ForegroundColor Gray
    } else {
        if ($IsCritical) {
            Write-Host "  [✗] " -ForegroundColor Red -NoNewline
            Write-Host "$DisplayName ($CommandName) is " -ForegroundColor White -NoNewline
            Write-Host "NOT INSTALLED" -ForegroundColor Red
            Write-Host "      Install via: $InstallHint" -ForegroundColor Yellow
            $script:MissingCritical++
        } else {
            Write-Host "  [!] " -ForegroundColor Yellow -NoNewline
            Write-Host "$DisplayName ($CommandName) is " -ForegroundColor White -NoNewline
            Write-Host "NOT FOUND" -ForegroundColor Yellow
            Write-Host "      Install via: $InstallHint" -ForegroundColor Yellow
            $script:MissingOptional++
        }
    }
}

Write-Host "1. Core CLI & Autonomous Agent Tooling:" -ForegroundColor White
Check-Tool -CommandName "agy" -DisplayName "Google Antigravity CLI" -InstallHint "npm install -g @google/antigravity-cli (or run inside WSL2)" -IsCritical $true
Check-Tool -CommandName "git" -DisplayName "Git Version Control" -InstallHint "winget install Git.Git" -IsCritical $true
Check-Tool -CommandName "gh" -DisplayName "GitHub CLI" -InstallHint "winget install GitHub.cli" -IsCritical $false

Write-Host "`n2. Python & Package Runtime:" -ForegroundColor White
Check-Tool -CommandName "python" -DisplayName "Python 3.11+" -InstallHint "winget install Python.Python.3.12" -IsCritical $true
Check-Tool -CommandName "uv" -DisplayName "Astral uv Package Manager" -InstallHint "powershell -c 'irm https://astral.sh/uv/install.ps1 | iex' or winget install astral-sh.uv" -IsCritical $true

Write-Host "`n3. Node.js & Astro Frontend Runtime:" -ForegroundColor White
Check-Tool -CommandName "node" -DisplayName "Node.js (v20+)" -InstallHint "winget install OpenJS.NodeJS.LTS" -IsCritical $true
Check-Tool -CommandName "npm" -DisplayName "npm Package Manager" -InstallHint "Included with Node.js LTS" -IsCritical $true

Write-Host "`n4. Container Engine (ArcadeDB & Chainlit):" -ForegroundColor White
$hasDocker = Get-Command "docker" -ErrorAction SilentlyContinue
$hasPodman = Get-Command "podman" -ErrorAction SilentlyContinue

if ($hasDocker) {
    Check-Tool -CommandName "docker" -DisplayName "Docker Desktop (WSL2 Backend)" -InstallHint "winget install Docker.DockerDesktop" -IsCritical $true
} elseif ($hasPodman) {
    Check-Tool -CommandName "podman" -DisplayName "Podman Desktop for Windows" -InstallHint "winget install RedHat.PodmanDesktop" -IsCritical $true
} else {
    Write-Host "  [✗] Container Engine (docker or podman) is " -ForegroundColor Red -NoNewline
    Write-Host "NOT INSTALLED" -ForegroundColor Red
    Write-Host "      Install via: winget install Docker.DockerDesktop (recommended for Windows WSL2)" -ForegroundColor Yellow
    $MissingCritical++
}

Write-Host "`n5. Desktop IDE & Knowledge Exploration:" -ForegroundColor White
$obsidianCmd = Get-Command "obsidian" -ErrorAction SilentlyContinue
$obsidianAppPath = "$env:LOCALAPPDATA\Programs\obsidian\Obsidian.exe"
$obsidianProgramFiles = "$env:ProgramFiles\Obsidian\Obsidian.exe"

if ($obsidianCmd -or (Test-Path $obsidianAppPath) -or (Test-Path $obsidianProgramFiles)) {
    Write-Host "  [✓] " -ForegroundColor Green -NoNewline
    Write-Host "Obsidian: Detected on Windows system" -ForegroundColor White
} else {
    Write-Host "  [!] " -ForegroundColor Yellow -NoNewline
    Write-Host "Obsidian is NOT FOUND" -ForegroundColor Yellow
    Write-Host "      Install via: winget install Obsidian.Obsidian or download from https://obsidian.md" -ForegroundColor Yellow
    $MissingOptional++
}

Write-Host "`n6. Optional Local Embedding Inference:" -ForegroundColor White
Check-Tool -CommandName "ollama" -DisplayName "Ollama Local LLM Runner" -InstallHint "winget install Ollama.Ollama" -IsCritical $false

Write-Host "`n======================================================" -ForegroundColor Cyan
if ($MissingCritical -eq 0) {
    Write-Host "✓ System is ready for the LLM-Wiki & Knowledge Lab!" -ForegroundColor Green
    if ($MissingOptional -gt 0) {
        Write-Host "  (Notice: $MissingOptional optional component(s) missing; see recommendations above)" -ForegroundColor Yellow
    }
} else {
    Write-Host "✗ System is NOT ready: $MissingCritical critical dependency/dependencies missing." -ForegroundColor Red
    Write-Host "  Please install the missing critical tools before bootstrapping." -ForegroundColor Red
}
Write-Host "======================================================" -ForegroundColor Cyan
