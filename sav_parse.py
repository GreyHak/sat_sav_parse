#!/usr/bin/env python3
# This file is part of the Satisfactory Save Parser distribution
#                                  (https://github.com/GreyHak/sat_sav_parse).
# Copyright (c) 2024-2025 GreyHak (github.com/GreyHak).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

# References which aren't accurate for Satisfactory v1.0:
# - https://satisfactory.wiki.gg/wiki/Save_files#Save_file_format

import datetime
import enum
import glob
import os
import struct
import sys
import zlib
from sav_data.data import CONVEYOR_BELTS, SOMERSLOOP, MERCER_SPHERE, MERCER_SHRINE, POWER_SLUG
import sav_data.readableNames

PROGRESS_BAR_ENABLE_DECOMPRESS = True
PROGRESS_BAR_ENABLE_PARSE = True
PROGRESS_BAR_ENABLE_DUMP = True
PRINT_DEBUG = False

class HistoryType(enum.Enum):
   NONE = 255
   BASE = 0
   ARGUMENT_FORMAT = 3
   STRING_TABLE_ENTRY = 11

satisfactoryCalculatorInteractiveMapExtras: list[str] = []

class ParseError(Exception):
    pass

def parseInt8(offset: int, data) -> tuple:
   nextOffset = offset + 1
   if nextOffset > len(data):
      raise ParseError(f"Offset {offset} too large for int8 in {len(data)}-byte data.")
   return (nextOffset, struct.unpack("<c", data[offset:nextOffset])[0])

def parseUint8(offset: int, data) -> tuple:
   nextOffset = offset + 1
   if nextOffset > len(data):
      raise ParseError(f"Offset {offset} too large for uint8 in {len(data)}-byte data.")
   return (nextOffset, struct.unpack("<B", data[offset:nextOffset])[0])

def parseInt32(offset: int, data) -> tuple:
   nextOffset = offset + 4
   if nextOffset > len(data):
      raise ParseError(f"Offset {offset} too large for int32 in {len(data)}-byte data.")
   return (nextOffset, struct.unpack("<i", data[offset:nextOffset])[0])

def parseUint32(offset: int, data) -> tuple:
   nextOffset = offset + 4
   if nextOffset > len(data):
      raise ParseError(f"Offset {offset} too large for uint32 in {len(data)}-byte data.")
   return (nextOffset, struct.unpack("<I", data[offset:nextOffset])[0])

def parseInt64(offset: int, data) -> tuple:
   nextOffset = offset + 8
   if nextOffset > len(data):
      raise ParseError(f"Offset {offset} too large for int64 in {len(data)}-byte data.")
   return (nextOffset, struct.unpack("<q", data[offset:nextOffset])[0])

def parseUint64(offset: int, data) -> tuple:
   nextOffset = offset + 8
   if nextOffset > len(data):
      raise ParseError(f"Offset {offset} too large for int64 in {len(data)}-byte data.")
   return (nextOffset, struct.unpack("<Q", data[offset:nextOffset])[0])

def parseFloat(offset: int, data) -> tuple:
   nextOffset = offset + 4
   if nextOffset > len(data):
      raise ParseError(f"Offset {offset} too large for float in {len(data)}-byte data.")
   return (nextOffset, struct.unpack("<f", data[offset:nextOffset])[0])

def parseDouble(offset: int, data) -> tuple:
   nextOffset = offset + 8
   if nextOffset > len(data):
      raise ParseError(f"Offset {offset} too large for double in {len(data)}-byte data.")
   return (nextOffset, struct.unpack("<d", data[offset:nextOffset])[0])

def parseBool(offset: int, data, parser, contextForException) -> tuple[int, bool]:
   (offset, flag) = parser(offset, data)
   if flag != 0 and flag != 1:
      raise ParseError(f"Oops: Inaccurate assumption of {contextForException} value.  Actual={flag}")
   return (offset, flag != 0)

def parseString(offset: int, data) -> tuple[int, str]:
   (offset, strlen) = parseInt32(offset, data)
   if strlen == 0:
      return (offset, "")
   if len(data) < offset + abs(strlen):
      raise ParseError(f"String length too large, size {strlen} at offset {offset-4}.")
   try:
      if strlen > 0:
         string = data[offset:offset+strlen-1].decode()
      else:
         string = data[offset:offset-strlen*2-2].decode("utf-16")
         strlen = -strlen * 2
   except UnicodeDecodeError as error:
      raise ParseError(f"String decode failure at offset {offset} of length {strlen}: {error}")

   return (offset + strlen, string)

def parseData(offset: int, data, length: int) -> tuple:
   if offset + length > len(data):
      raise ParseError(f"Offset {offset} too large for data of length {length} in {len(data)}-byte data.")
   return (offset + length, data[offset:offset+length])

def parseTextProperty(offset: int, data) -> tuple:
   (offset, flags) = parseUint32(offset, data)
   (offset, historyType) = parseUint8(offset, data)
   if historyType == HistoryType.NONE.value:
      (offset, isTextCultureInvariant) = parseUint32(offset, data)
      (offset, s) = parseString(offset, data)
      textProperty = [flags, historyType, isTextCultureInvariant, s]
   elif historyType == HistoryType.BASE.value: # Only observed in modded save
      (offset, namespace) = parseString(offset, data)
      (offset, key) = parseString(offset, data)
      (offset, value) = parseString(offset, data)
      textProperty = [flags, historyType, namespace, key, value]
   elif historyType == HistoryType.ARGUMENT_FORMAT.value: # Only observed in modded save (for propertyName="mMapText")
      offset = confirmBasicType(offset, data, parseUint32, 8)
      offset = confirmBasicType(offset, data, parseUint8, 0)
      offset = confirmBasicType(offset, data, parseUint32, 1)
      offset = confirmBasicType(offset, data, parseUint8, 0)
      (offset, uuid) = parseString(offset, data)
      (offset, format) = parseString(offset, data)
      (offset, argCount) = parseUint32(offset, data)
      args = []
      for idx in range(argCount):
         (offset, argName) = parseString(offset, data)
         offset = confirmBasicType(offset, data, parseUint8, 4)
         (offset, argFlags) = parseUint32(offset, data) # some-nuclear.sav
         offset = confirmBasicType(offset, data, parseUint8, 255) # historyType
         offset = confirmBasicType(offset, data, parseUint32, 1)  # isTextCultureInvariant
         (offset, argValue) = parseString(offset, data)
         args.append([argName, argValue, argFlags])
      textProperty = [flags, historyType, uuid, format, args]
   elif historyType == HistoryType.STRING_TABLE_ENTRY.value: # Only observed in modded save
      (offset, tableId) = parseString(offset, data)
      (offset, textKey) = parseString(offset, data)
      textProperty = [flags, historyType, tableId, textKey]
   else:
      raise ParseError(f"Unexpected TextProperty historyType {historyType}")
   return (offset, textProperty)

def TESTING_ONLY_dumpSection(offset: int, data, sectionStart, sectionSize: int, name: str = "") -> int:
   if offset > sectionStart + sectionSize:
      print(f"ERROR: TESTING_ONLY_dumpSection called already passed end offset")
      return offset
   print(f"DUMP SECTION from {offset} to {sectionStart + sectionSize}")
   numInts = int((sectionStart + sectionSize - offset) / 4)
   for idx in range(numInts):
      (offset, uint32) = parseUint32(offset, data)
      print(f"DUMP SECTION {name} uint32[{idx}]={hex(uint32)}")
   idx = 0
   while sectionStart + sectionSize - offset > 0:
      (offset, int8) = parseInt8(offset, data)
      print(f"DUMP SECTION {name} int8[{idx}]={int8}")
      idx += 1
   return offset

def TESTING_ONLY_dumpData(offset: int, data, length: int, name: str = "") -> int:
   return TESTING_ONLY_dumpSection(offset, data, offset, length, name)

def TESTING_ONLY_dumpInt8(offset: int, data: list, name: str = "") -> int:
   (newOffset, int8) = parseInt8(offset, data)
   print(f"DUMP({offset}) int8 {name} {int8}")
   return newOffset

def TESTING_ONLY_dumpUint32(offset: int, data: list, name: str = "") -> int:
   (newOffset, uint32) = parseUint32(offset, data)
   print(f"DUMP({offset}) uint32 {name} {uint32}")
   return newOffset

def TESTING_ONLY_dumpFloat(offset: int, data: list, name: str = "") -> int:
   (newOffset, val) = parseFloat(offset, data)
   print(f"DUMP({offset}) float {name} {val}")
   return newOffset

def TESTING_ONLY_dumpString(offset: int, data: list, name: str = "") -> int:
   (newOffset, string) = parseString(offset, data)
   print(f"DUMP({offset}) string {name} {string}")
   return newOffset

def confirmBasicType(originalOffset, data, parser, expectedValue, message = None) -> int:
   (newOffset, value) = parser(originalOffset, data)
   if value != expectedValue:
      if message is None:
         raise ParseError(f"Value {value} at offset {originalOffset} does not match the expected value {expectedValue}.")
      else:
         raise ParseError(f"Value {value} at offset {originalOffset} does not match the expected value {expectedValue}: {message}")
   return newOffset

