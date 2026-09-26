@echo off
setlocal
cd /d "%~dp0"
if not exist tools\ffmpeg.exe (
  echo Missing tools\ffmpeg.exe
  echo Add ffmpeg.exe to the tools folder, then run this file again.
  pause
  exit /b 1
)
if not exist tools\exiftool.exe (
  echo Missing tools\exiftool.exe
  echo Add exiftool.exe to the tools folder, then run this file again.
  pause
  exit /b 1
)
py -m pip install --upgrade pyinstaller
if errorlevel 1 python -m pip install --upgrade pyinstaller
pyinstaller --noconfirm --clean --windowed --name MediaMetadataMerge --add-binary "tools\ffmpeg.exe;tools" --add-binary "tools\exiftool.exe;tools" app.py
if errorlevel 1 exit /b 1
copy /Y tools\ffmpeg.exe dist\MediaMetadataMerge\tools\ffmpeg.exe >nul
copy /Y tools\exiftool.exe dist\MediaMetadataMerge\tools\exiftool.exe >nul
echo.
echo Build complete: dist\MediaMetadataMerge\MediaMetadataMerge.exe
pause
