from wstcan.WSTCan import WSTCan
import time
import openpyxl
from spparser.SpFileWriter import SpFileWriter
from spparser.SpParser import SpParser

import json
import sys

wstcan = WSTCan(debugging=False, baudrate=250)

wstcan.setBaudrate(250)
wstcan.wakeBMS()

if wstcan.isBatteryConnected(verbose=False):
	print("Battery Found!")
	wstcan.write_cell_voltage_calibrations({1: 2.925})
	print(wstcan.getCellVoltages())
	wstcan.uninitialize()
	wstcan_ny = WSTCan(debugging=False, baudrate=250)
	wstcan_ny.initialize()
	wstcan_ny.write_cell_voltage_calibrations({1: 3.325})
	print(wstcan_ny.getCellVoltages())
	#print("getting raw cell voltages")
	#raw_cell_voltages = WSTCan.get_raw_cell_voltages()
	#print("Raw Cell Voltages: %s" % raw_cell_voltages)
	#parms = WSTCan.readCustomParameters()
	#print("parms: %s" % parms)
	#basic_description = WSTCan.get_battery_description()
	#for key,value in basic_description.items():
	#	print("%s: %s" % (key, value))

	#print("SP STATUS:")
	#status = WSTCan.get_all_sp_status()
	#print(json.dumps(status, indent=2))

	#print("")
	#cell = 1
	#voltage = 3.6
	#calib_Data = {cell: voltage}
	#WSTCan.write_cell_voltage_calibrations(calib_Data)

	#parameter_data = WSTCan.readParameters()
	#parameter_data['custom_parameters'] = WSTCan.getCustomParameters()
	#_sp_parser = SpParser()
	#print("Parameters Raw data: %s" % parameter_data)
	#parsed_parameters = _sp_parser.parse_sp_parameters(parameter_data, bms_model=basic_description['bms_model'])
	#print(json.dumps(parsed_parameters, indent=2))

	#model = basic_description['battery_model']
	#serial_number = basic_description['serial_number']
	#filename = "%s_%s_log" % (model, serial_number)
	#print("Writing to filename: %s" % filename)
	
	#spfw = SpFileWriter()
	#spfw.write_log_to_excel(status['log']['parsed_log'], filename , overwrite=True)
	#spfw.write_log_stats_to_excel(status['log']['parsed_log_statistics'], filename, append=True)
	#spfw.write_general_info_to_excel(status['basic_info'], filename, append=True)
	#spfw.write_realtime_status_to_excel(status['realtime_status'], filename, append=True)
	#spfw.write_parameters_to_excel(parsed_parameters, filename, append=False)


else:
	print("No battery connected")