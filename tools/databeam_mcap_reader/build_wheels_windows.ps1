# script.ps1

param (
    [Parameter(Mandatory=$false, ValueFromRemainingArguments=$true)]
    [string[]]$PY_VERSIONS
)

if (-not $PY_VERSIONS -or $PY_VERSIONS.Count -eq 0) {
    Write-Host "Usage: .\$($MyInvocation.MyCommand.Name) <python_version> [<python_version> ...]"
    Write-Host "Example:"
    Write-Host " .\$($MyInvocation.MyCommand.Name) 3.10 3.11 3.12"
    exit 1
}

Set-Location -Path $PSScriptRoot

# $paths = @('.\build', '.\dist')
# foreach ($dir in $paths) {
#     if (Test-Path $dir) {
#         Remove-Item -Path $dir -Recurse -Force
#     }
# }

$ErrorActionPreference = "Stop"

function CleanBuildDir {
    if (Test-Path '.\build') {
        Remove-Item -Path '.\build' -Recurse -Force
    }
}

# download mcap cli
py -m pip install --upgrade requests
py src\download_mcap_cli.py

foreach ($PYVER in $PY_VERSIONS)
{
    try
    {
        CleanBuildDir

        Write-Host "Using Python $PYVER"
        
        py -$PYVER -m pip install --upgrade setuptools build
        if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

        conan install . --update --output-folder=build --build=missing -g CMakeDeps -g CMakeToolchain -s compiler.cppstd=20
        if ($LASTEXITCODE -ne 0) { throw "conan failed" }

        py -$PYVER -m build --wheel
    }
    catch {
    }
    CleanBuildDir
}
Read-Host "(press return to close)"
