from random import choice

from wstcan.WSTCan import WSTCan


#Delete this when proper localization is added.
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
		self.test_results = {}

		if init_battery and self.wstcom.isBatteryConnected(verbose=False):
			print(_("Battery Found!"))
			print(_("Model: %s" % self.wstcom.getModelString()))
			print(_("serial: %s" % self.wstcom.getSerial("hex")))
			print(_("Firmware version: %s" % self.wstcom.getFirmwareVersion()))
		else:
			print("No battery connected")

	def run_tests(self) -> dict:
		tests_to_run = ["test_custom_parameter_single_byte", "test_custom_parameter_short_int", "test_change_baudrates"]
		#  tests_to_run = ["test_change_baudrates"]

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

	def test_custom_parameter_short_int(self) -> bool:
		test_success = True
		for i in range(9, 21):
			random_int = choice(list(range(65535)))
			#print(_("Writing %s to parameter: %s") % (random_int, i))
			self.wstcom.write_custom_parameter_short_int(node_id=2, parameter_number=i, data=random_int, verbose=False)
			value = self.wstcom.read_custom_parameter_short_int(node_id=2, parameter_number=i)
			if value != random_int:
				test_success = False
				print(_("Wrong parameter value in parameter: %s. (%s is not %s) [FAIL]" % (i, value, random_int)))
			else:
				print(_("Extended Custom parameter %s is [OK]" % i))

		return test_success

	def test_custom_parameter_single_byte(self) -> bool:
		current_parameter_value = self.wstcom.readCustomParameter(2, 1)
		#  parms test syntax is, [wst_write, wst_read, errormsg, SPread]
		old_parameter_values_to_test = {
			1: [1, 1, "Error in CP1", 1],
			2: [2, 2, "Error in CP2", 2],
			3: [3, 3, "Error in CP3", 3],
			4: [4, 4, "Error in CP4", 4],
			5: [5, 5, "Error in CP5", 5],
			6: [120, 120, "Error in CP 6 in set heating voltage threshold", 2.4],
			7: [140, 140, "Error in CP 7 SOC 100% correction voltage threshold", 2.8],
			8: [255, 1, "Error in CP8 - expected to revert to 1 to show initialization was successful", 1]
		}
		test_failed = False
		for parameter_number, value_array in old_parameter_values_to_test.items():
			written_parm_value = value_array[0]
			expected_read_value = value_array[1]
			error_message = value_array[2]
			expected_read_value_sp = value_array[3]

			# print(_("Testing Custom Parameter %s. Writing %s") % (parameter_number, written_parm_value))
			old_value = self.wstcom.readCustomParameter(2, parameter_number)
			if old_value != 0 and False:
				test_failed = True
				print(_("Could not read custom parameter %s. [FAIL]" % parameter_number))
				continue

			self.wstcom.writeCustomParameter(2, parameter_number, written_parm_value)
			actual_read_value = self.wstcom.readCustomParameter(2, parameter_number)
			self.wstcom.emptyQueue()
			sp_custom_parameters = self.wstcom.readCustomParameters(verbose=True)
			actual_read_value_sp = self.wstcom.readCustomParameters()[parameter_number-1]
			if actual_read_value != expected_read_value:
				self.wstcom.writeCustomParameter(2, parameter_number, old_value)
				test_failed = True
				print(_("%s - Parameter %s is %s, but %s was expected when reading WST protocol[FAIL]" % (error_message, parameter_number, actual_read_value, expected_read_value)))
			elif actual_read_value_sp != expected_read_value_sp:
				self.wstcom.writeCustomParameter(2, parameter_number, old_value)
				test_failed = True
				print(_("%s - Parameter %s is %s, but %s was expected when reading SP protocol[FAIL]" % (error_message, parameter_number, actual_read_value, expected_read_value)))
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
