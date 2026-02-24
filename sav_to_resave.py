#!/usr/bin/python3
# This file is part of the Satisfactory Save Parser distribution
#                                  (https://github.com/GreyHak/sat_sav_parse).
# Copyright (c) 2024-2026 GreyHak (github.com/GreyHak).
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

import sys
import struct
import zlib
import sav_parse

def addInt8(val):
   if isinstance(val, bytes):
      return struct.pack("<c", val)
   else:
      raise Exception(f"ERROR: Unsupported type passed to addInt8 {type(val)}")

def addUint8(val):
   if isinstance(val, int):
      return struct.pack("<B", val)
   else:
      raise Exception(f"ERROR: Unsupported type passed to addUint8 {type(val)}")

def addUint16(val):
   return struct.pack("<H", val)

def addInt32(val):
   return struct.pack("<i", val)

def addUint32(val):
   return struct.pack("<I", val)

def addInt64(val):
   return struct.pack("<q", val)

def addUint64(val):
   return struct.pack("<Q", val)

def addFloat(val):
   return struct.pack("<f", val)

def addDouble(val):
   return struct.pack("<d", val)

def addString(val):
   if len(val) == 0:
      return addInt32(0)
   try:
      return addInt32(len(val) + 1) + val.encode("ascii") + b"\0"
   except UnicodeEncodeError:
      return addInt32(-len(val)-1) + val.encode("utf-16")[2:] + b"\0\0"

def addSaveObjectVersionData(saveObjectVersionData):
   saveObjectVersionDataVersion, (packageFileVersion_FileVersionUE4, packageFileVersion_FileVersionUE5), licenseeVersion, (engineVersion_Major, engineVersion_Minor, engineVersion_Patch, engineVersion_Changelist, engineVersion_Branch), customVersionContainer = saveObjectVersionData

   data = bytearray()
   data.extend(addUint32(saveObjectVersionDataVersion))
   data.extend(addUint32(packageFileVersion_FileVersionUE4))
   data.extend(addUint32(packageFileVersion_FileVersionUE5))
   data.extend(addUint32(licenseeVersion))
   data.extend(addUint16(engineVersion_Major))
   data.extend(addUint16(engineVersion_Minor))
   data.extend(addUint16(engineVersion_Patch))
   data.extend(addUint32(engineVersion_Changelist))
   data.extend(addString(engineVersion_Branch))

   data.extend(addUint32(len(customVersionContainer)))
   for (keyUuidA, keyUuidB, version) in customVersionContainer:
      data.extend(addUint64(keyUuidA))
      data.extend(addUint64(keyUuidB))
      data.extend(addUint32(version))

   return data

def addObjectReference(objectReference):
   return addString(objectReference.levelName) + addString(objectReference.pathName)

def addTextProperty(textPropertyValue):
   dataTextProp = bytearray()
   if len(textPropertyValue) == 4 and textPropertyValue[1] == sav_parse.HistoryType.NONE.value:
      (flags, historyType, isTextCultureInvariant, s) = textPropertyValue
      dataTextProp.extend(addUint32(flags))
      dataTextProp.extend(addUint8(historyType))
      dataTextProp.extend(addUint32(isTextCultureInvariant))
      dataTextProp.extend(addString(s))
   elif len(textPropertyValue) == 5 and textPropertyValue[1] == sav_parse.HistoryType.BASE.value:
      (flags, historyType, namespace, key, value) = textPropertyValue
      dataTextProp.extend(addUint32(flags))
      dataTextProp.extend(addUint8(historyType))
      dataTextProp.extend(addString(namespace))
      dataTextProp.extend(addString(key))
      dataTextProp.extend(addString(value))
   elif len(textPropertyValue) == 5 and textPropertyValue[1] == sav_parse.HistoryType.ARGUMENT_FORMAT.value:
      (flags, historyType, uuid, format, args) = textPropertyValue
      dataTextProp.extend(addUint32(flags))
      dataTextProp.extend(addUint8(historyType))
      dataTextProp.extend(addUint32(8))
      dataTextProp.extend(addUint8(0))
      dataTextProp.extend(addUint32(1))
      dataTextProp.extend(addUint8(0))
      dataTextProp.extend(addString(uuid))
      dataTextProp.extend(addString(format))
      dataTextProp.extend(addUint32(len(args)))
      for (argName, argValue, argFlags) in args:
         dataTextProp.extend(addString(argName))
         dataTextProp.extend(addUint8(4))
         dataTextProp.extend(addUint32(argFlags))
         dataTextProp.extend(addUint8(255)) # historyType
         dataTextProp.extend(addUint32(1)) # isTextCultureInvariant
         dataTextProp.extend(addString(argValue))
   elif len(textPropertyValue) == 4 and textPropertyValue[1] == sav_parse.HistoryType.STRING_TABLE_ENTRY.value:
      (flags, historyType, tableId, textKey) = textPropertyValue
      dataTextProp.extend(addUint32(flags))
      dataTextProp.extend(addUint8(historyType))
      dataTextProp.extend(addString(tableId))
      dataTextProp.extend(addString(textKey))
   return dataTextProp

def addPackageName(packageNames):
   data = bytearray()
   packageNameFlag1 = len(packageNames) > 0
   data.extend(addUint32(packageNameFlag1))
   if packageNameFlag1:
      data.extend(addString(packageNames[0]))

      packageNameFlag2 = len(packageNames) > 1
      data.extend(addUint32(packageNameFlag2))
      if packageNameFlag2:
         data.extend(addString(packageNames[1]))
         data.extend(addString(packageNames[2]))
   return data

