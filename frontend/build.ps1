# Compila il CSS del frontend (Tailwind v4 standalone). Uso: .\build.ps1 [-Watch]
param([switch]$Watch)

$cli = Join-Path $PSScriptRoot "bin\tailwindcss.exe"
if (-not (Test-Path $cli)) {
    Write-Error "CLI Tailwind non trovata in bin\tailwindcss.exe - vedi README.md per scaricarla."
    exit 1
}

$inFile = Join-Path $PSScriptRoot "input.css"
$outFile = Join-Path $PSScriptRoot "..\fantaApp\static\fantaApp\css\main.css"

if ($Watch) {
    & $cli -i $inFile -o $outFile --watch
} else {
    & $cli -i $inFile -o $outFile --minify
}
