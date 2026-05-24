# Set Xochitl-optimized Ollama settings as permanent Windows user env vars.
# Run this ONCE. Settings persist across reboots and apply to Ollama automatically.
# After running: restart Ollama from the system tray (right-click → Quit, then relaunch).
#
# What each setting does:
#   OLLAMA_KEEP_ALIVE=30m        — keep model hot in VRAM between turns (default: 5m)
#   OLLAMA_NUM_PARALLEL=2        — allow router model + primary model concurrently
#   OLLAMA_FLASH_ATTENTION=1     — faster prefill, lower peak VRAM during long prompts
#   OLLAMA_KV_CACHE_TYPE=q8_0   — halves KV cache VRAM cost, negligible quality loss
#   OLLAMA_MAX_LOADED_MODELS=2   — keep primary + router resident simultaneously

$vars = @{
    OLLAMA_KEEP_ALIVE        = "30m"
    OLLAMA_NUM_PARALLEL      = "2"
    OLLAMA_FLASH_ATTENTION   = "1"
    OLLAMA_KV_CACHE_TYPE     = "q8_0"
    OLLAMA_MAX_LOADED_MODELS = "2"
}

foreach ($name in $vars.Keys) {
    [System.Environment]::SetEnvironmentVariable($name, $vars[$name], "User")
    Write-Host "  Set $name = $($vars[$name])" -ForegroundColor Green
}

Write-Host ""
Write-Host "Done. Restart Ollama from the system tray for settings to take effect." -ForegroundColor Cyan
Write-Host "(Right-click the Ollama tray icon → Quit, then relaunch Ollama.)" -ForegroundColor DarkGray
