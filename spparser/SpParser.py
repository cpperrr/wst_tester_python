import json
import math
import os
import pathlib
import struct
import sys
from datetime import datetime


# noinspection PyListCreation,PyDictCreation
class SpParser:
	def __init__(self):
		self.is_frozen = getattr(sys, 'frozen', False)
		self.possible_status_codes = [
			# [byte, bit, [shortDesc, abbreviation]]
			[0, 0, ["Discharging", "DSG"]],
			[0, 1, ["Charging", "CHG"]],

			[3, 0, ["Cell Over Voltage", "Cell OV"]],
			[3, 1, ["Pack Over Voltage", "Pack OV"]],
			[3, 4, ["Over Charge Protection", "OCP"]],

			[4, 0, ["Cell Under Voltage", "Cell UV"]],
			[4, 1, ["Pack Under Voltage", "Pack UV"]],

			[5, 0, ["Charge Temperature", "CT"]],
			[5, 1, ["Discharge Temperature", "DT"]],
			[5, 2, ["Mos Temperature", "MT"]],
			[5, 4, ["High Temperature", "O"]],
			# these are special as they are used in conjunction with other temperature triggers
			[5, 5, ["Under Temperature", "U"]],  # also special

			[6, 0, ["Short Circuit", "SC"]],
			[6, 1, ["Discharge Over Current", "DOC"]],
			[6, 2, ["Charge Over Current", "COC"]],
			[6, 4, ["Ambient Over Temperature", "AOT"]],
			[6, 5, ["Ambient Under Temperature", "AUT"]],
		]
		self.dropdown_values = self.load_drop_down_values_from_file()
		self.front_ends = {"default": "TI", 0x3: "SW", 0x4: "TI"}
		self.extended_frame_0x04_values = {"default": False, 0x0E: "True"}

	# check if bit is set. smallest bit value is 0 and then incrementing.
	@staticmethod
	def is_bit_set(flag_data, nth_bit):
		if flag_data & (1 << nth_bit):
			return True
		else:
			return False

	def get_status_codes_snake_case(self, current_data_array):
		status_codes_abbr_array = self.get_status_code_desc_abbr_array(current_data_array)
		list_of_status_codes = []
		for status_code in status_codes_abbr_array:
			list_of_status_codes.append(status_code[1].lower().replace(" ", "_"))
		return list_of_status_codes

	def get_status_code_desc_abbr_array(self, current_data_array):
		return_array = []
		for codeToCheck in self.possible_status_codes:
			byte_location = codeToCheck[0]
			bit_location = codeToCheck[1]
			desc_and_abbr = codeToCheck[2]
			byte_to_check = current_data_array[byte_location]
			if self.is_bit_set(byte_to_check, bit_location):
				return_array.append(desc_and_abbr)

		# sanitize over and under temp charge discharge current.
		if ["Charge Temperature", "CT"] in return_array:
			if ["High Temperature", "O"] in return_array:
				return_array.append(["Charge Over Temperature", "COT"])
			if ["Under Temperature", "U"] in return_array:
				return_array.append(["Charge Under Temperature", "CUT"])

		if ["Discharge Temperature", "DT"] in return_array:
			if ["High Temperature", "O"] in return_array:
				return_array.append(["Discharge Over Temperature", "DOT"])
			if ["Under Temperature", "U"] in return_array:
				return_array.append(["Discharge Under Temperature", "DUT"])

		if ["Mos Temperature", "MT"] in return_array:
			if ["High Temperature", "O"] in return_array:
				return_array.append(["MOS Over Temperature", "MOT"])
			if ["Under Temperature", "U"] in return_array:
				return_array.append(["MOS Under Temperature", "MUT"])

		# clean out all the "half status code. we have what we want"
		if ["Charge Temperature", "CT"] in return_array:
			return_array.remove(["Charge Temperature", "CT"])
		if ["Discharge Temperature", "DT"] in return_array:
			return_array.remove(["Discharge Temperature", "DT"])
		if ["Mos Temperature", "MT"] in return_array:
			return_array.remove(["Mos Temperature", "MT"])
		if ["High Temperature", "O"] in return_array:
			return_array.remove(["High Temperature", "O"])
		if ["Under Temperature", "U"] in return_array:
			return_array.remove(["Under Temperature", "U"])

		return return_array

	def is_byte_array_valid(self, sp_data_package):
		start_byte_valid = False
		product_id_valid = False
		battery_pack_address_valid = False
		byte_package_length_valid = False
		checksum_valid = False

		if sp_data_package is None:
			return

		if sp_data_package[0] == 0xEA:
			start_byte_valid = True
		if sp_data_package[1] == 0xD1:
			product_id_valid = True
		if sp_data_package[2] == 0x01:
			battery_pack_address_valid = True
		byte_package_length = sp_data_package[3]
		if byte_package_length + 4 == len(sp_data_package):
			byte_package_length_valid = True
		checksum = sp_data_package[len(sp_data_package) - 2]

		arr_subset = sp_data_package[3:]
		if checksum == self.calc_checksum(arr_subset):
			checksum_valid = True

		if start_byte_valid and product_id_valid and battery_pack_address_valid and byte_package_length_valid and checksum_valid:
			return True
		else:
			return False

	@staticmethod
	def calc_checksum(arr):
		checksum = 0
		for i in range(len(arr)):
			checksum = checksum ^ arr[i]
		return checksum

	def read_four_bytes_big_endian_from_array(self, data_array, start_location, unsigned=True):
		high_high_byte = data_array[start_location]
		low_high_byte = data_array[start_location+1]
		high_low_byte = data_array[start_location+2]
		low_low_byte = data_array[start_location+3]
		return self.parse_four_bytes_big_endian(high_high_byte, low_high_byte, high_low_byte, low_low_byte, unsigned=unsigned)

	def read_two_bytes_big_endian_from_array(self, data_array, start_location, unsigned=True):
		high_byte = data_array[start_location]
		low_byte = data_array[start_location+1]
		return self.parse_two_bytes_big_endian(high_byte, low_byte, unsigned=unsigned)
	# noinspection PyDictCreation

	@staticmethod
	def parse_two_bytes_big_endian(high_byte, low_byte, unsigned=True):
		parsed_word = 0
		if unsigned:
			parsed_word = int(struct.unpack('>H', bytes([high_byte, low_byte]))[0])
		if not unsigned:
			parsed_word = int(struct.unpack('>h', bytes([high_byte, low_byte]))[0])
		if parsed_word == 65535:
			parsed_word = 0
		return parsed_word

	@staticmethod
	def parse_four_bytes_big_endian(high_high_byte, low_high_byte, high_low_byte, low_low_byte, unsigned=True):
		parsed_word = 0
		if unsigned:
			parsed_word = int(struct.unpack('>I', bytes([high_high_byte, low_high_byte, high_low_byte, low_low_byte]))[0])
		if not unsigned:
			parsed_word = int(struct.unpack('>i', bytes([high_high_byte, low_high_byte, high_low_byte, low_low_byte]))[0])
		if parsed_word == 65535:
			parsed_word = 0
		return parsed_word

	def parse_voltage_status(self, voltage_data_array):
		voltage_status = {}
		voltage_status['pack_cells_total'] = voltage_data_array[0]
		voltage_status['temperature_probes_total'] = voltage_data_array[1]
		voltage_status['system_cells_total'] = voltage_data_array[2]  # Not really used as far as we have seen.

		# Loop to get all cell voltages
		voltage_status["cell_voltages"] = {}
		cell_diff_temp_array = []
		for i in range(voltage_status['pack_cells_total']):
			array_location_for_current_cell_voltage_high_byte = 3 + i * 2
			array_location_for_current_cell_voltage_low_byte = 4 + i * 2
			high_byte = voltage_data_array[array_location_for_current_cell_voltage_high_byte]
			low_byte = voltage_data_array[array_location_for_current_cell_voltage_low_byte]
			cell_voltage_in_mv = self.parse_two_bytes_big_endian(high_byte, low_byte)
			cell_voltage_in_v = float(cell_voltage_in_mv) / 1000
			cell_diff_temp_array.append(cell_voltage_in_v)
			voltage_status["cell_voltages"]["cell_%s" % (i+1)] = cell_voltage_in_v

		# calculate cell diff and add to voltage_status
		voltage_status["cell_voltage_diff"] = round((max(cell_diff_temp_array) - min(cell_diff_temp_array)), 4)

		return voltage_status

	def parse_current_status(self, current_data_array):
		current_status = {}
		current_status_byte = current_data_array[0]
		current_status['mos_temperature_probe_present'] = self.is_bit_set(current_status_byte, 4)
		current_status['ambient_temperature_probe_present'] = self.is_bit_set(current_status_byte, 5)
		current_status['status_flags'] = self.get_status_code_desc_abbr_array(current_data_array)
		current_status['status_flags_snake_case'] = self.get_status_codes_snake_case(current_data_array)

		high_byte = current_data_array[1]
		low_byte = current_data_array[2]
		# current is in 10mA, so we convert to A
		current_value = float(self.parse_two_bytes_big_endian(high_byte, low_byte))/100
		if 'dsg' in current_status['status_flags_snake_case']:
			current_status['current'] = current_value * (-1)
		else:
			current_status['current'] = current_value

		# temperature probes for cells are in a dict. mos and ambient have separate keys
		current_status['cell_temperature_probes'] = {}
		current_status['total_temperature_probes_count'] = current_data_array[7]
		total_probes = current_status['total_temperature_probes_count']
		mos_probes = int(current_status['mos_temperature_probe_present'])
		ambient_probes = int(current_status['ambient_temperature_probe_present'])
		# cell probes are what is left when the ambient and mos are removed.
		current_status['cell_temperature_probes_count'] = total_probes - mos_probes - ambient_probes
		# loop over cells temperature probes and save in dict
		for i in range(current_status['cell_temperature_probes_count']):
			array_location_for_temperature_probe = 8 + i
			current_status['cell_temperature_probes']["cell_temperature_%s" % (i+1)] = current_data_array[array_location_for_temperature_probe] - 40

		# Mos and ambient probe temp.
		array_location_for_mos_probe = 8 + current_status['cell_temperature_probes_count']
		array_location_for_ambient_probe = 8 + current_status['cell_temperature_probes_count'] + 1
		if current_status['mos_temperature_probe_present']:
			current_status['mos_temperature'] = current_data_array[array_location_for_mos_probe] - 40
		else:
			current_status['mos_temperature'] = "NA"
		if current_status['ambient_temperature_probe_present']:
			current_status['ambient_temperature'] = current_data_array[array_location_for_ambient_probe] - 40
		else:
			current_status['ambient_temperature'] = "NA"

		#  resistor value
		array_start_location_for_shunt_resistor = 8 + current_status['cell_temperature_probes_count'] + mos_probes + ambient_probes#  two bytes
		shunt_resistor_byte = self.read_two_bytes_big_endian_from_array(current_data_array, array_start_location_for_shunt_resistor)
		self.debug_print("Shunt resistor data %s from array %s" % (current_data_array[array_start_location_for_shunt_resistor:array_start_location_for_shunt_resistor+1], current_data_array))
		current_status['shunt_resistor'] = float(shunt_resistor_byte) / 100

		#  balancing bytes are in reversed order. last byte in array holds the first cells.
		balancing_byte_3_array_location = array_start_location_for_shunt_resistor + 2	 # Holds cell 17-24 balancing flags
		balancing_byte_2_array_location = array_start_location_for_shunt_resistor + 3  # Holds cell 9-16 balancing flags
		balancing_byte_1_array_location = array_start_location_for_shunt_resistor + 4  # Holds cell 1-8 balancing flags
		bal_byte_1 = current_data_array[balancing_byte_1_array_location]
		bal_byte_2 = current_data_array[balancing_byte_2_array_location]
		bal_byte_3 = current_data_array[balancing_byte_3_array_location]
		balancing_flags = int.from_bytes(struct.pack('BBB', bal_byte_3, bal_byte_2, bal_byte_1), 'big')
		current_status["cells_currently_balancing"] = {}
		for cell_number in range(24):
			current_status["cells_currently_balancing"]["cell_%s_balancing" % (cell_number + 1)] = self.is_bit_set(balancing_flags, cell_number)

		# Firmware version
		array_fw_version_byte_location = balancing_byte_1_array_location + 1
		current_status['firmware_version'] = current_data_array[array_fw_version_byte_location]

		# Mosfet status
		array_location_mosfet_status = array_fw_version_byte_location + 1
		mosfet_status_byte = current_data_array[array_location_mosfet_status]
		current_status['discharge_mosfet_on'] = self.is_bit_set(mosfet_status_byte, 1)
		current_status['charge_mosfet_on'] = self.is_bit_set(mosfet_status_byte, 2)

		# failure status for mosfet and cell voltage and temperature
		array_location_failure_status = array_location_mosfet_status + 1
		failure_status_byte = current_data_array[array_location_failure_status]
		current_status['temperature_sensor_failure'] = self.is_bit_set(failure_status_byte, 0)
		current_status['cell_voltage_failure'] = self.is_bit_set(failure_status_byte, 1)
		current_status['discharge_mosfet_failure'] = self.is_bit_set(failure_status_byte, 2)
		current_status['charge_mosfet_failure'] = self.is_bit_set(failure_status_byte, 3)
		return current_status

	def parse_power_status(self, power_data_array):
		power_status = {}

		# SoC
		power_status['soc'] = power_data_array[1]

		# empty flag byte in power_data_array[2]

		# Cycle count - sp docs refer to this as checksum for some strange reason.
		high_byte = power_data_array[3]
		low_byte = power_data_array[4]
		power_status['cycles'] = self.parse_two_bytes_big_endian(high_byte, low_byte)

		# empty flag byte in power_data_array[5]

		# Design capacity
		high_high_byte = power_data_array[6]
		low_high_byte = power_data_array[7]
		# empty flag byte in power_data_array[8]
		high_low_byte = power_data_array[9]
		low_low_byte = power_data_array[10]
		power_status['design_capacity'] = self.parse_four_bytes_big_endian(high_high_byte, low_high_byte, high_low_byte, low_low_byte)

		# empty flag byte in power_data_array[11]

		# full capacity
		high_high_byte = power_data_array[12]
		low_high_byte = power_data_array[13]
		# empty flag byte in power_data_array[14]
		high_low_byte = power_data_array[15]
		low_low_byte = power_data_array[16]
		power_status['full_capacity'] = self.parse_four_bytes_big_endian(high_high_byte, low_high_byte, high_low_byte, low_low_byte)

		# empty flag byte in power_data_array[17]

		# remaining capacity
		high_high_byte = power_data_array[18]
		low_high_byte = power_data_array[19]
		# empty flag byte in power_data_array[20]
		high_low_byte = power_data_array[21]
		low_low_byte = power_data_array[22]
		power_status['remaining_capacity'] = self.parse_four_bytes_big_endian(high_high_byte, low_high_byte, high_low_byte, low_low_byte)

		# empty flag byte in power_data_array[23]

		# Remaining discharge time in min
		high_byte = power_data_array[24]
		low_byte = power_data_array[25]
		power_status['remaining_discharge_minutes'] = self.parse_two_bytes_big_endian(high_byte, low_byte)
		if power_status['remaining_discharge_minutes'] == 65535:
			power_status['remaining_discharge_minutes'] = -1

		# empty flag byte in power_data_array[26]

		# remaining charge time in min
		high_byte = power_data_array[27]
		low_byte = power_data_array[28]
		power_status['remaining_charge_minutes'] = self.parse_two_bytes_big_endian(high_byte, low_byte)
		if power_status['remaining_charge_minutes'] == 65535:
			power_status['remaining_charge_minutes'] = -1

		# empty flag byte in power_data_array[29]

		# charge intervals(time since last charge) in hours
		high_byte = power_data_array[30]
		low_byte = power_data_array[31]
		power_status['hours_since_last_charge'] = self.parse_two_bytes_big_endian(high_byte, low_byte)
		# obs - no flag byte here
		# the longest charge interval (max time between two charges ever)
		high_byte = power_data_array[32]
		low_byte = power_data_array[33]
		power_status['max_hours_between_charge'] = self.parse_two_bytes_big_endian(high_byte, low_byte)

		# reserved bytes 34-40

		# total battery voltage
		high_byte = power_data_array[41]
		low_byte = power_data_array[42]
		# total battery voltage is on 10mV, so we convert to V
		power_status['total_battery_voltage'] = float(self.parse_two_bytes_big_endian(high_byte, low_byte)) / 100

		# cell max voltage
		high_byte = power_data_array[43]
		low_byte = power_data_array[44]
		power_status['cell_max_voltage'] = float(self.parse_two_bytes_big_endian(high_byte, low_byte))/1000

		# cell min voltage
		high_byte = power_data_array[45]
		low_byte = power_data_array[46]
		power_status['cell_min_voltage'] = float(self.parse_two_bytes_big_endian(high_byte, low_byte))/1000

		# Handle extended protocol
		# See: "SuperPower common communication protocol V1.1 06.06.2022.doc"

		# Default values for when we don't have the extended bytes.
		power_status['extended_0x04_frame'] = self.extended_frame_0x04_values['default']
		power_status['front_end'] = self.front_ends['default']
		power_status['hardware_version'] = False
		power_status['solution_id_byte_raw'] = False
		if len(power_data_array) > 49 and (power_data_array[47] == 0x0D):
			power_status['hardware_version'] = power_data_array[48]
			power_status['solution_id_byte_raw'] = power_data_array[49]
			high_nibble = power_data_array[49] >> 4
			low_nibble = power_data_array[49] & 0x0F
			power_status['front_end'] = self.front_ends[high_nibble]
			power_status['extended_0x04_frame'] = self.extended_frame_0x04_values[low_nibble]

		return power_status

	def parse_log_statistics(self, log_statistics_data_array):
		# if argument is an array, we assume two stat frames are here. If not we assume it's the correct-merged array.
		# this "should" make us UART compatible.
		log_statistics = {}

		if isinstance(log_statistics_data_array[0], list):
			log_statistics_data_array = log_statistics_data_array[0][1:] + log_statistics_data_array[1][1:]

		offset = 4  # first 4 bytes are reserved
		log_statistics['cot_count'] = self.read_two_bytes_big_endian_from_array(log_statistics_data_array, 0+offset, unsigned=True)
		log_statistics['cut_count'] = self.read_two_bytes_big_endian_from_array(log_statistics_data_array, 2+offset, unsigned=True)
		log_statistics['dot_count'] = self.read_two_bytes_big_endian_from_array(log_statistics_data_array, 4+offset, unsigned=True)
		log_statistics['dut_count'] = self.read_two_bytes_big_endian_from_array(log_statistics_data_array, 6+offset, unsigned=True)
		log_statistics['fet_ot_count'] = self.read_two_bytes_big_endian_from_array(log_statistics_data_array, 8+offset, unsigned=True)
		log_statistics['software_ov_count'] = self.read_two_bytes_big_endian_from_array(log_statistics_data_array, 10+offset, unsigned=True)
		log_statistics['software_uv_count'] = self.read_two_bytes_big_endian_from_array(log_statistics_data_array, 12+offset, unsigned=True)
		log_statistics['pack_ov_count'] = self.read_two_bytes_big_endian_from_array(log_statistics_data_array, 14+offset, unsigned=True)
		log_statistics['pack_uv_count'] = self.read_two_bytes_big_endian_from_array(log_statistics_data_array, 16+offset, unsigned=True)
		log_statistics['chg_full_count'] = self.read_two_bytes_big_endian_from_array(log_statistics_data_array, 18+offset, unsigned=True)
		log_statistics['hardware_ov_count'] = self.read_two_bytes_big_endian_from_array(log_statistics_data_array, 20+offset, unsigned=True)
		log_statistics['hard_uv'] = self.read_two_bytes_big_endian_from_array(log_statistics_data_array, 22+offset, unsigned=True)
		log_statistics['soft_coc'] = self.read_two_bytes_big_endian_from_array(log_statistics_data_array, 24+offset, unsigned=True)
		log_statistics['soft_doc'] = self.read_two_bytes_big_endian_from_array(log_statistics_data_array, 26+offset, unsigned=True)
		log_statistics['hard_oc'] = self.read_two_bytes_big_endian_from_array(log_statistics_data_array, 28+offset, unsigned=True)
		log_statistics['hardware_sc'] = self.read_two_bytes_big_endian_from_array(log_statistics_data_array, 30+offset, unsigned=True)
		log_statistics['uv_shutdown'] = self.read_two_bytes_big_endian_from_array(log_statistics_data_array, 32+offset, unsigned=True)
		log_statistics['auto_shutdown_count'] = self.read_two_bytes_big_endian_from_array(log_statistics_data_array, 34+offset, unsigned=True)
		log_statistics['button_shutdown_count'] = self.read_two_bytes_big_endian_from_array(log_statistics_data_array, 36+offset, unsigned=True)
		log_statistics['reset_count'] = self.read_two_bytes_big_endian_from_array(log_statistics_data_array, 38+offset, unsigned=True)
		log_statistics['accumulated_discharge_minutes'] = self.read_four_bytes_big_endian_from_array(log_statistics_data_array, 40+offset, unsigned=True)
		log_statistics['accumulated_charge_minutes'] = self.read_four_bytes_big_endian_from_array(log_statistics_data_array, 44+offset, unsigned=True)
		log_statistics['app_updates_count'] = 0 if log_statistics_data_array[48+offset] == 255 else log_statistics_data_array[48+offset]
		return log_statistics

	# expects a 6 integer array
	@staticmethod
	def parse_sp_log_date(date_array) -> str:
		# all the date values are parsed to padded hex string, then to int.
		# it is a strange way it is coded...
		year = int("20"+"{:02x}".format(date_array[0]))
		month = int("{:02x}".format(date_array[1]))
		day = int("{:02x}".format(date_array[2]))
		hour = int("{:02x}".format(date_array[3]))
		minute = int("{:02x}".format(date_array[4]))
		second = int("{:02x}".format(date_array[5]))
		try:
			date_time = datetime(year, month, day, hour, minute, second)
		except ValueError:
			date_time = "corrupted"

		return str(date_time)

	def parse_log(self, log_data_array):
		parsed_log = {}
		parsed_log['headings'] = [
			'Entry #', 'Date', 'Pack V', 'Cell min (V)', 'Cell Max (V)', 'Current (A)',
			'Min Temp (deg-C)', 'Max Temp (deg-C)', 'SoC (%)', 'Rem Cap (mAh)', 'Cycles #',
			'State 1', 'State 2', 'State 3', 'CHG/DHG ', 'Event', 'SoH (%)',
			'MOS Temp. (C)', 'Cell # min temp', 'Cell # max temp.']

		parsed_records = []  # holds the parsed records before assigning to dict in the end
		for i, raw_record in enumerate(log_data_array):  # loop to parse all log data into new parsed records
			parsed_record = []

			# Index. We assign our own, because the actual entry id from the record is 1 byte, so it
			# restarts multiple times in large logs.
			parsed_record.append(i+1)  # Index - see comment above
			date = self.parse_sp_log_date(raw_record[1:7])  # Date
			parsed_record.append(date)

			pack_voltage = self.read_two_bytes_big_endian_from_array(raw_record, 7)  # 'Pack_V'
			pack_voltage = float(pack_voltage)/100
			parsed_record.append(pack_voltage)

			cell_min_voltage = self.read_two_bytes_big_endian_from_array(raw_record, 9)  # 'Cell_min_(V)'
			cell_min_voltage = float(cell_min_voltage)/1000
			parsed_record.append(cell_min_voltage)

			cell_max_voltage = self.read_two_bytes_big_endian_from_array(raw_record, 11)  # 'Cell_Max_(V)'
			cell_max_voltage = float(cell_max_voltage) / 1000
			parsed_record.append(cell_max_voltage)

			current = self.read_two_bytes_big_endian_from_array(raw_record, 13, unsigned=False)  # 'Current_(A)'
			current = float(current)/100
			parsed_record.append(current)

			min_temp = raw_record[15]-40  # 'Min_Temp_(deg-C)'
			parsed_record.append(min_temp)

			max_temp = raw_record[16]-40  # 'Max_Temp_(deg-C)'
			parsed_record.append(max_temp)

			soc = raw_record[17]  # 'SoC_(%)'
			parsed_record.append(soc)

			remaining_capacity = self.read_four_bytes_big_endian_from_array(raw_record, start_location=18)  # 'Rem_Cap_(mAh)'
			parsed_record.append(remaining_capacity)

			cycle_count = self.read_two_bytes_big_endian_from_array(raw_record, start_location=22)  # 'Cycles_#'
			parsed_record.append(cycle_count)

			# States 1,2 & 3
			# I have chosen to use hex representation as keys, because they are like this in the documentation.
			states_dict_array = []
			states_dict_array.append({
				0x00: 'Normal',
				0x01: 'Pack UV Recovery',
				0x02: 'Cell UV Recovery',
				0x04: 'Pack OV Recovery',
				0x08: 'Cell OV Recovery',
				0x10: 'Pack UV',
				0x20: 'Cell UV',
				0x40: 'Pack OV',
				0x80: 'Cell OV',
				0xa0: 'Cell OV/Cell UV (Failure)'})  # State 1 dict

			states_dict_array.append({
				0x00: 'Normal',
				0x04: 'SC Recovery',
				0x08: 'DOC Recovery',
				0x10: 'COC Recovery',
				0x20: 'SC',
				0x40: 'DOC',
				0x80: 'COC'})  # State 2 dict

			states_dict_array.append({
				0x00: 'Normal',
				0x10: 'DOT Recovery',
				0x20: 'COT Recovery',
				0x40: 'DOT',
				0x80: 'COT'})  # State 3 dict

			# ready array with the three state values from the raw data, transformed to hex string.
			state_values = [raw_record[24], raw_record[25], raw_record[26]]

			# write the human-readable version by 'translating' from the indexes
			# we have 3 states, so we do this 3 times
			for state_index in range(3):
				if state_values[state_index] in states_dict_array[state_index]:
					parsed_record.append(states_dict_array[state_index][state_values[state_index]])
				else:
					# if the status is not found, pass on the raw value as hex for readability.
					parsed_record.append("0x" + "{:02x}".format(state_values[state_index]))

			# Charge / Discharge flag
			charge_flag_index = {
				0x20: 'Standby',
				0x40: 'DSG',
				0x80: 'CHG'}
			charge_flag = raw_record[27]

			charge_status = "0x" + "{:02x}".format(charge_flag)  # default value if not in flag_index dict

			if charge_flag in charge_flag_index:
				charge_status = charge_flag_index[charge_flag]

			parsed_record.append(charge_status)

			# 'Event'
			event_code_dict = {
				0x1: "Manual Restart",
				0x2: "Manual Shutdown",
				0x3: "UV Shutdown",
				0x4: "Power Up",
				0x5: "Reserved",
				0x6: "Full Cap. Update",
				0x7: "Cycle Count Update",
				0x8: "D-Fet Off",
				0x9: "C-Fet Off",
				0xA: "D-Fet On",
				0xB: "C-Fet On",
				0xC: "Write Configuration Parameters",
				0xD: "Charging Current Calibration",
				0xE: "Discharge Current Calibration",
				0xF: "Voltage Calibration",
				0x16: "Cell Over voltage Alarm",
				0x17: "Tov Alarm",
				0x18: "Battery Over-Discharge Alarm",
				0x19: "Tuv Alarm",
				0x1A: "Charging Over current Alarm",
				0x1B: "Discharge Over current Alarm",
				0x1C: "Charging Over temperature Alarm",
				0x1D: "Discharge Over-Temperature Alarm",
				0x1E: "Charging Mos Failure",
				0x1F: "Discharge Mos Failure",
				0x20: "Voltage Acquisition Failure",
				0x21: "Temperature Acquisition Failure",
				0x22: "Current Acquisition Failure",
				0x23: "Charging Starts",
				0x24: "Charging Stopped",
				0x25: "Full Charge Protection",
				0x26: "Full Charge Recovery",
				0x27: "Discharge Starts",
				0x28: "Discharge Stops",
				0x29: "Automatic Power Off",
				0x2A: "AFE Internal Error",
				0x2B: "Soc Corrected To 0%",
				0x2C: "Open Circuit - Full Of FCC Updates",
				0x2D: "Charges - Full Of FCC Updates",
				0x2E: "Open Circuit-Charge Stop Fcc Update",
				0x2F: "Charge - Full Of Fcc Updates",
				0x30: "Anti-Sparking Switch Short Circuit Protection",
				0x31: "Pre-Discharge Short Circuit Protection",
				0x32: "Heating Start ",
				0x33: "Heating Stop ",
				0x34: "15S Delayed Current Detection ",
				0x35: "Low Voltage Brick",
				0x36: "Low Voltage Brick Recovery",
				0x37: "Cell Voltage Diff. Brick",
				0x38: "Cell Voltage Diff. Brick Recovery",
				0x39: "Cp8 Extended Protection Initialized",
				0x5A: "Cell Imbalance Alarm",
				0x5B: "Cell Imbalance Alarm Recovery",
				0x5C: "Pc Design Capacity Calibration",
				0x5D: "Pc Remaining Capacity Calibration",
				0x5E: "Full Soc Correction",
				0x5F: "Scheduled Recording",
				0x60: "Mos High Temperature Protection",
				0x61: "Mos High Temperature Recovery",
				0x62: "Charging",
				0x63: "Discharging",
				0x64: "Program Update Enters Bootloader",
				0x65: "Battery Over Voltage Alarm Recovery",
				0x66: "Battery Under Voltage Alarm Recovery",
				0x67: "Total Pressure Over voltage Alarm Recovery",
				0x68: "Total Pressure Over-Discharge Alarm Recovery",
				0x69: "Charging Temperature Alarm Recovery",
				0x6A: "Discharge Temperature Alarm Recovery",
				0x6B: "Short Circuit Automatic Recovery Lock",
				0x6C: "Over current Automatic Recovery Lock",
				0x6D: "Cell Voltage Failure Protection",
				0x6E: "Cell Voltage Difference Failure Recovery",
				0x6F: "Charging Is Prohibited",
				0x70: "Prohibit Charging Recovery",
				0x71: "Charging Over current Alarm Recovery",
				0x72: "Discharge Over current Alarm Recovery",
				0x73: "Mos High Temperature Alarm",
				0x74: "Mos High Temperature Alarm Recovery",
				0x75: "Environmental High Temperature Alarm",
				0x76: "Environment High Temperature Alarm Recovery",
				0x77: "Environmental Low Temperature Alarm",
				0x78: "Environmental Low Temperature Alarm Recovery",
				0x79: "Capacity Low Alarm",
				0x7A: "Capacity Low Alarm Recovery",
				0x7B: "Environmental High Temperature Protection",
				0x7C: "Environmental High Temperature Protection Recovery",
				0x7D: "Environmental Low Temperature Protection",
				0x7E: "Environmental Low Temperature Protection Recovery",
				0x7F: "Charging Current Limit Is On",
				0x80: "Charging Current Limit Off"
			}
			event_code = raw_record[28]
			event_text = "0x" + "{:02x}".format(event_code)  # Default
			if event_code in event_code_dict:
				event_text = event_code_dict[event_code]
			parsed_record.append(event_text)

			# 'SoH_(%)'
			soh = raw_record[29]
			parsed_record.append(soh)

			# 'MOS_Temp._(C)'
			mos_temperature = raw_record[30] - 40  # offset ntc by -40
			parsed_record.append(mos_temperature)

			# 'Cell_#_min_temp'
			cell_number_min_temp = raw_record[31]
			parsed_record.append(cell_number_min_temp)

			# 'Cell_#_max_temp.'
			cell_number_max_temp = raw_record[32]
			parsed_record.append(cell_number_max_temp)

			parsed_records.append(parsed_record)  # Add to list of parsed records

		parsed_log['records'] = parsed_records
		return parsed_log

	@staticmethod
	def decode_bms_serial_number(encoded_data):
		bms_batch_packed_as_hex = encoded_data[0:5]
		bms_date_packed_as_hex = encoded_data[5:9]
		bms_serial_packed_as_hex = encoded_data[9:13]

		bms_batch = int(bms_batch_packed_as_hex, 16)
		bms_serial = int(bms_serial_packed_as_hex, 16)
		bms_date_as_int = int(bms_date_packed_as_hex, 16)

		bms_date_as_bin_string = format(bms_date_as_int, '014b')

		year_as_bin = bms_date_as_bin_string[0:5]
		month_as_bin = bms_date_as_bin_string[5:9]
		day_as_bin = bms_date_as_bin_string[9:14]

		year = int(year_as_bin, 2) + 22  # offset year by 22
		month = int(month_as_bin, 2)
		day = int(day_as_bin, 2)
		year_as_string = format(year, "02d")
		month_as_string = format(month, "02d")
		day_as_string = format(day, "02d")
		date_string = year_as_string + month_as_string + day_as_string

		bms_batch_as_string = format(bms_batch, "06d")
		bms_serial_as_string = format(bms_serial, "04d")
		return {
			'bms_batch': bms_batch_as_string,
			'bms_prod_date': date_string,
			'bms_serial_number_on_day': bms_serial_as_string
		}

	def parse_sp_parameters_0x07(self, parameters_data, parsed_status, bms_model):
		parsed_parameters = self.set_up_parsed_parameters_groups()
		dropdown_values = self.parse_dropdown_values(parsed_status)
		#  ocd_2_array = self.load_drop_down_value_type(bms_model, "OCD2")
		#  ocd_2_delay_array = self.load_drop_down_value_type(bms_model, "OCD2_DELAY")
		#  sc_array = self.load_drop_down_value_type(bms_model, "SC")
		#  sc_delay_array = self.load_drop_down_value_type(bms_model, "SC_DELAY")
		#  occ2_array = self.load_drop_down_value_type(bms_model, "OCC2")
		#  occ2_delay_array = self.load_drop_down_value_type(bms_model, "OCC2_DELAY")

		# 0x07 package parsing
		shutdown_current = parameters_data[0x7][0]
		shutdown_current_parsed = float(shutdown_current) * 0.1
		parsed_parameters['parameter_group_4']['shutdown_current'] = {
			'value': shutdown_current_parsed,
			'unit': 'A',
			'type': 'single'
		}

		occ1_threshold = parameters_data[0x7][1]
		occ1_threshold_parsed = occ1_threshold + 1
		parsed_parameters['parameter_group_1']['occ1_threshold'] = {
			'value': occ1_threshold_parsed,
			'unit': 'A',
			'type': 'single'
		}

		ov_threshold = parameters_data[0x7][2]
		ov_threshold_parsed = round(float(ov_threshold) * 0.01 + 2, 2)
		parsed_parameters['parameter_group_1']['ov_threshold'] = {
			'value': ov_threshold_parsed,
			'unit': 'V',
			'type': 'single'
		}

		ov_delay = parameters_data[0x7][3]
		ov_delay_parsed = (ov_delay + 1) * 100
		parsed_parameters['parameter_group_1']['ov_delay'] = {
			'value': ov_delay_parsed,
			'unit': 'ms',
			'type': 'single'
		}

		uv_threshold = parameters_data[0x7][4]
		uv_threshold_parsed = round(float(uv_threshold) * 0.05 + 0.7, 2)
		parsed_parameters['parameter_group_1']['uv_threshold'] = {
			'value': uv_threshold_parsed,
			'unit': 'V',
			'type': 'single'
		}

		uv_delay = parameters_data[0x7][5]
		uv_delay_parsed = float(uv_delay + 1) * 100
		parsed_parameters['parameter_group_1']['uv_delay'] = {
			'value': uv_delay_parsed,
			'unit': 'ms',
			'type': 'single'
		}

		ov_recovery = parameters_data[0x7][6]
		ov_recovery_parsed = round(float(ov_recovery) * 0.01, 2)
		parsed_parameters['parameter_group_1']['ov_recovery'] = {
			'value': ov_recovery_parsed,
			'unit': 'V',
			'type': 'single'
		}

		uv_recovery = parameters_data[0x7][7]
		uv_recovery_parsed = round(float(uv_recovery) * 0.01, 2)
		parsed_parameters['parameter_group_1']['uv_recovery'] = {
			'value': uv_recovery_parsed,
			'unit': 'V',
			'type': 'single'
		}

		ocd2_threshold = parameters_data[0x7][8]
		ocd2_threshold_parsed = dropdown_values["OCD2"][ocd2_threshold]
		parsed_parameters['parameter_group_1']['ocd2_threshold'] = {
			'value': ocd2_threshold_parsed,
			'unit': 'A',
			'type': 'multi'
		}

		ocd2_delay = parameters_data[0x7][9]
		ocd2_delay_parsed = dropdown_values["OCD2_DELAY"][ocd2_delay]
		parsed_parameters['parameter_group_1']['ocd2_delay'] = {
			'value': ocd2_delay_parsed,
			'unit': 'ms',
			'type': 'multi'
		}

		dot_threshold = parameters_data[0x7][10]
		dot_threshold_parsed = dot_threshold + 30
		parsed_parameters['parameter_group_1']['dot_threshold'] = {
			'value': dot_threshold_parsed,
			'unit': 'C',
			'type': 'single'
		}

		dot_recovery = parameters_data[0x7][11]
		dot_recovery_parsed = dot_recovery + 30
		parsed_parameters['parameter_group_1']['dot_recovery'] = {
			'value': dot_recovery_parsed,
			'unit': 'C',
			'type': 'single'
		}

		dut_threshold = parameters_data[0x7][12]
		dut_threshold_parsed = dut_threshold - 40
		parsed_parameters['parameter_group_1']['dut_threshold'] = {
			'value': dut_threshold_parsed,
			'unit': 'C',
			'type': 'single'
		}

		dut_recovery = parameters_data[0x7][13]
		dut_recovery_parsed = dut_recovery - 40
		parsed_parameters['parameter_group_1']['dut_recovery'] = {
			'value': dut_recovery_parsed,
			'unit': 'C',
			'type': 'single'
		}

		cot_threshold = parameters_data[0x7][14]
		cot_threshold_parsed = cot_threshold + 30
		parsed_parameters['parameter_group_1']['cot_threshold'] = {
			'value': cot_threshold_parsed,
			'unit': 'C',
			'type': 'single'
		}

		cot_recovery = parameters_data[0x7][15]
		cot_recovery_parsed = cot_recovery + 30
		parsed_parameters['parameter_group_1']['cot_recovery'] = {
			'value': cot_recovery_parsed,
			'unit': 'C',
			'type': 'single'
		}

		cut_threshold = parameters_data[0x7][16]
		cut_threshold_parsed = cut_threshold - 40
		parsed_parameters['parameter_group_1']['cut_threshold'] = {
			'value': cut_threshold_parsed,
			'unit': 'C',
			'type': 'single'
		}

		cut_recovery = parameters_data[0x7][17]
		cut_recovery_parsed = cut_recovery - 40
		parsed_parameters['parameter_group_1']['cut_recovery'] = {
			'value': cut_recovery_parsed,
			'unit': 'C',
			'type': 'single'
		}

		balv_threshold = parameters_data[0x7][18]
		balv_threshold_parsed = round(float(balv_threshold) * 0.05 + 2, 2)
		parsed_parameters['parameter_group_1']['balv_threshold'] = {
			'value': balv_threshold_parsed,
			'unit': 'V',
			'type': 'single'
		}

		balv_delta = parameters_data[0x7][19]
		balv_delta_parsed = balv_delta + 2
		parsed_parameters['parameter_group_1']['balv_delta'] = {
			'value': balv_delta_parsed,
			'unit': 'mV',
			'type': 'single'
		}

		ocd1_threshold = parameters_data[0x7][20]
		ocd1_threshold_parsed = ocd1_threshold + 1
		parsed_parameters['parameter_group_1']['ocd1_threshold'] = {
			'value': ocd1_threshold_parsed,
			'unit': 'A',
			'type': 'single'
		}

		ocd1_delay = parameters_data[0x7][21]
		ocd1_delay_parsed = ocd1_delay + 1
		parsed_parameters['parameter_group_1']['ocd1_delay'] = {
			'value': ocd1_delay_parsed,
			'unit': 'S',
			'type': 'single'
		}

		occ1_delay = parameters_data[0x7][22]
		occ1_delay_parsed = occ1_delay + 1
		parsed_parameters['parameter_group_1']['occ1_delay'] = {
			'value': occ1_delay_parsed,
			'unit': 'S',
			'type': 'single'
		}

		sc_threshold = parameters_data[0x7][23]
		sc_threshold_parsed = dropdown_values["SC"][sc_threshold]
		parsed_parameters['parameter_group_1']['sc_threshold'] = {
			'value': sc_threshold_parsed,
			'unit': 'A',
			'type': 'multi'
		}

		sc_delay = parameters_data[0x7][24]
		sc_delay_parsed = dropdown_values["SC_DELAY"][sc_delay]
		parsed_parameters['parameter_group_1']['sc_delay'] = {
			'value': sc_delay_parsed,
			'unit': 'us',
			'type': 'multi'
		}

		ov_recovery_delay = parameters_data[0x7][25]
		ov_recovery_delay_parsed = ov_recovery_delay + 1
		parsed_parameters['parameter_group_1']['ov_recovery_delay'] = {
			'value': ov_recovery_delay_parsed,
			'unit': 'S',
			'type': 'single'
		}

		uv_recovery_delay = parameters_data[0x7][26]
		uv_recovery_delay_parsed = uv_recovery_delay + 1
		parsed_parameters['parameter_group_1']['uv_recovery_delay'] = {
			'value': uv_recovery_delay_parsed,
			'unit': 'S',
			'type': 'single'
		}

		return parsed_parameters

	def parse_sp_parameters_0x0b(self, parameters_data, bms_model):
		parsed_parameters = self.set_up_parsed_parameters_groups()

		unknown_value_byte_0_in_0b_frame = parameters_data[0x0B][0]
		unknown_value_byte_0_in_0b_frame_parsed = unknown_value_byte_0_in_0b_frame + 1
		parsed_parameters['parameter_group_2']['unknown_value_byte_0_in_0b_frame'] = {
			'value': unknown_value_byte_0_in_0b_frame_parsed,
			'unit': 'unit',
			'type': 'single'
		}

		functions_byte_0xb = parameters_data[0x0B][1]
		parsed_parameters["parameter_group_2"]['total_voltage_protect'] = {
			'value': self.is_bit_set(functions_byte_0xb, 0),
			'unit': 'bool',
			'type': 'single'
		}
		parsed_parameters["parameter_group_2"]['occ_recovery_by_discharge'] = {
			'value': self.is_bit_set(functions_byte_0xb, 1),
			'unit': 'bool',
			'type': 'single'
		}
		parsed_parameters["parameter_group_2"]['ocd_sc_auto_recovery'] = {
			'value': self.is_bit_set(functions_byte_0xb, 2),
			'unit': 'bool',
			'type': 'single'
		}
		parsed_parameters["parameter_group_2"]['ocd_sc_recovery_by_charge'] = {
			'value': self.is_bit_set(functions_byte_0xb, 3),
			'unit': 'bool',
			'type': 'single'
		}
		parsed_parameters["parameter_group_2"]['static_balance'] = {
			'value': self.is_bit_set(functions_byte_0xb, 4),
			'unit': 'bool',
			'type': 'single'
		}

		tov_threshold = self.read_two_bytes_big_endian_from_array(parameters_data[0x0B], 2)
		tov_threshold_parsed = float(tov_threshold) * 0.01
		parsed_parameters['parameter_group_2']['tov_threshold'] = {
			'value': tov_threshold_parsed,
			'unit': 'V',
			'type': 'single'
		}
		tov_recovery = self.read_two_bytes_big_endian_from_array(parameters_data[0x0B], 4)
		tov_recovery_parsed = float(tov_recovery) * 0.01
		parsed_parameters['parameter_group_2']['tov_recovery'] = {
			'value': tov_recovery_parsed,
			'unit': 'V',
			'type': 'single'
		}

		tuv_threshold = self.read_two_bytes_big_endian_from_array(parameters_data[0x0B], 6)
		tuv_threshold_parsed = float(tuv_threshold) * 0.01
		parsed_parameters['parameter_group_2']['tuv_threshold'] = {
			'value': tuv_threshold_parsed,
			'unit': 'V',
			'type': 'single'
		}
		tuv_recovery = self.read_two_bytes_big_endian_from_array(parameters_data[0x0B], 8)
		tuv_recovery_parsed = float(tuv_recovery) * 0.01
		parsed_parameters['parameter_group_2']['tuv_recovery'] = {
			'value': tuv_recovery_parsed,
			'unit': 'V',
			'type': 'single'
		}

		tov_delay = parameters_data[0x0B][10]
		tov_delay_parsed = tov_delay + 1 * 100
		parsed_parameters['parameter_group_2']['tov_delay'] = {
			'value': tov_delay_parsed,
			'unit': 'ms',
			'type': 'single'
		}
		tuv_delay = parameters_data[0x0B][11]
		tuv_delay_parsed = tuv_delay + 1 * 100
		parsed_parameters['parameter_group_2']['tuv_delay'] = {
			'value': tuv_delay_parsed,
			'unit': 'ms',
			'type': 'single'
		}
		occ_auto_recovery_dly = parameters_data[0x0B][12]
		occ_auto_recovery_dly_parsed = occ_auto_recovery_dly + 1
		parsed_parameters['parameter_group_2']['occ_auto_recovery_dly'] = {
			'value': occ_auto_recovery_dly_parsed,
			'unit': 'min',
			'type': 'single'
		}
		occ_auto_recovery_lock = parameters_data[0x0B][13]
		occ_auto_recovery_lock_parsed = occ_auto_recovery_lock
		parsed_parameters['parameter_group_2']['occ_auto_recovery_lock'] = {
			'value': occ_auto_recovery_lock_parsed,
			'unit': 'n',
			'type': 'single'
		}
		ocd_sc_auto_recovery_dly = parameters_data[0x0B][14]
		ocd_sc_auto_recovery_dly_parsed = ocd_sc_auto_recovery_dly + 1
		parsed_parameters['parameter_group_2']['ocd_sc_auto_recovery_dly'] = {
			'value': ocd_sc_auto_recovery_dly_parsed,
			'unit': 'min',
			'type': 'single'
		}
		ocd_sc_auto_recovery_lock = parameters_data[0x0B][15]
		ocd_sc_auto_recovery_lock_parsed = ocd_sc_auto_recovery_lock
		parsed_parameters['parameter_group_2']['ocd_sc_auto_recovery_lock'] = {
			'value': ocd_sc_auto_recovery_lock_parsed,
			'unit': 'n',
			'type': 'single'
		}

		static_balance_time = parameters_data[0x0B][16]
		static_balance_time_parsed = static_balance_time + 1
		parsed_parameters['parameter_group_2']['static_balance_time'] = {
			'value': static_balance_time_parsed,
			'unit': 'min',
			'type': 'single'
		}

		unknown_value_byte_17_in_0b_frame = parameters_data[0x0B][17]
		unknown_value_byte_17_in_0b_frame_parsed = unknown_value_byte_17_in_0b_frame + 1
		parsed_parameters['parameter_group_2']['unknown_value_byte_17_in_0b_frame'] = {
			'value': unknown_value_byte_17_in_0b_frame_parsed,
			'unit': 'unit',
			'type': 'single'
		}

		tov_recovery_dly = parameters_data[0x0B][18]
		tov_recovery_dly_parsed = tov_recovery_dly + 1
		parsed_parameters['parameter_group_2']['tov_recovery_dly'] = {
			'value': tov_recovery_dly_parsed,
			'unit': 'S',
			'type': 'single'
		}
		tuv_recovery_dly = parameters_data[0x0B][19]
		tuv_recovery_dly_parsed = tuv_recovery_dly + 1
		parsed_parameters['parameter_group_2']['tuv_recovery_dly'] = {
			'value': tuv_recovery_dly_parsed,
			'unit': 'S',
			'type': 'single'
		}

		return parsed_parameters

	def parse_sp_parameters_0x0d(self, parameters_data, bms_model):
		parsed_parameters = self.set_up_parsed_parameters_groups()
		functions_byte_0xd = parameters_data[0x0d][0]
		parsed_parameters["parameter_group_3"]['voltage_alarm'] = {
			'value': self.is_bit_set(functions_byte_0xd, 0),
			'unit': 'bool',
			'type': 'single'
		}
		parsed_parameters["parameter_group_3"]['current_alarm'] = {
			'value': self.is_bit_set(functions_byte_0xd, 1),
			'unit': 'bool',
			'type': 'single'
		}
		parsed_parameters["parameter_group_3"]['cell_temp_alarm'] = {
			'value': self.is_bit_set(functions_byte_0xd, 2),
			'unit': 'bool',
			'type': 'single'
		}
		parsed_parameters["parameter_group_3"]['mos_temp_alarm'] = {
			'value': self.is_bit_set(functions_byte_0xd, 3),
			'unit': 'bool',
			'type': 'single'
		}
		parsed_parameters["parameter_group_3"]['unbalance_alarm'] = {
			'value': self.is_bit_set(functions_byte_0xd, 4),
			'unit': 'bool',
			'type': 'single'
		}
		parsed_parameters["parameter_group_3"]['ambient_temp_alarm'] = {
			'value': self.is_bit_set(functions_byte_0xd, 5),
			'unit': 'bool',
			'type': 'single'
		}
		parsed_parameters["parameter_group_3"]['soc_alarm'] = {
			'value': self.is_bit_set(functions_byte_0xd, 6),
			'unit': 'bool',
			'type': 'single'
		}
		parsed_parameters["parameter_group_4"]['heat_fan_enabled'] = {
			'value': self.is_bit_set(functions_byte_0xd, 7),
			'unit': 'bool',
			'type': 'single'
		}

		pack_voltage_high_alarm = self.read_two_bytes_big_endian_from_array(parameters_data[0x0d], 1)
		pack_voltage_high_alarm_parsed = round(float(pack_voltage_high_alarm)/100, 2)
		parsed_parameters['parameter_group_3']['pack_voltage_high_alarm'] = {
			'value': pack_voltage_high_alarm_parsed,
			'unit': 'V',
			'type': 'single'
		}
		pack_voltage_low_alarm = self.read_two_bytes_big_endian_from_array(parameters_data[0x0d], 3)
		pack_voltage_low_alarm_parsed = round(float(pack_voltage_low_alarm)/100, 2)
		parsed_parameters['parameter_group_3']['pack_voltage_low_alarm'] = {
			'value': pack_voltage_low_alarm_parsed,
			'unit': 'V',
			'type': 'single'
		}
		cell_voltage_high_alarm = parameters_data[0x0d][5]
		cell_voltage_high_alarm_parsed = float(cell_voltage_high_alarm) * 0.05 + 2
		parsed_parameters['parameter_group_3']['cell_voltage_high_alarm'] = {
			'value': cell_voltage_high_alarm_parsed,
			'unit': 'V',
			'type': 'single'
		}
		cell_voltage_low_alarm = parameters_data[0x0d][6]
		cell_voltage_low_alarm_parsed = float(cell_voltage_low_alarm) * 0.10 + 0.7
		parsed_parameters['parameter_group_3']['cell_voltage_low_alarm'] = {
			'value': cell_voltage_low_alarm_parsed,
			'unit': 'V',
			'type': 'single'
		}
		current_alarm_chg_threshold = parameters_data[0x0d][7]
		current_alarm_chg_threshold_parsed = current_alarm_chg_threshold + 1
		parsed_parameters['parameter_group_3']['current_alarm_chg_threshold'] = {
			'value': current_alarm_chg_threshold_parsed,
			'unit': 'A',
			'type': 'single'
		}
		current_alarm_dsg_threshold = parameters_data[0x0d][8]
		current_alarm_dsg_threshold_parsed = current_alarm_dsg_threshold + 1
		parsed_parameters['parameter_group_3']['current_alarm_dsg_threshold'] = {
			'value': current_alarm_dsg_threshold_parsed,
			'unit': 'A',
			'type': 'single'
		}
		cell_temp_alarm_ot_charge = parameters_data[0x0d][9]
		cell_temp_alarm_ot_charge_parsed = cell_temp_alarm_ot_charge + 30
		parsed_parameters['parameter_group_3']['cell_temp_alarm_ot_charge'] = {
			'value': cell_temp_alarm_ot_charge_parsed,
			'unit': 'C',
			'type': 'single'
		}
		cell_temp_alarm_ut_charge = parameters_data[0x0d][10]
		cell_temp_alarm_ut_charge_parsed = cell_temp_alarm_ut_charge - 40
		parsed_parameters['parameter_group_3']['cell_temp_alarm_ut_charge'] = {
			'value': cell_temp_alarm_ut_charge_parsed,
			'unit': 'C',
			'type': 'single'
		}
		cell_temp_alarm_ot_discharge = parameters_data[0x0d][11]
		cell_temp_alarm_ot_discharge_parsed = cell_temp_alarm_ot_discharge + 30
		parsed_parameters['parameter_group_3']['cell_temp_alarm_ot_discharge'] = {
			'value': cell_temp_alarm_ot_discharge_parsed,
			'unit': 'C',
			'type': 'single'
		}
		cell_temp_alarm_ut_discharge = parameters_data[0x0d][12]
		cell_temp_alarm_ut_discharge_parsed = cell_temp_alarm_ut_discharge - 40
		parsed_parameters['parameter_group_3']['cell_temp_alarm_ut_discharge'] = {
			'value': cell_temp_alarm_ut_discharge_parsed,
			'unit': 'C',
			'type': 'single'
		}
		mos_temp_alarm_ot = parameters_data[0x0d][13]
		mos_temp_alarm_ot_parsed = mos_temp_alarm_ot - 40
		parsed_parameters['parameter_group_3']['mos_temp_alarm_ot'] = {
			'value': mos_temp_alarm_ot_parsed,
			'unit': 'C',
			'type': 'single'
		}
		mos_temp_alarm_ot_recovery = parameters_data[0x0d][14]
		mos_temp_alarm_ot_recovery_parsed = mos_temp_alarm_ot_recovery - 40
		parsed_parameters['parameter_group_3']['mos_temp_alarm_ot_recovery'] = {
			'value': mos_temp_alarm_ot_recovery_parsed,
			'unit': 'C',
			'type': 'single'
		}

		unbalanced_alarm_vol_difference = self.read_two_bytes_big_endian_from_array(parameters_data[0x0d], 15)
		unbalanced_alarm_vol_difference_parsed = round(float(unbalanced_alarm_vol_difference)*0.001, 3)
		parsed_parameters['parameter_group_3']['unbalanced_alarm_vol_difference'] = {
			'value': unbalanced_alarm_vol_difference_parsed,
			'unit': 'V',
			'type': 'single'
		}
		unbalanced_alarm_recovery_difference = self.read_two_bytes_big_endian_from_array(parameters_data[0x0d], 17)
		unbalanced_alarm_recovery_difference_parsed = round(float(unbalanced_alarm_recovery_difference)*0.001, 3)
		parsed_parameters['parameter_group_3']['unbalanced_alarm_recovery_difference'] = {
			'value': unbalanced_alarm_recovery_difference_parsed,
			'unit': 'V',
			'type': 'single'
		}
		ambient_temp_alarm_ot = parameters_data[0x0d][19]
		ambient_temp_alarm_ot_parsed = ambient_temp_alarm_ot + 30
		parsed_parameters['parameter_group_3']['ambient_temp_alarm_ot'] = {
			'value': ambient_temp_alarm_ot_parsed,
			'unit': 'C',
			'type': 'single'
		}
		ambient_temp_alarm_ut = parameters_data[0x0d][20]
		ambient_temp_alarm_ut_parsed = ambient_temp_alarm_ut - 40
		parsed_parameters['parameter_group_3']['ambient_temp_alarm_ut'] = {
			'value': ambient_temp_alarm_ut_parsed,
			'unit': 'C',
			'type': 'single'
		}
		soc_alarm_soc_low_threshold = parameters_data[0x0d][21]
		soc_alarm_soc_low_threshold_parsed = soc_alarm_soc_low_threshold
		parsed_parameters['parameter_group_3']['soc_alarm_soc_low_threshold'] = {
			'value': soc_alarm_soc_low_threshold_parsed,
			'unit': '%',
			'type': 'single'
		}
		if len(parameters_data[0x0d]) > 22:
			heat_fan_on = parameters_data[0x0d][22]
			heat_fan_on_parsed = heat_fan_on - 40
			parsed_parameters['parameter_group_4']['heat_fan_on'] = {
				'value': heat_fan_on_parsed,
				'unit': 'C',
				'type': 'single'
			}
			heat_fan_off = parameters_data[0x0d][23]
			heat_fan_off_parsed = heat_fan_off - 40
			parsed_parameters['parameter_group_4']['heat_fan_off'] = {
				'value': heat_fan_off_parsed,
				'unit': 'C',
				'type': 'single'
			}

		return parsed_parameters

	def parse_sp_parameters_0x70(self, parameters_data, parsed_status, bms_model):
		parsed_parameters = self.set_up_parsed_parameters_groups()
		dropdown_values = self.parse_dropdown_values(parsed_status)
		shut_down_voltage = parameters_data[0x70][0]
		shut_down_voltage_parsed = shut_down_voltage * 0.05 + 2
		parsed_parameters['parameter_group_4']['shut_down_voltage'] = {
			'value': shut_down_voltage_parsed,
			'unit': 'V',
			'type': 'single'
		}
		shut_down_delay = self.read_two_bytes_big_endian_from_array(parameters_data[0x70], 1)
		shut_down_delay_parsed = shut_down_delay
		parsed_parameters['parameter_group_4']['shut_down_delay'] = {
			'value': shut_down_delay_parsed,
			'unit': 'min',
			'type': 'single'
		}
		mos_otp = parameters_data[0x70][3]
		mos_otp_parsed = mos_otp + 1
		parsed_parameters['parameter_group_4']['mos_otp'] = {
			'value': mos_otp_parsed,
			'unit': 'V',
			'type': 'single'
		}
		mos_otp_recovery = parameters_data[0x70][4]
		mos_otp_recovery_parsed = mos_otp_recovery + 1
		parsed_parameters['parameter_group_4']['mos_otp_recovery'] = {
			'value': mos_otp_recovery_parsed,
			'unit': 'V',
			'type': 'single'
		}
		mos_ot_delay = parameters_data[0x70][5]
		mos_ot_delay_parsed = mos_ot_delay + 1
		parsed_parameters['parameter_group_4']['mos_ot_delay'] = {
			'value': mos_ot_delay_parsed,
			'unit': 'S',
			'type': 'single'
		}
		self_dsg_rate = parameters_data[0x70][6]
		self_dsg_rate_parsed = self_dsg_rate
		parsed_parameters['parameter_group_4']['self_dsg_rate'] = {
			'value': self_dsg_rate_parsed,
			'unit': '%',
			'type': 'single'
		}
		cycle_cap = parameters_data[0x70][7]
		cycle_cap_parsed = cycle_cap
		parsed_parameters['parameter_group_4']['cycle_cap'] = {
			'value': cycle_cap_parsed,
			'unit': '%',
			'type': 'single'
		}
		soc_0_voltage = self.read_two_bytes_big_endian_from_array(parameters_data[0x70], 8)
		soc_0_voltage_parsed = round(float(soc_0_voltage) * 0.001, 2)
		parsed_parameters['parameter_group_4']['soc_0_voltage'] = {
			'value': soc_0_voltage_parsed,
			'unit': 'V',
			'type': 'single'
		}
		ambient_otp = parameters_data[0x70][10]
		ambient_otp_parsed = ambient_otp + 30
		parsed_parameters['parameter_group_4']['ambient_otp'] = {
			'value': ambient_otp_parsed,
			'unit': 'C',
			'type': 'single'
		}
		ambient_otp_recovery = parameters_data[0x70][11]
		ambient_otp_recovery_parsed = ambient_otp_recovery + 30
		parsed_parameters['parameter_group_4']['ambient_otp_recovery'] = {
			'value': ambient_otp_recovery_parsed,
			'unit': 'C',
			'type': 'single'
		}
		ambient_utp = parameters_data[0x70][12]
		ambient_utp_parsed = ambient_utp - 40
		parsed_parameters['parameter_group_4']['ambient_utp'] = {
			'value': ambient_utp_parsed,
			'unit': 'C',
			'type': 'single'
		}
		ambient_utp_recovery = parameters_data[0x70][13]
		ambient_utp_recovery_parsed = ambient_utp_recovery - 40
		parsed_parameters['parameter_group_4']['ambient_utp_recovery'] = {
			'value': ambient_utp_recovery_parsed,
			'unit': 'C',
			'type': 'single'
		}

		if parsed_status['parsed_power_status']['front_end'] == "TI":  # TI does not have this parameter, so we revert to first element in the arrays.
			occ2_threshold_index = 0
			occ2_delay_index = 0
		else:
			occ2_both_raw_byte = parameters_data[0x70][14]
			occ2_threshold_index = occ2_both_raw_byte >> 4
			occ2_delay_index = occ2_both_raw_byte & 0x0F

		parsed_parameters['parameter_group_1']['occ2_threshold'] = {
			'value': dropdown_values["OCC2"][occ2_threshold_index],
			'unit': 'unit',
			'type': 'single'
		}
		parsed_parameters['parameter_group_1']['occ2_delay'] = {
			'value': dropdown_values["OCC2_DELAY"][occ2_delay_index],
			'unit': 'unit',
			'type': 'single'
		}

		return parsed_parameters

	def parse_sp_parameters_0x6e(self, parameters_data, bms_model):
		parsed_parameters = self.set_up_parsed_parameters_groups()
		pack_full_charge_voltage = self.read_two_bytes_big_endian_from_array(parameters_data[0x6e], 0)
		pack_full_charge_voltage_parsed = round(float(pack_full_charge_voltage) * 0.01, 2)
		parsed_parameters['parameter_group_5']['pack_full_charge_voltage'] = {
			'value': pack_full_charge_voltage_parsed,
			'unit': 'V',
			'type': 'single'
		}
		pack_full_charge_current = self.read_two_bytes_big_endian_from_array(parameters_data[0x6e], 0)
		pack_full_charge_current_parsed = round(float(pack_full_charge_current) * 0.01, 2)
		parsed_parameters['parameter_group_5']['pack_full_charge_current'] = {
			'value': pack_full_charge_current_parsed,
			'unit': 'A',
			'type': 'single'
		}
		soc_correction_full_capacity_att = self.read_two_bytes_big_endian_from_array(parameters_data[0x6e], 0)
		soc_correction_full_capacity_att_parsed = round(float(soc_correction_full_capacity_att) * 0.001, 3)
		parsed_parameters['parameter_group_5']['soc_correction_full_capacity_att'] = {
			'value': soc_correction_full_capacity_att_parsed,
			'unit': '%',
			'type': 'single'
		}
		temp_higher_att_factor_deprecated = self.read_two_bytes_big_endian_from_array(parameters_data[0x6e], 0)
		temp_higher_att_factor_deprecated_parsed = temp_higher_att_factor_deprecated
		parsed_parameters['parameter_group_5']['temp_higher_att_factor_DEPRECATED'] = {
			'value': temp_higher_att_factor_deprecated_parsed,
			'unit': '%',
			'type': 'single'
		}
		temp_lower_att_factor_deprecated = self.read_two_bytes_big_endian_from_array(parameters_data[0x6e], 0)
		temp_lower_att_factor_deprecated_parsed = temp_lower_att_factor_deprecated
		parsed_parameters['parameter_group_5']['temp_lower_att_factor_DEPRECATED'] = {
			'value': temp_lower_att_factor_deprecated_parsed,
			'unit': '%',
			'type': 'single'
		}
		full_charge_dly = parameters_data[0x6e][10]
		full_charge_dly_parsed = full_charge_dly * 0.01
		parsed_parameters['parameter_group_5']['full_charge_dly'] = {
			'value': full_charge_dly_parsed,
			'unit': 'S',
			'type': 'single'
		}
		return parsed_parameters

	def parse_sp_custom_parameters(self, parameters_data, bms_model):

		parsed_parameters = self.set_up_parsed_parameters_groups()

		for parameter_number in range(8):
			if not parameters_data['custom_parameters'] or len(parameters_data['custom_parameters']) < 8:
				return parsed_parameters
			parsed_value = parameters_data['custom_parameters'][parameter_number]
			if parsed_value == 655.35:
				parsed_value = 0
			parsed_parameters['parameter_group_6']["custom_parameter_%s" % (parameter_number + 1)] = {
				'value': parsed_value,
				'unit': '',
				'type': 'single'
			}
		return parsed_parameters

	def parse_sp_parameters(self, parameters_data, parsed_status, bms_model=None):

		parsed_parameters = self.set_up_parsed_parameters_groups()
		parsed_parameters = self.merge_parsed_parameter_groups(parsed_parameters, self.parse_sp_parameters_0x07(parameters_data, parsed_status, bms_model))
		parsed_parameters = self.merge_parsed_parameter_groups(parsed_parameters, self.parse_sp_parameters_0x0b(parameters_data, bms_model))
		parsed_parameters = self.merge_parsed_parameter_groups(parsed_parameters, self.parse_sp_parameters_0x0d(parameters_data, bms_model))
		parsed_parameters = self.merge_parsed_parameter_groups(parsed_parameters, self.parse_sp_parameters_0x70(parameters_data, parsed_status, bms_model))
		parsed_parameters = self.merge_parsed_parameter_groups(parsed_parameters, self.parse_sp_parameters_0x6e(parameters_data, bms_model))
		parsed_parameters = self.merge_parsed_parameter_groups(parsed_parameters, self.parse_sp_custom_parameters(parameters_data, bms_model))

		return parsed_parameters

	@staticmethod
	def load_drop_down_values_from_file():
		return json.loads("{}")
		# We directly calculate the dropdown values now.
		# determine if application is a script file or frozen exe
		# if getattr(sys, 'frozen', False):
		#	application_path = os.path.dirname(sys.executable)
		#	dropdown_values_file_path = pathlib.Path(application_path, "dropdown_values.json")
		#else:
		#	application_path = os.path.dirname(__file__)
		#	dropdown_values_file_path = pathlib.Path("spparser/dropdown_values.json")

		#return json.load(open(dropdown_values_file_path))

	@staticmethod
	def set_up_parsed_parameters_groups():
		return {
			"parameter_group_1": {},
			"parameter_group_2": {},
			"parameter_group_3": {},
			"parameter_group_4": {},
			"parameter_group_5": {},
			"parameter_group_6": {},
		}
		pass

	@staticmethod
	def merge_parsed_parameter_groups(parsed_parameters, new_parameters):
		parsed_parameters["parameter_group_1"].update(new_parameters["parameter_group_1"])
		parsed_parameters["parameter_group_2"].update(new_parameters["parameter_group_2"])
		parsed_parameters["parameter_group_3"].update(new_parameters["parameter_group_3"])
		parsed_parameters["parameter_group_4"].update(new_parameters["parameter_group_4"])
		parsed_parameters["parameter_group_5"].update(new_parameters["parameter_group_5"])
		parsed_parameters["parameter_group_6"].update(new_parameters["parameter_group_6"])
		return parsed_parameters

	@staticmethod
	def parse_dropdown_values(parsed_status):
		shunt_resistor_value = parsed_status['parsed_current_status']['shunt_resistor']
		front_end = parsed_status['parsed_power_status']['front_end']

		base_sw_values = {
			"OCD2": [30, 40, 50, 60, 70, 80, 90, 100, 120, 140, 160, 180, 200, 300, 400, 500],
			"OCD2_DELAY": [10, 20, 40, 60, 80, 100, 200, 400, 600, 800, 1000, 2000, 4000, 8000, 10000, 20000],
			"SC": [50, 80, 110, 140, 170, 200, 230, 260, 290, 320, 350, 400, 500, 600, 800, 1000],
			"SC_DELAY": [0, 64, 128, 192, 256, 320, 384, 448, 512, 576, 640, 704, 768, 832, 896, 960],
			"OCC2": [20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 160, 180, 200],
			"OCC2_DELAY": [10, 20, 40, 60, 80, 100, 200, 400, 600, 800, 1000, 2000, 4000, 8000, 10000, 20000]
		}
		base_ti_values = {
			"OCD2": [0, 1, 2, 3, 4, 5, 6, 7],
			"OCD2_DELAY": [8, 20, 40, 80, 160, 320, 640, 1280],
			"SC": [0, 1, 2, 3, 4, 5, 6, 7],
			"SC_DELAY": [70, 100, 200, 400],
			"OCC2": ["NA"],
			"OCC2_DELAY": ["NA"]
		}
		dropdown_values = {}

		if front_end == 'SW':
			dropdown_values = base_sw_values

			if shunt_resistor_value == 0:
				return dropdown_values

			for parameter_type in ["OCD2", "SC", "OCC2"]:
				temp_list_of_current_values = []
				for i in dropdown_values[parameter_type]:
					temp_list_of_current_values.append(int(round((i / float(shunt_resistor_value)), 0)))
				dropdown_values[parameter_type] = temp_list_of_current_values

		if front_end == 'TI':
			dropdown_values = base_ti_values

			if shunt_resistor_value == 0:
				return dropdown_values

			temp_list_of_current_values = []
			for i in dropdown_values["SC"]:
				temp_list_of_current_values.append(int(round((i * 22 + 44) / shunt_resistor_value + 0.5, 0)))
			dropdown_values["SC"] = temp_list_of_current_values

			temp_list_of_current_values = []
			for i in dropdown_values["OCD2"]:
				temp_list_of_current_values.append(int(round((i * 5.5 + 17) / shunt_resistor_value + 0.5, 0)))
			dropdown_values["OCD2"] = temp_list_of_current_values

		return dropdown_values

	def debug_print(self, param):
		if not self.is_frozen:
			print(param)
