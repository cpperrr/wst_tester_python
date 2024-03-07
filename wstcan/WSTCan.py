# SEE CHANGELOG FILE
import random
import string

# CANbus lib
from pcanbasic.PCANBasic import *  ## PCAN-Basic library import
from spparser.SpParser import SpParser

import time
from datetime import datetime
import re
import os
import sys

from pathlib import Path
import xlsxwriter

# Variables for use with pcanAPI
PCANBasic = PCANBasic()
PCANHANDLE = PCAN_USBBUS1
ZERO_8BYTE_FRAME = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
EMPTY_FRAME = []

_SP_MODEL_TO_WST_MODEL_NAME_TABLE = {

		'WST-TI07-002-A05-HD7S50A': 'BMS-050-024-CBAS02',
		'WST21-SW07-001-A01-HD7S50A': 'BMS-050-024-CBAS03',
		'WST21-SW07-001-A02-HD7S50A': 'BMS-050-024-CBAS03',
		'WST21-SW07-001-A04-HD7S50A': 'BMS-050-024-CBAS04',
		
		'WST-TI13-005-A02-13S80A': 'BMS-080-048-CBAS02',
		'WST-TI13-005-A02-13SA80': 'BMS-080-048-CBAS02',
		
		'N32-WST21-TI04-002-A01-HD4S6A': 'MS0400600621',
		
		'WST20-TI04-001-A01-HD4S120A': 'MS0412012011',
		
		'WST19-TI10-013-A01-HD7S25A': 'MS0702502511',
		'SPB19-TI10-013-A01-HD7S25A': 'MS0702502511',
		'WST18-TI15-005-A02-HD7S120A': 'MS0712012011',
		'WST22-SW15-002-A03-HD7S120A': 'MS0712012012',

		'WST18-TI15-005-A02-HD8S120A': 'MS0812012011',
		'WST18-TI15-005-A02-8S120A': 'MS0812012011',
		'WST22-SW15-002-A03-HD8S120A': 'MS0812012012',
		'WST22-SW15-002-A01-HD8S120A': 'MS0812012012',

		'WST19-TI13-025-A02-HD13S50A': 'MS1305005011',
		'WST20-TI15-001-A02-13S120A': 'MS1312012011',
		
		'WST18-TI15-005-A02-HD14S120A': 'MS1412012011',
		'WST20-TI15-001-A02-HD14S120A': 'MS1412012012',

		'WST22-SW15-001-A02-HD15S25A': 'MS1502502512',
		
		'N32RB-WST20-TI20-001-A03-HD16S1': 'MS1612012021',
		'N32G455-WST20-TI20-001-A03-HD16': 'MS1612012031',

		'N32G455-WST20-TI20-001-A03-HD18': 'MS1812012021',
}

_SHORTENED_MODEL_NAMES = {
		'ADL24LINMC-3': 'ADL24LINMC-39AH-50A-CB',
		'ADL24LINMC-39AH': 'ADL24LINMC-39AH-50A-CB',
		'ADL48LINMC-4': 'ADL48LINMC-41AH-CB',
		'ADL48LINMC-41AH': 'ADL48LINMC-41AH-CB'
}

_BMS_MODEL_PRODUCT_MODEL_CORRELATION = {
		'B024F120HG01': {
				'WST22-SW15-002-A03-HD8S120A': '-BMS2',
				'WST22-SW15-002-A01-HD8S120A': '-BMS2'

		},
		'B024F120HG02': {
				'WST22-SW15-002-A03-HD8S120A': '-BMS2',
				'WST22-SW15-002-A01-HD8S120A': '-BMS2'

		},
		'ADL24LINMC-39AH-50A-CB': {
				'WST-TI07-002-A05-HD7S50A': '-BMS2',
				'WST21-SW07-001-A01-HD7S50A': '-BMS3',
				'WST21-SW07-001-A02-HD7S50A': '-BMS3',
				'WST21-SW07-001-A04-HD7S50A': '-BMS4'
		},
		'B024N041HK01': {
				'WST-TI07-002-A05-HD7S50A': '-BMS2',
				'WST21-SW07-001-A01-HD7S50A': '-BMS3',
				'WST21-SW07-001-A02-HD7S50A': '-BMS3',
				'WST21-SW07-001-A04-HD7S50A': '-BMS4'
		},
		'ADL48LINMC-41AH-CB': {
				'WST-TI13-005-A02-13S80A': '-BMS2'
		},
		'B048F102FH02': {
				'N32G455-WST20-TI20-001-A03-HD16': '-BMS2'
		}
}

_POSSIBLESTATUSCODES = [
		# [byte, bit, [shortDesc, abbrivation]]
		[0, 0, ["Discharging", "DCHG"]],
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
		# these are special as they are used in conjuction with other temperature triggers
		[5, 5, ["Under Temperature", "U"]],  # also special

		[6, 0, ["Short Circuit", "SC"]],
		[6, 1, ["Discharge Over Current", "DOC"]],
		[6, 2, ["Charge Over Current", "COC"]],
		[6, 4, ["Ambient Over Temperature", "AOT"]],
		[6, 5, ["Ambient Under Temperature", "AUT"]],
]

