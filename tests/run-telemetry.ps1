$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$compilerBin = Join-Path $env:USERPROFILE '.platformio\packages\toolchain-gccmingw32\bin'
$compiler = Join-Path $compilerBin 'g++.exe'
if (!(Test-Path -LiteralPath $compiler)) {
    throw 'Jalankan python -m platformio pkg install --global --tool platformio/toolchain-gccmingw32'
}
$env:PATH = $compilerBin + ';' + $env:PATH
$target = Join-Path ([System.IO.Path]::GetTempPath()) ('telemetry-' + [Guid]::NewGuid().ToString('N') + '.exe')
try {
    & $compiler -std=c++11 -Wall -Wextra -Werror ('-I' + (Join-Path $projectRoot 'firmware\include')) (Join-Path $PSScriptRoot 'telemetry_test.cpp') -o $target
    if ($LASTEXITCODE -ne 0) { throw "Build tes gagal: $LASTEXITCODE" }
    & $target
    if ($LASTEXITCODE -ne 0) { throw "Tes telemetry gagal: $LASTEXITCODE" }
    Write-Output 'PASS: JSON suhu valid, penolakan nilai gagal, dan konversi startup'
} finally {
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target }
}