TICKS_IN_SECOND = 10 * 1000 * 1000
EPOCH_1_TO_1970 = 719162 * 24 * 60 * 60
class SaveFileInfo:

   def parse(self, data):
      (offset, self.saveHeaderType) = parseUint32(0, data)
      if self.saveHeaderType != 14: # 13=(v0.8.3.3 thru v1.0.0.4)  14=(v1.1.0.0 thru v1.1.1.6)
         raise ParseError(f"Unsupported save header version number {self.saveHeaderType}.")
      (offset, self.saveVersion) = parseUint32(offset, data)
      if self.saveVersion != 52:  # 30=v0.6.1.3  42=v0.8.3.3  46=v1.0.0.1-v1.0.0.4  51=v1.1.0.0-v1.1.0.3  52=v1.1.0.4-v1.1.1.6
         raise ParseError(f"Unsupported save version number {self.saveVersion}.")
      (offset, self.buildVersion) = parseUint32(offset, data)
      (offset, self.saveName) = parseString(offset, data)
      (offset, self.mapName) = parseString(offset, data)
      (offset, self.mapOptions) = parseString(offset, data)
      (offset, self.sessionName) = parseString(offset, data)
      (offset, self.playDurationInSeconds) = parseUint32(offset, data)
      (offset, self.saveDateTimeInTicks) = parseUint64(offset, data)
      try:
         self.saveDatetime = datetime.datetime.fromtimestamp(self.saveDateTimeInTicks / TICKS_IN_SECOND - EPOCH_1_TO_1970)
      except:
         print(f"ERROR: Failed to perform fromtimestamp with saveDateTimeInTicks={self.saveDateTimeInTicks}")
         raise
      (offset, self.sessionVisibility) = parseInt8(offset, data)
      (offset, self.editorObjectVersion) = parseUint32(offset, data)
      (offset, self.modMetadata) = parseString(offset, data)
      (offset, self.isModdedSave) = parseBool(offset, data, parseUint32, "isModdedSave")
      (offset, self.persistentSaveIdentifier) = parseString(offset, data)

      offset = confirmBasicType(offset, data, parseUint32, 1)
      offset = confirmBasicType(offset, data, parseUint32, 1)
      (offset, random1) = parseUint64(offset, data)
      (offset, random2) = parseUint64(offset, data)
      self.random = [random1, random2]
      (offset, self.cheatFlag) = parseBool(offset, data, parseUint32, "SaveFileInfo.cheatFlag")

      return offset

   def __str__(self):
      string = "<SaveFileInfo: "
      string += f"saveHeaderType={self.saveHeaderType}, "
      string += f"saveVersion={self.saveVersion}, "
      string += f"buildVersion={self.buildVersion}, "
      string += f"mapName={self.mapName}, "
      string += f"mapOptions={self.mapOptions}, "
      string += f"sessionName={self.sessionName}, "
      string += f"playDurationInSeconds={self.playDurationInSeconds}, "
      string += f"saveDateTimeInTicks={self.saveDateTimeInTicks} ({self.saveDatetime.strftime('%m/%d/%Y %I:%M:%S %p')}), "
      string += f"sessionVisibility={self.sessionVisibility}, "
      string += f"editorObjectVersion={self.editorObjectVersion}, "
      string += f"modMetadata={self.modMetadata}, "
      string += f"isModdedSave={self.isModdedSave}, "
      string += f"persistentSaveIdentifier={self.persistentSaveIdentifier}, "
      string += f"random={self.random}, "
      string += f"cheatFlag={self.cheatFlag}>"
      return string

class ParsedSave:
   def __init__(self, saveFileInfo, headhex, grids, levels, aLevelName, dropPodObjectReferenceList, extraObjectReferenceList):
      self.saveFileInfo = saveFileInfo
      self.headhex = headhex
      self.grids = grids
      self.levels = levels
      self.aLevelName = aLevelName
      self.dropPodObjectReferenceList = dropPodObjectReferenceList
      self.extraObjectReferenceList = extraObjectReferenceList

class Level:
   def __init__(self, levelName, actorAndComponentObjectHeaders, levelPersistentFlag, collectables1, objects, levelSaveVersion, collectables2):
      self.levelName = levelName
      self.actorAndComponentObjectHeaders = actorAndComponentObjectHeaders
      self.levelPersistentFlag = levelPersistentFlag
      self.collectables1 = collectables1
      self.objects = objects
      self.levelSaveVersion = levelSaveVersion
      self.collectables2 = collectables2

class ActorHeader:

   def parse(self, offset: int, data) -> int:
      (offset, self.typePath) = parseString(offset, data)
      (offset, self.rootObject) = parseString(offset, data)
      (offset, self.instanceName) = parseString(offset, data)
      (offset, self.flags) = parseUint32(offset, data)
      (offset, self.needTransform) = parseBool(offset, data, parseUint32, "needTransform")

      (offset, xRotation) = parseFloat(offset, data)
      (offset, yRotation) = parseFloat(offset, data)
      (offset, zRotation) = parseFloat(offset, data)
      (offset, wRotation) = parseFloat(offset, data)
      self.rotation = [xRotation, yRotation, zRotation, wRotation]

      (offset, xPosition) = parseFloat(offset, data)
      (offset, yPosition) = parseFloat(offset, data)
      (offset, zPosition) = parseFloat(offset, data)
      self.position = [xPosition, yPosition, zPosition]

      (offset, xScale) = parseFloat(offset, data)
      (offset, yScale) = parseFloat(offset, data)
      (offset, zScale) = parseFloat(offset, data)
      self.scale = [xScale, yScale, zScale]

      (offset, self.wasPlacedInLevel) = parseBool(offset, data, parseUint32, "wasPlacedInLevel")
      return offset

   def __str__(self):
      return f"<ActorHeader: typePath={self.typePath}, rootObject={self.rootObject}, instanceName={self.instanceName}, flags={self.flags}, needTransform={self.needTransform}, rotation={self.rotation}, position={self.position}, scale={self.scale}, wasPlacedInLevel={self.wasPlacedInLevel}>"

class ComponentHeader:

   def parse(self, offset: int, data) -> int:
      (offset, self.className) = parseString(offset, data)
      (offset, self.rootObject) = parseString(offset, data)
      (offset, self.instanceName) = parseString(offset, data)
      (offset, self.flags) = parseUint32(offset, data)
      (offset, self.parentActorName) = parseString(offset, data)
      return offset

   def __str__(self):
      return f"<ComponentHeader: className={self.className}, rootObject={self.rootObject}, instanceName={self.instanceName}, flags={self.flags}, parentActorName={self.parentActorName}>"

def toString(value) -> str:
   if isinstance(value, str):
      return f"'{value}'"
   elif isinstance(value, (tuple, list)):
      string = ""
      for element in value:
         if len(string) > 0:
            string += ", "
         string += toString(element)
      if isinstance(value, tuple):
         return f"({string})"
      else:
         return f"[{string}]"
   elif isinstance(value, dict):
      string = ""
      for key in value:
         if len(string) > 0:
            string += ", "
         string += f"{toString(key)}: {toString(value[key])}"
      return "{" + string + "}"
   else: # if isinstance(value, (int, float, bool, complex)):
      return str(value)

def getPropertyValue(properties, needlePropertyName: str):
   for (haystackPropertyName, propertyValue) in properties:
      if haystackPropertyName == needlePropertyName:
         return propertyValue
   return None

