rem Remember to install PyInstaller
rem pip3 install PyInstaller

set /p Version=<wst_protocol_test_version.txt
set filein=perform_wst_protocol_test.py
set fileout=WST_CAN_protocol_test.V%Version%

echo %filein%
python -m PyInstaller --onefile --clean --icon=wst.ico --name %fileout% %filein%
pause