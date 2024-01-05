import serial
import serial.tools.list_ports
import winreg
import itertools
import datetime
import re
import random
import zlib
import json
from pathlib import Path
import os, sys

_COMPORT_REGESTRY_URI = 'HARDWARE\\DEVICEMAP\\SERIALCOMM'

class BarcodeReaderNotFoundException(Exception):
	pass

class WSTBarcodeSerialReader():	

	def print_debugging(self, s):
		if self._DEBUGGING:
			print(s)


	def __init__(self, port=False, grepString="honeywell", baudrate=9600, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, initialize=True, verbose=False):
		
		self.settings = {"baudrate": baudrate, "bytesize": bytesize, "parity": parity, "stopbits": stopbits}
		
		if initialize:
			if port:
				self.COMPort = port
			else:
				try:
					self.COMPort = self.getGreppedCOMPorts(grepString)[0][0]
				except:
					print("Could not find a suitable COMPORT. Did you connect the scanner and set it up?")
					raise BarcodeReaderNotFoundException()

		##Constants and regexps
		self._BMSBARCODE_REGEXP = r"^(.{10,30})[-/](\d{6})[-/](\d{10})$"
		self._BATTERYBARCODE_REGEXP = r"^(adl.*CB|lix\w{3,9}NX\w{2}|B\d{3}[F|N]\d{3}\w{4})(\d{6})(\d{6})$"
		self._CELLBARCODE_REGEXP = r"^(\w{3})(C)(\w)(.{8})(\w)(.{3})(\d{7})$"
		self._AC_BATTERYBARCODE_REGEXP = r"^(\d{6})([0-3][0-9][0-9])(\d{1})(\d{4})$"
		self._AC_BATTERY_MODEL_DICT = {
			"9902": "B012N014AC02",
			"9903": "B012N015AC01",
			"9905": "B012N015AC01",
			}
		self._YEAROFFSET = 22 #22 is 0	
		self._DEBUGGING = False
		self._VERBOSE = verbose

	def initialize(self, grepString="honeywell"):
		try:
			self.COMPort = self.getGreppedCOMPorts(grepString)[0][0]
		except:
			print("Could not find a suitable COMPORT. Did you connect the scanner and set it up?")
			raise BarcodeReaderNotFoundException()

	#returns only non BT ports of interest
	def getGreppedCOMPorts(self, grepString):
		try:
			allPorts = self.getAllCOMPorts()
			if len(allPorts) > 0:
				pass #we are good
			else: #if no ports, we report and return empty array
				print("no ports found")
				return []
			greppedPorts = []
			for portObject in allPorts:
				m = re.search(".*%s.*" % grepString, portObject[1])
				if m:
					print("%s: %s" % (portObject[0], portObject[1]))
					greppedPorts.append([portObject[0], portObject[1]])
			return greppedPorts
		except:
			print("ERROR - Could not find the barcode reader. Please coonect it qat make sure it has been setup correctly.")
			return[]


	
	def getAllCOMPorts(self):
			allPorts = self.enumerate_serial_ports()
			portsToReturn = []
			for portObject in allPorts:
				portsToReturn.append([portObject[1], portObject[0]])
			return portsToReturn

	def enumerate_serial_ports(self):
			""" Uses the Win32 registry to return an
					list of serial (COM) ports
					existing on this computer.
			"""
			listOfCOMPorts = []
			path = 'HARDWARE\\DEVICEMAP\\SERIALCOMM'
			try:
					key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
			except WindowsError:
					raise IterationError

			for i in itertools.count():
					try:
							val = winreg.EnumValue(key, i)
							listOfCOMPorts.append(list(val))
					except EnvironmentError:
							break
			return(listOfCOMPorts)
	
	def readBarcode(self, timeout=60, test=False):
		
		if test:
			return random.choice(["00008720919902", "ADL24LINMC-39AH-50A-CB180520009600", "WST21-TI04-003-A01-M4ST-002233/2205175001"])			

		ser = serial.Serial(self.COMPort, timeout=timeout, write_timeout=1, baudrate=self.settings["baudrate"], bytesize=self.settings["bytesize"], parity=self.settings["parity"], stopbits=self.settings["stopbits"])   # open serial port
		try:
			ser.flush()
			barcodeData = ser.readline()			
			if len(barcodeData)>0:
				return barcodeData[:-2].decode("ascii")
			else:
				return False
		except Exception as e:
			raise e
			raise "Could not read serial"
		finally:
			ser.close()

	def getBarcode(self, timeout=60, test=False):		
		try:
			barcodeData = self.readBarcode(timeout=timeout, test=test)			
			barcodeType = self.identifyBarcode(barcodeData)

			if barcodeType == "BATTERY":
				barcode_regexp_data = re.search(self._BATTERYBARCODE_REGEXP, barcodeData, re.IGNORECASE)
				model = barcode_regexp_data.group(1)
				date = barcode_regexp_data.group(2)
				serial = barcode_regexp_data.group(3)
				return [barcodeType, barcodeData, model, date, serial]

			elif barcodeType == 'ACBATTERY':
				barcode_regexp_data = re.search(self._AC_BATTERYBARCODE_REGEXP, barcodeData, re.IGNORECASE)				
				serial = barcode_regexp_data.group(1)
				
				days = int(barcode_regexp_data.group(2))
				year = int(barcode_regexp_data.group(3)) + 2020
				dateObject = datetime.datetime(year, 1, 1) + datetime.timedelta(days - 1)

				date = dateObject.strftime("%d%m%y")

				#use the real model name if exist in the dict else use the code identifier directly
				modelCode = barcode_regexp_data.group(4)
				if str(modelCode) in self._AC_BATTERY_MODEL_DICT:
					model = self._AC_BATTERY_MODEL_DICT[modelCode]
				else:
					model = modelCode
				return [barcodeType, barcodeData, model, date, serial]

			elif barcodeType == 'BMS':
				barcode_regexp_data = re.search(self._BMSBARCODE_REGEXP, barcodeData, re.IGNORECASE)
				return [barcodeType, barcodeData, barcode_regexp_data.group(1),barcode_regexp_data.group(2),barcode_regexp_data.group(3)]

			elif barcodeType == 'CELL':
				parsedCellBarcode = self.decodeCellBarcode(barcodeData)				
				return [barcodeType, barcodeData, parsedCellBarcode]

			else:       
				return [barcodeType, barcodeData]

		except Exception as e:			
			return False

	def identifyBarcode(self, barcodeData):
		if re.match(self._BMSBARCODE_REGEXP, barcodeData, re.IGNORECASE):
			return "BMS"
		elif re.match(self._BATTERYBARCODE_REGEXP, barcodeData, re.IGNORECASE):
			return "BATTERY"
		elif re.match(self._AC_BATTERYBARCODE_REGEXP, barcodeData, re.IGNORECASE):
			return "ACBATTERY"
		elif re.match(self._CELLBARCODE_REGEXP, barcodeData, re.IGNORECASE):
			return "CELL"
		else:
			return "UNKNOWN"

	def encodeBMSBarcode(self, BMSBarcodeArray):
		try:
			BMSBatch = BMSBarcodeArray[3] # 5 hex chars max
			BMSDate = BMSBarcodeArray[4][0:6] # 4 hex chars max
			BMSSerial = BMSBarcodeArray[4][6:10] #4 hex chars max
			
			#DELTE ME
			#BMSBatch = "999999"
			#BMSDate = "521231"
			#BMSSerial = "9999"

			self.print_debugging("%s, %s, %s" % (BMSBatch, BMSDate, BMSSerial))
			year = int(BMSDate[0:2])
			month = int(BMSDate[2:4])
			day = int(BMSDate[4:6])
			self.print_debugging("Year: %s" % year)
			self.print_debugging("Month: %s" % month)
			self.print_debugging("Day: %s" % day)

			yearToPack = year - self._YEAROFFSET #max length 5 bits
			monthToPack = month #max length  4
			dayToPack = day #max length 5 bits

			datePackedAsString = format(yearToPack, '05b') #notice that we use 7 char bin padding to get 5 binary numbers, because the 0b in front is also counted as pddaing chars by python
			datePackedAsString = datePackedAsString + format(monthToPack, '04b')
			datePackedAsString = datePackedAsString + format(dayToPack, '05b')
			self.print_debugging("bin year: %s" % format(yearToPack, '05b'))
			self.print_debugging("bin month: %s" % format(monthToPack, '04b'))
			self.print_debugging("bin day: %s" % format(dayToPack, '05b'))

			self.print_debugging("packed date: %s" % (datePackedAsString))
			datePackedAsInt = int(datePackedAsString, 2)
			datePackedAsHex = "{:04x}".format(datePackedAsInt)
			self.print_debugging("packed date as int: %s" % datePackedAsInt)
			self.print_debugging("packed date as hex: %s" % datePackedAsHex)
			self.print_debugging("packed date int as bin: %s" % bin(datePackedAsInt))

			BMSBatchPackedAsHex = format(int(BMSBatch), '05X')
			BMSSerialPackedAsHex = format(int(BMSSerial), '04X')
			BMSDatePackedAsHex = format(int(datePackedAsInt), '04X')

			
			packedBMSDataWithControlAsHex = BMSBatchPackedAsHex + BMSDatePackedAsHex + BMSSerialPackedAsHex 
			self.print_debugging("Packed Data: %s"  % packedBMSDataWithControlAsHex)	
		except:
			return False
			
		return packedBMSDataWithControlAsHex

	def decodeBMSBarcode(self, encodeddata):
		BMSBatchPackedAsHex = encodeddata[0:5]
		BMSDatePackedAsHex = encodeddata[5:9]
		BMSSerialPackedAsHex = encodeddata[9:13]

		BMSBatch = int(BMSBatchPackedAsHex, 16)
		BMSSerial = int(BMSSerialPackedAsHex, 16)
		BMSDateAsInt = int(BMSDatePackedAsHex, 16)

		self.print_debugging("BMSBatch: %s" % BMSBatch)
		self.print_debugging("BMSSerial: %s" % BMSSerial)
		self.print_debugging("BMSDateAsInt: %s" % BMSDateAsInt)
		BMSDateAsBinString = format(BMSDateAsInt, '014b')
		self.print_debugging("Date as bin %s " % BMSDateAsBinString)
		yearAsBin = BMSDateAsBinString[0:5]
		monthAsBin = BMSDateAsBinString[5:9]
		dayAsBin = BMSDateAsBinString[9:14]
		self.print_debugging("yearAsBin: %s" % yearAsBin)
		self.print_debugging("monthAsBin: %s" % monthAsBin)
		self.print_debugging("dayAsBin: %s" % dayAsBin)

		year = int(yearAsBin, 2) + self._YEAROFFSET
		month = int(monthAsBin, 2)
		day = int(dayAsBin, 2)
		yearAsString = format(year, "02d")
		monthAsString = format(month, "02d")
		dayAsString = format(day, "02d")
		dateString = yearAsString + monthAsString + dayAsString
		self.print_debugging("dateString: %s" % dateString)

		BMSBatchAsString = format(BMSBatch, "06d")
		BMSSerialAsString = format(BMSSerial, "04d")
		return [BMSBatchAsString, dateString, BMSSerialAsString]
		#return("Decoded: %s, %s, %s" % (BMSBatchAsString, dateString, BMSSerialAsString))

	def decodeCellBarcode(self, QRCode):
		decodedData = {}
		raw_data = {}

		try:
			cell_code_database_path = Path("cell_code_database.json")
			with open(cell_code_database_path) as cell_code_database_file:
			    cell_code_database = json.load(cell_code_database_file)
		except Exception as e:
			print(e)
			print("could not open the cell_code_database")
			sys.exit(1)

		vendor_code = QRCode[0:3]
		
		decode_settings = cell_code_database['Default'].copy() #set all default settings

		#override default settings if they are available
		if vendor_code in cell_code_database:
			decode_settings.update(cell_code_database[vendor_code])
			#print("decode_settings: %s" % decode_settings)
		else:
			print("Using default settings")

		#print(decode_settings['RegExp'])		
		regExGroups = re.search(decode_settings['RegExp'], QRCode, re.IGNORECASE)
		if regExGroups:
			if self._VERBOSE:
				print("Decoded cell")
		else:
			if self._VERBOSE:
				print("Could not decode QRCode")

		for index, groupname in enumerate(decode_settings['RegExpGroupNames'], start=1):
			raw_data[groupname] = regExGroups[index]		
				
		for raw_data_key, raw_data_value in raw_data.items():
			if raw_data_key in decode_settings:				
				try:
					if raw_data_value in decode_settings[raw_data_key]:						
						decodedData[raw_data_key] = [decode_settings[raw_data_key][raw_data_value], "Decoded"]
					else:						
						decodedData[raw_data_key] = [raw_data_value, "Raw"]
				except:
					
					decodedData[raw_data_key] = [raw_data_value, "Raw"]
			else:
				decodedData[raw_data_key] = [raw_data_value, "Raw"]


		#Apply special rules and re decode
		if "SpecialRules" in decode_settings:
			#print("special rules: %s" % decode_settings['SpecialRules'])
			for special_key, special_value in decode_settings['SpecialRules'].items():
				if special_key in decode_settings:
					#print("special key found")
					#print(decodedData[special_key][0])
					#print(special_value[decodedData[special_key][0]])
					if decodedData[special_key][0] in special_value:
						#print(decode_settings)
						decode_settings.update(special_value[decodedData[special_key][0]])
						#print(decode_settings)
						raw_data = {}
						decodedData = {} #redecode
						
						regExGroups = re.search(decode_settings['RegExp'], QRCode, re.IGNORECASE)
						if regExGroups:
							if self._VERBOSE:
								print("Decoded cell")
						else:
							if self._VERBOSE:
								print("Could not decode QRCode")

						for index, groupname in enumerate(decode_settings['RegExpGroupNames'], start=1):
							raw_data[groupname] = regExGroups[index]	

						for raw_data_key, raw_data_value in raw_data.items():
							if raw_data_key in decode_settings:				
								try:
									if raw_data_value in decode_settings[raw_data_key]:						
										decodedData[raw_data_key] = [decode_settings[raw_data_key][raw_data_value], "Decoded"]
									else:						
										decodedData[raw_data_key] = [raw_data_value, "Raw"]
								except:
									
									decodedData[raw_data_key] = [raw_data_value, "Raw"]
							else:
								decodedData[raw_data_key] = [raw_data_value, "Raw"]

		#add vendor name
		if "VendorName" in decode_settings:
			decodedData["VendorName"] = [decode_settings['VendorName'], "Decoded"]
		else:
			decodedData["VendorName"] = ["Unknown", "Raw"]

		#handle date decode
		raw_year = decodedData['Date'][0][0]
		raw_month = decodedData['Date'][0][1]
		raw_day = decodedData['Date'][0][2]		
		years_table = decode_settings['Years_table']
		months_table = decode_settings['Months_table']
		days_table = decode_settings['Days_table']

		if raw_year in years_table and raw_month in months_table and raw_day in days_table:
			decodedData['Date'] = [datetime.datetime(years_table[raw_year], months_table[raw_month], days_table[raw_day]), "Decoded"]

		return decodedData