class Object: # Both ActorObject and ComponentObject

   def parse(self, offset: int, data, actorOrComponentObjectHeader):
      self.instanceName = actorOrComponentObjectHeader.instanceName
      (offset, self.objectGameVersion) = parseUint32(offset, data) # 42=v0.8.3.3  46=v1.0.0.1 & v1.0.0.3  52=v1.1.0.4-v1.1.1.6
      (offset, self.shouldMigrateObjectRefsToPersistentFlag) = parseBool(offset, data, parseUint32, "Object.shouldMigrateObjectRefsToPersistentFlag")
      (offset, objectSize) = parseUint32(offset, data)
      offsetStartThis = offset

      self.actorReferenceAssociations: list | None = None
      if isinstance(actorOrComponentObjectHeader, ActorHeader):
         (offset, parentObjectReference) = parseObjectReference(offset, data)
         (offset, actorComponentReferenceCount) = parseUint32(offset, data)
         actorComponentReferences: list[ObjectReference] = []
         for jdx in range(actorComponentReferenceCount):
            (offset, actorComponentReference) = parseObjectReference(offset, data)
            actorComponentReferences.append(actorComponentReference)
         self.actorReferenceAssociations = [parentObjectReference, actorComponentReferences]

      (offset, self.properties, self.propertyTypes) = parseProperties(offset, data)

      offset = confirmBasicType(offset, data, parseUint32, 0)

      self.actorSpecificInfo: list | bool | int | None = None
      trailingByteSize = offsetStartThis + objectSize - offset
      if isinstance(actorOrComponentObjectHeader, ActorHeader):
         if actorOrComponentObjectHeader.typePath in CONVEYOR_BELTS:
            (offset, count) = parseUint32(offset, data)
            self.actorSpecificInfo = []
            for idx in range(count):
               (offset, length) = parseUint32(offset, data)
               (offset, name) = parseString(offset, data)
               offset = confirmBasicType(offset, data, parseString, "")
               offset = confirmBasicType(offset, data, parseString, "")
               (offset, position) = parseFloat(offset, data)
               self.actorSpecificInfo.append([length, name, position])
         elif actorOrComponentObjectHeader.typePath in (
               "/Game/FactoryGame/-Shared/Blueprint/BP_GameMode.BP_GameMode_C",
               "/Game/FactoryGame/-Shared/Blueprint/BP_GameState.BP_GameState_C"):
            (offset, count) = parseUint32(offset, data)
            self.actorSpecificInfo = []
            for idx in range(count):
               (offset, levelPathName) = parseObjectReference(offset, data)
               self.actorSpecificInfo.append(levelPathName)
         elif actorOrComponentObjectHeader.typePath == "/Game/FactoryGame/Character/Player/BP_PlayerState.BP_PlayerState_C": # Format very similar to ClientIdentityInfo
            (offset, playerStateType) = parseUint8(offset, data)
            if trailingByteSize == 1 and playerStateType == 3:
               self.actorSpecificInfo = playerStateType
            elif playerStateType == 241: # = 0xF1
               (offset, clientType) = parseUint8(offset, data) # Seen 1 or 6 (Maybe 1=Epic 6=Steam)
               (offset, clientSize) = parseUint32(offset, data)
               (offset, clientData) = parseData(offset, data, clientSize)
               self.actorSpecificInfo = [clientType, clientData]
            else: # Only observed in modded save
               offset -= 1
               (offset, self.actorSpecificInfo) = parseData(offset, data, trailingByteSize)
               #print(f"TO DO: Unexpected player state {playerStateType} of size {trailingByteSize} now allows greater parse testing: 0x{self.actorSpecificInfo.hex(',')}", file=sys.stderr)
         elif actorOrComponentObjectHeader.typePath == "/Game/FactoryGame/Buildable/Factory/DroneStation/BP_DroneTransport.BP_DroneTransport_C":
            (offset, self.actorSpecificInfo) = parseData(offset, data, trailingByteSize)
         elif actorOrComponentObjectHeader.typePath == "/Game/FactoryGame/-Shared/Blueprint/BP_CircuitSubsystem.BP_CircuitSubsystem_C":
            (offset, numCircuits) = parseUint32(offset, data)
            self.actorSpecificInfo = []
            for idx in range(numCircuits):
               (offset, circuitId) = parseUint32(offset, data)
               (offset, circuitReference) = parseObjectReference(offset, data)
               self.actorSpecificInfo.append([circuitId, circuitReference])
         elif actorOrComponentObjectHeader.typePath in (
               "/Game/FactoryGame/Buildable/Factory/PowerLine/Build_PowerLine.Build_PowerLine_C",
               "/Game/FactoryGame/Events/Christmas/Buildings/PowerLineLights/Build_XmassLightsLine.Build_XmassLightsLine_C"):
            (offset, source) = parseObjectReference(offset, data)
            (offset, target) = parseObjectReference(offset, data)
            self.actorSpecificInfo = [source, target]
         elif actorOrComponentObjectHeader.typePath in (
               "/Game/FactoryGame/Buildable/Vehicle/Train/Locomotive/BP_Locomotive.BP_Locomotive_C",
               "/Game/FactoryGame/Buildable/Vehicle/Train/Wagon/BP_FreightWagon.BP_FreightWagon_C"):
            (offset, numTrains) = parseUint32(offset, data)
            #print(f"   numTrains={numTrains}")
            trainList: list[str] = []
            for idx in range(numTrains):
               raise ParseError(f"numTrains {numTrains} for Object trailing data for {actorOrComponentObjectHeader.typePath} now allows greater parse testing.")
               #(offset, name) = parseString(offset, data)
               #print(f"   name={name}")
               #offset += 53
               #trainList.append(name)
            (offset, previous) = parseObjectReference(offset, data)
            #print(f"   previous={toString(previous)}")
            (offset, next) = parseObjectReference(offset, data)
            #print(f"   next={toString(next)}")
            self.actorSpecificInfo = [trainList, previous, next]
         elif actorOrComponentObjectHeader.typePath in (
               "/Game/FactoryGame/Buildable/Vehicle/Cyberwagon/Testa_BP_WB.Testa_BP_WB_C",
               "/Game/FactoryGame/Buildable/Vehicle/Explorer/BP_Explorer.BP_Explorer_C",
               "/Game/FactoryGame/Buildable/Vehicle/Golfcart/BP_Golfcart.BP_Golfcart_C",
               "/Game/FactoryGame/Buildable/Vehicle/Tractor/BP_Tractor.BP_Tractor_C",
               "/Game/FactoryGame/Buildable/Vehicle/Truck/BP_Truck.BP_Truck_C"):
            (offset, numVehicles) = parseUint32(offset, data)
            self.actorSpecificInfo = []
            for idx in range(numVehicles):
               (offset, name) = parseString(offset, data)
               (offset, vehicleData) = parseData(offset, data, 105)
               self.actorSpecificInfo.append([name, vehicleData])
         elif actorOrComponentObjectHeader.typePath == "/Script/FactoryGame.FGLightweightBuildableSubsystem": # Becomes <Object: instanceName=Persistent_Level:PersistentLevel.LightweightBuildableSubsystem ...>
            (offset, lightweightVersion) = parseUint32(offset, data)
            (offset, count1) = parseUint32(offset, data)
            self.actorSpecificInfo = [lightweightVersion]
            for jdx in range(count1):
               offset = confirmBasicType(offset, data, parseUint32, 0)

               (offset, buildItemPathName) = parseString(offset, data)
               (offset, count2) = parseUint32(offset, data)

               lightweightBuildableInstances = []
               for kdx in range(count2):

                  rotationQuaternion = []
                  for ldx in range(4):
                     (offset, value) = parseDouble(offset, data)
                     rotationQuaternion.append(value)
                  position = []
                  for ldx in range(3): # X,Y,Z Position
                     (offset, value) = parseDouble(offset, data)
                     position.append(value)
                  for ldx in range(3): # X/Y/Z Scale
                     offset = confirmBasicType(offset, data, parseDouble, 1.0)
                  offset = confirmBasicType(offset, data, parseUint32, 0)

                  (offset, swatchPathName) = parseString(offset, data)

                  for ldx in range(3):
                     offset = confirmBasicType(offset, data, parseUint32, 0)

                  (offset, patternDescNumber) = parseString(offset, data)
                  offset = confirmBasicType(offset, data, parseUint32, 0)
                  offset = confirmBasicType(offset, data, parseUint32, 0)

                  primaryColor = []
                  for ldx in range(4):
                     (offset, value) = parseFloat(offset, data)
                     primaryColor.append(value)

                  secondaryColor = []
                  for ldx in range(4):
                     (offset, value) = parseFloat(offset, data)
                     secondaryColor.append(value)

                  offset = confirmBasicType(offset, data, parseUint32, 0)

                  (offset, somethingSize) = parseUint32(offset, data)
                  (offset, somethingData) = parseData(offset, data, somethingSize)

                  (offset, maybeIndex) = parseUint32(offset, data) # seen 0-4 or rotation
                  offset = confirmBasicType(offset, data, parseUint8, 0)

                  (offset, recipePathName) = parseString(offset, data)
                  (offset, blueprintProxyLevelPath) = parseObjectReference(offset, data)

                  (offset, dataFlag) = parseUint32(offset, data)
                  beamLength = None
                  if dataFlag:
                     offset = confirmBasicType(offset, data, parseUint32, 0)
                     offset = confirmBasicType(offset, data, parseString, "/Script/FactoryGame.BuildableBeamLightweightData")
                     offset = confirmBasicType(offset, data, parseUint32, 55)
                     offset = confirmBasicType(offset, data, parseString, "BeamLength")
                     offset = confirmBasicType(offset, data, parseString, "FloatProperty")
                     offset = confirmBasicType(offset, data, parseUint32, 4)
                     offset = confirmBasicType(offset, data, parseUint8, 0)
                     offset = confirmBasicType(offset, data, parseUint32, 0)
                     (offset, beamLength) = parseFloat(offset, data)
                     offset = confirmBasicType(offset, data, parseString, "None")

                  lightweightBuildableInstances.append([rotationQuaternion, position, swatchPathName, patternDescNumber, [primaryColor, secondaryColor], somethingData, maybeIndex, recipePathName, blueprintProxyLevelPath, beamLength])

               self.actorSpecificInfo.append([buildItemPathName, lightweightBuildableInstances])
         elif actorOrComponentObjectHeader.typePath in (
                "/Script/FactoryGame.FGConveyorChainActor",
                "/Script/FactoryGame.FGConveyorChainActor_RepSizeNoCull",
                "/Script/FactoryGame.FGConveyorChainActor_RepSizeMedium",
                "/Script/FactoryGame.FGConveyorChainActor_RepSizeLarge",
                "/Script/FactoryGame.FGConveyorChainActor_RepSizeHuge"):
            (offset, levelPathName_startingBelt) = parseObjectReference(offset, data)
            (offset, levelPathName_endingBelt) = parseObjectReference(offset, data)
            (offset, numBeltsInChain) = parseUint32(offset, data)

            chainBelts = []
            for idx in range(numBeltsInChain):

               (offset, levelPathName_conveyorChainActor) = parseObjectReference(offset, data)
               (offset, levelPathName_belt) = parseObjectReference(offset, data)

               chainBeltElements = []
               (offset, numElements) = parseUint32(offset, data)
               for jdx in range(numElements):
                  nine = []
                  for kdx in range(3):
                     three = []
                     for ldx in range(3):
                        (offset, uint3) = parseUint64(offset, data)
                        three.append(uint3)
                     nine.append(three)
                  chainBeltElements.append(nine)

               (offset, buint32a) = parseUint32(offset, data)
               (offset, buint32b) = parseUint32(offset, data)
               (offset, buint32c) = parseUint32(offset, data)
               (offset, bint32a) = parseInt32(offset, data)
               (offset, bint32b) = parseInt32(offset, data)
               offset = confirmBasicType(offset, data, parseUint32, idx)

               chainBelts.append([levelPathName_belt, chainBeltElements, buint32a, buint32b, buint32c, bint32a, bint32b])

            (offset, cuint32) = parseUint32(offset, data)
            (offset, cint32a) = parseInt32(offset, data)
            (offset, cint32b) = parseInt32(offset, data)
            (offset, cint32c) = parseInt32(offset, data)

            chainItems = []
            (offset, numItems) = parseUint32(offset, data)
            for jdx in range(numItems):
               offset = confirmBasicType(offset, data, parseUint32, 0)
               (offset, itemPath) = parseString(offset, data)
               offset = confirmBasicType(offset, data, parseUint32, 0)
               (offset, h) = parseUint32(offset, data)
               chainItems.append([itemPath, h])

            # Note: Able to reconstruct starting and ending belts and the ConveyorChainActor is the same for all belts
            self.actorSpecificInfo = [levelPathName_conveyorChainActor, chainBelts, chainItems, cuint32, cint32a, cint32b, cint32c]
         elif actorOrComponentObjectHeader.typePath == "/Script/FactoryGame.FGItemPickup_Spawnable":
            if trailingByteSize == 4:
               self.actorSpecificInfo = True
               offset = confirmBasicType(offset, data, parseUint32, 0)
            else:
               self.actorSpecificInfo = False
         elif actorOrComponentObjectHeader.typePath in ( # Only observed in modded save
               "/AB_CableMod/Cables_Heavy/Build_AB-PLHeavy-Cu.Build_AB-PLHeavy-Cu_C",
               "/FlexSplines/Conveyor/Build_Belt2.Build_Belt2_C",
               "/FlexSplines/PowerLine/Build_FlexPowerline.Build_FlexPowerline_C",
               "/Game/FactoryGame/Buildable/Vehicle/Golfcart/BP_GolfcartGold.BP_GolfcartGold_C",
               "/CharacterReplacer/Logic/SCS_CR_PlayerHook.SCS_CR_PlayerHook_C"):
            (offset, self.actorSpecificInfo) = parseData(offset, data, trailingByteSize)
      else: # ComponentHeader
         if actorOrComponentObjectHeader.className in (
               "/Script/FactoryGame.FGDroneMovementComponent", # Nothern_Forest_20232627_191024-123703.sav
               "/Script/FactoryGame.FGFactoryConnectionComponent",
               "/Script/FactoryGame.FGFactoryLegsComponent",
               "/Script/FactoryGame.FGHealthComponent",
               "/Script/FactoryGame.FGInventoryComponent",
               "/Script/FactoryGame.FGInventoryComponentEquipment",
               "/Script/FactoryGame.FGInventoryComponentTrash",
               "/Script/FactoryGame.FGPipeConnectionComponent",
               "/Script/FactoryGame.FGPipeConnectionComponentHyper",
               "/Script/FactoryGame.FGPipeConnectionFactory",
               "/Script/FactoryGame.FGPowerConnectionComponent",
               "/Script/FactoryGame.FGPowerInfoComponent",
               "/Script/FactoryGame.FGRailroadTrackConnectionComponent",
               "/Script/FactoryGame.FGShoppingListComponent",
               "/Script/FactoryGame.FGTrainPlatformConnection",
               "/Script/FicsitFarming.FFDoggoHealthInfoComponent", # Only observed in modded save
               "/EditSwatchNames/DataHolder.DataHolder_C",         # Only observed in modded save
               ):
            self.actorSpecificInfo = offset < offsetStartThis + objectSize
            if self.actorSpecificInfo: # some-nuclear.sav
               offset = confirmBasicType(offset, data, parseUint32, 0, actorOrComponentObjectHeader.className)

      if offset < offsetStartThis + objectSize: # Items here for save files saved by satisfactory-calculator.com/en/interactive-map
         global satisfactoryCalculatorInteractiveMapExtras
         if isinstance(actorOrComponentObjectHeader, ActorHeader):
            satisfactoryCalculatorInteractiveMapExtras.append(actorOrComponentObjectHeader.typePath)
            if actorOrComponentObjectHeader.typePath in (
                  "/Script/FactoryGame.FGBlueprintProxy",
                  "/Script/FactoryGame.FGCentralStorageSubsystem",
                  "/Script/FactoryGame.FGDockingStationInfo",
                  "/Script/FactoryGame.FGDrivingTargetList",
                  "/Script/FactoryGame.FGDroneStationInfo",
                  "/Script/FactoryGame.FGFoliageRemovalSubsystem",
                  "/Script/FactoryGame.FGGameRulesSubsystem",
                  "/Script/FactoryGame.FGMapManager",
                  "/Script/FactoryGame.FGPipeNetwork",
                  "/Script/FactoryGame.FGPipeSubsystem",
                  "/Script/FactoryGame.FGRailroadTimeTable",
                  "/Script/FactoryGame.FGRecipeManager",
                  "/Script/FactoryGame.FGResourceSinkSubsystem",
                  "/Script/FactoryGame.FGSavedWheeledVehiclePath",
                  "/Script/FactoryGame.FGScannableSubsystem",
                  "/Script/FactoryGame.FGStatisticsSubsystem",
                  "/Script/FactoryGame.FGTrainStationIdentifier",
                  "/Script/FactoryGame.FGWheeledVehicleInfo",
                  "/Script/FactoryGame.FGWorldSettings"):
               offset = confirmBasicType(offset, data, parseUint32, 0)
         else: # ComponentHeader
            satisfactoryCalculatorInteractiveMapExtras.append(actorOrComponentObjectHeader.className)
            if actorOrComponentObjectHeader.className in (
                  "/Script/FactoryGame.FGBlueprintShortcut",
                  "/Script/FactoryGame.FGEmoteShortcut",
                  "/Script/FactoryGame.FGFactoryCustomizationShortcut",
                  "/Script/FactoryGame.FGHighlightedMarker_MapMarker",
                  "/Script/FactoryGame.FGPlayerHotbar",
                  "/Script/FactoryGame.FGPowerCircuit",
                  "/Script/FactoryGame.FGRecipeShortcut"):
               offset = confirmBasicType(offset, data, parseUint32, 0)

      if offset > offsetStartThis + objectSize:
         raise ParseError(f"Unexpected objectSize: expect={objectSize} < actual={offset - offsetStartThis}.  Offset passed expected position by {offset - offsetStartThis - objectSize} bytes.  Started at {offsetStartThis}.")
      if offset < offsetStartThis + objectSize:
         if isinstance(actorOrComponentObjectHeader, ActorHeader):
            raise ParseError(f"Found {offsetStartThis + objectSize - offset} extra trailing bytes for ActorHeader {actorOrComponentObjectHeader.typePath}.")
         else:
            raise ParseError(f"Found {offsetStartThis + objectSize - offset} extra trailing bytes for ComponentHeader {actorOrComponentObjectHeader.className}.")
         offset = offsetStartThis + objectSize

      return offset

   def __str__(self) -> str:
      actorReferenceAssociationsStr = "n/a"
      if self.actorReferenceAssociations is not None:
         actorReferenceAssociationsStr = ""
         for levelPathName in self.actorReferenceAssociations[1]:
            if len(actorReferenceAssociationsStr) > 0:
               actorReferenceAssociationsStr += ", "
            actorReferenceAssociationsStr += str(levelPathName)
         actorReferenceAssociationsStr = f"({self.actorReferenceAssociations[0]}, [{actorReferenceAssociationsStr}])"
      return f"<Object: instanceName={self.instanceName}, objectGameVersion={self.objectGameVersion}, smortpFlag={self.shouldMigrateObjectRefsToPersistentFlag}, actorReferenceAssociations={actorReferenceAssociationsStr}, properties={toString(self.properties)}, actorSpecificInfo={toString(self.actorSpecificInfo)}>"

