# JobPilot installer for Windows (PowerShell 5.1 or newer).
#
#   irm https://raw.githubusercontent.com/dheerajkarwasra/jobpilot/main/install.ps1 | iex
#
# Options (environment variables, set before running):
#   JOBPILOT_REPO      GitHub repo to install from      (default dheerajkarwasra/jobpilot)
#   JOBPILOT_REF       branch or tag                     (default main)
#   JOBPILOT_DIR       where the code and venv live      (default %USERPROFILE%\.jobpilot)
#   JOBPILOT_EXTRAS    pip extras, e.g. "gsheets"
#   JOBPILOT_NO_SETUP  set to 1 to skip the setup wizard
#
# Re-running updates JobPilot. Your workspace is never touched.
$ErrorActionPreference = "Stop"

$Repo   = if ($env:JOBPILOT_REPO) { $env:JOBPILOT_REPO } else { "dheerajkarwasra/jobpilot" }
$Ref    = if ($env:JOBPILOT_REF)  { $env:JOBPILOT_REF }  else { "main" }
$Dir    = if ($env:JOBPILOT_DIR)  { $env:JOBPILOT_DIR }  else { Join-Path $env:USERPROFILE ".jobpilot" }
$Extras = $env:JOBPILOT_EXTRAS
$BinDir = Join-Path $Dir "bin"

function Say($m)  { Write-Host "==> $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "[!] $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "[x] $m" -ForegroundColor Red; exit 1 }

# 1. Python 3.9 or newer
$Py = $null
foreach ($cand in @(@("py", "-3"), @("python"), @("python3"))) {
    $exe = $cand[0]
    if (Get-Command $exe -ErrorAction SilentlyContinue) {
        $args0 = @($cand | Select-Object -Skip 1)
        & $exe @args0 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) { $Py = $cand; break }
    }
}
if (-not $Py) { Die "Python 3.9 or newer is needed. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH') or run: winget install Python.Python.3.12" }
$PyExe = $Py[0]; $PyArgs = @($Py | Select-Object -Skip 1)
Say ("Using " + (& $PyExe @PyArgs --version))

# 2. Get the code
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
$Here = if ($PSScriptRoot) { $PSScriptRoot } else { "" }
if ($Here -and (Test-Path (Join-Path $Here "pyproject.toml")) -and (Select-String -Quiet -Path (Join-Path $Here "pyproject.toml") -Pattern 'name = "jobpilot"')) {
    $Src = $Here
    Say "Installing from local folder $Src"
} else {
    $Src = Join-Path $Dir "src"
    if (Get-Command git -ErrorAction SilentlyContinue) {
        if (Test-Path (Join-Path $Src ".git")) {
            Say "Updating $Src"
            git -C $Src fetch --depth 1 origin $Ref; git -C $Src checkout -q FETCH_HEAD
        } else {
            Say "Downloading github.com/$Repo ($Ref)"
            if (Test-Path $Src) { Remove-Item -Recurse -Force $Src }
            git clone -q --depth 1 --branch $Ref "https://github.com/$Repo.git" $Src
        }
    } else {
        Say "Downloading github.com/$Repo ($Ref) as a zip"
        $zip = Join-Path $env:TEMP "jobpilot.zip"
        $tmp = Join-Path $env:TEMP "jobpilot-extract"
        Invoke-WebRequest -UseBasicParsing "https://codeload.github.com/$Repo/zip/$Ref" -OutFile $zip
        if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
        Expand-Archive $zip -DestinationPath $tmp
        if (Test-Path $Src) { Remove-Item -Recurse -Force $Src }
        Move-Item (Get-ChildItem $tmp | Select-Object -First 1).FullName $Src
        Remove-Item $zip
    }
}

# 3. Virtual environment and package
$VenvPy = Join-Path $Dir "venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
    Say "Creating virtual environment in $Dir\venv"
    & $PyExe @PyArgs -m venv (Join-Path $Dir "venv")
}
& $VenvPy -m pip install -q --upgrade pip
$Target = if ($Extras) { "$Src[$Extras]" } else { $Src }
Say "Installing JobPilot"
& $VenvPy -m pip install -q --upgrade $Target
if ($LASTEXITCODE -ne 0) { Die "pip install failed" }

# 4. Put `jobpilot` on the user PATH
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
$Shim = Join-Path $BinDir "jobpilot.cmd"
Set-Content -Path $Shim -Encoding ASCII -Value "@echo off`r`n`"$Dir\venv\Scripts\jobpilot.exe`" %*"
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not ($UserPath -split ";" | Where-Object { $_ -eq $BinDir })) {
    [Environment]::SetEnvironmentVariable("Path", ($UserPath.TrimEnd(";") + ";" + $BinDir), "User")
    Warn "Added $BinDir to your PATH. Open a new terminal for it to take effect."
}
$env:Path = "$BinDir;$env:Path"
Say ("Installed " + (& $Shim --version))

# 5. Setup wizard
if ($env:JOBPILOT_NO_SETUP -eq "1") {
    Say "Skipping setup. Run 'jobpilot setup' when ready."
} else {
    Say "Starting setup. You can re-run it any time with: jobpilot setup"
    & $Shim setup
}
