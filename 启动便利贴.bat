@echo off
rem ============================================================
rem  Sticky Notes - lightweight native edition (Python + Tk)
rem  Memory: ~30 MB   |   No browser engine required
rem ============================================================
setlocal
set "APP=%~dp0sticky.pyw"

if not exist "%APP%" (
  echo [ERROR] sticky.pyw was not found next to this script.
  pause
  exit /b 1
)

rem --- Prefer a portable pythonw.exe shipped in the same folder ---
if exist "%~dp0pythonw.exe" (
  start "" "%~dp0pythonw.exe" "%APP%"
  exit /b
)

rem --- Then try pythonw.exe on PATH ---
for %%I in (pythonw.exe) do set "PYW=%%~$PATH:I"
if defined PYW (
  start "" "%PYW%" "%APP%"
  exit /b
)

rem --- Then probe the usual install locations ---
for %%P in (
  "%LocalAppData%\Programs\Python\Python314\pythonw.exe"
  "%LocalAppData%\Programs\Python\Python313\pythonw.exe"
  "%LocalAppData%\Programs\Python\Python312\pythonw.exe"
  "%LocalAppData%\Programs\Python\Python311\pythonw.exe"
  "C:\Python314\pythonw.exe"
  "C:\Python313\pythonw.exe"
  "C:\Python312\pythonw.exe"
  "C:\Python311\pythonw.exe"
  "%ProgramFiles%\Python314\pythonw.exe"
  "%ProgramFiles%\Python313\pythonw.exe"
  "C:\Python\pythonw.exe"
) do (
  if exist %%P (
    start "" %%P "%APP%"
    exit /b
  )
)

echo [ERROR] Python (pythonw.exe) was not found on this computer.
echo.
echo   This app needs Python 3.10 or newer WITH the "tcl/tk" component.
echo   Download: https://www.python.org/downloads/windows/
echo   During setup, keep "Add python.exe to PATH" checked.
echo.
pause