class ObjectReference:

   def parse(self, offset: int, data) -> int:
      (offset, self.levelName) = parseString(offset, data)
      (offset, self.pathName) = parseString(offset, data)
      return offset

   def __str__(self) -> str:
      if self.levelName == "" and self.pathName == "":
         return "<ObjectReference/>"
      else:
         return f"<ObjectReference: levelName={self.levelName}, pathName={self.pathName}>"

def parseObjectReference(offset: int, data) -> tuple[int, ObjectReference]:
   objectReference = ObjectReference()
   offset = objectReference.parse(offset, data)
   return (offset, objectReference)

def getLevelSize(offset: int, data, persistentLevelFlag: bool = False):
   if persistentLevelFlag:
      levelName = None
   else:
      (offset, levelName) = parseString(offset, data)

   (offset, objectHeaderAndCollectable1Size) = parseUint64(offset, data)
   objectHeaderAndCollectable1StartOffset = offset
   (offset, actorAndComponentCount) = parseUint32(offset, data)

   offset = objectHeaderAndCollectable1StartOffset + objectHeaderAndCollectable1Size

   (offset, allObjectsSize) = parseUint64(offset, data)
   offset += allObjectsSize

   offset += 4 # levelSaveVersion

   # Collectables #2
   if not persistentLevelFlag:
      (offset, collectedCount2) = parseUint32(offset, data)
      for count in range(collectedCount2):
         (offset, objectReference) = parseObjectReference(offset, data)

   return (offset, actorAndComponentCount * 2)

class ProgressBar():
   prior = None
   current = 0
   fillChar = "#"
   emptyChar = "."
   completedChar = b'\x13\x27'.decode('utf-16')
   fillColor = "\033[1;37;47m"
   emptyColor = "\033[0;30;40m"
   resetColor = "\033[0m"

   def __init__(self, total, prefix: str = "", width: int = 70):
      self.total = total
      self.prefix = prefix
      self.width = width
      self.show()
   def add(self, more = 1):
      self.current += more
      self.show()
   def set(self, current = 1):
      self.current = current
      self.show()
   def show(self):
      # Loosely based on imbr's (https://stackoverflow.com/users/1207193/imbr) code at https://stackoverflow.com/questions/3160699/python-progress-bar
      filled = int(round(self.current / self.total * self.width))
      if filled != self.prior:
         if sys.stdout.isatty():
            print(f"{self.prefix}[{self.fillColor}{self.fillChar*filled}{self.emptyColor}{(self.emptyChar*(self.width-filled))}{self.resetColor}]   {round(self.current)}/{self.total}", end='\r', flush=True)
         self.prior = filled
   def complete(self):
      if sys.stdout.isatty():
         print(f"{self.prefix}[{self.fillChar*self.width}] {self.completedChar} {self.total}/{self.total}", flush=True)

def parseLevel(offset: int, data, persistentLevelFlag: bool = False, progressBar = ProgressBar):
   if persistentLevelFlag:
      levelName = None
   else:
      (offset, levelName) = parseString(offset, data)

   (offset, objectHeaderAndCollectable1Size) = parseUint64(offset, data)
   objectHeaderAndCollectable1StartOffset = offset
   (offset, actorAndComponentCount) = parseUint32(offset, data)

   # ActorHeaders and ComponentHeaders
   actorAndComponentObjectHeaders = []
   for idx in range(actorAndComponentCount):
      (offset, headerType) = parseUint32(offset, data)

      objectHeader: ActorHeader | ComponentHeader
      if headerType == 1:
         objectHeader = ActorHeader()
      elif headerType == 0:
         objectHeader = ComponentHeader()
      else:
         raise ParseError(f"Invalid headerType {headerType}")
      offset = objectHeader.parse(offset, data)
      actorAndComponentObjectHeaders.append(objectHeader)
      if progressBar is not None:
         progressBar.add()

   levelPersistentFlag = None
   if persistentLevelFlag:
      (offset, levelPersistentFlag) = parseBool(offset, data, parseUint32, "Level Persistent Flag")
      if levelPersistentFlag:
         offset = confirmBasicType(offset, data, parseString, "Persistent_Level", "Level Persistent String")

   # Collectables #1
   collectables1: list[ObjectReference] | None = None
   if objectHeaderAndCollectable1Size != offset - objectHeaderAndCollectable1StartOffset:
      collectables1 = []
      (offset, collectedCount1) = parseUint32(offset, data)
      for idx in range(collectedCount1):
         (offset, objectReference) = parseObjectReference(offset, data)
         collectables1.append(objectReference)

   if objectHeaderAndCollectable1Size != offset - objectHeaderAndCollectable1StartOffset:
      raise ParseError(f"Level actor/object size mismatch: expect={objectHeaderAndCollectable1Size} != actual={offset - objectHeaderAndCollectable1StartOffset}")

   # Objects
   objects = []
   (offset, allObjectsSize) = parseUint64(offset, data)
   objectStartOffset = offset
   (offset, objectCount) = parseUint32(offset, data)
   if objectCount != actorAndComponentCount:
      raise ParseError(f"Object count mismatch: objectCount={objectCount} != actorAndComponentCount={actorAndComponentCount}")
   for idx in range(actorAndComponentCount):
      object = Object()
      offset = object.parse(offset, data, actorAndComponentObjectHeaders[idx])
      objects.append(object)
      if progressBar is not None:
         progressBar.add()
   if offset - objectStartOffset != allObjectsSize:
      raise ParseError(f"Object size mismatch: expect={allObjectsSize} != actual={offset - objectStartOffset}")

   offset, levelSaveVersion = parseUint32(offset, data)

   # Collectables #2
   collectables2 = []
   if not persistentLevelFlag:
      (offset, collectedCount2) = parseUint32(offset, data)
      for count in range(collectedCount2):
         (offset, objectReference) = parseObjectReference(offset, data)
         collectables2.append(objectReference)

   return (offset, Level(levelName, actorAndComponentObjectHeaders, levelPersistentFlag, collectables1, objects, levelSaveVersion, collectables2))

