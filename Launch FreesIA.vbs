Set oShell = CreateObject("WScript.Shell")
Set oFS = CreateObject("Scripting.FileSystemObject")

' Get the directory where this script is located
strScriptPath = WScript.ScriptFullName
strScriptDir = oFS.GetParentFolderName(strScriptPath)

' Launch FreesIA GUI without showing console window
strCommand = "python.exe FreesIA_GUI.py"
oShell.CurrentDirectory = strScriptDir
oShell.Run strCommand, 0, False
