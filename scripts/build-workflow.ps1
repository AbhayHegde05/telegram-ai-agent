$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
node (Join-Path $PSScriptRoot "build-workflow.mjs")