def parseProperties(offset: int, data: list) -> tuple:
   properties = []
   propertyTypes = []
   while True:
      (offset, propertyName) = parseString(offset, data)
      if propertyName == "None":
         break

      (offset, propertyType) = parseString(offset, data)
      (offset, propertySize) = parseUint32(offset, data)
      (offset, propertyIndex) = parseUint32(offset, data)  # Doesn't appear to be an actual 'index'.  Can be non-zero for propertyType=StructProperty.
      retainedPropertyType: str | list = propertyType

      propertyStartOffset = 0
      if propertyType == "BoolProperty":
         (offset, value) = parseBool(offset, data, parseUint8, "Property.BoolProperty.value")
         properties.append([propertyName, value])
         offset = confirmBasicType(offset, data, parseUint8, 0)
         propertyStartOffset = offset
         if propertySize != offset - propertyStartOffset:
            raise ParseError(f"Unexpected propery size. diff={offset - propertyStartOffset - propertySize} type={propertyType} start={propertyStartOffset}")
      elif propertyType == "ByteProperty":
         (offset, intOrString) = parseString(offset, data)
         offset = confirmBasicType(offset, data, parseUint8, 0)
         propertyStartOffset = offset
         if intOrString == "None":
            (offset, value) = parseUint8(offset, data)
            properties.append([propertyName, value])
         else: # This case exists for 5 EGamePhase
            (offset, value) = parseString(offset, data)
            properties.append([propertyName, [intOrString, value]])
         if propertySize != offset - propertyStartOffset:
            raise ParseError(f"Unexpected propery size. diff={offset - propertyStartOffset - propertySize} type={propertyType} start={propertyStartOffset}")
      elif propertyType == "Int8Property":
         offset = confirmBasicType(offset, data, parseUint8, 0)
         propertyStartOffset = offset
         (offset, value) = parseInt8(offset, data)
         properties.append([propertyName, value])
         if propertySize != offset - propertyStartOffset:
            raise ParseError(f"Unexpected propery size. diff={offset - propertyStartOffset - propertySize} type={propertyType} start={propertyStartOffset}")
      elif propertyType == "IntProperty":
         offset = confirmBasicType(offset, data, parseUint8, 0)
         propertyStartOffset = offset
         (offset, value) = parseInt32(offset, data)
         properties.append([propertyName, value])
         if propertySize != offset - propertyStartOffset:
            raise ParseError(f"Unexpected propery size. diff={offset - propertyStartOffset - propertySize} type={propertyType} start={propertyStartOffset}")
      elif propertyType == "UInt32Property":
         offset = confirmBasicType(offset, data, parseUint8, 0)
         propertyStartOffset = offset
         (offset, value) = parseUint32(offset, data)
         properties.append([propertyName, value])
         if propertySize != offset - propertyStartOffset:
            raise ParseError(f"Unexpected propery size. diff={offset - propertyStartOffset - propertySize} type={propertyType} start={propertyStartOffset}")
      elif propertyType == "Int64Property":
         offset = confirmBasicType(offset, data, parseUint8, 0)
         propertyStartOffset = offset
         (offset, value) = parseInt64(offset, data)
         properties.append([propertyName, value])
         if propertySize != offset - propertyStartOffset:
            raise ParseError(f"Unexpected propery size. diff={offset - propertyStartOffset - propertySize} type={propertyType} start={propertyStartOffset}")
      elif propertyType == "FloatProperty":
         offset = confirmBasicType(offset, data, parseUint8, 0)
         propertyStartOffset = offset
         (offset, value) = parseFloat(offset, data)
         properties.append([propertyName, value])
         if propertySize != offset - propertyStartOffset:
            raise ParseError(f"Unexpected propery size. diff={offset - propertyStartOffset - propertySize} type={propertyType} start={propertyStartOffset}")
      elif propertyType == "DoubleProperty":
         offset = confirmBasicType(offset, data, parseUint8, 0)
         propertyStartOffset = offset
         (offset, value) = parseDouble(offset, data)
         properties.append([propertyName, value])
         if propertySize != offset - propertyStartOffset:
            raise ParseError(f"Unexpected propery size. diff={offset - propertyStartOffset - propertySize} type={propertyType} start={propertyStartOffset}")
      elif propertyType == "EnumProperty":
         (offset, name) = parseString(offset, data)
         offset = confirmBasicType(offset, data, parseUint8, 0)
         propertyStartOffset = offset
         (offset, value) = parseString(offset, data)
         properties.append([propertyName, [name, value]])
         if propertySize != offset - propertyStartOffset:
            raise ParseError(f"Unexpected propery size. diff={offset - propertyStartOffset - propertySize} type={propertyType} start={propertyStartOffset}")
      elif propertyType in ("StrProperty", "NameProperty"):
         offset = confirmBasicType(offset, data, parseUint8, 0)
         propertyStartOffset = offset
         (offset, value) = parseString(offset, data)
         properties.append([propertyName, value])
         if propertySize != offset - propertyStartOffset:
            raise ParseError(f"Unexpected propery size. diff={offset - propertyStartOffset - propertySize} type={propertyType} start={propertyStartOffset}")
      elif propertyType == "TextProperty":
         offset = confirmBasicType(offset, data, parseUint8, 0)
         propertyStartOffset = offset
         (offset, textProperty) = parseTextProperty(offset, data)
         properties.append([propertyName, textProperty])
         if propertySize != offset - propertyStartOffset:
            raise ParseError(f"Unexpected propery size. diff={offset - propertyStartOffset - propertySize} type={propertyType} start={propertyStartOffset}")
      elif propertyType == "SetProperty":
         (offset, setType) = parseString(offset, data)
         offset = confirmBasicType(offset, data, parseUint8, 0)
         propertyStartOffset = offset
         offset = confirmBasicType(offset, data, parseUint32, 0)
         (offset, typeCount) = parseUint32(offset, data)
         values = []
         if setType == "UInt32Property":
            for jdx in range(typeCount):
               (offset, value) = parseUint32(offset, data)
               values.append(value)
         elif setType == "StructProperty":
            for jdx in range(typeCount):
                (offset, value1) = parseUint64(offset, data)
                (offset, value2) = parseUint64(offset, data)
                values.append([value1, value2])
         elif setType == "ObjectProperty":
            for jdx in range(typeCount):
               (offset, objectReference) = parseObjectReference(offset, data)
               values.append(objectReference)
         else:
            raise ParseError(f"Unhandled SetProperty type {setType}")
         properties.append([propertyName, [setType, values]])
         if propertySize != offset - propertyStartOffset:
            raise ParseError(f"Unexpected propery size. diff={offset - propertyStartOffset - propertySize} type={propertyType} start={propertyStartOffset}")
      elif propertyType == "ObjectProperty":
         offset = confirmBasicType(offset, data, parseUint8, 0)
         propertyStartOffset = offset
         (offset, levelPathName) = parseObjectReference(offset, data)
         properties.append([propertyName, levelPathName])
         if propertySize != offset - propertyStartOffset:
            raise ParseError(f"Unexpected propery size. diff={offset - propertyStartOffset - propertySize} type={propertyType} start={propertyStartOffset}")
      elif propertyType == "SoftObjectProperty":
         offset = confirmBasicType(offset, data, parseUint8, 0)
         propertyStartOffset = offset
         (offset, levelPathName) = parseObjectReference(offset, data)
         (offset, value) = parseUint32(offset, data)
         properties.append([propertyName, [levelPathName, value]])
         if propertySize != offset - propertyStartOffset:
            raise ParseError(f"Unexpected propery size. diff={offset - propertyStartOffset - propertySize} type={propertyType} start={propertyStartOffset}")
      elif propertyType == "ArrayProperty":
         (offset, arrayType) = parseString(offset, data)
         retainedPropertyType = [propertyType, arrayType]
         offset = confirmBasicType(offset, data, parseUint8, 0)
         propertyStartOffset = offset
         (offset, arrayCount) = parseUint32(offset, data)
         values = []
         if arrayType == "IntProperty":
            for jdx in range(arrayCount):
               (offset, value) = parseInt32(offset, data)
               values.append(value)
         elif arrayType == "Int64Property":
            for jdx in range(arrayCount):
               (offset, value) = parseInt64(offset, data)
               values.append(value)
         elif arrayType == "ByteProperty":
            for jdx in range(arrayCount):
               (offset, value) = parseUint8(offset, data)
               values.append(value)
         elif arrayType == "FloatProperty":
            for jdx in range(arrayCount):
               (offset, value) = parseFloat(offset, data)
               values.append(value)
         elif arrayType == "DoubleProperty": # Only observed in modded save
            for jdx in range(arrayCount):
               (offset, value) = parseDouble(offset, data)
               values.append(value)
         elif arrayType in ("StrProperty", "EnumProperty"):
            for jdx in range(arrayCount):
               (offset, value) = parseString(offset, data)
               values.append(value)
         elif arrayType == "SoftObjectProperty":
            for jdx in range(arrayCount):
               (offset, levelPathName) = parseObjectReference(offset, data)
               (offset, value) = parseUint32(offset, data)
               values.append([levelPathName, value])
         elif arrayType in ("InterfaceProperty", "ObjectProperty"):
            for jdx in range(arrayCount):
               (offset, levelPathName) = parseObjectReference(offset, data)
               values.append(levelPathName)
         elif arrayType == "TextProperty": # Only observed in modded save
            for jdx in range(arrayCount):
               (offset, textProperty) = parseTextProperty(offset, data)
               values.append(textProperty)
         elif arrayType == "StructProperty":
            (offset, name) = parseString(offset, data)
            if name != propertyName:
               raise ParseError(f"Unexpected StructProperty name '{name}' != propertyName '{propertyName}'")
            offset = confirmBasicType(offset, data, parseString, "StructProperty")
            (offset, structSize) = parseUint32(offset, data)
            offset = confirmBasicType(offset, data, parseUint32, 0)
            (offset, structElementType) = parseString(offset, data)
            retainedPropertyType = [propertyType, arrayType, structElementType]
            (offset, uuid) = parseData(offset, data, 17) # Always zero except in modded save
            if any(byte != 0 for byte in uuid):
               retainedPropertyType.append(uuid)
            structStartOffset = offset
            if structElementType == "LinearColor":
               for jdx in range(arrayCount):
                  (offset, r) = parseFloat(offset, data)
                  (offset, g) = parseFloat(offset, data)
                  (offset, b) = parseFloat(offset, data)
                  (offset, a) = parseFloat(offset, data)
                  values.append([r, g, b, a])
            elif structElementType == "Vector":
               for jdx in range(arrayCount):
                  (offset, x) = parseDouble(offset, data)
                  (offset, y) = parseDouble(offset, data)
                  (offset, z) = parseDouble(offset, data)
                  values.append([x, y, z])
            elif structElementType == "SpawnData":
               for jdx in range(arrayCount):
                  (offset, name) = parseString(offset, data)
                  offset = confirmBasicType(offset, data, parseString, "ObjectProperty")
                  (offset, spawnDataSize) = parseUint32(offset, data)
                  offset = confirmBasicType(offset, data, parseUint32, 0)
                  offset = confirmBasicType(offset, data, parseUint8, 0)
                  spawnDataStartOffset = offset
                  (offset, levelPathName) = parseObjectReference(offset, data)
                  if spawnDataSize != offset - spawnDataStartOffset:
                     raise ParseError(f"Unexpected spawn data size. diff={offset - spawnDataStartOffset - spawnDataSize} type={propertyType}")
                  (offset, prop, propTypes) = parseProperties(offset, data)
                  values.append([name, levelPathName, prop, propTypes])
            elif structElementType in (
                  "ConnectionData",             # Only observed in modded save
                  "BuildingConnection",         # Only observed in modded save
                  "STRUCT_ProgElevator_Floor",  # Only observed in modded save
                  "Struct_InputConfiguration"): # Only observed in modded save
               (offset, allValues) = parseData(offset, data, structSize)
               values.append(allValues)
               while len(values) < arrayCount:
                  values.append(None)
            elif structElementType == "LocalUserNetIdBundle":
               for _ in range(arrayCount):
                  (offset, prop, propTypes) = parseProperties(offset, data)
                  values.append([prop, propTypes])
            elif structElementType in (
                  "BlueprintCategoryRecord",
                  "BlueprintSubCategoryRecord",
                  "DroneTripInformation",
                  "ElevatorFloorStopInfo",
                  "FactoryCustomizationColorSlot",
                  "FeetOffset",
                  "FGCachedConnectedWire", # SatisFaction_20240921-092707.sav
                  "FGDroneFuelRuntimeData", # Nothern_Forest_20232627_191024-123703.sav
                  "GCheckmarkUnlockData",
                  "GlobalColorPreset",
                  "HardDriveData",
                  "HighlightedMarkerPair",
                  "Hotbar",
                  "InventoryStack",
                  "ItemAmount",
                  "MapMarker",
                  "MessageData",
                  "MiniGameResult",
                  "PhaseCost",
                  "PrefabIconElementSaveData",
                  "PrefabTextElementSaveData",
                  "ProjectAssemblyLaunchSequenceValue",
                  "ResearchData",
                  "ResearchTime",
                  "ResourceSinkHistory",
                  "ScannableObjectData",
                  "ScannableResourcePair",
                  "SchematicCost",
                  "ShoppingListBlueprintEntry",
                  "ShoppingListClassEntry",
                  "ShoppingListRecipeEntry",
                  "SplinePointData",
                  "SplitterSortRule",
                  "SubCategoryMaterialDefault",
                  "TimeTableStop",
                  "WireInstance",
                  "DTConfigStruct",                # Only observed in modded save
                  "ManagedSignConnectionSettings", # Only observed in modded save
                  "ResourceNodeData",              # Only observed in modded save
                  "SignComponentData",             # Only observed in modded save
                  "SignComponentVariableData",     # Only observed in modded save
                  "SignComponentVariableMetaData", # Only observed in modded save
                  "SwatchGroupData",               # Only observed in modded save
                  "USSSwatchSaveInfo",             # Only observed in modded save
                  ):
               for jdx in range(arrayCount):
                  (offset, prop, propTypes) = parseProperties(offset, data)
                  values.append([prop, propTypes])
            else:
               raise ParseError(f"Unsupported StructProperty structElementType '{structElementType}'")
            if structSize != offset - structStartOffset:
               raise ParseError(f"Unexpected StructProperty size. diff={offset - structStartOffset - structSize} type={propertyType}")
         else:
            raise ParseError(f"Unsupported ArrayProperty type '{arrayType}'")
         if propertySize != offset - propertyStartOffset:
            raise ParseError(f"Unexpected propery size. diff={offset - propertyStartOffset - propertySize} type={propertyType} start={propertyStartOffset}")
         properties.append([propertyName, values])
      elif propertyType == "StructProperty":
         (offset, structPropertyType) = parseString(offset, data)
         retainedPropertyType = [propertyType, structPropertyType]
         (offset, structUuid1) = parseUint32(offset, data)
         (offset, structUuid2) = parseUint32(offset, data)
         (offset, structUuid3) = parseUint32(offset, data)
         (offset, structUuid4) = parseUint32(offset, data)
         if structUuid1 != 0 or structUuid2 != 0 or structUuid3 != 0 or structUuid4 != 0: # Only observed in modded save
            retainedPropertyType.append([structUuid1, structUuid2, structUuid3, structUuid4])
         offset = confirmBasicType(offset, data, parseUint8, 0)
         propertyStartOffset = offset
         if structPropertyType == "InventoryItem":
            offset = confirmBasicType(offset, data, parseUint32, 0)
            (offset, itemName) = parseString(offset, data)
            (offset, itemHasPropertiesFlag) = parseBool(offset, data, parseUint32, "StructProperty.InventoryItem.itemHasPropertiesFlag")
            itemProperties: list | int = 1
            if itemHasPropertiesFlag:
               offset = confirmBasicType(offset, data, parseUint32, 0)
               (offset, typePath) = parseString(offset, data)
               (offset, itemPropertySize) = parseUint32(offset, data)
               itemPropertyStart = offset
               (offset, prop, propTypes) = parseProperties(offset, data)
               itemProperties = [typePath, prop, propTypes]
               if itemPropertySize != offset - itemPropertyStart:
                  raise ParseError(f"Unexpected InventoryItem size. diff={offset - itemPropertyStart - itemPropertySize}")
            elif propertyStartOffset + propertySize - offset == 4: # Observed only in a v0.8-created save resaved in v1.0, but does not correlate to objectGameVersion. Some times itemName is empty, and sometimes not.
               itemProperties = 2
               offset = confirmBasicType(offset, data, parseUint32, 0)
            properties.append([propertyName, [itemName, itemProperties]])
         elif structPropertyType == "LinearColor":
            (offset, r) = parseFloat(offset, data)
            (offset, g) = parseFloat(offset, data)
            (offset, b) = parseFloat(offset, data)
            (offset, a) = parseFloat(offset, data)
            properties.append([propertyName, [r, g, b, a]])
         elif structPropertyType == "Vector":
            (offset, x) = parseDouble(offset, data)
            (offset, y) = parseDouble(offset, data)
            (offset, z) = parseDouble(offset, data)
            properties.append([propertyName, [x, y, z]])
         elif structPropertyType == "Quat":
            (offset, x) = parseDouble(offset, data)
            (offset, y) = parseDouble(offset, data)
            (offset, z) = parseDouble(offset, data)
            (offset, w) = parseDouble(offset, data)
            properties.append([propertyName, [x, y, z, w]])
         elif structPropertyType == "Box":
            (offset, minx) = parseDouble(offset, data)
            (offset, miny) = parseDouble(offset, data)
            (offset, minz) = parseDouble(offset, data)
            (offset, maxx) = parseDouble(offset, data)
            (offset, maxy) = parseDouble(offset, data)
            (offset, maxz) = parseDouble(offset, data)
            (offset, flag) = parseBool(offset, data, parseUint8, "StructProperty.Box.flag")
            properties.append([propertyName, [minx, miny, minz, maxx, maxy, maxz, flag]])
         elif structPropertyType == "FluidBox":
            (offset, content) = parseFloat(offset, data) # "current content of this fluid box"
            properties.append([propertyName, content])
         elif structPropertyType == "RailroadTrackPosition":
            (offset, levelPathName) = parseObjectReference(offset, data)
            (offset, rtpOffset) = parseFloat(offset, data)
            (offset, forward) = parseFloat(offset, data)
            properties.append([propertyName, [levelPathName, rtpOffset, forward]])
         elif structPropertyType == "DateTime":
            (offset, value) = parseInt64(offset, data)
            properties.append([propertyName, value])
         elif structPropertyType == "ClientIdentityInfo": # Format very similar to BP_PlayerState_C
            (offset, clientUuid) = parseString(offset, data)
            (offset, identityCount) = parseUint32(offset, data)
            identities = []
            for _ in range(identityCount):
               (offset, clientType) = parseUint8(offset, data) # Seen 1 or 6 (Maybe 1=Epic 6=Steam)
               (offset, clientSize) = parseUint32(offset, data)
               (offset, clientData) = parseData(offset, data, clientSize)
               identities.append([clientType, clientData])
            properties.append([propertyName, [clientUuid, identities]])
         elif structPropertyType in ("Guid", "Rotator", "SignComponentEditorMetadata"): # Only observed in modded save
            (offset, rawData) = parseData(offset, data, propertySize)
            properties.append([propertyName, rawData])
         elif structPropertyType in (
               "BlueprintRecord",
               "BoomBoxPlayerState",
               "DroneDockingStateInfo",
               "DroneTripInformation",
               "FGPlayerPortalData",
               "FGPortalCachedFactoryTickData",
               "FactoryCustomizationColorSlot",
               "FactoryCustomizationData",
               "InventoryStack",
               "InventoryToRespawnWith",
               "LightSourceControlData",
               "MapMarker",
               "PersistentGlobalIconId", # 20240915\SatisFaction_20240915-002433.sav
               "PlayerCustomizationData",
               "PlayerRules",
               "ResearchData",
               "ShoppingListSettings",
               "SwitchData", # OPO_current_111025-175328.sav
               "TimerHandle",
               "TopLevelAssetPath", # 20240915\SatisFaction_20240915-002433.sav
               "TrainDockingRuleSet",
               "TrainSimulationData",
               "Transform",
               "Vector_NetQuantize",
               "BuildingConnections", # Only observed in modded save
               "DTActiveConfig",      # Only observed in modded save
               "LBBalancerData",      # Only observed in modded save
               "ManagedSignData",     # Only observed in modded save
               "Struct_PC_PartInfo",  # Only observed in modded save
               ):
            (offset, prop, propTypes) = parseProperties(offset, data)
            properties.append([propertyName, [prop, propTypes]])
         else:
            if True:
               raise ParseError(f"Unsupported structPropertyType '{structPropertyType}'")
            else: # For debug only
               offset = TESTING_ONLY_dumpSection(offset, data, propertyStartOffset, propertySize, f"Skipping unsupported structPropertyType '{structPropertyType}'")
               properties.append([propertyName])
         if propertySize != offset - propertyStartOffset:
            raise ParseError(f"Unexpected propery size. diff={offset - propertyStartOffset - propertySize} type={propertyType} structPropertyType={structPropertyType} start={propertyStartOffset}")
         if False: # For debug only
            print(f"DEBUG: Successfully parsed StructProperty '{structPropertyType}'.")

      elif propertyType == "MapProperty":
         (offset, keyType) = parseString(offset, data)
         (offset, valueType) = parseString(offset, data)
         retainedPropertyType = [propertyType, keyType, valueType]
         offset = confirmBasicType(offset, data, parseUint8, 0)
         propertyStartOffset = offset
         offset = confirmBasicType(offset, data, parseUint32, 0)
         (offset, numberOfElements) = parseUint32(offset, data)
         values = []
         propTypess: list | None = None
         if valueType == "StructProperty":
            propTypess = []
         for jdx in range(numberOfElements):
            if keyType == "StructProperty":
               (offset, int1) = parseInt32(offset, data)
               (offset, int2) = parseInt32(offset, data) # Can be negative
               (offset, int3) = parseInt32(offset, data)
               mapKey = [int1, int2, int3]
            elif keyType == "ObjectProperty":
               (offset, levelPathName) = parseObjectReference(offset, data)
               mapKey = levelPathName
            elif keyType == "IntProperty":
               (offset, mapKey) = parseInt32(offset, data)
            elif keyType == "NameProperty": # Only observed in modded save
               (offset, mapKey) = parseString(offset, data)
            elif keyType == "EnumProperty": # Only observed in modded save
               (offset, mapKey) = parseString(offset, data)
            else:
               raise ParseError(f"Unsupported map keyType {keyType}")

            if valueType == "StructProperty":
               (offset, mapValue, propTypes) = parseProperties(offset, data)
               propTypess.append(propTypes)
            elif valueType == "IntProperty":
               (offset, mapValue) = parseInt32(offset, data)
            elif valueType == "Int64Property":
               (offset, mapValue) = parseInt64(offset, data)
            elif valueType == "ByteProperty":
               (offset, mapValue) = parseUint8(offset, data)
            elif valueType == "DoubleProperty": # Only observed in modded save
               (offset, mapValue) = parseDouble(offset, data)
            elif valueType == "ObjectProperty": # Only observed in modded save
               (offset, mapValue) = parseObjectReference(offset, data)
            else:
               raise ParseError(f"Unsupported map valueType {valueType}")

            values.append([mapKey, mapValue])
         properties.append([propertyName, values])
         if valueType == "StructProperty":
            retainedPropertyType = [propertyType, keyType, valueType, propTypess]
         if propertySize != offset - propertyStartOffset:
            raise ParseError(f"Unexpected propery size. diff={offset - propertyStartOffset - propertySize} type={propertyType} start={propertyStartOffset}")

      else:
         raise ParseError(f"Unsupported propertyType '{propertyType}' for property '{propertyName}' at offset {offset} of size {propertySize} bytes")

      propertyTypes.append([propertyName, retainedPropertyType, propertyIndex])

      if len(properties) != len(propertyTypes):
         raise ParseError(f"Logic error: Number of properties {len(properties)} != Number of property types {len(propertyTypes)}")

   return (offset, properties, propertyTypes)

