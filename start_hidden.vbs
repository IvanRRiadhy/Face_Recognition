Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "E:\Face_Detection"
WshShell.Run "cmd /c ""E:\Face_Detection\.venv\Scripts\python.exe"" ""E:\Face_Detection\run_server.py"" > ""E:\Face_Detection\service.log"" 2> ""E:\Face_Detection\service_error.log""", 0, False
