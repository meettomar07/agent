import subprocess
import sys

ps_script = """
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Security.Cryptography.CryptographicBuffer, Windows.Security.Cryptography, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType = WindowsRuntime]
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($engine) {
    Write-Host "FOUND_WIN_OCR: $($engine.RecognizerLanguage.LanguageTag)"
} else {
    Write-Host "NOT_FOUND"
}
"""

res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)