def readCompressedSaveFile(filename: str):
   with open(filename, "rb") as fin:
      return fin.read()

def decompressSaveFile(offset: int, data: list):
   decompressedData = b""
   if PROGRESS_BAR_ENABLE_DECOMPRESS:
      progressBar = ProgressBar(len(data), "Decompression: ")
   while offset < len(data):
      offset = confirmBasicType(offset, data, parseUint32, 0x9e2a83c1)  # unrealEnginePackageSignature
      offset = confirmBasicType(offset, data, parseUint32, 0x22222222)
      offset = confirmBasicType(offset, data, parseUint8, 0)

      (offset, maximumChunkSize) = parseUint32(offset, data)
      offset = confirmBasicType(offset, data, parseUint32, 0x03000000)
      (offset, currentChunkCompressedLength1) = parseUint64(offset, data)
      (offset, currentChunkUncompressedLength1) = parseUint64(offset, data)
      (offset, currentChunkCompressedLength2) = parseUint64(offset, data)
      (offset, currentChunkUncompressedLength2) = parseUint64(offset, data)

      if currentChunkCompressedLength1 != currentChunkCompressedLength2:
         raise ParseError(f"Compressed size mismatch {currentChunkCompressedLength1} != {currentChunkCompressedLength2}")
      if currentChunkUncompressedLength1 != currentChunkUncompressedLength2:
         raise ParseError(f"Uncompressed size mismatch {currentChunkUncompressedLength1} != {currentChunkUncompressedLength2}")
      if offset+currentChunkCompressedLength1 > len(data):
         raise ParseError(f"Chunk compressed length exceeds end of file by {offset+currentChunkCompressedLength1 - len(data)}")

      dData = zlib.decompress(data[offset:offset+currentChunkCompressedLength1])
      if len(dData) != currentChunkUncompressedLength1:
         raise ParseError(f"Decompression didn't return the expected amount return={len(dData)} != expected={currentChunkUncompressedLength1}")
      decompressedData += dData
      offset += currentChunkCompressedLength1
      if PROGRESS_BAR_ENABLE_DECOMPRESS:
         progressBar.set(offset)

   if PROGRESS_BAR_ENABLE_DECOMPRESS:
      progressBar.complete()
   return decompressedData

