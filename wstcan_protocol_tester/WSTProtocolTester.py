import time
from random import choice

from spparser.SpParser import SpParser
from wstcan.WSTCan import WSTCan


# Delete this when proper localization is added.
def _(arg):
	return arg


class TestException(Exception):
	def __init__(self, message):
		self.message = message
		print("[FAIL]", message)
		super().__init__(self.message)


class WSTProtocolTester:
	def __init__(self, baudrate=250, init_battery=True):
		self.wstcom = WSTCan(debugging=False, baudrate=baudrate)
		self.wstcom.initializePCAN()
		self.test_results = {}

		if init_battery:
			self.wstcom.wakeBMS()
			if self.wstcom.isBatteryConnected(verbose=False):
				print(_("Battery Found!"))
				print(_("Model: %s" % self.wstcom.getModelString()))
				print(_("serial: %s" % self.wstcom.getSerial("hex")))
				print(_("Firmware version: %s" % self.wstcom.getFirmwareVersion()))
				print(_("CP4: %s" % self.wstcom.readCustomParameter(2, 4)))
			else:
				print("No battery connected")
				raise TestException("No battery connected or dongle not attached")

	def run_tests(self, tests_to_run="all") -> dict:
		if tests_to_run == "all":
			tests_to_run = [
				"test_custom_parameter_single_byte",
				"test_custom_parameter_short_int",
				"test_change_baudrates",
				"test_cp8_cell_diff",
				"test_can_charge_protocol",
				"test_0x68e_0x68d_mode"]

		print(_("\nRunning %s Tests:") % len(tests_to_run))

		for test_string_name in tests_to_run:
			print(_("Running test: %s") % test_string_name)
			function_name_as_string = "self.%s" % test_string_name
			try:
				self.test_results[test_string_name] = eval(function_name_as_string)()
			except TestException as e:
				self.test_results[test_string_name] = False
			print("")
		return self.test_results

	def test_0x68e_0x68d_mode(self) -> bool:
		test_success = True
		backup_cp4 = self.wstcom.read_custom_parameter_short_int(2, 4)
		try:
			print("Setting up CP4 to enalbe 0x68E and D mode.")
			self.wstcom.write_custom_parameter_short_int(2, 4, 64)
			print("Changing wstcom to use 0x68E and D mode.")
			self.wstcom.set_protocol2_ids(self.wstcom.protocol_2_bluebotics_ids[0], self.wstcom.protocol_2_bluebotics_ids[1])
			response = self.wstcom.getStatus(2)
			if response:
				print(_("0x68E and 0x68D function works [OK]"))
			else:
				print(_("0x68E and 0x68D function fails [FAIL]"))
				test_success = False

		except:
			print("Exception while test_0x68E_0x68D_mode")
			test_success = False
		finally:
			print("Reverting wstcom to use default ids")
			self.wstcom.set_protocol2_ids(self.wstcom.protocol_2_default_ids[0], self.wstcom.protocol_2_default_ids[1])
			self.wstcom.write_custom_parameter_short_int(2, 4, backup_cp4)
			return test_success

	def test_custom_parameter_short_int(self) -> bool:
		spparser = SpParser
		test_success = True
		all_status = self.wstcom.get_all_sp_status(skip=['log'])
		ov_limit = int(all_status['parsed_parameters']['parameter_group_1']['ov_threshold']['value'])
		ov_limit = round(ov_limit * 100)
		uv_limit = int(all_status['parsed_parameters']['parameter_group_1']['uv_threshold']['value'])
		uv_limit = round(uv_limit * 100)
		occ_limit = int(all_status['parsed_parameters']['parameter_group_1']['occ1_threshold']['value'])
		occ_limit = round(occ_limit * 10)
		cells_in_total = all_status['realtime_status']['parsed_voltage_status']['pack_cells_total']
		test_parameter_data = {
			"1": {"start": 1, "end": 255},
			"2": {"start": 1, "end": 255},
			"3": {"start": 1, "end": 255},
			"4": {"start": 1, "end": 8},
			"5": {"start": 1, "end": 65535},
			"6": {"start": 1, "end": 65535},
			"7": {"start": 1, "end": 65535},
			"9": {"start": 1, "end": 65535},
			"10": {"start": 1, "end": 65535},
			"11": {"start": 1, "end": 65535},
			"12": {"start": uv_limit, "end": ov_limit},  # This CP accepts only values between uv and ov.
			"13": {"start": 100, "end": occ_limit},  # This CP accepts only values below the occ threshold.
			"14": {"start": 1, "end": 65535},
			"15": {"start": 1, "end": 65535},
			"16": {"start": 1, "end": 65535},
			"17": {"start": 1, "end": 65535},
			"18": {"start": 1, "end": 65535},
			"19": {"start": 1, "end": 65535},
			"20": {"start": 1, "end": 65535},
			"21": {"start": 1, "end": 65535},
			"22": {"start": 1, "end": 65535},
			"23": {"start": 1, "end": 65535},
			"24": {"start": 1, "end": 65535},
			"25": {"start": 1, "end": 65535},
			"26": {"start": 1, "end": 65535},
			"27": {"start": 1, "end": 65535},
			"28": {"start": 1, "end": 65535},
			"29": {"start": 1, "end": 65535},
			"30": {"start": 1, "end": 65535}
		}
		print("cells_in_total: %s" % cells_in_total)

		for i in range(1, 31):
			if i in [1, 2, 3, 4, 8]:  # skip parameters only accessible by old method.
				continue

			start_int = test_parameter_data[str(i)]['start']
			end_int = test_parameter_data[str(i)]['end']
			random_int = choice(list(range(start_int, end_int)))

			old_value = self.wstcom.read_custom_parameter_short_int(node_id=2, parameter_number=i)
			for retries in range(5):
				if old_value:
					break
				old_value = self.wstcom.read_custom_parameter_short_int(node_id=2, parameter_number=i)

			self.wstcom.write_custom_parameter_short_int(node_id=2, parameter_number=i, data=random_int, verbose=False)
			value = self.wstcom.read_custom_parameter_short_int(node_id=2, parameter_number=i)
			for retries in range(5):
				if value:
					break
				value = self.wstcom.read_custom_parameter_short_int(node_id=2, parameter_number=i)


			self.wstcom.write_custom_parameter_short_int(node_id=2, parameter_number=i, data=old_value,
																									 verbose=False)  # reset to old value
			if value != random_int:
				test_success = False
				print(_("Wrong parameter value in parameter: %s. (%s is not %s) [FAIL]" % (i, value, random_int)))
			else:
				print(_("Extended Custom parameter %s is [OK]" % i))

		return test_success

	def test_custom_parameter_single_byte(self) -> bool:
		#  parms test syntax is, [wst_write, wst_read, errormsg, SPread]
		old_parameter_values_to_test = {
			1: [1, 1, "Error in CP1", 1],
			2: [2, 2, "Error in CP2", 2],
			3: [3, 3, "Error in CP3", 3],
			4: [4, 4, "Error in CP4", 4],
			# 5: [5, 5, "Error in CP5", 5], #5,6,7 only accessible by new short int method.
			# 6: [120, 120, "Error in CP 6 in set heating voltage threshold", 2.4], skipped in new versions
			# 7: [140, 140, "Error in CP 7 SOC 100% correction voltage threshold", 2.8], skipped in new versions.
			8: [255, 1, "Error in CP8 - expected to revert to 1 to show initialization was successful", 1]
		}
		test_failed = False
		for parameter_number, value_array in old_parameter_values_to_test.items():
			written_parm_value = value_array[0]
			expected_read_value = value_array[1]
			error_message = value_array[2]
			expected_read_value_sp = value_array[3]

			# print(_("Testing Custom Parameter %s. Writing %s") % (parameter_number, written_parm_value))
			self.wstcom.initializePCAN()
			old_value = self.wstcom.readCustomParameter(2, parameter_number)
			if old_value != 0 and False:
				test_failed = True
				print(_("Could not read custom parameter %s. [FAIL]" % parameter_number))
				continue

			self.wstcom.writeCustomParameter(2, parameter_number, written_parm_value)
			actual_read_value = self.wstcom.readCustomParameter(2, parameter_number)
			self.wstcom.emptyQueue()
			sp_custom_parameters = self.wstcom.readCustomParameters(verbose=True)
			actual_read_value_sp = self.wstcom.readCustomParameters()[parameter_number - 1]
			if actual_read_value != expected_read_value:
				self.wstcom.writeCustomParameter(2, parameter_number, old_value)
				test_failed = True
				print(_("%s - Parameter %s is %s, but %s was expected when reading WST protocol[FAIL]" % (
					error_message, parameter_number, actual_read_value, expected_read_value)))
			elif actual_read_value_sp != expected_read_value_sp:
				self.wstcom.writeCustomParameter(2, parameter_number, old_value)
				test_failed = True
				print(_("%s - Parameter %s is %s, but %s was expected when reading SP protocol[FAIL]" % (
					error_message, parameter_number, actual_read_value, expected_read_value)))
			else:
				print(_("Testing Custom Parameter %s. Writing %s [OK]") % (parameter_number, written_parm_value))
				self.wstcom.writeCustomParameter(2, parameter_number, old_value)

		if test_failed:
			raise TestException(_("A custom parameter test in 1-8 failed See messages above [FAIL]"))
		return True  # test was a success

	def test_change_baudrates(self) -> bool:
		test_success = True
		baudrates_to_test = [125, 250, 500, 1000]
		for baudrate in baudrates_to_test:
			try:

				self.wstcom.setBaudrate(250, verbose=False)
				self.wstcom.initialize()
				self.wstcom.change_bms_baudrate(baudrate, verbose=False)
				self.wstcom.setBaudrate(baudrate, verbose=False)
				self.wstcom.initialize()
				self.wstcom.emptyQueue()

				if self.wstcom.isBatteryConnected():
					print(_("Battery found on baudrate %d [OK]" % baudrate))
				else:
					print(_("Battery not found on baudrate %d [FAIL]" % baudrate))
					test_success = False
			except Exception as e:
				print(_("Exception - Battery not found on baudrate %d [FAIL]" % baudrate))
				test_success = False
			finally:
				self.wstcom.change_bms_baudrate(250, verbose=False)
				self.wstcom.uninitialize()
				self.wstcom.setBaudrate(250)
				self.wstcom.initialize()

		if not test_success:
			self.wstcom.setBaudrate(250)
			self.wstcom.initialize()
			raise TestException(_("Failed Baudrate test"))

		self.wstcom.uninitialize()
		self.wstcom.setBaudrate(250)
		self.wstcom.initialize()
		return test_success

	def test_cp8_cell_diff(self):
		self.wstcom.initialize()
		test_success = False
		original_cell_voltages = self.wstcom.getCellVoltages()
		test_cell_voltage = original_cell_voltages[0]
		original_test_cell_voltage = original_cell_voltages[0]
		print("original voltage is: ", original_test_cell_voltage)
		node_id = self.wstcom.getAvailableNodeIDs()[0]
		try:
			all_status = self.wstcom.get_all_sp_status(skip=['log'])
			# get_parameters
			spparser = SpParser()
			ov_limit = all_status['parsed_parameters']['parameter_group_1']['ov_threshold']['value']
			uv_limit = all_status['parsed_parameters']['parameter_group_1']['uv_threshold']['value']

			# reset CP8
			self.wstcom.writeCustomParameter(node_id, 8, 255)
			cp8 = self.wstcom.readCustomParameter(node_id, 8)
			assert cp8 == 1
			print("Uv limit: %s" % str(uv_limit))
			if test_cell_voltage > uv_limit + 0.4:
				test_cell_voltage = test_cell_voltage - 0.4
			else:
				test_cell_voltage = test_cell_voltage + 0.4
			print("testing with cell 1 at %s V" % test_cell_voltage)
			self.wstcom.write_cell_voltage_calibrations({1: test_cell_voltage})
			time.sleep(5)  # wait x seconds until CP8 brick kicks in
			cp8 = self.wstcom.readCustomParameter(node_id, 8)
			print("cp8 after calibration of voltages: %s" % cp8)
			if cp8 == 6:
				print("CP8 cell voltage diff. test successful [OK]")
				test_success = True
			else:
				print("CP8 cell voltage diff. test failed [FAIL]")
				test_success = False
		except:
			test_success = False
		finally:
			print("reverting cell 1 voltage to: %s" % original_test_cell_voltage)
			self.wstcom.write_cell_voltage_calibrations({1: original_test_cell_voltage})
			self.wstcom.writeCustomParameter(node_id, 8, 255)

		return test_success

	def test_can_charge_protocol(self):
		test_ok = True
		spparser = SpParser()
		# wake bms
		self.wstcom.wakeBMS()
		# get_all_status
		all_status = self.wstcom.get_all_sp_status(skip=['log'])
		ov_limit = all_status['parsed_parameters']['parameter_group_1']['ov_threshold']['value']
		uv_limit = all_status['parsed_parameters']['parameter_group_1']['uv_threshold']['value']
		cells_in_total = all_status['realtime_status']['parsed_voltage_status']['pack_cells_total']
		print("cells_in_total: %s" % cells_in_total)

		# setup parameters
		print("Setting up can charge parameters")
		receive_id = 0x7C0
		transmit_id = 0x7C1
		volt_per_cell = 4.1
		max_current = 10
		can_charge_params = {
			10: receive_id,  # Receive from charger ID
			11: transmit_id,  # Send to charger ID
			12: round(volt_per_cell * 100),  # 0.01V unit
			13: round(max_current * 10),  # 0.1A unit
			14: 1  # SP Can charge protocol
		}
		print("CAN charge parameters: %s" % can_charge_params)
		for param_number, value in can_charge_params.items():
			self.wstcom.write_custom_parameter_short_int(node_id=2, parameter_number=param_number, data=value, verbose=False)

		# check params
		for param_number, value in can_charge_params.items():
			print("param %s is %s" % (
			param_number, self.wstcom.read_custom_parameter_short_int(node_id=2, parameter_number=param_number)))

		# wait for BMS to be ready
		time.sleep(1)

		# trigger a CAN Charge reply from BMS
		self.wstcom.writeCANFrame(transmit_id, [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
		can_charge_frames = []
		for i in range(10):
			can_charge_frames.append(self.wstcom.readWSTFrame(expectedID=receive_id))

		ten_frames_received = True
		if len(can_charge_frames) != 10:
			ten_frames_received = False

		charge_frames_ok = True

		for frame in can_charge_frames:
			try:
				voltage_in_frame = spparser.read_two_bytes_big_endian_from_array(frame, 0)
				calculated_voltage = round(volt_per_cell * cells_in_total * 10)
				if voltage_in_frame != calculated_voltage:
					print("voltage_in_frame %s, is not expected %s * %s * 10 = %s [FAIL]" % (
					voltage_in_frame, volt_per_cell, cells_in_total, calculated_voltage))
					charge_frames_ok = False
					break

				current_in_frame = spparser.read_two_bytes_big_endian_from_array(frame, 2)
				if current_in_frame != max_current * 10:
					print("current_in_frame %s, is not expected %s * 10 = %s [FAIL]" % (
					current_in_frame, max_current, round(max_current * 10)))
					charge_frames_ok = False
					break

			except TypeError:
				print("TypeError")
				ten_frames_received = False
				break

		if ten_frames_received:
			print("We got 10 CAN charge frames for one trigger [OK]")
		else:
			print("We did not read 10 frames [FAIL]")

		if charge_frames_ok:
			print("Charge frames included ok data [OK]")
		else:
			print("Charge frames had malformed data. See specific errors above [FAIL]")

		test_ok = ten_frames_received and charge_frames_ok
		return False
