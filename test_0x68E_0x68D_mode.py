from wstcan_protocol_tester.WSTProtocolTester import WSTProtocolTester, TestException

if __name__ == "__main__":
	print("Running All Tests")
	wst_protocol_tester = WSTProtocolTester()
	tests_to_run = [
		"test_0x68e_0x68d_mode"]
	results = wst_protocol_tester.run_tests(tests_to_run)

	print("\n\nTest Results: ")
	for test, result in results.items():
		indicator = "[FAIL]"
		if result:
			indicator = "[TRUE]"

		print("%s %s" % (test, indicator))