def pathNameToReadableName(name: str) -> str:
   if len(name) == 0:
      return name
   originalName = name
   pos = name.rfind(".")
   if pos != -1:
      name = name[pos+1:]
   if name in sav_data.readableNames.READABLE_PATH_NAME_CORRECTIONS:
      return sav_data.readableNames.READABLE_PATH_NAME_CORRECTIONS[name]
   pos = name.find("_", pos)
   if pos != -1:
      name = name[pos+1:]
   if name.endswith("_C"):
      name = name[:-2]
   name = name.replace("_", ", ")
   for letter in ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"):
      name = name.replace(letter, f" {letter}")
   name = name.replace("  ", " ")
   if name[0] == " ":
      name = name[1:]
   return f"{name} ({originalName})"

def readFullSaveFile(filename: str, decompressedOutputFilename: str | None = None):
   global satisfactoryCalculatorInteractiveMapExtras
   satisfactoryCalculatorInteractiveMapExtras = []

   data = readCompressedSaveFile(filename)
   saveFileInfo = SaveFileInfo()
   offset = saveFileInfo.parse(data)
   data = decompressSaveFile(offset, data)

   # SaveFileHeader
   (offset, uncompressedSize) = parseUint64(0, data) # uncompressedSize <= len(data)
   uncompressedSize += 8 # Length doesn't include the length itself even if the length is called compressed data length and the length is itself compressed.

   if decompressedOutputFilename is not None:
      with open(decompressedOutputFilename, "wb") as fout:
         fout.write(data)

   if uncompressedSize > len(data):
      raise ParseError(f"Reported uncompressed size {uncompressedSize} is larger than the actual uncompressed size {len(data)}.")
   data = data[:uncompressedSize]

   offset = confirmBasicType(offset, data, parseUint32, 6)
   offset = confirmBasicType(offset, data, parseString, "None")
   offset = confirmBasicType(offset, data, parseUint32, 0)
   (offset, headhex1) = parseUint32(offset, data)
   offset = confirmBasicType(offset, data, parseUint32, 1)
   offset = confirmBasicType(offset, data, parseString, "None")
   (offset, headhex2) = parseUint32(offset, data)

   # Grids: Lists of Level Information
   grids = []
   for idx in range(5):
      (offset, gridName) = parseString(offset, data) # MainGrid, LandscapeGrid, ExplorationGrid, FoliageGrid, HLOD0_256m_1023m
      (offset, i) = parseUint32(offset, data)
      (offset, ghex) = parseUint32(offset, data)
      (offset, count) = parseUint32(offset, data)
      gridLevels = []
      for jdx in range(count):
         (offset, levelName) = parseString(offset, data)
         (offset, lhex) = parseUint32(offset, data)
         gridLevels.append([levelName, lhex])
      grids.append([gridName, i, ghex, gridLevels])

   # Levels
   levels = []
   (offset, levelCount) = parseUint32(offset, data)

   if PROGRESS_BAR_ENABLE_PARSE:
      totalLevelSize = 0
      levelSizes = []
      tmpOffset = offset
      for idx in range(levelCount):
         (tmpOffset, levelSize) = getLevelSize(tmpOffset, data)
         totalLevelSize += levelSize
         levelSizes.append(levelSize)
      (tmpOffset, levelSize) = getLevelSize(tmpOffset, data, True)
      totalLevelSize += levelSize
      levelSizes.append(levelSize)
      progressBar = ProgressBar(totalLevelSize, "      Parsing: ")
   else:
      progressBar = None

   for idx in range(levelCount):
      (offset, level) = parseLevel(offset, data, False, progressBar)
      levels.append(level)
   (offset, level) = parseLevel(offset, data, True, progressBar) # Potentially sets the global satisfactoryCalculatorInteractiveMapExtras
   levels.append(level)

   if offset == len(data):
      satisfactoryCalculatorInteractiveMapExtras.append("Missing final array count") # This can cause the input save file to lose content
      data += b"\x00\x00\x00\x00"

   (offset, aLevelName) = parseString(offset, data)

   dropPodObjectReferenceList = []
   extraObjectReferenceList = []
   if aLevelName == "Persistent_Level":
      (offset, dropPodCount) = parseUint32(offset, data)
      for idx in range(dropPodCount):
         (offset, dropPodReference) = parseObjectReference(offset, data)
         dropPodObjectReferenceList.append(dropPodReference)

      # Unresolved/destroyed actors
      (offset, extraObjectReferenceCount) = parseUint32(offset, data)
      for idx in range(extraObjectReferenceCount):
         (offset, objectReference) = parseObjectReference(offset, data)
         extraObjectReferenceList.append(objectReference)

   if offset != len(data):
      raise ParseError(f"Parsed data {offset} does not match decompressed data {len(data)}.")
   if PROGRESS_BAR_ENABLE_PARSE and progressBar is not None:
      progressBar.complete()

   if len(satisfactoryCalculatorInteractiveMapExtras) > 0:
      print(f"File suspected of having been saved by satisfactory-calculator.com/en/interactive-map for {len(satisfactoryCalculatorInteractiveMapExtras)} reasons.", file=sys.stderr)

   if PRINT_DEBUG:
      countOfNoneCollectables1 = 0
      emptyCollectables1 = 0
      for level in levels:
         if level.collectables1 is None:
            countOfNoneCollectables1 += 1
         elif len(level.collectables1) == 0:
            emptyCollectables1 += 1
      if countOfNoneCollectables1 > 0:
         print(f"Skipped {countOfNoneCollectables1} level collectables1 with {emptyCollectables1} empty collectables1")
      if level.extraObjectReferenceCount > 0:
         print(f"extraObjectReferenceCount={level.extraObjectReferenceCount}")

   return ParsedSave(saveFileInfo, (headhex1, headhex2), grids, levels, aLevelName, dropPodObjectReferenceList, extraObjectReferenceList)

def readSaveFileInfo(filename: str) -> SaveFileInfo:
   with open(filename, "rb") as fin:
      data = fin.read() # 400 should be good enough for non-modded.  Needs to be 6k+ for modMetadata
   saveFileInfo = SaveFileInfo()
   offset = saveFileInfo.parse(data)
   return saveFileInfo

