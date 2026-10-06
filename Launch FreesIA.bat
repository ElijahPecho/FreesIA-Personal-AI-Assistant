@echo off
cd /d "%~dp0"
:: Launch GUI in hidden mode (no terminal window)
start "" /B pythonw.exe FreesIA_GUI.py
exit