def addProperties(currentEntitySaveVersion, properties, propertyTypes):
   data = bytearray()

   for propertyIdx in range(len(properties)):

      (propertyName, propertyValue) = properties[propertyIdx]
      data.extend(addString(propertyName))

      retainedPropertyType = list(propertyTypes[propertyIdx]).copy()
      propertyNameFromType = retainedPropertyType.pop(0)
      if propertyNameFromType != propertyName:
         raise Exception(f"ERROR: Mismatch type/value property name: '{propertyNameFromType}' != '{propertyName}'")

      propertyType = retainedPropertyType.pop(0)
      data.extend(addString(propertyType))

      if currentEntitySaveVersion >= 53:
         propertyHeaderTypeA = retainedPropertyType.pop(0)
         data.extend(addUint32(propertyHeaderTypeA))
         if propertyHeaderTypeA == 1:
            if propertyType == "ArrayProperty":
               arrayType = retainedPropertyType.pop(0)
               data.extend(addString(arrayType))
               propertyHeaderTypeB = retainedPropertyType.pop(0)
               data.extend(addUint32(propertyHeaderTypeB))
               if propertyHeaderTypeB == 1:
                  structureSubType = retainedPropertyType.pop(0)
                  data.extend(addString(structureSubType))
                  data.extend(addPackageName(retainedPropertyType.pop(0)))
               elif propertyHeaderTypeB == 2:
                  enumName = retainedPropertyType.pop(0)
                  data.extend(addString(enumName))
                  data.extend(addPackageName(retainedPropertyType.pop(0)))
                  data.extend(addString("ByteProperty"))
                  data.extend(addUint32(0))
            elif propertyType == "ByteProperty":
               enumName = retainedPropertyType.pop(0)
               data.extend(addString(enumName))
               data.extend(addPackageName(retainedPropertyType.pop(0)))
            elif propertyType == "SetProperty":
               setType = retainedPropertyType.pop(0)
               data.extend(addString(setType))
               data.extend(addPackageName(retainedPropertyType.pop(0)))
            elif propertyType == "StructProperty":
               structPropertyType = retainedPropertyType.pop(0)
               data.extend(addString(structPropertyType))
               data.extend(addPackageName(retainedPropertyType.pop(0)))
         elif propertyHeaderTypeA == 2:
            if propertyType == "EnumProperty":
               enumName = retainedPropertyType.pop(0)
               data.extend(addString(enumName))
               data.extend(addPackageName(retainedPropertyType.pop(0)))
               data.extend(addString("ByteProperty"))
               data.extend(addUint32(0))
            elif propertyType == "MapProperty":
               keyType = retainedPropertyType.pop(0)
               data.extend(addString(keyType))
               keyPackageNames = retainedPropertyType.pop(0)
               hasKeyTypeName = keyPackageNames is not None
               data.extend(addUint32(hasKeyTypeName))
               if hasKeyTypeName:
                  data.extend(addString("IntVector"))
                  data.extend(addPackageName(keyPackageNames))
               valueType = retainedPropertyType.pop(0)
               data.extend(addString(valueType))
               valueName = retainedPropertyType.pop(0)
               hasValueTypeName = valueName is not None
               data.extend(addUint32(hasValueTypeName))
               if hasValueTypeName:
                  data.extend(addString(valueName))
                  data.extend(addPackageName(retainedPropertyType.pop(0)))

      if currentEntitySaveVersion < 53:
         propertyIndex = retainedPropertyType.pop(0)

      dataProp = bytearray()
      propertyStartSize = 0

      match propertyType:
         case "BoolProperty":
            dataProp.extend(addUint8(propertyValue))
            if currentEntitySaveVersion < 53:
               dataProp.extend(addUint8(0))
            propertyStartSize = len(dataProp)
         case "ByteProperty":
            enumName = propertyValue[0]
            if currentEntitySaveVersion < 53:
               dataProp.extend(addString(enumName))
            dataProp.extend(addUint8(0))
            propertyStartSize = len(dataProp)
            if enumName is None or enumName == "None":
               dataProp.extend(addUint8(propertyValue[1]))
            else:
               dataProp.extend(addString(propertyValue[1]))
         case "Int8Property":
            dataProp.extend(addUint8(0))
            propertyStartSize = len(dataProp)
            dataProp.extend(addInt8(propertyValue))
         case "IntProperty":
            dataProp.extend(addUint8(0))
            propertyStartSize = len(dataProp)
            dataProp.extend(addInt32(propertyValue))
         case "UInt32Property":
            dataProp.extend(addUint8(0))
            propertyStartSize = len(dataProp)
            dataProp.extend(addUint32(propertyValue))
         case "Int64Property":
            dataProp.extend(addUint8(0))
            propertyStartSize = len(dataProp)
            dataProp.extend(addInt64(propertyValue))
         case "FloatProperty":
            dataProp.extend(addUint8(0))
            propertyStartSize = len(dataProp)
            dataProp.extend(addFloat(propertyValue))
         case "DoubleProperty":
            dataProp.extend(addUint8(0))
            propertyStartSize = len(dataProp)
            dataProp.extend(addDouble(propertyValue))
         case "EnumProperty":
            if currentEntitySaveVersion < 53:
               dataProp.extend(addString(propertyValue[0]))
            dataProp.extend(addUint8(0))
            propertyStartSize = len(dataProp)
            dataProp.extend(addString(propertyValue[1]))
         case propertyType if propertyType in ("StrProperty", "NameProperty"):
            dataProp.extend(addUint8(0))
            propertyStartSize = len(dataProp)
            dataProp.extend(addString(propertyValue))
         case "TextProperty":
            dataProp.extend(addUint8(0))
            propertyStartSize = len(dataProp)
            dataProp.extend(addTextProperty(propertyValue))
         case "SetProperty":
            (setType, values) = propertyValue
            if currentEntitySaveVersion < 53:
               dataProp.extend(addString(setType))
            zeroOrEight = retainedPropertyType.pop(0)
            dataProp.extend(addUint8(zeroOrEight))
            propertyStartSize = len(dataProp)
            dataProp.extend(addUint32(0))
            dataProp.extend(addUint32(len(values)))
            if setType == "UInt32Property":
               for value in values:
                  dataProp.extend(addUint32(value))
            elif setType == "StructProperty":
               for (value1, value2) in values:
                  dataProp.extend(addUint64(value1))
                  dataProp.extend(addUint64(value2))
            elif setType == "ObjectProperty":
               for value in values:
                  dataProp.extend(addObjectReference(value))
            else:
               raise Exception(f"ERROR: Unknown SetProperty type '{setType}'")
         case "ObjectProperty":
            dataProp.extend(addUint8(0))
            propertyStartSize = len(dataProp)
            dataProp.extend(addObjectReference(propertyValue))
         case "SoftObjectProperty":
            (levelPathName, value) = propertyValue
            dataProp.extend(addUint8(0))
            propertyStartSize = len(dataProp)
            dataProp.extend(addObjectReference(levelPathName))
            dataProp.extend(addUint32(value))
         case "ArrayProperty":
            if currentEntitySaveVersion < 53:
               arrayType = retainedPropertyType.pop(0)
               dataProp.extend(addString(arrayType))
            zeroOrEight = retainedPropertyType.pop(0)
            dataProp.extend(addUint8(zeroOrEight))
            propertyStartSize = len(dataProp)
            dataProp.extend(addUint32(len(propertyValue)))
            match arrayType:
               case "IntProperty":
                  for value in propertyValue:
                     dataProp.extend(addInt32(value))
               case "Int64Property":
                  for value in propertyValue:
                     dataProp.extend(addInt64(value))
               case "ByteProperty":
                  for value in propertyValue:
                     dataProp.extend(addUint8(value))
               case "FloatProperty":
                  for value in propertyValue:
                     dataProp.extend(addFloat(value))
               case "DoubleProperty": # Only observed in modded save
                  for value in propertyValue:
                     dataProp.extend(addDouble(value))
               case arrayType if arrayType in ("StrProperty", "EnumProperty"):
                  for value in propertyValue:
                     dataProp.extend(addString(value))
               case "SoftObjectProperty":
                  for (levelPathName, value) in propertyValue:
                     dataProp.extend(addObjectReference(levelPathName))
                     dataProp.extend(addUint32(value))
               case arrayType if arrayType in ("InterfaceProperty", "ObjectProperty"):
                  for value in propertyValue:
                     dataProp.extend(addObjectReference(value))
               case "TextProperty": # Only observed in modded save
                  for value in propertyValue:
                     dataProp.extend(addTextProperty(value))
               case "StructProperty":
                  if currentEntitySaveVersion < 53:
                     structureSubType = retainedPropertyType.pop(0)
                  dataStruct = bytearray()
                  match structureSubType:
                     case "LinearColor":
                        for value in propertyValue:
                           (r, g, b, a) = value
                           dataStruct.extend(addFloat(r))
                           dataStruct.extend(addFloat(g))
                           dataStruct.extend(addFloat(b))
                           dataStruct.extend(addFloat(a))
                     case "Vector":
                        for value in propertyValue:
                           (x, y, z) = value
                           dataStruct.extend(addDouble(x))
                           dataStruct.extend(addDouble(y))
                           dataStruct.extend(addDouble(z))
                     case structureSubType if structureSubType in (
                           "ConnectionData",             # Only observed in modded save
                           "BuildingConnection",         # Only observed in modded save
                           "STRUCT_ProgElevator_Floor",  # Only observed in modded save
                           "Struct_InputConfiguration"): # Only observed in modded save
                        dataStruct.extend(propertyValue[0])
                     case "LocalUserNetIdBundle":
                        for value in propertyValue:
                           (prop, propTypes) = value
                           dataStruct.extend(addProperties(currentEntitySaveVersion, prop, propTypes))
                     case structureSubType if structureSubType in (
                           "BlueprintCategoryRecord",
                           "BlueprintSubCategoryRecord",
                           "CachedPlayerInfo",
                           "CachedPlayerPlatformInfo",
                           "DroneTripInformation",
                           "ElevatorFloorStopInfo",
                           "FactoryCustomizationColorSlot",
                           "FeetOffset",
                           "FGCachedConnectedWire", # SatisFaction_20240921-092707.sav
                           "FGDroneFuelRuntimeData",
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
                           "SpawnData",
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
                        for value in propertyValue:
                           (prop, propTypes) = value
                           dataStruct.extend(addProperties(currentEntitySaveVersion, prop, propTypes))
                     case _:
                        raise Exception(f"ERROR: Unknown structureSubType '{structureSubType}'")

                  if currentEntitySaveVersion < 53:
                     dataProp.extend(addString(propertyName))
                     dataProp.extend(addString("StructProperty"))
                     dataProp.extend(addUint32(len(dataStruct)))
                     dataProp.extend(addUint32(0))
                     dataProp.extend(addString(structureSubType))
                     uuid = retainedPropertyType.pop(0)
                     if uuid is None:
                        uuid = bytearray(17)
                     dataProp.extend(uuid)
                  dataProp.extend(dataStruct)
               case _:
                  raise Exception(f"ERROR: Unknown ArrayProperty type '{arrayType}'")
         case "StructProperty":
            if currentEntitySaveVersion < 53:
               structPropertyType = retainedPropertyType.pop(0)
               dataProp.extend(addString(structPropertyType))
               structUuid = retainedPropertyType.pop(0)
               if structUuid is None:
                  structUuid1 = structUuid2 = 0
               else:
                  (structUuid1, structUuid2) = structUuid
               dataProp.extend(addUint64(structUuid1))
               dataProp.extend(addUint64(structUuid2))
            stuctIndex1 = retainedPropertyType.pop(0)
            dataProp.extend(addUint8(stuctIndex1))
            if stuctIndex1 == 9:
               stuctIndex2 = retainedPropertyType.pop(0)
               dataProp.extend(addUint32(stuctIndex2))
            propertyStartSize = len(dataProp)
            match structPropertyType:
               case "InventoryItem":
                  (itemName, itemProperties) = propertyValue
                  dataProp.extend(addUint32(0))
                  dataProp.extend(addString(itemName))
                  if itemProperties == 1:
                     dataProp.extend(addUint32(0))
                  elif itemProperties == 2:
                     dataProp.extend(addUint32(0))
                     dataProp.extend(addUint32(0))
                  else:
                     dataProp.extend(addUint32(1))
                     (typePath, prop, propTypes) = itemProperties
                     dataProp.extend(addUint32(0))
                     dataProp.extend(addString(typePath))
                     itemProp = bytearray()
                     itemProp.extend(addProperties(currentEntitySaveVersion, prop, propTypes))
                     dataProp.extend(addUint32(len(itemProp)))
                     dataProp.extend(itemProp)
               case "LinearColor":
                  (r, g, b, a) = propertyValue
                  dataProp.extend(addFloat(r))
                  dataProp.extend(addFloat(g))
                  dataProp.extend(addFloat(b))
                  dataProp.extend(addFloat(a))
               case "Vector":
                  (x, y, z) = propertyValue
                  dataProp.extend(addDouble(x))
                  dataProp.extend(addDouble(y))
                  dataProp.extend(addDouble(z))
               case "Quat":
                  (x, y, z, w) = propertyValue
                  dataProp.extend(addDouble(x))
                  dataProp.extend(addDouble(y))
                  dataProp.extend(addDouble(z))
                  dataProp.extend(addDouble(w))
               case "Box":
                  (minx, miny, minz, maxx, maxy, maxz, flag) = propertyValue
                  dataProp.extend(addDouble(minx))
                  dataProp.extend(addDouble(miny))
                  dataProp.extend(addDouble(minz))
                  dataProp.extend(addDouble(maxx))
                  dataProp.extend(addDouble(maxy))
                  dataProp.extend(addDouble(maxz))
                  dataProp.extend(addUint8(flag))
               case "FluidBox":
                  dataProp.extend(addFloat(propertyValue))
               case "RailroadTrackPosition":
                  (levelPathName, rtpOffset, forward) = propertyValue
                  dataProp.extend(addObjectReference(levelPathName))
                  dataProp.extend(addFloat(rtpOffset))
                  dataProp.extend(addFloat(forward))
               case "DateTime":
                  dataProp.extend(addInt64(propertyValue))
               case "ClientIdentityInfo":
                  (clientUuid, identities) = propertyValue
                  dataProp.extend(addString(clientUuid))
                  dataProp.extend(addUint32(len(identities)))
                  for (clientType, clientData) in identities:
                     dataProp.extend(addUint8(clientType))
                     dataProp.extend(addUint32(len(clientData)))
                     dataProp.extend(clientData)
               case structPropertyType if structPropertyType in (
                     "PlayerInfoHandle",
                     "UniqueNetIdRepl",
                     "Guid",                       # Only observed in modded save
                     "Rotator",                    # Only observed in modded save
                     "SignComponentEditorMetadata" # Only observed in modded save
                     ):
                  dataProp.extend(propertyValue)
               case structPropertyType if structPropertyType in (
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
                  (prop, propTypes) = propertyValue
                  dataProp.extend(addProperties(currentEntitySaveVersion, prop, propTypes))
               case _:
                  raise Exception(f"ERROR: Unknown structPropertyType '{structPropertyType}'")
         case "MapProperty":
            if currentEntitySaveVersion < 53:
               keyType = retainedPropertyType.pop(0)
               valueType = retainedPropertyType.pop(0)
               dataProp.extend(addString(keyType))
               dataProp.extend(addString(valueType))
            zeroOrEight = retainedPropertyType.pop(0)
            dataProp.extend(addUint8(zeroOrEight))
            propertyStartSize = len(dataProp)
            dataProp.extend(addUint32(0))
            dataProp.extend(addUint32(len(propertyValue)))
            if valueType == "StructProperty":
               propTypess = retainedPropertyType.pop(0)
            for mapIdx in range(len(propertyValue)):
               (mapKey, mapValue) = propertyValue[mapIdx]
               match keyType:
                  case "StructProperty":
                     (int1, int2, int3) = mapKey
                     dataProp.extend(addInt32(int1))
                     dataProp.extend(addInt32(int2))
                     dataProp.extend(addInt32(int3))
                  case "ObjectProperty":
                     dataProp.extend(addObjectReference(mapKey))
                  case "IntProperty":
                     dataProp.extend(addInt32(mapKey))
                  case "NameProperty":
                     dataProp.extend(addString(mapKey))
                  case "EnumProperty":
                     dataProp.extend(addString(mapKey))
                  case _:
                     raise Exception(f"ERROR: Unknown MapProperty keyType '{keyType}'")

               match valueType:
                  case "StructProperty":
                     dataProp.extend(addProperties(currentEntitySaveVersion, mapValue, propTypess[mapIdx]))
                  case "IntProperty":
                     dataProp.extend(addInt32(mapValue))
                  case "Int64Property":
                     dataProp.extend(addInt64(mapValue))
                  case "ByteProperty":
                     dataProp.extend(addUint8(mapValue))
                  case "DoubleProperty":
                     dataProp.extend(addDouble(mapValue)) # Only observed in modded save
                  case "ObjectProperty":
                     dataProp.extend(addObjectReference(mapValue))
                  case _:
                     raise Exception(f"ERROR: Unknown MapProperty valueType '{valueType}'")
         case _:
            raise Exception(f"ERROR: Unknown propertyType '{propertyType}'")

      data.extend(addUint32(len(dataProp) - propertyStartSize))
      if currentEntitySaveVersion < 53:
         data.extend(addUint32(propertyIndex))
      data.extend(dataProp)

   data.extend(addString("None"))

   return data

def addObject(headerSaveVersion, object, actorOrComponentObjectHeader):
   isActorFlag = object.actorReferenceAssociations is not None

   dataTrailing = bytearray()

   if isActorFlag:
      if actorOrComponentObjectHeader.typePath in sav_parse.CONVEYOR_BELTS:
         dataTrailing.extend(addUint32(len(object.actorSpecificInfo)))
         for (length, name, position) in object.actorSpecificInfo:
            dataTrailing.extend(addUint32(length))
            dataTrailing.extend(addString(name))
            dataTrailing.extend(addString(""))
            dataTrailing.extend(addString(""))
            dataTrailing.extend(addFloat(position))
      elif actorOrComponentObjectHeader.typePath in (
            "/Game/FactoryGame/-Shared/Blueprint/BP_GameMode.BP_GameMode_C",
            "/Game/FactoryGame/-Shared/Blueprint/BP_GameState.BP_GameState_C"):
         dataTrailing.extend(addUint32(len(object.actorSpecificInfo)))
         for objectReference in object.actorSpecificInfo:
            dataTrailing.extend(addObjectReference(objectReference))
      elif actorOrComponentObjectHeader.typePath == "/Game/FactoryGame/Character/Player/BP_PlayerState.BP_PlayerState_C":
         if isinstance(object.actorSpecificInfo, int):
            dataTrailing.extend(addUint8(object.actorSpecificInfo))
         elif isinstance(object.actorSpecificInfo, list):
            (clientType, clientData) = object.actorSpecificInfo
            dataTrailing.extend(addUint8(241))
            dataTrailing.extend(addUint8(clientType))
            dataTrailing.extend(addUint32(len(clientData)))
            dataTrailing.extend(clientData)
         elif isinstance(object.actorSpecificInfo, bytes):
            dataTrailing.extend(object.actorSpecificInfo)
         else:
            raise Exception(f"ERROR: Unexpected PlayerState actorSpecificInfo type '{type(object.actorSpecificInfo)}'")
      elif actorOrComponentObjectHeader.typePath == "/Game/FactoryGame/Buildable/Factory/DroneStation/BP_DroneTransport.BP_DroneTransport_C":
         dataTrailing.extend(object.actorSpecificInfo)
      elif actorOrComponentObjectHeader.typePath == "/Game/FactoryGame/-Shared/Blueprint/BP_CircuitSubsystem.BP_CircuitSubsystem_C":
         dataTrailing.extend(addUint32(len(object.actorSpecificInfo)))
         for (circuitId, circuitReference) in object.actorSpecificInfo:
            dataTrailing.extend(addUint32(circuitId))
            dataTrailing.extend(addObjectReference(circuitReference))
      elif actorOrComponentObjectHeader.typePath in (
            "/Game/FactoryGame/Buildable/Factory/PowerLine/Build_PowerLine.Build_PowerLine_C",
            "/Game/FactoryGame/Events/Christmas/Buildings/PowerLineLights/Build_XmassLightsLine.Build_XmassLightsLine_C"):
         (source, target) = object.actorSpecificInfo
         dataTrailing.extend(addObjectReference(source))
         dataTrailing.extend(addObjectReference(target))
      elif actorOrComponentObjectHeader.typePath in (
            "/Game/FactoryGame/Buildable/Vehicle/Train/Locomotive/BP_Locomotive.BP_Locomotive_C",
            "/Game/FactoryGame/Buildable/Vehicle/Train/Wagon/BP_FreightWagon.BP_FreightWagon_C"):
         (trainList, previous, next) = object.actorSpecificInfo
         dataTrailing.extend(addUint32(len(trainList)))
         for (name, trainData) in trainList:
            dataTrailing.extend(addString(name))
            dataTrailing.extend(trainData)
         dataTrailing.extend(addObjectReference(previous))
         dataTrailing.extend(addObjectReference(next))
      elif actorOrComponentObjectHeader.typePath in (
            "/Game/FactoryGame/Buildable/Vehicle/Cyberwagon/Testa_BP_WB.Testa_BP_WB_C",
            "/Game/FactoryGame/Buildable/Vehicle/Explorer/BP_Explorer.BP_Explorer_C",
            "/Game/FactoryGame/Buildable/Vehicle/Golfcart/BP_Golfcart.BP_Golfcart_C",
            "/Game/FactoryGame/Buildable/Vehicle/Tractor/BP_Tractor.BP_Tractor_C",
            "/Game/FactoryGame/Buildable/Vehicle/Truck/BP_Truck.BP_Truck_C"):
         dataTrailing.extend(addUint32(len(object.actorSpecificInfo)))
         for vehicle in object.actorSpecificInfo:
            dataTrailing.extend(addString(vehicle[0]))
            dataTrailing.extend(vehicle[1])
      elif actorOrComponentObjectHeader.typePath == "/Script/FactoryGame.FGLightweightBuildableSubsystem":
         lightweightVersion = object.actorSpecificInfo[0]
         dataTrailing.extend(addUint32(lightweightVersion))
         dataTrailing.extend(addUint32(len(object.actorSpecificInfo) - 1))
         for lightweightBuildable in object.actorSpecificInfo:
            if isinstance(lightweightBuildable, list):
               (buildItemPathName, lightweightBuildableInstances) = lightweightBuildable
               dataTrailing.extend(addUint32(0))
               dataTrailing.extend(addString(buildItemPathName))
               dataTrailing.extend(addUint32(len(lightweightBuildableInstances)))
               for (rotationQuaternion, position, swatchLevelPath, patternLevelPath, (primaryColor, secondaryColor), paintFinishLevelPath, patternRotation, recipeLevelPath, blueprintProxyLevelPath, lightweightDataProperty, serviceProvider, playerInfoTableIndex) in lightweightBuildableInstances:
                  for xyzw in rotationQuaternion:
                     dataTrailing.extend(addDouble(xyzw))
                  for xyz in position:
                     dataTrailing.extend(addDouble(xyz))
                  for scale in range(3):
                     dataTrailing.extend(addDouble(1.0))
                  dataTrailing.extend(addObjectReference(swatchLevelPath))
                  dataTrailing.extend(addString(""))
                  dataTrailing.extend(addString(""))
                  dataTrailing.extend(addObjectReference(patternLevelPath))
                  dataTrailing.extend(addString(""))
                  dataTrailing.extend(addString(""))
                  for component in primaryColor:
                     dataTrailing.extend(addFloat(component))
                  for component in secondaryColor:
                     dataTrailing.extend(addFloat(component))
                  dataTrailing.extend(addObjectReference(paintFinishLevelPath))
                  dataTrailing.extend(addUint8(patternRotation))
                  dataTrailing.extend(addObjectReference(recipeLevelPath))
                  dataTrailing.extend(addObjectReference(blueprintProxyLevelPath))
                  if lightweightVersion >= 2:
                     dataFlag = lightweightDataProperty is not None
                     dataTrailing.extend(addUint32(dataFlag))
                     if dataFlag:
                        dataTrailing.extend(addUint32(0))
                        dataTrailing.extend(addString("/Script/FactoryGame.BuildableBeamLightweightData"))
                        dataLightweightDataProperty = addProperties(headerSaveVersion, *lightweightDataProperty)
                        dataTrailing.extend(addUint32(len(dataLightweightDataProperty)))
                        dataTrailing.extend(dataLightweightDataProperty)
                     if lightweightVersion >= 3:
                        dataTrailing.extend(addUint8(serviceProvider))
                        dataTrailing.extend(addUint8(playerInfoTableIndex))
      elif actorOrComponentObjectHeader.typePath in (
             "/Script/FactoryGame.FGConveyorChainActor",
             "/Script/FactoryGame.FGConveyorChainActor_RepSizeNoCull",
             "/Script/FactoryGame.FGConveyorChainActor_RepSizeMedium",
             "/Script/FactoryGame.FGConveyorChainActor_RepSizeLarge",
             "/Script/FactoryGame.FGConveyorChainActor_RepSizeHuge"):
         (levelPathName_conveyorChainActor, chainBelts, chainItems, cuint32, maximumItems, chainLeadItemIndex, chainTailItemIndex) = object.actorSpecificInfo
         dataTrailing.extend(addObjectReference(chainBelts[0][0]))
         dataTrailing.extend(addObjectReference(chainBelts[-1][0]))
         dataTrailing.extend(addUint32(len(chainBelts)))
         for idx in range(len(chainBelts)):
            (levelPathName_belt, chainBeltElements, buint32a, buint32b, buint32c, beltLeadItemIndex, beltTailItemIndex) = chainBelts[idx]
            dataTrailing.extend(addObjectReference(levelPathName_conveyorChainActor))
            dataTrailing.extend(addObjectReference(levelPathName_belt))
            dataTrailing.extend(addUint32(len(chainBeltElements)))
            for element in chainBeltElements:
               for kdx in range(3):
                  for ldx in range(3):
                     dataTrailing.extend(addUint64(element[kdx][ldx]))
            dataTrailing.extend(addUint32(buint32a))
            dataTrailing.extend(addUint32(buint32b))
            dataTrailing.extend(addUint32(buint32c))
            dataTrailing.extend(addInt32(beltLeadItemIndex))
            dataTrailing.extend(addInt32(beltTailItemIndex))
            dataTrailing.extend(addUint32(idx))
         dataTrailing.extend(addUint32(cuint32))
         dataTrailing.extend(addInt32(maximumItems))
         dataTrailing.extend(addInt32(chainLeadItemIndex))
         dataTrailing.extend(addInt32(chainTailItemIndex))
         dataTrailing.extend(addUint32(len(chainItems)))
         for (itemPath, h) in chainItems:
            dataTrailing.extend(addUint32(0))
            dataTrailing.extend(addString(itemPath))
            dataTrailing.extend(addUint32(0))
            dataTrailing.extend(addUint32(h))
      elif actorOrComponentObjectHeader.typePath == "/Script/FactoryGame.FGItemPickup_Spawnable":
         if object.actorSpecificInfo:
            dataTrailing.extend(addUint32(0))
      elif actorOrComponentObjectHeader.typePath in ( # Only observed in modded save
            "/AB_CableMod/Cables_Heavy/Build_AB-PLHeavy-Cu.Build_AB-PLHeavy-Cu_C",
            "/FlexSplines/Conveyor/Build_Belt2.Build_Belt2_C",
            "/FlexSplines/PowerLine/Build_FlexPowerline.Build_FlexPowerline_C",
            "/Game/FactoryGame/Buildable/Vehicle/Golfcart/BP_GolfcartGold.BP_GolfcartGold_C",
            "/CharacterReplacer/Logic/SCS_CR_PlayerHook.SCS_CR_PlayerHook_C"):
         dataTrailing.extend(object.actorSpecificInfo)
   else:
      if actorOrComponentObjectHeader.className in (
            "/Script/FactoryGame.FGDroneMovementComponent",
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
         if object.actorSpecificInfo:
            dataTrailing.extend(addUint32(0))

   dataEntity = bytearray()

   if isActorFlag:
      (parentObjectReference, actorComponentReferences) = object.actorReferenceAssociations
      dataEntity.extend(addObjectReference(parentObjectReference))
      dataEntity.extend(addUint32(len(actorComponentReferences)))
      for actorComponentReference in actorComponentReferences:
         dataEntity.extend(addObjectReference(actorComponentReference))

   if object.objectGameVersion >= 53:
      dataEntity.extend(addUint8(0))
   dataEntity.extend(addProperties(object.objectGameVersion, object.properties, object.propertyTypes))
   dataEntity.extend(addUint32(0))

   data = bytearray()
   data.extend(addUint32(object.objectGameVersion))
   data.extend(addUint32(object.shouldMigrateObjectRefsToPersistentFlag))
   data.extend(addUint32(len(dataEntity)+len(dataTrailing)))
   data.extend(dataEntity)
   data.extend(dataTrailing)
   if object.objectGameVersion >= 53:
      data.extend(addUint32(0))
   return data

def addLevel(headerSaveVersion, level):
   #print(f"Level {level.levelName} with {len(level.actorAndComponentObjectHeaders)} actor/component headers and {len(level.objects)} objects.")

   dataOH = bytearray()
   #print(f"len(level.actorAndComponentObjectHeaders)=")
   dataOH.extend(addUint32(len(level.actorAndComponentObjectHeaders)))
   for actorOrComponentObjectHeader in level.actorAndComponentObjectHeaders:
      if isinstance(actorOrComponentObjectHeader, sav_parse.ActorHeader):
         #print(f"ActorHeader {actorOrComponentObjectHeader.typePath}")
         dataOH.extend(addUint32(1))
         dataOH.extend(addString(actorOrComponentObjectHeader.typePath))
         dataOH.extend(addString(actorOrComponentObjectHeader.rootObject))
         dataOH.extend(addString(actorOrComponentObjectHeader.instanceName))
         dataOH.extend(addUint32(actorOrComponentObjectHeader.flags))
         dataOH.extend(addUint32(actorOrComponentObjectHeader.needTransform))

         dataOH.extend(addFloat(actorOrComponentObjectHeader.rotation[0]))
         dataOH.extend(addFloat(actorOrComponentObjectHeader.rotation[1]))
         dataOH.extend(addFloat(actorOrComponentObjectHeader.rotation[2]))
         dataOH.extend(addFloat(actorOrComponentObjectHeader.rotation[3]))

         dataOH.extend(addFloat(actorOrComponentObjectHeader.position[0]))
         dataOH.extend(addFloat(actorOrComponentObjectHeader.position[1]))
         dataOH.extend(addFloat(actorOrComponentObjectHeader.position[2]))

         dataOH.extend(addFloat(actorOrComponentObjectHeader.scale[0]))
         dataOH.extend(addFloat(actorOrComponentObjectHeader.scale[1]))
         dataOH.extend(addFloat(actorOrComponentObjectHeader.scale[2]))

         dataOH.extend(addUint32(actorOrComponentObjectHeader.wasPlacedInLevel))

      else: # ComponentHeader
         #print(f"ComponentHeader {actorOrComponentObjectHeader.className}")
         dataOH.extend(addUint32(0))
         dataOH.extend(addString(actorOrComponentObjectHeader.className))
         dataOH.extend(addString(actorOrComponentObjectHeader.rootObject))
         dataOH.extend(addString(actorOrComponentObjectHeader.instanceName))
         dataOH.extend(addUint32(actorOrComponentObjectHeader.flags))
         dataOH.extend(addString(actorOrComponentObjectHeader.parentActorName))

   if level.levelPersistentFlag is not None:
      dataOH.extend(addUint32(level.levelPersistentFlag))
      if level.levelPersistentFlag:
         dataOH.extend(addString("Persistent_Level"))

   if level.collectables1 is not None:
      dataOH.extend(addUint32(len(level.collectables1)))
      for levelPathName in level.collectables1:
         dataOH.extend(addObjectReference(levelPathName))

   dataObj = bytearray()
   dataObj.extend(addUint32(len(level.objects)))
   for idx in range(len(level.objects)):
      dataObj.extend(addObject(headerSaveVersion, level.objects[idx], level.actorAndComponentObjectHeaders[idx]))

   data = bytearray()
   if level.levelName is not None: # levelName will be None for the last "persistent" level
      data.extend(addString(level.levelName))

   data.extend(addUint64(len(dataOH)))
   data.extend(dataOH)
   data.extend(addUint64(len(dataObj)))
   data.extend(dataObj)

   data.extend(addUint32(level.levelSaveVersion))

   if level.levelName is not None:
      data.extend(addUint32(len(level.collectables2)))
      for levelPathName in level.collectables2:
         data.extend(addObjectReference(levelPathName))

      if headerSaveVersion >= 53:
         hasSaveObjectVersionData = level.saveObjectVersionData is not None
         data.extend(addUint32(hasSaveObjectVersionData))
         if hasSaveObjectVersionData:
            data.extend(addSaveObjectVersionData(level.saveObjectVersionData))

   return data

def saveFile(parsedSave: sav_parse.ParsedSave, outFilename: str):

   data = bytearray()

   if parsedSave.persistentLevelSaveObjectVersionData is not None:
      data.extend(addSaveObjectVersionData(parsedSave.persistentLevelSaveObjectVersionData))

   data.extend(addUint32(len(parsedSave.partitions)))
   for partition in parsedSave.partitions:
      (partitionName, i, gridHex, partitionLevels) = partition
      data.extend(addString(partitionName))
      data.extend(addUint32(i))
      data.extend(addUint32(gridHex))
      data.extend(addUint32(len(partitionLevels)))
      for element in partitionLevels:
         (levelName, lhex) = element
         data.extend(addString(levelName))
         data.extend(addUint32(lhex))

   data.extend(addUint32(len(parsedSave.levels)-1))
   progressBar = sav_parse.ProgressBar(len(parsedSave.levels), "   Reencoding: ")
   for level in parsedSave.levels:
      data.extend(addLevel(parsedSave.saveFileInfo.saveVersion, level))
      progressBar.add()

   data.extend(addString(parsedSave.aLevelName))

   if parsedSave.aLevelName == "Persistent_Level":
      data.extend(addUint32(len(parsedSave.dropPodObjectReferenceList)))
      for objectReference in parsedSave.dropPodObjectReferenceList:
         data.extend(addObjectReference(objectReference))

      data.extend(addUint32(len(parsedSave.extraObjectReferenceList)))
      for objectReference in parsedSave.extraObjectReferenceList:
         data.extend(addObjectReference(objectReference))

   rdata = bytearray()
   rdata.extend(addUint64(len(data))) # Length doesn't include the length itself even if the length is called compressed data length and the length is itself compressed.
   rdata.extend(data)
   progressBar.complete()

   #with open(f"{outFilename}-raw.txt", "wb") as fout:
   #   fout.write(rdata)

   MAXIMUM_CHUNK_SIZE = 128 * 1024

   sdata = bytearray()
   sdata.extend(addUint32(parsedSave.saveFileInfo.saveHeaderType))
   sdata.extend(addUint32(parsedSave.saveFileInfo.saveVersion))

   sdata.extend(addUint32(parsedSave.saveFileInfo.buildVersion))
   sdata.extend(addString(parsedSave.saveFileInfo.saveName))
   sdata.extend(addString(parsedSave.saveFileInfo.mapName))
   sdata.extend(addString(parsedSave.saveFileInfo.mapOptions))
   sdata.extend(addString(parsedSave.saveFileInfo.sessionName))
   sdata.extend(addUint32(parsedSave.saveFileInfo.playDurationInSeconds))
   sdata.extend(addUint64(parsedSave.saveFileInfo.saveDateTimeInTicks))
   sdata.extend(addInt8(parsedSave.saveFileInfo.sessionVisibility))
   sdata.extend(addUint32(parsedSave.saveFileInfo.editorObjectVersion))
   sdata.extend(addString(parsedSave.saveFileInfo.modMetadata))
   sdata.extend(addUint32(parsedSave.saveFileInfo.isModdedSave))
   sdata.extend(addString(parsedSave.saveFileInfo.saveIdentifier))
   sdata.extend(addUint32(1))
   sdata.extend(addUint32(1))
   sdata.extend(addUint64(parsedSave.saveFileInfo.saveDataHash[0]))
   sdata.extend(addUint64(parsedSave.saveFileInfo.saveDataHash[1]))
   sdata.extend(addUint32(parsedSave.saveFileInfo.isCreativeModeEnabled))

   dataOffset = 0
   progressBar = sav_parse.ProgressBar(len(rdata), "  Compressing: ")
   while dataOffset < len(rdata):

      chunkSize = MAXIMUM_CHUNK_SIZE
      if dataOffset + chunkSize > len(rdata):
         chunkSize = len(rdata) - dataOffset

      cdata = zlib.compress(rdata[dataOffset:dataOffset+chunkSize])

      sdata.extend(addUint32(0x9e2a83c1))
      sdata.extend(addUint32(0x22222222))
      sdata.extend(addUint8(0))

      sdata.extend(addUint32(MAXIMUM_CHUNK_SIZE))
      sdata.extend(addUint32(0x03000000))
      sdata.extend(addUint64(len(cdata)))
      sdata.extend(addUint64(chunkSize))
      sdata.extend(addUint64(len(cdata)))
      sdata.extend(addUint64(chunkSize))
      sdata.extend(cdata)

      dataOffset += chunkSize
      progressBar.set(dataOffset)
   progressBar.complete()

   with open(outFilename, "wb") as fout:
      fout.write(sdata)

if __name__ == '__main__':

   if len(sys.argv) != 3:
      print("USAGE: sav_to_resave.py <input-file> <output-file>")
      exit(1)

   inFilename = sys.argv[1]
   outFilename = sys.argv[2]

   print("Parsing save file")
   parsedSave = sav_parse.readFullSaveFile(inFilename)

   print("Recreating save file")
   saveFile(parsedSave, outFilename)

   exit(0)
