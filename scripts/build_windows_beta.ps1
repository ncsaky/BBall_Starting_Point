param([string]$Version = "0.1.0-beta.8")
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
if ($env:OS -ne "Windows_NT") { throw "Run this build on Windows, not on macOS." }
$Venv = Join-Path $Repo ".cache/windows-beta-build/venv"
$Python = Join-Path $Venv "Scripts/python.exe"
if (!(Test-Path $Python)) {
    & py -3.13 -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw "Install official CPython 3.13.16 x64 with Tcl/Tk and the Python launcher." }
}
& $Python -c "import struct,sys,tkinter; assert sys.version_info[:3] == (3,13,16) and struct.calcsize('P') == 8, 'CPython 3.13.16 x64 required'"
if ($LASTEXITCODE -ne 0) { throw "Pinned Python/Tk check failed. Remove only the build venv and recreate it with CPython 3.13.16 x64." }
& $Python (Join-Path $Repo "packaging/windows/build.py") --check-inputs
if ($LASTEXITCODE -ne 0) { throw "Required release assets are missing." }
& $Python -m pip install -r (Join-Path $Repo "packaging/windows/build-requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Build dependency installation failed." }
& $Python (Join-Path $Repo "packaging/windows/build.py") --version $Version
if ($LASTEXITCODE -ne 0) { throw "Windows build failed." }
