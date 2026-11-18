# SPDX-License-Identifier: GPL-2.0-or-later
# Fetch a pinned compiler from the official immutable release and verify its hash.
$ErrorActionPreference = 'Stop'
$target = Join-Path $env:RUNNER_TEMP 'fdgcast-inno-6.7.4'
$compiler = Join-Path $target 'ISCC.exe'
if (-not (Test-Path $compiler)) {
  $download = Join-Path $env:RUNNER_TEMP 'innosetup-6.7.4.exe'
  Invoke-WebRequest 'https://github.com/jrsoftware/issrc/releases/download/is-6_7_4/innosetup-6.7.4.exe' -OutFile $download
  $expected = 'a549929319f9120716677c685535ca4671e4b937b5fdc87e2585f32d8eb30e8c'
  if ((Get-FileHash $download -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
    throw 'Official Inno Setup compiler checksum mismatch'
  }
  $process = Start-Process $download -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',"/DIR=`"$target`"" -Wait -PassThru
  if ($process.ExitCode -ne 0) { throw 'Inno Setup compiler installation failed' }
}
if (-not (Test-Path $compiler)) { throw 'Pinned Inno Setup compiler is missing' }
Write-Output $compiler