class WSTCan:
		def __init__(self, debugging=False, baudrate=250):
				self.baudrate = None
				if os.path.isfile("baudrate.txt"):
					try:
						f = open("baudrate.txt", "r")
						baudrate_setting = f.read()
						if baudrate_setting == "500":
							baudrate = 500
						if baudrate_setting == "250":
							baudrate = 250
						if baudrate_setting == "125":
							baudrate = 125
					except:
						pass
				self.filters_ready = False
				self.debugging = debugging
				self.timeout = 1
				self.voltageStatusCommand = bytes.fromhex("EAD10104FF02F9F5")
				self.currentStatusCommand = bytes.fromhex("EAD10104FF03F8F5")
				self.powerStatusCommand = bytes.fromhex("EAD10104FF04FFF5")
				self.serialCommand = bytes.fromhex("EAD10104FF11EAF5")
				self.logCommand = bytes.fromhex("EAD1FF04FF08F3F5")
				self.shutdownCommand = bytes.fromhex("EAD1FF05FF1331D8F5")
				self.readCustomParametersCommand = bytes.fromhex("EAD10104FF28D3F5")
				self.readModelnumberCommand = bytes.fromhex("EAD10104FF30CBF5")
				self.readBMSModelnumberCommand = bytes.fromhex("EAD10104FF01FAF5")
				self.writeModelAndDateCommandPrefix = "EAD1FF%sFF12" #insert the length by doing %s string interpolation
				self.writeSerialNumberCommandPrefix = "EAD1FF%sFF10" #insert the lenght by doing %s string interpolation
				self.parametersReadCommands = [0x07, 0x0B, 0x0D, 0x70, 0x6E]
				self.fwVersionCommand = bytes.fromhex(
						"EB0101039093F5")  # version is 255 when BMS is in BOOT. Byte 5 of the reply is the version.
				self.getStatsAndLogCommand = bytes.fromhex(
						"EAD1FF04FF08F3F5")  # First two records are not log records, but stat data as seen in the top of the log history get tool in SP Software
				#add number of cells in next byte, then n, highbyte, lowbyte, (3 bytes per cell) with 0.1mv unit. see the docs
				self.calibrate_cell_voltages_command_start = [0xEA, 0xD1, 0x01, 0x1E, 0xFF, 0x0F, 0x02]
				self.get_raw_cell_voltages_command = bytes.fromhex("EAD10105FF0F00F5F5")
				self.setBaudrate(baudrate)
				self.type = "CAN"

		def intToHexString(self, intNumber):
			return "%02x" % intNumber

		# Create a excel serial style date from a python date.
		def excel_date(self, date):
			temp = datetime(1899, 12, 30)  # Note, not 31st Dec but 30th!
			delta = date - temp
			return float(delta.days) + (float(delta.seconds) / 86400)

		def toHex(self, int):
			return '{:02x}'.format(int)

		def arrayToHex(self, array):
			return list(map(self.toHex, array))

		def ctypeByteToArray(self, cbytes):
			normalArray = []
			for b in cbytes:
				normalArray.append(b)
			return normalArray

		# check if bit is set. smallest bit value is 0 and then incrementing.
		def isBitSet(self, byteToCheck, nthBit):
			if byteToCheck & (1 << (nthBit)):
				return True
			else:
				return False

		def calcXOR(self, array):
				xor = 0
				for b in array:
						xor = xor ^ b
				return xor

		def TranslateSPBMSModelToWSTNaming(self, SPBMSModelName):
				if SPBMSModelName in _SP_MODEL_TO_WST_MODEL_NAME_TABLE:
						return _SP_MODEL_TO_WST_MODEL_NAME_TABLE[SPBMSModelName]
				else:
						return SPBMSModelName

		#def isBitSet(self, byteToCheck, nthBit):
		#		return isBitSet(byteToCheck, nthBit)

		def setBaudrate(self, baudrate=250, verbose=False):
			baudrate_dict = {
				125: PCAN_BAUD_125K,
				250: PCAN_BAUD_250K,
				500: PCAN_BAUD_500K,
				1000: PCAN_BAUD_1M
			}
			assert baudrate in baudrate_dict.keys()

			self.baudrate = baudrate_dict[baudrate]
			if verbose:
				print("baudrate set to %s" % baudrate)


		def wakeBMS(self, ID=0x004, DATA=[0, 0, 0, 0, 0, 0, 0, 0], retries=2):
				for i in range(retries):
						print("Sending wake")
						PCANBasic.Uninitialize(PCANHANDLE)
						PCANBasic.Initialize(PCANHANDLE, self.baudrate)
						self.writeCANFrame(ID, DATA)

		def wakeBMS2(self, ID=0x001, DATA=[]):
				# print("Wake called")
				if not self.isBatteryConnected():
						for i in range(12):
								PCANBasic.Uninitialize(PCANHANDLE)
								PCANBasic.Initialize(PCANHANDLE, self.baudrate)
								self.writeCANFrame(ID, DATA)

		def init_filters(self, extra_can_filter=[]):
			#print("extra_can_filter set to %s" % extra_can_filter)
			#  The message filter is closed first to ensure the reception of the new range of IDs.
			#
			result = PCANBasic.SetValue(PCANHANDLE, PCAN_MESSAGE_FILTER, PCAN_FILTER_CLOSE)
			if result != PCAN_ERROR_OK:
				# An error occurred, get a text describing the error and show it
				#
				result = PCANBasic.GetErrorText(result)
				print(result[1])
			else:
				# The message filter is configured to receive the IDs 2,3,4 and 5 on the PCAN-USB, Channel 1
				#
				can_filters = [
					[1, 3],
					[0xD, 0xD],
					[0x7C0, 0x7C0]
				]
				if len(extra_can_filter) > 0:
					can_filters.append(extra_can_filter)
				for can_filter in can_filters:
					result = PCANBasic.FilterMessages(PCANHANDLE, can_filter[0], can_filter[1], PCAN_MODE_STANDARD)
					if result != PCAN_ERROR_OK:
						# An error occurred, get a text describing the error and show it
						#
						result = PCANBasic.GetErrorText(result)
						print(result[1])
					else:
						# print("Filter successfully configured.")
						pass


		def uninitialize(self):
			self.uninitializePCAN()

		def initialize(self, baudrate="Deprecated - use setBaudrate method"):
			return self.initializePCAN()

		def uninitializePCAN(self):
			self.filters_ready = False
			PCANBasic.Uninitialize(PCANHANDLE)

		def initializePCAN(self, baudrate="Deprecated - use setBaudrate method"):
			self.debugging = False
			# time.sleep(0.05)
			# print("initializing")
			if self.debugging:
					print("initializing")
			result = PCANBasic.GetStatus(PCANHANDLE)
			if result == PCAN_ERROR_OK:
					if self.debugging:
							print("Get status: OK")
					return True
			else:
					if self.debugging:
							print("Get status: NOT OK, reinitializing")
					PCANBasic.Uninitialize(PCANHANDLE)
					result = PCANBasic.Initialize(PCANHANDLE, self.baudrate)
					if result != PCAN_ERROR_OK:
						# An error occurred, get a text describing the error and show it
						#
						result = PCANBasic.GetErrorText(result)
						if self.debugging:
							print("debug message after failed reinit: %s " % str(result[1]))
						return False
					else:
						# self.wakeBMS()
						if not self.filters_ready:
							self.init_filters()
							self.filters_ready = True
						return True

		def getStatusCodeDescAbbrArray(self):
				returnArray = []
				CurrentStatusPayload = self.getCurrentStatus()
				for codeToCheck in _POSSIBLESTATUSCODES:
						byteLocation = codeToCheck[0]
						bitLocation = codeToCheck[1]
						DescAndAbbr = codeToCheck[2]
						byteToCheck = CurrentStatusPayload[byteLocation]
						if isBitSet(byteToCheck, bitLocation):
								returnArray.append(DescAndAbbr)

				# sanitize over and under temp charge discharge current.
				if ["Charge Temperature", "CT"] in returnArray:
						if ["High Temperature", "O"] in returnArray:
								returnArray.append(["Charge Over Temperature", "COT"])
						if ["Under Temperature", "U"] in returnArray:
								returnArray.append(["Charge Under Temperature", "CUT"])

				if ["Discharge Temperature", "DT"] in returnArray:
						if ["High Temperature", "O"] in returnArray:
								returnArray.append(["Discharge Over Temperature", "DOT"])
						if ["Under Temperature", "U"] in returnArray:
								returnArray.append(["Discharge Under Temperature", "DUT"])

				if ["Mos Temperature", "MT"] in returnArray:
						if ["High Temperature", "O"] in returnArray:
								returnArray.append(["MOS Over Temperature", "MOT"])
						if ["Under Temperature", "U"] in returnArray:
								returnArray.append(["MOS Under Temperature", "MUT"])

				# clean out all the "half status code. we have what we want"
				if ["Charge Temperature", "CT"] in returnArray:
						returnArray.remove(["Charge Temperature", "CT"])
				if ["Discharge Temperature", "DT"] in returnArray:
						returnArray.remove(["Discharge Temperature", "DT"])
				if ["Mos Temperature", "MT"] in returnArray:
						returnArray.remove(["Mos Temperature", "MT"])
				if ["High Temperature", "O"] in returnArray:
						returnArray.remove(["High Temperature", "O"])
				if ["Under Temperature", "U"] in returnArray:
						returnArray.remove(["Under Temperature", "U"])

				return returnArray

		def getSerials(self):
				self.initializePCAN()
				time.sleep(0.010)
				getSerialsCommand = [0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
				getSerialsID = 0x00E
				self.writeCANFrame(getSerialsID, getSerialsCommand)
				time.sleep(0.005)
				serials = []
				nodes_found = 0
				# we must spend at least 1000ms looking forserials, because the BMS has 1000ms to report back.
				t_end = time.time() + 2
				while time.time() < t_end:
						# do whatever you do
						frame = self.readWSTFrame(timeout=1, sleepTime=0.00, verbose=False, fast=True)
						if frame and frame[0] == 0x02:
								nodes_found += 1
								payload = frame
								serial = ''
								length = payload[1]
								for i in range(2, 8):
										serial = serial + "{:02x}".format(payload[i])
										serial = serial[:length]
								serials.append(serial)
				# time.sleep(0.01)
				self.uninitializePCAN()
				outputSerials = []
				for serial in serials:
						if not serial in outputSerials:
								outputSerials.append(serial)
				return outputSerials

		def sendSPPackage(self, dataArray):
				
				#Construct the frames from the data
				dataArray = list(dataArray) #convert to normal list
				frames = []
				while len(dataArray) > 0:
						#pop first 8 bytes into frames and remove from data
						frame = dataArray[:8]
						#pad the frame if not 8 bytes
						if len(frame) < 8:
								for i in range(8-len(frame)):
										frame.append(0)
						frames.append(frame)
						del dataArray[:8]
				

				self.writeCANFrame(0x001, ZERO_8BYTE_FRAME)
				time.sleep(0.001)
				
				for frame in frames:            
						self.writeCANFrame(0x002, frame)
						time.sleep(0.003)
				
				self.writeCANFrame(0x003, ZERO_8BYTE_FRAME)
				time.sleep(0.3)
		

		def sendSPCommand(self, command):
				self.writeCANFrame(0x001, ZERO_8BYTE_FRAME)
				time.sleep(0.005)
				
				self.writeCANFrame(0x002, command)
				time.sleep(0.005)
				self.writeCANFrame(0x003, ZERO_8BYTE_FRAME)
				time.sleep(0.005)

		def queryBMS(self, command, timeout=1, verbose=False, dataOnly=True, expectedPackages=1):
				""" Send a command and receives a response from a BMS SP Style
				:arguments
					command:
						The command payload to send to BMS
				:raises connectionError:
					If the port could not be opened
				:returns:
						A bytearray with the response
		"""
				self.initializePCAN()
				self.emptyQueue() #Make sure the receive buffer is empty before trying new communication.
				if len(command) > 8:
					self.sendSPPackage(command)
				else:
					self.sendSPCommand(command)
				responseArray = []
				for i in range(expectedPackages):
						response = self.readPackage(dataOnly=False)

						commandByteList = list(command)
						if response and len(response) > 6 and commandByteList[:3] == response[:3]:

								if dataOnly:
										response = response[6:response[3] + 2]
										responseArray.append(response)
								else:
										responseArray.append(response)
						else:
								if self.debugging:
										print("query bms response: %s " % response)
				# print("commandByteList: %s" % commandByteList)
				self.emptyQueue()
				self.uninitializePCAN()
				if len(responseArray) > 0:

						if expectedPackages == 1:
								return responseArray[0]
						else:
								return responseArray
				else:
						return False

		def queryBMSProtocol1(self, ID, payload=None, timeout=1, verbose=False, dataOnly=True):
				""" Send a command and receives a response from a BMS SP Style
				:arguments
					command:
						The command payload to send to BMS
				:raises connectionError:
					If the port could not be opened
				:returns:
						A bytearray with the response
		"""
				self.initializePCAN()
				self.init_filters(extra_can_filter=[0x000, 0x7FF])
				self.sendWSTCommand(ID, payload)
				response = self.readWSTFrame(ID)
				self.emptyQueue()
				self.uninitializePCAN()
				return response

		def sendWSTCommand(self, ID, payload=None, format="hexstring"):
				if payload:
						try:
								if format == "hexstring":
									data = bytes.fromhex(payload)
								elif format == "intarray":
									data = payload
								else:
									data = bytes.fromhex(payload)
								self.writeCANFrame(ID, data)
						except:
								print("could not understand the payload hexstring")
				else:
						try:
								if ID > 0 and ID < 0x7FF:
										validatedID = ID
						except:
								print("Could not parse ID")
						self.writeCANFrame(ID, bytes.fromhex(""))

		def writeCANFrame(self, ID, payload):
				# Check contents of message and do whatever is needed. As a
				# simple test, print it (in real life, you would
				# suitably update the GUI's display in a richer fashion).
				CANMsg = TPCANMsg()
				CANMsg.ID = ID
				CANMsg.LEN = len(payload)
				CANMsg.MSGTYPE = PCAN_MESSAGE_STANDARD

				# We get so much data as the Len of the message
				for i in range(CANMsg.LEN):
						CANMsg.DATA[i] = payload[i]
				result = PCANBasic.Write(PCANHANDLE, CANMsg)
				if result != PCAN_ERROR_OK:
						# print("error in canwrite")
						# print(PCANBasic.GetErrorText(result))
						PCANBasic.Uninitialize(PCANHANDLE)
						PCANBasic.Initialize(PCANHANDLE, self.baudrate)
						PCANBasic.Write(PCANHANDLE, CANMsg)

		def readWSTFrame(self, expectedID=0x00D, timeout=10, sleepTime=0.050, verbose=False, fast=False):
				self.init_filters(extra_can_filter=[expectedID, expectedID])
				incomming_data_bundle = []
				while timeout > 0:
						timeout -= 1
						readResult = PCANBasic.Read(PCANHANDLE)
						if verbose:
								print(PCANBasic.GetErrorText(readResult[0]))
						# print(readResult[0])
						if readResult[0] == PCAN_ERROR_OK:
								if not fast:
										timeout += 1
								# Process the received message
								#
								if readResult[1].ID == expectedID:
										for i in range(8):
												incomming_data_bundle.append(readResult[1].DATA[i])
										return incomming_data_bundle
						elif readResult[0] == PCAN_ERROR_QRCVEMPTY:
								if not fast:
										time.sleep(0.01)
								if self.debugging:
										print("empty queue - skipping cycle")
						time.sleep(sleepTime)

		def readPackage(self, retries=50, dataOnly=True, offset_start=0, offset_end=0):
				self.initializePCAN()
				debugging = False
				incomming_data_bundle = []
				rcv001 = False
				rcv002 = False
				while retries > 0:
						retries -= 1
						readResult = PCANBasic.Read(PCANHANDLE)
						if readResult[0] == PCAN_ERROR_OK:
								retries += 1
								# Process the received message
								#
								if readResult[1].ID == 0x001:
										rcv001 = True
										if self.debugging:
												print("")
										# print("001 - %s" % arrayToHex(ctypeByteToArray(readResult[1].DATA)))
										pass
								elif (readResult[1].ID == 0x002) and rcv001:
										rcv002 = True
										if self.debugging:
												pass
										# print("002 - %s" % arrayToHex(ctypeByteToArray(readResult[1].DATA)))
										for i in range(8):
												incomming_data_bundle.append(readResult[1].DATA[i])
								elif (readResult[1].ID == 0x003) and rcv002:
										if self.debugging:
												pass
										# print("003 - %s" % arrayToHex(ctypeByteToArray(readResult[1].DATA)))
										# print("")
										self.initializePCAN()
										if dataOnly:
												data = incomming_data_bundle[6 + offset_start:incomming_data_bundle[3] + 2 + offset_end]
												return (data)
										else:
												return incomming_data_bundle

						elif readResult[0] == PCAN_ERROR_QRCVEMPTY:
								time.sleep(0.005)
								if debugging:
										print("empty queue - skipping cycle")
						else:
								if debugging:
										print("readpackage error: " + str(PCANBasic.GetErrorText(readResult[0], 9)[1]))
								time.sleep(0.05)

				# if we get beyond the while loop, we are out of time, and the package was not read correctly.
				if self.debugging:
						print("Read Package retries")
				self.initializePCAN()
				return False

		def emptyQueue(self, verbose=False):
				PCANBasic.Reset(PCANHANDLE)
				while self.readFrame():
						if self.debugging or verbose:
								print("emptyQueue cleaning frame")

		def readFrame(self):
				readResult = PCANBasic.Read(PCANHANDLE)
				if readResult[0] == PCAN_ERROR_OK:
						return readResult[1]
				else:
						return False

		def getVoltageStatus(self):
				response = self.queryBMS(self.voltageStatusCommand)
				return response

		def getCellVoltages(self, protocol="SP"):
			if protocol == "SP":
				voltageStatus = self.getVoltageStatus()
				#print(voltageStatus)
				cellVoltages = []
				cellsCount = voltageStatus[0]
				cellVoltagesStartByte = 3
				cellVoltageByteArray = voltageStatus[3:3+cellsCount*2]				
				#print("cells: %s" % cellsCount)
				#print("cellVoltageArray: %s" % cellVoltageByteArray)
				for i in range(cellsCount):
					cellVoltagemV = cellVoltageByteArray[i*2]*256+cellVoltageByteArray[i*2+1]
					cellVoltageV = cellVoltagemV / 1000
					cellVoltages.append(cellVoltageV)
				return(cellVoltages)
			else:
				return False

		def getAvarageCellVoltage(self, protocol="SP"):
			if protocol=="SP":
				cellVoltagesArray = self.getCellVoltages()
				avgCellVoltage = sum(cellVoltagesArray)/len(cellVoltagesArray)
				return avgCellVoltage
			else:
				return False

		def getPackVoltage(self, protocol="SP"):
			if protocol=="SP":
				cellVoltagesArray = self.getCellVoltages()
				packVoltage = sum(cellVoltagesArray)
				return packVoltage
			else:
				return False

		def getCurrentStatus(self):
				response = self.queryBMS(self.currentStatusCommand)
				return response

		def getPowerStatus(self):
				response = self.queryBMS(self.powerStatusCommand)
				return response

		def getBMSModelString(self, dataFormat="ascii", verbose=False, retries=10, spnaming=False):
				self.initializePCAN()

				# special case for old 7s50a bms

				model = self.getModelString(noFilter=True)
				try:
						serialnumber = int(self.getSerial())

						if model == "ADL24LINMC-39AH-50A-CB" and serialnumber < 12967:
								return "BMS-050-024-CBAS01"

						# special case for old 13s80a bms
						if model == "ADL48LINMC-41AH-CB" and serialnumber < 1190:
								return "BMS-080-048-CBAS01"
				except:
						pass

				if spnaming:
						return self.getBMSModelStringRecursiveFunction(dataFormat=dataFormat, verbose=verbose, retries=retries)
				else:
						return self.TranslateSPBMSModelToWSTNaming(self.getBMSModelStringRecursiveFunction(dataFormat=dataFormat, verbose=verbose, retries=retries))
				#
				# we need more special cases for old bms here!!!
				#

				self.uninitializePCAN()

		def getBMSModelStringRecursiveFunction(self, dataFormat="ascii", verbose=False, retries=5):
				if retries == 0:
						return False

				response = self.queryBMS(self.readBMSModelnumberCommand)
				if response:
						BMSModelStringLenght = response[0]
						if dataFormat == "bytes":
								return list(response)
						else:  # default to ascii
								ascii_string = bytes(response[1:1 + BMSModelStringLenght]).decode("ascii")
								ascii_string_stripped_of_whitespace = re.sub(r"[\n\t\s]*", "", ascii_string)
								return ascii_string_stripped_of_whitespace
				else:
						return self.getBMSModelStringRecursiveFunction(dataFormat=dataFormat, verbose=verbose, retries=retries - 1)

		def getBMSSerialNumber(self, retries=5):
			if retries < 1:
				print("getBMSSerialNumber timeout")
				return False
			
			modelFieldString = self.getModelField()
			if modelFieldString:
				modelFieldStringArray = modelFieldString.split("!")

				# if not, we check for length. If 26 chars, then new way is present and we do another split        
				if len(modelFieldString) == 25:
					return modelFieldString[12:25]
					
				# if a ! was found we should have two elements in the array.
				if len(modelFieldStringArray) != 2:            
					return False
				
				BMSSerialNumber = modelFieldStringArray[1]
				return BMSSerialNumber

			return self.getBMSSerialNumber(retries=retries - 1) #return recursive functioncall to leverage retries

		def getModelString(self, dataFormat="ascii", verbose=False, retries=5, noFilter=False):
				if retries == 0:
						return False
				modelFieldString = self.getModelField(dataFormat=dataFormat)
				if modelFieldString:
						if len(modelFieldString) == 25:            
								modelFromBMS = modelFieldString[:12]
						else:
								modelFromBMS = modelFieldString.split("!")[0]
						# check for shortened model names. Was shortened becaouse of field length limit in the modelfield and we need to also include the BMS serial number
						if modelFromBMS in _SHORTENED_MODEL_NAMES:
								modelToReturn = _SHORTENED_MODEL_NAMES[modelFromBMS]
						else:
								modelToReturn = modelFromBMS

						# return this without additional filtering, if set in paramters
						if noFilter:
								return modelToReturn

						# add model suffix on old models with new bms
						BMSModelString = self.getBMSModelString(spnaming=True)
						if BMSModelString:
								if modelToReturn in _BMS_MODEL_PRODUCT_MODEL_CORRELATION:
										_BMS_MODEL_PRODUCT_MODEL_CORRELATION_FOR_SPECIFIC_MODEL = _BMS_MODEL_PRODUCT_MODEL_CORRELATION[
												modelToReturn]
										if BMSModelString in _BMS_MODEL_PRODUCT_MODEL_CORRELATION_FOR_SPECIFIC_MODEL:
												modelToReturn = modelToReturn + _BMS_MODEL_PRODUCT_MODEL_CORRELATION_FOR_SPECIFIC_MODEL[
														BMSModelString]

						return modelToReturn
				else:
						return self.getModelString(dataFormat=dataFormat, verbose=verbose, retries=retries - 1)

		#datebytearray [YY,MM,DD]
		def writeDateAndModelField(self, dateByteArray, modelString):
				#0002  8  EA D1 FF 18 FF 12 10 61 
				#0002  8  62 63 64 65 66 31 32 33 
				#0002  8  34 35 36 37 38 39 30 06 
				#0002  8  05 01 E1 F5 00 00 00 00 
				
				if len(modelString) > 26:
						raise Exception("Model string exceed 26 chars!")
				if dateByteArray[0]<15 or dateByteArray[0]>40:
						raise Exception("Year must be 41 > year > 14")

				package = []
				package.append(len(modelString))
				package = package + list( bytes(modelString, 'ascii') )
				package.append(dateByteArray[0]-15) #year is offset so year 2015 is 0 and 2016 is 1
				package.append(dateByteArray[1]-1) #month is offset so january is 0 feb 1
				package.append(dateByteArray[2]-1) #days is ofset so the 1. is 0 and the 2. is 1

				lengthAsHexString = '{:02X}'.format(len(package)+4)
				package = list(bytes.fromhex(self.writeModelAndDateCommandPrefix % lengthAsHexString)) + package
				package.append(self.calcXOR(package[3:]))
				package.append(0xF5)
				#print(arrayToHex(package))
				self.sendSPPackage(package)
				self.emptyQueue()

		def writeSerialNumber(self, serialNumberAsInt):
				if serialNumberAsInt < 1 or serialNumberAsInt > 999999:
						raise Exception("Serial number must be in range 0-999999")

				paddedSerialString = "{:06d}".format(serialNumberAsInt)        
								
				package = []
				package.append(len(paddedSerialString))
				package = package + list( bytes(paddedSerialString, 'ascii') )        

				lengthAsHexString = '{:02X}'.format(len(package)+4)
				package = list(bytes.fromhex(self.writeSerialNumberCommandPrefix % lengthAsHexString)) + package
				package.append(self.calcXOR(package[3:]))
				package.append(0xF5)
				self.sendSPPackage(package)
				self.emptyQueue()


		# reads the SP model field containing battery model and bms serial number on newer bms
		def getModelField(self, dataFormat="ascii"):				
				response = self.queryBMS(self.readModelnumberCommand)        
				try:
						if response:  # Handle the modern case were we actually can retrieve the model string like this.
								modelStringLenght = response[0]
								if dataFormat == "ascii":
										return bytes(response[1:1 + modelStringLenght]).decode("ascii")
								elif dataFormat == "bytes":
										return list(response)
								else:  # default to ascii
										return response[0:0 + modelStringLenght].decode("ascii")

						else:  # attempt the old style as seen on ADL24 and properly adl48
								response = self.queryBMS(self.serialCommand, expectedPackages=2)                
								if response and len(response) == 2 and response[
										1]:  # we expect two frames and both must have data (not False)
										modelStringLenght = response[1][0]
										if dataFormat == "ascii":
												return bytes(response[1][1:1 + modelStringLenght]).decode("ascii")
										elif dataFormat == "bytes":
												return list(response[1])
				except:
						return False
				self.uninitializePCAN()

		def getProductionDate(self):				
				response = self.queryBMS(self.readModelnumberCommand)
				try:
					if response:  # Handle the modern case were we actually can retrieve the model string like this.
							modelStringLenght = response[0]
							date_time_array = response[1 + modelStringLenght:1 + modelStringLenght + 3]  # get the 3 bytes for date
							year = date_time_array[0] + 2015
							month = date_time_array[1] + 1
							day = date_time_array[2] + 1
							date_time_str = "%s-%s-%s" % (year, month, day)
							date_time_obj = datetime.strptime(date_time_str, '%Y-%m-%d')
							self.uninitializePCAN()
							return date_time_obj
					else:  # attempt the old style as seen on ADL24 and properly adl48
							response = self.queryBMS(self.serialCommand, expectedPackages=2)
							if response and len(response) == 2:  # we expect two frames
									modelStringLenght = response[1][0]
									date_time_array = response[1][1 + modelStringLenght:1 + modelStringLenght + 3]  # get the 3 bytes for date
									if len(date_time_array) < 3:
										self.uninitializePCAN()
										return False
									year = date_time_array[0] + 2015
									month = date_time_array[1] + 1
									day = date_time_array[2] + 1
									date_time_str = "%s-%s-%s" % (year, month, day)
									date_time_obj = datetime.strptime(date_time_str, '%Y-%m-%d')
									return date_time_obj
				except IndexError:
					return False
				self.uninitializePCAN()

		def readCustomParameters(self, verbose=False, asArray=True):
			return self.getCustomParameters(verbose=verbose, asArray=asArray)

		def getCustomParameters(self, verbose=False, asArray=True):
				self.initialize()
				self.emptyQueue()
				response = self.queryBMS(self.readCustomParametersCommand)
				self.uninitialize()
				if (type(response) is list) and (len(response) >= 8):
						# transform to array if required
						if asArray:
								tempArray = []
								# first we get the signed as it was unsigned
								for i in range(8):
										signedWord = response[i * 2] * 256 + response[i * 2 + 1]
										# convert two twos compliment sigend int
										if signedWord > 32767:
												signedWord = (-1) * (65535 - signedWord)
										tempArray.append(float(signedWord) / 100)
								response = tempArray
				return response

		def getSerial(self, returnType="hex"):
				"""
		Ge the serial from the BMS
		:arguments
			returnType:
				int - returns list of byte integers interperted as hex - This is default
				string - returns serial as a string
		:returns
			depending on the returntype:
				int array of each byte where the serial is interperted as a string of 2 hex char bytes
				string where the serial is an ascii string.
		"""
				response = self.queryBMS(self.serialCommand)
				if self.debugging:
						print("Serial Response data: %s" % response)
				try:
						if response[0] == 255 or response[0] == 0:
								raise Exception("No Serial Number set in BMS")
				except:
						return False
				serialCharBytes = []
				for i in range(response[0]):
						serialCharBytes.append(response[i + 1])

				hexString = ""
				for i in range(int(len(serialCharBytes) / 2)):
						hexString += chr(serialCharBytes[0 + 2 * i]) + chr(serialCharBytes[1 + 2 * i])

				if returnType == "hex":
						return hexString

				# Default return
				return serialCharBytes

		def testLog(self):
				logArray = []
				self.initializePCAN()
				self.sendSPCommand(self.logCommand)
				time.sleep(0.050)
				logFrame = self.readPackage(dataOnly=False)
				while len(logFrame) > 8:
						if logFrame[5] == 0x08:
								print("raw logframe(%s): %s" % (len(logFrame), str(logFrame)))
								print("raw logframe(%s): %s" % (len(logFrame[6:39]), str(logFrame[6:39])))
								logArray.append(logFrame)
								logArray.append(logFrame[6:39])
								self.emptyQueue()
								self.uninitializePCAN()
								return logArray
						logFrame = self.readPackage(dataOnly=False)
				self.emptyQueue()
				self.uninitializePCAN()
				return logArray

		def getLog(self, asarray=False, includeStats=False, dataOnly=True):
				logArray = []
				self.initializePCAN()
				self.sendSPCommand(self.logCommand)
				time.sleep(0.050)
				logFrame = self.readPackage(dataOnly=False)
				while len(logFrame) > 8:
						if (logFrame[5] == 0x09) and (includeStats == False):
								logFrame = self.readPackage(dataOnly=False)  # read next frame
								continue  # skip frame if we are not including stats
						if dataOnly:
								logArray.append(logFrame[6:39])
						else:
								logArray.append(logFrame)
						logFrame = self.readPackage(dataOnly=False)
				self.emptyQueue()
				self.uninitializePCAN()
				return logArray

		def getRawLogStats(self):
				logStats = []
				self.initializePCAN()
				self.sendSPCommand(self.logCommand)
				time.sleep(0.050)
				logFrame = self.readPackage(dataOnly=False)
				logStats.append(logFrame)
				logFrame = self.readPackage(dataOnly=False)
				logStats.append(logFrame)
				self.emptyQueue()
				for i in range(5):
					time.sleep(0.05)
					self.emptyQueue()
				self.uninitializePCAN()
				return logStats

		def getFirmwareVersion(self, verbose=False, bootmode=False):
				if bootmode:
					try:
							self.initializePCAN()
							self.sendSPCommand(self.fwVersionCommand)
							time.sleep(0.050)
							response = self.readPackage(dataOnly=True, offset_start=-1, offset_end=0)
							self.uninitializePCAN()
							return response[0]
					except:
							return False
				else:
					try:
							self.initializePCAN()
							response = self.getCurrentStatus()
							if verbose:
								print(response)
							self.uninitializePCAN()
							if len(response) > 15 and response[13+response[7]] == 0:
								return 300 #testing firmware
							return response[13+response[7]] #firmware version byte is offset by temp probe count in byte 7.
					except:
							return False

		def isBatteryConnected(self, verbose=False, bootmode=False):
				self.initializePCAN()
				try:
						firmwareVersion = self.getFirmwareVersion(bootmode=bootmode, verbose=verbose)
						if verbose:
							print(firmwareVersion)
						if int(firmwareVersion) > 1:
								return True
						else:
								return False
				except Exception:
						return False
				self.uninitializePCAN()

		def isBatteryInBOOT(self, verbose=False):
				self.initializePCAN()
				try:
						if self.isBatteryConnected():
								firmwareVersion = self.getFirmwareVersion()
								if firmwareVersion == 255:
										return True
								else:
										return False
						elif self.isBatteryConnected(bootmode=True):
								firmwareVersion = self.getFirmwareVersion(bootmode=True)
								if firmwareVersion == 255:
										return True
								else:
										return False
						else:
								print("no battery found")
				except Exception as e:
						print("Error in boot check")
						raise (e)
				finally:
						self.uninitializePCAN()

		# Returns an array with two objects [serials, ids]
		# each object has key values where key is the serials in the serials object and values are the corresponding ids. ITs reversed in the ids object.
		def scanNodeIDs(self, verbose=False):
				self.initializePCAN()
				time.sleep(1)
				NODE_IDsToFind = len(self.getSerials())
				if verbose:
						print("Looking for %s ids" % NODE_IDsToFind)
				nodesFound = 0
				serials = {}
				ids = {}
				time.sleep(1)
				for i in range(2, 256):  # set back to 256
						serial = self.getSerialP2(i, retries=5, sleepTime=0.010, verbose=False, initialized=True)
						if serial:
								nodesFound += 1
								if verbose:
										print("serial %s has id %s" % (serial, i))
								serials[serial] = i
								ids[i] = serial
								if nodesFound == NODE_IDsToFind:
										return [serials, ids]
				return False
				self.uninitializePCAN()

		def getAvailableNodeIDs(self):			
			retry_counter = 5
			nodes = None			
			while retry_counter > 0:
				retry_counter = retry_counter - 1
				try:
					nodes = self.scanNodeIDs()
					if nodes:
						break
				except:
					pass
			nodelist = []
			for nodeid, serial in nodes[1].items():
				nodelist.append(nodeid)
			return(nodelist)

		def readStatus(self, NODE_ID, retries=100, sleepTime=0.005, verbose=False, initialized=False):
				if not initialized:
						self.initializePCAN()
				# request status from NODE_ID
				NODE_ID = int(NODE_ID)
				self.emptyQueue()
				self.writeCANFrame(0x00e, [0x01, int(NODE_ID), 0x00, 0x00, 0x00, 0x00, 0x00, 0x01])
				time.sleep(0.005)
				data_bundle_incomplete = True

				data_array = []
				data_length = 0
				total_frames = 0
				while data_bundle_incomplete:
						# print("NODE: %s - Retry %s " % (NODE_ID, retries))
						readResult = PCANBasic.Read(PCAN_USBBUS1)
						if readResult[0] != PCAN_ERROR_OK:
								# print(PCANBasic.GetErrorText(readResult[0]))
								pass
						if readResult[0] == PCAN_ERROR_OK:
								retries += 1
								# Process the received message
								#
								if (readResult[1].ID == 0x00D
												and readResult[1].DATA[0] == int(NODE_ID)
												and readResult[1].DATA[1] == 0
												and readResult[1].DATA[2] == 1
												and readResult[1].DATA[7] == 0):
										# we add one here, because SP made mistake in implementation. Will be fixed in next revision.
										total_frames = readResult[1].DATA[3]
										incomming_data_bundle = []

								if (readResult[1].DATA[0] == NODE_ID
												and readResult[1].DATA[7] == 1):
										for i in range(2, 7):
												data_array.append(readResult[1].DATA[i])

								if (readResult[1].DATA[0] == NODE_ID
												and readResult[1].DATA[7] > 1):
										for i in range(1, 7):
												data_array.append(readResult[1].DATA[i])

								if (readResult[1].DATA[0] == NODE_ID
												and readResult[1].DATA[7] == total_frames - 1):  #
										data_bundle_incomplete = False
										return (data_array)
										frame_number = 1
										while len(data_array) >= 8:
												temp_array = []
												for i in range(0, 8):
														temp_array.append(data_array.pop(0))
												frame_number += 1

						time.sleep(sleepTime)
						retries -= 1
						if retries < 1:
								raise Exception("ERROR 102: Could not read status data P2")
				if not initialized:
						self.uninitializePCAN()

		def getSerialP2(self, NODE_ID, verbose=False, retries=10, sleepTime=0.005, initialized=False):
				if verbose:
						print("get status for node: %s" % NODE_ID)
				try:
						statusData = self.readStatus(NODE_ID, verbose=verbose, retries=retries, sleepTime=sleepTime,
																				 initialized=initialized)
						# Serial number
						serial = ''
						SERIAL_BEGIN_BYTE = 80
						length = statusData[SERIAL_BEGIN_BYTE]
						for i in range(1, 6):
								serial = serial + "{:02x}".format(statusData[SERIAL_BEGIN_BYTE + i])
								serial = serial[:length]
						return int(serial)
				except Exception as e:
						if verbose:
								# raise e
								print(e)
								print("Could not get serial")
						return False
		def get_status_as_dict(self, NODE_ID=2):
			status_array = self.getStatus(NODE_ID=NODE_ID)
			status_dict = {}
			for data_point in status_array:
				status_dict[data_point[0].lower().replace(" ", "_")] = data_point[1::]
			return status_dict


		def getStatus(self, NODE_ID, verbose=False, retries=10, sleepTime=0.005):
				# print("get status for node: " + NODE_ID)
				try:
						statusData = self.readStatus(NODE_ID, verbose=verbose, retries=retries, sleepTime=sleepTime)
				except Exception as e:
						if verbose:
								print("Could not get status")
						return False
				statusList = []

				# Serial number
				serial = ""
				SERIAL_BEGIN_BYTE = 80
				FIRST_SERIAL_BYTE = 81
				for i in range(3):
						serial = serial + "{:02x}".format(statusData[FIRST_SERIAL_BYTE + i])
				statusList.append(['Serial', serial, ''])

				# FW version
				statusList.append(['Firmware Version', statusData[11] / 10, ''])
				statusList.append(['Pack Voltage', (statusData[0] * 256 + statusData[1]) / 10, "V"])
				statusList.append(['Charge Current', (statusData[2] * 256 + statusData[3]) / 10, 'A'])
				statusList.append(['Discharge Current', (statusData[4] * 256 + statusData[5]) / 10, 'A'])
				statusList.append(['SoC', statusData[6], '%'])
				# we only show a rem charge if there is actual charge current - else it shows bogus value.
				if (statusData[2] * 256 + statusData[3]) > 0:
						statusList.append(['Estimated Charge Time Left', (statusData[7]) / 10, 'H'])
				else:
						statusList.append(['Estimated Charge Time Left', "Not Charging", ''])

				# We calculate the resolution 1mAh or 10mAh
				fullCapacity = statusData[12] * 256 + statusData[13]
				remainingCapacity = statusData[8] * 256 + statusData[9]
				capacityResolution = None
				if fullCapacity > 65000:
						capacityResolution = 10
				else:
						capacityResolution = 1
				# we devide by 1000 to get Ah
				statusList.append(['Full Capacity', (fullCapacity / 1), 'Ah'])
				statusList.append(['Remaining Capacity', (remainingCapacity / 1), 'Ah'])
				statusList.append(['SoH', statusData[10], '%'])

				statusList.append(['Cycles', (statusData[14] * 256 + statusData[15]), '  - @80% DoD Cycles'])

				##Status codes
				status_index = [[0x0000, 'Idle'],
												[0x0001, 'Discharge'],
												[0x0002, 'Charge'],
												[0x0004, 'OV'],
												[0x0008, 'UV'],
												[0x0010, 'COC'],
												[0x0020, 'DOC'],
												[0x0040, 'DOT'],
												[0x0080, 'DUT'],
												[0x0200, 'SC'],
												[0x0400, 'COT'],
												[0x0800, 'CUT']]
				status_code_int = statusData[16] * 256 + statusData[17]
				flags = []

				for status_index_entry in reversed(
								status_index):  # loop over all the possible status flags and assign as needed. Please notice that we can have multiple flags in one code!
						if status_code_int >= status_index_entry[0]:
								flags.append(status_index_entry[1])
								if status_code_int == 0x0001 or status_code_int == 0x0002:  # if we are charging or discharging, then we cannot also be idle, so we break after this flag is added.
										break
								status_code_int = - status_index_entry[0]

				statusList.append(['Status Flags', flags, ''])

				##Temperatures
				temp = statusData[18]
				if temp > 127:
						temp = (256 - temp) * (-1)
				statusList.append(['Cell 1', temp, 'C'])

				temp = statusData[19]
				unit = 'C'
				if temp == 0:
						unit = "C - Please notice that not all BMS's have this probe. It will show 0C in case it is not present!"
				if temp > 127:
						temp = (256 - temp) * (-1)
				statusList.append(['Cell 2', statusData[19], unit])

				temp = statusData[22]
				unit = 'C'
				if temp == 0:
						unit = "C - Please notice that not all BMS's have this probe. It will show 0C in case it is not present!"
				if temp > 127:
						temp = (256 - temp) * (-1)
				statusList.append(['Mosfet', statusData[22], unit])

				temp = statusData[23]
				unit = 'C'
				if temp == 0:
						unit = "C - Please notice that not all BMS's have this probe. It will show 0C in case it is not present!"
				if temp > 127:
						temp = (256 - temp) * (-1)
				statusList.append(['Ambient', statusData[23], unit])

				# cells
				cellVoltage = statusData[24] * 256 + statusData[25]
				cellNumber = 0
				while cellVoltage > 0:
						if cellNumber > 100:
								break
						cellNumber += 1
						cell_data = ['Cell ' + str(cellNumber) + " Voltage: ", cellVoltage, "mV"]
						statusList.append(cell_data)
						cellVoltage = statusData[24 + cellNumber * 2] * 256 + statusData[25 + cellNumber * 2]

				# CP8
				cp8_parser = {0: 'CP8 OFF',
											1: 'CP8 ON',
											2: 'OV Cycle',
											3: 'OV Lifetime',
											4: 'UV Cycle',
											5: 'UV Lifetime',
											6: '300mV Cell Diff',
											7: '<2.65V/2.35V',
											8: '>4.35V/3.8V',
											9: 'SC Cycle',
											10: 'SC Lifetime',
											11: 'DOC Cycle',
											12: 'DOC Lifetime',
											13: 'COC Cycle',
											14: 'COC Lifetime',
											15: 'DOT Cycle',
											16: 'DOT Lifetime',
											17: 'DUT Cycle',
											18: 'DUT Lifetime',
											19: 'COT Cycle',
											20: 'COT Lifetime',
											21: 'CUT Cycle',
											22: 'CUT Lifetime'}

				#Add the cascade CP8 values to the parser
				cp8_parser_enhanced = {}
				for CP8Value, CP8Text in cp8_parser.items():
					if CP8Value in [0,1]: #skip the off and on values
						next
					cp8_parser_enhanced[CP8Value] = CP8Text
					cp8_parser_enhanced[CP8Value+100] = "Cascaded CP8: %s" % CP8Text

				cp8_parser = cp8_parser_enhanced #reassign the new parser to the old variable

				CP8ByteValue = statusData[72] #get the CP8 value from the data
				if CP8ByteValue in cp8_parser:
					CPtext = cp8_parser[CP8ByteValue]
				else:
					CPtext = "Unkown CP8 Value: %s" % CP8ByteValue	

				statusList.append(['CP8 Flags', CPtext, ''])

				# Alarms bitflags
				alarm_index = [[0x00, 'Unbalanced'],
											 [0x02, 'Cell or Pack OV'],
											 [0x04, 'Cell or Pack UV'],
											 [0x08, 'Charge Current High'],
											 [0x10, 'Discharge Current High'],
											 [0x20, 'Any over temperature'],
											 [0x40, 'Any under temperature'],
											 [0x80, 'Over temperature charge']]
				alarm_flags = []
				alarm_code_int = statusData[75]
				for alarm_index_entry in reversed(alarm_index):
						if alarm_code_int >= alarm_index_entry[0]:
								alarm_flags.append(alarm_index_entry[1])
								alarm_code_int = - alarm_index_entry[0]

				statusList.append(['Alarm Flags', alarm_flags, ''])
				# heating system
				if statusData[79] == 1:
						heating_string = 'Enabled'
				else:
						heating_string = 'Disabled'

				if statusData[78] == 1:
						heating_status = 'True'
				else:
						heating_status = 'False'

				statusList.append(['Heating System', heating_string, ''])
				statusList.append(['Currently Heating', heating_status, ''])
				return statusList

		def sendCommand(self, command, dataOnly=True, printCommand=False):
				checksum = '{:02x}'.format(0x04 ^ 0xFF ^ command)
				hexCommand = '{:02x}'.format(command)
				hexString = "EAD10104FF" + hexCommand + checksum + "F5"
				if printCommand:
						print("TX 001: 00 00 00 00 00 00 00 00")
						print("TX 002: %s" % hexString)
						print("TX 003: 00 00 00 00 00 00 00 00")
				bytePackage = bytes.fromhex("EAD10104FF" + hexCommand + checksum + "F5")
				response = self.queryBMS(bytePackage, dataOnly=dataOnly)
				return response

		def TestGetLogProtocol2(self, node_id):

				if node_id < 2 or 255 < node_id:
						raise Exception("node_id not in range")

				self.emptyQueue()
				self.writeCANFrame(0x00E, [4, node_id, 0, 0, 0, 0, 1, 1])
				log = []
				logframe = []
				readFrame = self.readWSTFrame()
				while readFrame:
						if readFrame[7] == 0:
								# print("7 was 0")
								logframe.append(readFrame[5])
						if readFrame[7] == 1:
								# print("7 was 1")
								logframe = logframe + readFrame[2:7]
						if readFrame[7] in [2, 3, 4, 5]:
								# print("7 was 2-5")
								logframe = logframe + readFrame[1:7]
						if readFrame[7] == 6:
								# print("7 was 6")
								logframe = logframe + readFrame[1:4]
								log.append(logframe)
								logframe = []
						readFrame = self.readWSTFrame()  # read next frame
				return log

		def ParseAndSaveProtocol2LogToFile(self, log_array, filename, subdir="."):
				filePath = Path(subdir, str(filename) + ".xlsx")
				print(filePath)
				workbook = xlsxwriter.Workbook(filePath)
				worksheet = workbook.add_worksheet()
				worksheet.set_column('B:B', 16)
				##headings to use in excel
				entry_data_headings = ['Entry #', 'Date', 'Pack V', 'Cell min (V)', 'Cell Max (V)', 'Current (A)',
															 'Temp (deg-C)', 'SoC (%)', 'Rem Cap (mAh)', 'Cycles #', 'State 1', 'State 2', 'State 3',
															 'CHG/DHG ', 'Event', 'SoH (%)']
				##date format
				# date_format_str = 'YY-mm-dd hh:mm:ss'
				date_format = "%Y-%m-%d %H:%M:%S"

				date_format_excel = workbook.add_format({'num_format': 'yy-mm-dd hh:mm:ss'})

				##use like this:
				## number = 41333.5
				##worksheet.write('A5', number, format5)       # 28/02/13 12:00

				# var holds the number of non log entries, so we dont get empty rows in the sheet.
				offset = 0

				# write data headings
				for i in range(len(entry_data_headings)):
						worksheet.write(0, i, entry_data_headings[i])

				# loop over each record in log
				for e, record in enumerate(log_array):
						# check we acutally have a log entry
						##array for holding the computaed and formated log values
						# entry_data_formated_array = []
						# Log number
						worksheet.write(e + 1 - offset, 0, record[0])

						##DATE
						##We need to handle currupted input. If the date is not conforming, then strptime will fail.
						##In this case we notify user by writing the string "currupted string" in the date field
						date_time_str = "20" + self.intToHexString(record[1]) + "-" + self.intToHexString(record[2]) + "-" + self.intToHexString(
								record[3]) + " " + self.intToHexString(record[4]) + ":" + self.intToHexString(record[5]) + ":" + self.intToHexString(
								record[6])
						try:
								date_time = datetime.strptime(date_time_str, date_format)
								worksheet.write(e + 1 - offset, 1, excel_date(date_time), date_format_excel)
						except ValueError:
								date_time = "corrupted data"
								worksheet.write(e + 1 - offset, 1, date_time)

						# date_time = datetime(record[7]),record[8]),record[9]),record[10]),record[11]),record[12]))

						##Pack Voltage
						voltage = float(record[7] * 256 + record[8]) / 100
						worksheet.write(e + 1 - offset, 2, voltage)

						##Cell voltage
						cell_min = float(record[9] * 256 + record[10]) / 1000
						cell_max = float(record[11] * 256 + record[12]) / 1000
						worksheet.write(e + 1 - offset, 3, cell_min)
						worksheet.write(e + 1 - offset, 4, cell_max)

						##Current
						# first we get the signed as it was unsigned
						wrong_signed = record[13] * 256 + record[14]
						# convert two twos compliment sigend int
						if wrong_signed > 32767:
								wrong_signed = (65535 - wrong_signed) * (-1)

						worksheet.write(e + 1 - offset, 5, float(wrong_signed) / 100)

						##temp
						temp = record[15] - 40
						worksheet.write(e + 1 - offset, 6, temp)

						##Soc
						soc = record[17]
						worksheet.write(e + 1 - offset, 7, soc)

						##Remaining Capacity
						rem_cap = record[18] * 256 * 256 * 256 + record[19] * 256 * 256 + record[20] * 256 + record[21]
						worksheet.write(e + 1 - offset, 8, rem_cap)

						##Cyclecount
						cycles = record[22] * 256 + record[23]
						worksheet.write(e + 1 - offset, 9, cycles)

						##States 1,2 & 3

						##Status code
						state_1_index = {'00': '',
														 '01': 'Pack UV Recovery',
														 '02': 'Cell UV Recovery',
														 '04': 'Pack OV Recovery',
														 '08': 'Cell OV Recovery',
														 '10': 'Pack UV',
														 '20': 'Cell UV',
														 '40': 'Pack OV',
														 '80': 'Cell OV',
														 'a0': 'Cell OV/Cell UV (Failure)', }

						state_2_index = {'00': '',
														 '04': 'SC Recovery',
														 '08': 'DOC Recovery',
														 '10': 'COC Recovery',
														 '20': 'SC',
														 '40': 'DOC',
														 '80': 'COC'}

						state_3_index = {'00': '',
														 '10': 'DOT Recovery',
														 '20': 'COT Recovery',
														 '40': 'DOT',
														 '80': 'COT'}

						state_1_code = self.intToHexString(record[24])
						state_2_code = self.intToHexString(record[25])
						state_3_code = self.intToHexString(record[26])

						# write the human readable version by 'translating' from the indexs
						if state_1_code in state_1_index:
								worksheet.write(e + 1 - offset, 10, state_1_index[state_1_code])
						else:
								worksheet.write(e + 1 - offset, 10, "0x" + state_1_code)

						if state_2_code in state_2_index:
								worksheet.write(e + 1 - offset, 11, state_2_index[state_2_code])
						else:
								worksheet.write(e + 1 - offset, 11, "0x" + state_2_code)

						if state_3_code in state_3_index:
								worksheet.write(e + 1 - offset, 12, state_3_index[state_3_code])
						else:
								worksheet.write(e + 1 - offset, 12, "0x" + state_3_code)

						##Charge / Discharge flag
						charge_flag_index = {'20': '0x20 - standby',
																 '40': '0x40 - discharge',
																 '80': '0x80 - charge'}
						charge_flag = self.intToHexString(record[27])
						if charge_flag in charge_flag_index:
								worksheet.write(e + 1 - offset, 13, charge_flag_index[charge_flag])
						else:
								worksheet.write(e + 1 - offset, 13, "0x" + charge_flag)

						# Event
						event_flag_index = {'03': '0x03 - UV Shutdown',
																'04': '0x04 - Power Up',
																'06': '0x06 - Full charge cap update',
																'07': '0x07 - Cycle count update',
																'08': '0x08 - D-FET OFF',
																'09': '0x09 - C-FET OFF',
																'0a': '0x0A - D-FET ON',
																'0b': '0x0B - C-FET ON',
																'0c': '0x0C - Parameter Updated',
																'0d': '0x0D - Charge-Current Calibration',
																'0e': '0x0E - Discharge-Current Calibration',
																'0f': '0x0F - Voltage Calibration',
																'20': '0x20 - Voltage Failure',
																'23': '0x23 - Charging Start',
																'24': '0x24 - Charging Stop',
																'27': '0x27 - Discharge Begin',
																'28': '0x28 - Discharge Stop',
																'32': '0x32 - Heating start',
																'33': '0x33 - Heating stop',
																'34': '0x34 - 15s current',
																'35': '0x35 - Low voltage',
																'36': '0x36 - Low Voltage Released',
																'37': '0x37 - Cell Difference',
																'38': '0x38 - Cell Difference Release',
																'39': '0x39 - Misuse protection initialized'}

						event_flag = self.intToHexString(record[28])
						if event_flag in event_flag_index:
								worksheet.write(e + 1 - offset, 14, event_flag_index[event_flag])
						else:
								worksheet.write(e + 1 - offset, 14, "ID: 0x" + event_flag)

						##State of Health
						SOH = record[29]
						worksheet.write(e + 1 - offset, 15, SOH)

				workbook.close()

		def readParameters(self, dataOnly=True, returnHex=False):
			parameters = {}
			for command in self.parametersReadCommands:
				if returnHex:
					parameters[self.intToHex(command)] = self.intArrayToHex(self.sendCommand(command=command, dataOnly=dataOnly))
				else:
					parameters[command] = self.sendCommand(command=command, dataOnly=dataOnly)
			return parameters

		def readCustomParameter(self, node_id, parameterNumber):
				# print("reading parameter %i from node_id: %i" % (parameterNumber, node_id))
				# BD is for parameters
				# 0x04 0x10 is the read command
				payload = [0xBD, node_id, 0x00, parameterNumber, 0x00, 0x00, 0x04, 0x10]
				self.writeCANFrame(0x00E, payload)
				time.sleep(0.3)
				response = self.readWSTFrame()
				if response:
						data = response
						# print("Response: %s" % data)
						return data[7]
				else:
						# print("No response")
						return False

		def writeCustomParameter(self, node_id, parameterNumber, data):
				# print("writing %i, to parameter #%i" % (data, parameterNumber))
				payloadWithOutChecksum = [0xBD, int(node_id), 0x00, int(parameterNumber), int(data), 0x04, 0x40]
				# print("payload no checksum %s" % payloadWithOutChecksum)
				# calculate checksum and append
				checksum = 0
				for byte in payloadWithOutChecksum:
						checksum = checksum ^ int(byte)
				# insert checksum to position 5
				payload = payloadWithOutChecksum
				payload.insert(5, checksum)
				# print("payload to write: %s" % payload)
				# write the frame
				self.writeCANFrame(0x00E, payload)
				time.sleep(0.3)
				response = self.readWSTFrame()
				data = response
				if response:
						# print("Response: %s" % data)
						# print("Parameter #%i is now: %i" % (parameterNumber, data[7]))
						return (data[7])
				else:
						# print("No Response")
						return False
						
		def recalibrateSOC(self, node_id):
				payloadWithOutChecksum = [0xCC, int(node_id), 0x00, 0x00, 0x00, 0x01, 0x04]
				# print("payload no checksum %s" % payloadWithOutChecksum)
				# calculate checksum and append
				checksum = 0
				for byte in payloadWithOutChecksum:
						checksum = checksum ^ int(byte)
				payload = payloadWithOutChecksum
				payload.insert(5, checksum)
				# print("payload to write: %s" % payload)
				# write the frame
				self.writeCANFrame(0x00E, payload)

		def disableFirmwareUpgrades(self, node_id):
			payloadWithOutChecksum = [0xF5, int(node_id), 0x00, 0x00, 0x00, 0x20, 0x10]
			# print("payload no checksum %s" % payloadWithOutChecksum)
			# calculate checksum and append
			checksum = 0
			for byte in payloadWithOutChecksum:
					checksum = checksum ^ int(byte)
			payload = payloadWithOutChecksum
			payload.insert(5, checksum)
			# print("payload to write: %s" % payload)
			# write the frame
			self.writeCANFrame(0x00E, payload)
			time.sleep(0.1)
			response = self.readWSTFrame()
			if response:
				return True
			else:
				return False

		def enableFirmwareUpgrades(self, node_id):
			payloadWithOutChecksum = [0xF5, int(node_id), 0x00, 0x00, 0x00, 0x40, 0x01]
			# print("payload no checksum %s" % payloadWithOutChecksum)
			# calculate checksum and append
			checksum = 0
			for byte in payloadWithOutChecksum:
					checksum = checksum ^ int(byte)
			payload = payloadWithOutChecksum
			payload.insert(5, checksum)
			# print("payload to write: %s" % payload)
			# write the frame
			self.writeCANFrame(0x00E, payload)
			time.sleep(0.1)
			response = self.readWSTFrame()
			if response:
				return True
			else:
				return False	

		def enableAllFirmwareUpgrades(self):
			nodes = self.getAvailableNodeIDs()
			print("found these batteries %s" % nodes)
			for node_id in nodes:
				if self.enableFirmwareUpgrades(node_id):
					print("Enabled firmware upgrade in node_id: %s" % node_id)
				else:
					print("could not enable firmware upgrade in node_id: %s" % node_id)

		def disableAllFirmwareUpgrades(self):
			nodes = self.getAvailableNodeIDs()
			print("found these batteries %s" % nodes)
			for node_id in nodes:
				if self.disableFirmwareUpgrades(node_id):
					print("Disabled firmware upgrade in node_id: %s" % node_id)
				else:
					print("could not disable firmware upgrade in node_id: %s" % node_id)

		def shutdownBatteries(self):
				for i in range(10):
						self.sendSPPackage(self.shutdownCommand)

		def read_custom_parameter_short_int(self, node_id, parameter_number):
			assert 30 >= parameter_number >= 1
			# print("reading parameter %i from node_id: %i" % (parameterNumber, node_id))
			# BD is for parameters
			# 0x04 0x10 is the read command
			payload = [0xBD, node_id, 0x00, parameter_number, 0x00, 0x00, 0x04, 0x20]
			self.writeCANFrame(0x00E, payload)
			time.sleep(0.5)
			response = self.readWSTFrame()
			if response:
				# print("Response: %s" % data)
				parser = SpParser()
				result = parser.read_two_bytes_big_endian_from_array([response[5], response[7]], 0, True)
				return result
			else:
				# print("No response")
				return False

		def write_custom_parameter_short_int(self, node_id, parameter_number, data, verbose=False):
			try:
				assert 0 <= data <= 65535
			except:
				raise Exception("Cannot write a value not within 0<=VALUE<=65535")
			assert 30 >= parameter_number >= 1

			data_bytes = data.to_bytes(2, 'big')
			payloadWithOutChecksum = [0xBD, int(node_id), int(data_bytes[0]), int(parameter_number), int(data_bytes[1]), 0x04, 0x80]
			#print("payload no checksum %s" % payloadWithOutChecksum)
			# calculate checksum and append
			checksum = 0
			for byte in payloadWithOutChecksum:
				checksum = checksum ^ int(byte)
			# insert checksum to position 5
			payload = payloadWithOutChecksum
			payload.insert(5, checksum)
			if verbose:
				print("payload to write: %s" % self.arrayToHex(payload))
			# write the frame
			self.writeCANFrame(0x00E, payload)
			time.sleep(0.3)
			response = self.readWSTFrame()
			if response:
				if verbose:
					print("Response: %s" % self.arrayToHex(response))
				# print("Parameter #%i is now: %i" % (parameterNumber, data[7]))
				parser = SpParser()
				result = parser.read_two_bytes_big_endian_from_array([response[5], response[7]], 0, True)
				return result
			else:
				# print("No Response")
				return False

		def get_parsed_sp_status(self, status_type="realtime"):
			_sp_parser = SpParser()
			
			if status_type == "realtime":
				voltage_status_data_array = self.getVoltageStatus()			
				current_status_data_array = self.getCurrentStatus()			
				power_status_data_array = self.getPowerStatus()				
				
				status_data = {
					'parsed_voltage_status': _sp_parser.parse_voltage_status(voltage_status_data_array),
					'parsed_current_status': _sp_parser.parse_current_status(current_status_data_array),
					'parsed_power_status': _sp_parser.parse_power_status(power_status_data_array)
					}
			
			if status_type == "log":
				#get the status data packs. 
				log_data_array = self.getLog(includeStats=True, dataOnly=True)			
				log_statistics_data_array = log_data_array[:2] # first two records holds the statistics
				log_data_array = log_data_array[2:] # remaining records are the actual log.
				
				status_data = {
					"parsed_log_statistics": _sp_parser.parse_log_statistics(log_statistics_data_array),
					"parsed_log": _sp_parser.parse_log(log_data_array)					
					}

			if status_type == "parameters":
				voltage_status_data_array = self.getVoltageStatus()			
				current_status_data_array = self.getCurrentStatus()			
				power_status_data_array = self.getPowerStatus()				
				
				status_data = {
					'parsed_voltage_status': _sp_parser.parse_voltage_status(voltage_status_data_array),
					'parsed_current_status': _sp_parser.parse_current_status(current_status_data_array),
					'parsed_power_status': _sp_parser.parse_power_status(power_status_data_array)
					}
				parameter_data = self.readParameters()				
				parameter_data['custom_parameters'] = self.getCustomParameters()
				
				status_data = _sp_parser.parse_sp_parameters(parameter_data, status_data, bms_model=self.getBMSModelString(spnaming=True))


			return status_data
		

		def get_all_sp_status(self, skip=[]):
			#parse the status data and save in all status
			all_status = {}
			if not 'log' in skip:
				all_status['log'] = self.get_parsed_sp_status(status_type="log")
			all_status['realtime_status'] = self.get_parsed_sp_status(status_type="realtime")
			all_status['basic_info'] = self.get_battery_description()
			all_status['parsed_parameters'] = self.get_parsed_sp_status(status_type="parameters")
			return all_status

		def get_battery_description(self):
			_sp_parser = SpParser()
			firmware_version = self.getFirmwareVersion()
			battery_model = self.getModelString()
			serial_number = self.getSerial("hex") or "NA"

			bms_model = self.getBMSModelString(spnaming=True)
			bms_serial_number = self.getBMSSerialNumber()
			if bms_serial_number:
				bms_serial_number_decoded = _sp_parser.decode_bms_serial_number(bms_serial_number)
			else:
				bms_serial_number_decoded = {"bms_serial_number": "NA"}
			battery_production_date = self.getProductionDate()
			if battery_production_date:
				battery_production_date = battery_production_date.strftime("%Y/%m/%d")
			else:
				battery_production_date = "NA"

			if bms_serial_number:
				node_id = self.getAvailableNodeIDs()[0]
			else:
				node_id = "NA"
			
			basic_info = {
				'com_type': "CANBUS",
				'battery_model': battery_model,
				'serial_number': serial_number,
				'firmware_version': firmware_version,
				'bms_model': bms_model,
				'battery_production_date': battery_production_date,
				'node_id': node_id
				}

			for key, value in bms_serial_number_decoded.items():
				basic_info[key] = value

			return basic_info

		def get_raw_cell_voltages(self):
			response = self.queryBMS(self.get_raw_cell_voltages_command)
			if response:
				cells_in_total = response[2]
				#print("cells_in_total: %s" % cells_in_total)
				#print("response: %s" % response)
				raw_cell_voltages_in_mv = []
				spparser = SpParser()
				for i in range(cells_in_total):
					raw_cell_voltages_in_mv.append(spparser.read_two_bytes_big_endian_from_array(response, 3+2*i))
				#print("raw_cell_voltages_in_mv: %s " % raw_cell_voltages_in_mv)
				return raw_cell_voltages_in_mv
			else:
				print("no response from BMS in reading cell aq.")

		def calculate_cell_voltage_coefficient(self, raw_cell_voltage, target_cell_voltage):
			coefficient = raw_cell_voltage / target_cell_voltage
			return round(coefficient, 1)

		#remember to multiply by 10 before writing to BMS
		def get_cell_voltage_calibration_coefficients(self):
			raw_cell_voltages = self.get_raw_cell_voltages()
			calibrated_cell_voltages = self.getCellVoltages()

			if len(raw_cell_voltages) != len(calibrated_cell_voltages):
				raise Exception("The length of raw_cell_voltages and calibrated_cell_voltages do not match")

			cell_voltage_calibration_coefficients = []
			for i in range(len(calibrated_cell_voltages)):
				coefficient = self.calculate_cell_voltage_coefficient(raw_cell_voltages[i], calibrated_cell_voltages[i])
				cell_voltage_calibration_coefficients.append(coefficient)

			return cell_voltage_calibration_coefficients

		def change_bms_baudrate(self, baudrate, verbose=False):
			baudrate_commands = {
				125: [0xBC, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x10, 0x53],
				250: [0xBC, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x20, 0x63],
				500: [0xBC, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x30, 0x73],
				1000: [0xBC, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x40, 0x03]
			}
			assert baudrate in baudrate_commands.keys()

			self.sendWSTCommand(0x00E, baudrate_commands[baudrate], format="intarray")
			if verbose:
				print("Baudrate package: %s" % self.arrayToHex(baudrate_commands[baudrate]))
			self.uninitialize()
			self.setBaudrate(baudrate)
			self.initialize()
			if self.isBatteryConnected():
				return True
			else:
				return False

		def write_cell_voltage_calibrations(self, calibration_data):
			self.initialize()
			self.emptyQueue()
			model = "Unknown"
			try:
				model = self.getModelString()
			except:
				pass

			serial = "Unknown"
			try:
				serial = self.getSerial()
			except:
				pass

			# First we backup the current cell voltages - just in case...
			backup_cell_voltages = self.getCellVoltages()
			cells_total = len(backup_cell_voltages)
			assert cells_total > 1
			#print("Current backup_cell_voltages: %s" % backup_cell_voltages)

			now = datetime.now()
			backup_cell_voltage_file_name = "backup_cell_voltages_%s.txt" % str(datetime.timestamp(now)).replace(".", "")
			backup_cell_voltages_file_path = Path("backup_cell_voltage_data", backup_cell_voltage_file_name)
			backup_cell_voltages_file_path.parent.mkdir(parents=True, exist_ok=True)

			backup_cell_voltages_in_mv = list(map(lambda v: int(v*1000), backup_cell_voltages))
			#print("Cell voltages in mV: %s" % backup_cell_voltages_in_mv)

			with open(backup_cell_voltages_file_path, "w") as cell_voltage_backup_file:
				cell_voltage_backup_file.write("Model: %s\n" % model)
				cell_voltage_backup_file.write("Serial: %s\n" % serial)
				cell_voltage_backup_file.write("Existing cell voltages:  %s\n" % backup_cell_voltages_in_mv)

			calibration_cell_data = {}

			#for index, cell_voltage in enumerate(backup_cell_voltages_in_mv):
			#	print("cell %s, has: %s voltage" % (index+1, cell_voltage))

			#read raw cell voltages
			raw_cell_voltages = self.get_raw_cell_voltages()
			#print("raw_cell_voltages: %s" % raw_cell_voltages)
			cell_voltage_calibration_coefficients = self.get_cell_voltage_calibration_coefficients()
			#print("cell_voltage_calibration_coefficients: %s" % cell_voltage_calibration_coefficients)
			new_cell_voltage_calibration_coefficients = cell_voltage_calibration_coefficients.copy()

			#add changed voltages to new coefficients list
			for cell_number, cell_voltage in calibration_data.items():
				new_coefficient = int(self.calculate_cell_voltage_coefficient(raw_cell_voltages[cell_number - 1], round(cell_voltage, 3)))
				new_cell_voltage_calibration_coefficients[cell_number-1] = new_coefficient

			#print("new coefficients: %s " % new_cell_voltage_calibration_coefficients)

			# construct data package
			calibration_data_package = self.calibrate_cell_voltages_command_start.copy()
			calibration_data_package.append(cells_total)
			for index, coefficient in enumerate(new_cell_voltage_calibration_coefficients):
				calibration_data_package.append(index+1)
				data_bytes = int(coefficient*10).to_bytes(2, 'big')
				calibration_data_package.extend([data_bytes[0], data_bytes[1]])

			calibration_data_package.append(self.calcXOR(calibration_data_package[3:]))
			calibration_data_package.append(0xF5)
			#print("calibration data package: %s" % self.arrayToHex(calibration_data_package))
			self.sendSPPackage(calibration_data_package)
			self.uninitialize()
			#print("after: cell voltages: %s" % self.getCellVoltages())