if __name__ == '__main__':

   if (len(sys.argv) <= 1 or len(sys.argv[1]) == 0) and os.path.isdir(".config/Epic/FactoryGame/Saved/SaveGames/server"):
      allSaveFiles = glob.glob(".config/Epic/FactoryGame/Saved/SaveGames/server/*.sav")
      savFilename = max(allSaveFiles, key=os.path.getmtime)
   elif (len(sys.argv) <= 1 or len(sys.argv[1]) == 0) and "LOCALAPPDATA" in os.environ and os.path.isdir(f"{os.environ['LOCALAPPDATA']}\\FactoryGame\\Saved\\SaveGames"):
      allSaveFiles = glob.glob(f"{os.environ['LOCALAPPDATA']}\\FactoryGame\\Saved\\SaveGames\\*\\*.sav")
      savFilename = max(allSaveFiles, key=os.path.getmtime)
   elif len(sys.argv) <= 1:
      print("ERROR: Please supply save file path/name to perform parsing.", file=sys.stderr)
      exit(1)
   else:
      savFilename = sys.argv[1]

   if len(sys.argv) >= 3:
      outBase = sys.argv[2]
   elif len(savFilename) >= 5:
      outBase = savFilename[:-4]
   else:
      outBase = savFilename
   dumpOutputFilename = outBase + "-dump.txt"
   slugOutputFilename = outBase + "-slugs.txt"
   somersloopOutputFilename = outBase + "-somersloop.txt"
   mercerSphereOutputFilename = outBase + "-mercerSphere.txt"
   decompressedOutputFilename = outBase + "-decompressed.txt"
   droppedItemsOutputFilename = outBase + "-free.txt"
   crashSitesOutputFilename = outBase + "-crashSites.txt"

   if not os.path.isfile(savFilename):
      print(f"ERROR: Save file does not exist: '{savFilename}'", file=sys.stderr)
      exit(1)

   print(f"Parsing {savFilename}")
   with open(dumpOutputFilename, "w", encoding="utf-8") as dumpOut:

      dumpOut.write("=== Header Only ===\n")
      try:
         saveFileInfo = readSaveFileInfo(savFilename)
         dumpOut.write(f"Parsed Session Name: {saveFileInfo.sessionName}\n")
         dumpOut.write(f"Parsed Play Time: {round(saveFileInfo.playDurationInSeconds/60,1)} minutes\n")
         dumpOut.write(f"Parsed Save Date: {saveFileInfo.saveDatetime.strftime('%m/%d/%Y %I:%M:%S %p')}\n")

      except Exception as error:
         print(f"ERROR: {error}", file=sys.stderr)
         exit(1)
      dumpOut.write("\n=== Full File ===\n")
      try:
         parsedSave = readFullSaveFile(savFilename, decompressedOutputFilename)
         dumpOut.write("Successfully parsed save file\n\n")

         dumpOut.write(str(parsedSave.saveFileInfo))
         dumpOut.write("\nGrids:\n")
         for grid in parsedSave.grids:
            dumpOut.write(f"  {grid}\n")

         if PROGRESS_BAR_ENABLE_DUMP:
            progressBarTotal = 0
            for level in parsedSave.levels:
               progressBarTotal += len(level.actorAndComponentObjectHeaders)
               progressBarTotal += len(level.objects)
               if level.collectables1 is not None:
                  progressBarTotal += len(level.collectables1)
               progressBarTotal += len(level.collectables2)
            progressBar = ProgressBar(progressBarTotal, "      Dumping: ")
         dumpOut.write("\nLevels:\n")
         for level in parsedSave.levels:
            dumpOut.write(f"  Level: {level.levelName}\n")
            for actorOrComponentObjectHeader in level.actorAndComponentObjectHeaders:
               dumpOut.write(f"    {actorOrComponentObjectHeader}\n")
               if PROGRESS_BAR_ENABLE_DUMP:
                  progressBar.add()
            for object in level.objects:
               dumpOut.write(f"    {object}\n")
               if PROGRESS_BAR_ENABLE_DUMP:
                  progressBar.add()
            if level.collectables1 is not None:
               for collectable in level.collectables1:
                  dumpOut.write(f"    Collectable1: {collectable}\n")
                  if PROGRESS_BAR_ENABLE_DUMP:
                     progressBar.add()
            for collectable in level.collectables2:
               dumpOut.write(f"    Collectable2: {collectable}\n")
               if PROGRESS_BAR_ENABLE_DUMP:
                  progressBar.add()
         if PROGRESS_BAR_ENABLE_DUMP:
            progressBar.complete()

         dumpOut.write("\nDrop pod object references:\n")
         for msLevelPathName in parsedSave.dropPodObjectReferenceList:
            dumpOut.write(f"  {msLevelPathName}\n")

         dumpOut.write("\nAdditional object references:\n")
         for msLevelPathName in parsedSave.extraObjectReferenceList:
            dumpOut.write(f"  {msLevelPathName}\n")

         with open(somersloopOutputFilename, "w") as somersloopOut:
            somersloopOut.write("# Exported from Satisfactory\n")
            somersloopOut.write("SOMERSLOOPS = {\n")
            for level in parsedSave.levels:
               for actorOrComponentObjectHeader in level.actorAndComponentObjectHeaders:
                  if isinstance(actorOrComponentObjectHeader, ActorHeader):
                     if actorOrComponentObjectHeader.typePath == SOMERSLOOP:
                        # scale=(1.600000023841858, 1.600000023841858, 1.600000023841858)
                        somersloopOut.write(f'   "{actorOrComponentObjectHeader.instanceName}": ("{actorOrComponentObjectHeader.rootObject}", {actorOrComponentObjectHeader.rotation}, {actorOrComponentObjectHeader.position}),\n')
            somersloopOut.write("} # SOMERSLOOPS\n")

         with open(mercerSphereOutputFilename, "w") as mercerSphereOut:
            mercerSphereOut.write("# Exported from Satisfactory\n")
            mercerSphereOut.write("MERCER_SPHERES = {\n")
            for level in parsedSave.levels:
               for actorOrComponentObjectHeader in level.actorAndComponentObjectHeaders:
                  if isinstance(actorOrComponentObjectHeader, ActorHeader):
                     if actorOrComponentObjectHeader.typePath == MERCER_SPHERE:
                        # scale=(2.700000047683716, 2.6999998092651367, 2.6999998092651367)
                        mercerSphereOut.write(f'   "{actorOrComponentObjectHeader.instanceName}": ("{actorOrComponentObjectHeader.rootObject}", {actorOrComponentObjectHeader.rotation}, {actorOrComponentObjectHeader.position}),\n')
            mercerSphereOut.write("} # MERCER_SPHERES\n")
            mercerSphereOut.write("MERCER_SHRINES = {\n")
            for level in parsedSave.levels:
               for actorOrComponentObjectHeader in level.actorAndComponentObjectHeaders:
                  if isinstance(actorOrComponentObjectHeader, ActorHeader):
                     if actorOrComponentObjectHeader.typePath == MERCER_SHRINE:
                        # scale=(1.0, 1.0, 1.0) or (0.8999999761581421, 0.8999999761581421, 0.8999999761581421)
                        mercerSphereOut.write(f'   "{actorOrComponentObjectHeader.instanceName}": ("{actorOrComponentObjectHeader.rootObject}", {actorOrComponentObjectHeader.rotation}, {actorOrComponentObjectHeader.position}, {actorOrComponentObjectHeader.scale[1]}),\n')
            mercerSphereOut.write("} # MERCER_SHRINES\n")

         with open(slugOutputFilename, "w") as slugOut:

            numSlug = [0, 0, 0]
            for slugIdx in range(3):
               slugOut.write(f"POWER_SLUGS_{('BLUE', 'YELLOW', 'PURPLE')[slugIdx]} = " + "{\n")
               for level in parsedSave.levels:
                  for actorOrComponentObjectHeader in level.actorAndComponentObjectHeaders:
                     if isinstance(actorOrComponentObjectHeader, ActorHeader) and actorOrComponentObjectHeader.typePath == POWER_SLUG[slugIdx]:
                        slugOut.write(f'   "{actorOrComponentObjectHeader.instanceName}": {actorOrComponentObjectHeader.position},\n')
                        numSlug[slugIdx] += 1
               slugOut.write("}\n")
            slugOut.write(f"# Num slugs: {numSlug} exported from Satisfactory\n")

            for level in parsedSave.levels:
               if level.collectables1 is not None:
                  for collectable in level.collectables1:
                     if collectable.pathName.startswith("Persistent_Level:PersistentLevel.BP_Crystal"):
                        slugOut.write(f"COLLECTED: {collectable.pathName}\n")

         with open(droppedItemsOutputFilename, "w") as dropOut:
            items = {}
            for level in parsedSave.levels:
               for actorOrComponentObjectHeader in level.actorAndComponentObjectHeaders:
                  if isinstance(actorOrComponentObjectHeader, ActorHeader) and actorOrComponentObjectHeader.typePath == "/Script/FactoryGame.FGItemPickup_Spawnable":
                     items[actorOrComponentObjectHeader.instanceName] = actorOrComponentObjectHeader.position
            specificItems: dict[str, list] = {}
            for level in parsedSave.levels:
               for object in level.objects:
                  if object.instanceName in items:
                     pickupItems = getPropertyValue(object.properties, "mPickupItems")
                     if pickupItems is not None:
                        pickupItems = pickupItems[0]
                        item = getPropertyValue(pickupItems, "Item")
                        if item is not None:
                           item = item[0]
                           numItems = getPropertyValue(pickupItems, "NumItems")
                           if numItems is not None:
                              if item not in specificItems:
                                 specificItems[item] = []
                              specificItems[item].append([object.instanceName, numItems, items[object.instanceName]])
            dropOut.write("# Exported from Satisfactory\n")
            dropOut.write("FREE_DROPPED_ITEMS = {\n")
            for item in specificItems:
               dropOut.write(f'   "{item}": [ # {pathNameToReadableName(item)}\n')
               for (instanceName, quantity, location) in specificItems[item]:
                  dropOut.write(f'      ({quantity}, {location}, "{instanceName}"),\n')
               dropOut.write(f'      ],\n')
            dropOut.write("} # FREE_DROPPED_ITEMS\n")

         with open(crashSitesOutputFilename, "w") as csOut:
            csOut.write("# Exported from Satisfactory\n")
            csOut.write("CRASH_SITES = [\n")
            for level in parsedSave.levels:
               for actorOrComponentObjectHeader in level.actorAndComponentObjectHeaders:
                  if isinstance(actorOrComponentObjectHeader, ActorHeader):
                     if actorOrComponentObjectHeader.typePath == sav_data.data.CRASH_SITE:
                        csOut.write(f'   "{actorOrComponentObjectHeader.instanceName}", # {actorOrComponentObjectHeader.position}\n')
            csOut.write("] # CRASH_SITES\n")

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

   exit(0)
