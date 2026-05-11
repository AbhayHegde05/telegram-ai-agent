$ErrorActionPreference = "Stop"

if (-not (Test-Path ".env")) {
    throw "Missing .env file in the repository root."
}

Get-Content ".env" | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') {
        return
    }

    $parts = $_ -split '=', 2
    if ($parts.Count -eq 2) {
        [System.Environment]::SetEnvironmentVariable($parts[0], $parts[1])
    }
}

if (-not $env:TELEGRAM_BOT_TOKEN) {
    throw "TELEGRAM_BOT_TOKEN is missing."
}

if (-not $env:WEBHOOK_URL) {
    throw "WEBHOOK_URL is missing."
}

$webhookUrl = ($env:WEBHOOK_URL.TrimEnd('/')) + "/webhook/telegram-assistant"
$payload = @{
    url = $webhookUrl
    drop_pending_updates = $true
}

if ($env:TELEGRAM_WEBHOOK_SECRET) {
    $payload.secret_token = $env:TELEGRAM_WEBHOOK_SECRET
}

$response = Invoke-RestMethod `
    -Method Post `
    -Uri "https://api.telegram.org/bot$($env:TELEGRAM_BOT_TOKEN)/setWebhook" `
    -ContentType "application/json" `
    -Body ($payload | ConvertTo-Json -Depth 10)

$response | ConvertTo-Json -Depth 10

