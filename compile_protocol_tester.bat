rem Remember to install PyInstaller
rem pip3 install PyInstaller

set /p Version=<wst_protocol_test_version.txt
set filein=perform_wst_protocol_test.py
set fileout=WST_CAN_protocol_test.V%Version%
echo %filein%
python -m PyInstaller --onefile --clean --icon=wst.ico --name %fileout% %filein%

set filein=test_baudrate_change.py
set fileout=test_baudrate_change.V%Version%
echo %filein%
python -m PyInstaller --onefile --clean --icon=wst.ico --name %fileout% %filein%

set filein=test_can_charge.py
set fileout=test_can_charge.V%Version%
echo %filein%
python -m PyInstaller --onefile --clean --icon=wst.ico --name %fileout% %filein%

set filein=test_custom_params.py
set fileout=test_custom_params.V%Version%
echo %filein%
python -m PyInstaller --onefile --clean --icon=wst.ico --name %fileout% %filein%

set filein=test_0x68E_0x68D_mode.py
set fileout=test_0x68E_0x68D_mode.V%Version%
echo %filein%
python -m PyInstaller --onefile --clean --icon=wst.ico --name %fileout% %filein%


pause