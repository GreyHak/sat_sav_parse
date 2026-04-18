#!/usr/bin/env python3
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

import enum
import datetime
import json
import math
import os
import sys
import uuid

import sav_parse
import sav_to_resave
import sav_data.data

try:
   import sav_to_html
   from PIL import Image, ImageDraw, ImageFont
   pilAvailableFlag = True
except ModuleNotFoundError:
   pilAvailableFlag = False

VERIFY_CREATED_SAVE_FILES = False
USERNAME_FILENAME = "sav_cli_usernames.json"
CHECK_ITEMS_FOR_PLAYER_INVENTORY = False
UNCOLLECTED_MAP_MARKER_SCALE = 0.5
ENFORCE_MAP_MARKER_LIMIT = 250 # Critical for servers that will delete all map markers if above the limit.

DEFAULT_ICON_ID_FOR_NEW_CATEGORIES = sav_data.data.ICON_NAMES_TO_IDS["FICSIT Check Mark"]

PERSISTENT_LEVEL = "Persistent_Level"
WATER_EXTRACTOR_TYPE = "/Game/FactoryGame/Buildable/Factory/WaterPump/Build_WaterPump.Build_WaterPump_C"

def getBlankCategory(objectGameVersion: int, categoryName: str, iconId: int = -1) -> list:
   if objectGameVersion < 53:
      return [[['CategoryName', categoryName],
               ['IconID', iconId],
               ['MenuPriority', 0.0],
               ['IsUndefined', False],
               ['SubCategoryRecords',
                [[[['SubCategoryName', 'Undefined'],
                   ['MenuPriority', 0.0],
                   ['IsUndefined', ["None", 1]],
                   ['BlueprintNames', []]],
                  [['SubCategoryName', 'StrProperty', 0],
                   ['MenuPriority', 'FloatProperty', 0],
                   ['IsUndefined', 'ByteProperty', 0],
                   ['BlueprintNames', 'ArrayProperty', 0, 'StrProperty', 0]]]]]],
              [['CategoryName', 'StrProperty', 0],
               ['IconID', 'IntProperty', 0],
               ['MenuPriority', 'FloatProperty', 0],
               ['IsUndefined', 'BoolProperty', 0],
               ['SubCategoryRecords', 'ArrayProperty', 0, 'StructProperty', 0, 'BlueprintSubCategoryRecord', None]]]
   else:
      if iconId == -1:
         iconId = DEFAULT_ICON_ID_FOR_NEW_CATEGORIES
      return [[['CategoryName', categoryName],
               ['IconID', iconId],
               ['MenuPriority', 0.0],
               ['IsUndefined', 0],
               ['SubCategoryRecords',
                [[[['SubCategoryName', 'Undefined'],
                   ['MenuPriority', 0.0],
                   ['IsUndefined', [None, 0]],
                   ['BlueprintNames', []],
                   ['lastEditedBy', b'\x06\x00\x00\x00\x00']],
                  [['SubCategoryName', 'StrProperty', 0],
                   ['MenuPriority', 'FloatProperty', 0],
                   ['IsUndefined', 'ByteProperty', 0],
                   ['BlueprintNames', 'ArrayProperty', 1, 'StrProperty', 0, 0],
                   ['lastEditedBy', 'StructProperty', 1, 'PlayerInfoHandle', ['/Script/FactoryGame'], 8]]]]],
               ['lastEditedBy', b'\x06\x00\x00\x00\x00']],
              [['CategoryName', 'StrProperty', 0],
               ['IconID', 'IntProperty', 0],
               ['MenuPriority', 'FloatProperty', 0],
               ['IsUndefined', 'BoolProperty', 0],
               ['SubCategoryRecords', 'ArrayProperty', 1, 'StructProperty', 1, 'BlueprintSubCategoryRecord', ['/Script/FactoryGame'], 0],
               ['lastEditedBy', 'StructProperty', 1, 'PlayerInfoHandle', ['/Script/FactoryGame'], 8]]]

def getBlankSubcategory(objectGameVersion: int, subcategoryName: str) -> list:
   if objectGameVersion < 53:
      return [[['SubCategoryName', subcategoryName],
               ['MenuPriority', 0.0],
               ['IsUndefined', ["None", 1]],
               ['BlueprintNames', []]],
              [['SubCategoryName', 'StrProperty', 0],
               ['MenuPriority', 'FloatProperty', 0],
               ['IsUndefined', 'ByteProperty', 0],
               ['BlueprintNames', 'ArrayProperty', 0, 'StrProperty', 0]]]
   else:
      return [[['SubCategoryName', subcategoryName],
               ['MenuPriority', 0.0],
               ['IsUndefined', [None, 0]],
               ['BlueprintNames', []],
               ['lastEditedBy', b'\x06\x00\x00\x00\x00']],
              [['SubCategoryName', 'StrProperty', 0],
               ['MenuPriority', 'FloatProperty', 0],
               ['IsUndefined', 'ByteProperty', 0],
               ['BlueprintNames', 'ArrayProperty', 1, 'StrProperty', 0, 0],
               ['lastEditedBy', 'StructProperty', 1, 'PlayerInfoHandle', ['/Script/FactoryGame'], 8]]]

playerUsernames: dict[str, str] = {}

def getPlayerPaths(levels: list) -> list:
   playerPaths = [] # = (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath)

   playerStateInstances = []
   for level in levels:
      for actorOrComponentObjectHeader in level.actorAndComponentObjectHeaders:
         # "/Game/FactoryGame/Character/Player/BP_PlayerState.BP_PlayerState_C" leads to ShoppingListComponent, FGPlayerHotbar_*
         # This gives the "mOwnedPawn" property which gives the Char_Player_C.  These are different numbers.
         # "/Game/FactoryGame/Character/Player/Char_Player.Char_Player_C" leads to BodySlot, HeadSlot, HealthComponent, LegsSlot, BackSlot, ArmSlot, inventory
         if isinstance(actorOrComponentObjectHeader, sav_parse.ActorHeader) and actorOrComponentObjectHeader.typePath == "/Game/FactoryGame/Character/Player/BP_PlayerState.BP_PlayerState_C":
            playerStateInstances.append(actorOrComponentObjectHeader.instanceName)

   playerCharacterInstances = {} # Looked up by playerCharacter for the playerState value
   for level in levels:
      for object in level.objects:
         if object.instanceName in playerStateInstances:
            # mPlayerHotbars, mCurrentHotbarIndex, mBuildableSubCategoryDefaultMatDesc, mMaterialSubCategoryDefaultMatDesc, mNewRecipes, mPlayerRules, mOwnedPawn,
            # mHasReceivedInitialItems, mVisitedAreas, mCustomColorData, mRememberedFirstTimeEquipmentClasses, mCollapsedMapCategories, mNumObservedInventorySlots,
            # mShoppingListComponent, mOpenedWidgetsPersistent, mPlayerSpecificSchematics
            ownedPawn = sav_parse.getPropertyValue(object.properties, "mOwnedPawn")
            if ownedPawn is not None:
               playerHotbars = sav_parse.getPropertyValue(object.properties, "mPlayerHotbars")
               if playerHotbars is not None:
                  playerCharacterInstances[ownedPawn.pathName] = (object.instanceName)

   for level in levels:
      for object in level.objects:
         if object.instanceName in playerCharacterInstances:
            inventory = sav_parse.getPropertyValue(object.properties, "mInventory")
            if inventory is not None:
               armsEquipmentSlot = sav_parse.getPropertyValue(object.properties, "mArmsEquipmentSlot")
               if armsEquipmentSlot is not None:
                  backEquipmentSlot = sav_parse.getPropertyValue(object.properties, "mBackEquipmentSlot")
                  if backEquipmentSlot is not None:
                     legsEquipmentSlot = sav_parse.getPropertyValue(object.properties, "mLegsEquipmentSlot")
                     if legsEquipmentSlot is not None:
                        headEquipmentSlot = sav_parse.getPropertyValue(object.properties, "mHeadEquipmentSlot")
                        if headEquipmentSlot is not None:
                           bodyEquipmentSlot = sav_parse.getPropertyValue(object.properties, "mBodyEquipmentSlot")
                           if bodyEquipmentSlot is not None:
                              healthComponent = sav_parse.getPropertyValue(object.properties, "mHealthComponent")
                              if healthComponent is not None:
                                 (playerStateInstanceName) = playerCharacterInstances[object.instanceName]
                                 playerPaths.append((playerStateInstanceName, object.instanceName, inventory.pathName, armsEquipmentSlot.pathName, backEquipmentSlot.pathName, legsEquipmentSlot.pathName, headEquipmentSlot.pathName, bodyEquipmentSlot.pathName, healthComponent.pathName))

   return playerPaths

def getPlayerName(levels: list, playerCharacter: str) -> str | None:
   global playerUsernames
   loc = playerCharacter.rfind("_")
   playerId = playerCharacter[loc+1:]
   if playerId in playerUsernames:
      return playerUsernames[playerId]

   for level in levels:
      for object in level.objects:
         if object.instanceName == playerCharacter:
            cachedPlayerName = sav_parse.getPropertyValue(object.properties, "mCachedPlayerName")
            if cachedPlayerName is not None:
               return cachedPlayerName
   return None

def characterPlayerMatch(characterPlayer: str, playerId: str, levels: dict[dict]) -> bool:
   return characterPlayer == f"Persistent_Level:PersistentLevel.Char_Player_C_{playerId}" or playerId == getPlayerName(levels, characterPlayer)

def orderBlueprintCategoryMenuPriorities(blueprintCategoryRecords) -> None:
   for categoryIdx in range(len(blueprintCategoryRecords)):
      category = blueprintCategoryRecords[categoryIdx]
      for propertyIdx in range(len(category[0])):
         if category[0][propertyIdx][0] == "MenuPriority":
            # Must preserve the same propertyIdx because the property type is at this index
            category[0][propertyIdx] = [category[0][propertyIdx][0], float(categoryIdx)]
      subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
      if subCategoryRecords is not None:
         for subcategoryIdx in range(len(subCategoryRecords)):
            subcategory = subCategoryRecords[subcategoryIdx]
            for propertyIdx in range(len(subcategory[0])):
               if subcategory[0][propertyIdx][0] == "MenuPriority":
                  # Must preserve the same propertyIdx because the property type is at this index
                  subcategory[0][propertyIdx] = [subcategory[0][propertyIdx][0], float(subcategoryIdx)]

# Converts an sRGB component in hex to a luminance component (a linear measure of light)
#def hexToLc(channel):
#   channel = int(channel, 16)
#   channel = channel / 255
#   if channel <= 0:
#      return 0
#   if channel >= 1:
#      return 1
#   if channel < 0.04045:
#      return channel / 12.92
#   return pow((channel + 0.055) / 1.055, 2.4)

# Converts a luminance component (a linear measure of light) an sRGB component from 0 to 1
def lcToSRGBFloat(linearCol) -> float:
   if linearCol <= 0.0031308:
      return linearCol * 12.92
   else:
      return pow(abs(linearCol), 1.0/2.4) * 1.055 - 0.055

# Converts a luminance component (a linear measure of light) an sRGB component from 0 to 255
def lcToSRGBInt(linearCol) -> int:
   return max(0, min(255, round(lcToSRGBFloat(linearCol) * 255)))

def lcTupleToSrgbHex(linearCTuple) -> str:
   srgb = ""
   for i in range(3):
      srgb += "{:x}".format(lcToSRGBInt(linearCTuple[i])).zfill(2)
   return srgb

def radiansToDegrees(radians) -> float:
   return radians / math.pi * 180

def degreesToRadians(degrees) -> float:
   return degrees * math.pi / 180

# Credit to Addison Sears-Collins
# From https://automaticaddison.com/how-to-convert-a-quaternion-into-euler-angles-in-python/
def quaternionToEuler(quaternion):
   (x, y, z, w) = quaternion
   t0 = +2.0 * (w * x + y * z)
   t1 = +1.0 - 2.0 * (x * x + y * y)
   roll_x = math.atan2(t0, t1)

   t2 = +2.0 * (w * y - z * x)
   t2 = +1.0 if t2 > +1.0 else t2
   t2 = -1.0 if t2 < -1.0 else t2
   pitch_y = math.asin(t2)

   t3 = +2.0 * (w * z + x * y)
   t4 = +1.0 - 2.0 * (y * y + z * z)
   yaw_z = math.atan2(t3, t4)

   return [roll_x, pitch_y, yaw_z] # in radians

# Credit to Addison Sears-Collins
# From https://automaticaddison.com/how-to-convert-euler-angles-to-quaternions-using-python/
def eulerToQuaternion(euler):
   (roll, pitch, yaw) = euler
   qx = math.sin(roll/2) * math.cos(pitch/2) * math.cos(yaw/2) - math.cos(roll/2) * math.sin(pitch/2) * math.sin(yaw/2)
   qy = math.cos(roll/2) * math.sin(pitch/2) * math.cos(yaw/2) + math.sin(roll/2) * math.cos(pitch/2) * math.sin(yaw/2)
   qz = math.cos(roll/2) * math.cos(pitch/2) * math.sin(yaw/2) - math.sin(roll/2) * math.sin(pitch/2) * math.cos(yaw/2)
   qw = math.cos(roll/2) * math.cos(pitch/2) * math.cos(yaw/2) + math.sin(roll/2) * math.sin(pitch/2) * math.sin(yaw/2)
   return (qx, qy, qz, qw)

def toJSON(object):
   if object is None or isinstance(object, (str, int, float, bool, complex)):
      return object

   if isinstance(object, bytes):
      return {"jsonhexstr": object.hex()}

   if isinstance(object, datetime.datetime):
      return object.strftime('%m/%d/%Y %I:%M:%S %p')

   if isinstance(object, (tuple, list)):
      value = []
      for element in object:
         value.append(toJSON(element))
      return value

   if isinstance(object, dict):
      value = {}
      for key in object:
         value[key] = toJSON(object[key])
      return value

   if isinstance(object, sav_parse.Object):
      araData = None
      if object.actorReferenceAssociations is not None:
         (parentObjectReference, actorComponentReferences) = object.actorReferenceAssociations
         acrData = []
         for actorComponentReference in actorComponentReferences:
            acrData.append(toJSON(actorComponentReference))
         araData = {"parentObjectReference": toJSON(parentObjectReference), "actorComponentReferences": acrData}
      return {"instanceName": object.instanceName,
              "objectGameVersion": object.objectGameVersion,
              "smortpFlag": object.shouldMigrateObjectRefsToPersistentFlag,
              "actorReferenceAssociations": araData,
              "properties": toJSON(object.properties),
              "propertyTypes": toJSON(object.propertyTypes),
              "actorSpecificInfo": toJSON(object.actorSpecificInfo),
              "perObjectVersionData": toJSON(object.perObjectVersionData)}

   jdata = {}
   for element in object.__dict__:
      jdata[element] = toJSON(object.__dict__[element])
   return jdata

def fromJSON(object):
   if object is None or isinstance(object, (str, int, float, bool, complex)):
      return object

   if isinstance(object, dict) and len(object) == 1 and "jsonhexstr" in object:
      return bytes.fromhex(object["jsonhexstr"])

   if isinstance(object, dict) and len(object) == 2 and "levelName" in object and "pathName" in object:
      objectReference = sav_parse.ObjectReference(object["levelName"], object["pathName"])
      return objectReference

   if isinstance(object, (tuple, list)):
      value = []
      for element in object:
         value.append(fromJSON(element))
      return value

   print(object)
   return None

def addSomersloop(levels, targetPathName: str) -> bool:
   # For those items present in (both) collectables1 and collectables2, remove those,
   # and replace the original ActorHeader and Object.  Nothing unique is saved in the Object.

   for level in levels:
      if level.collectables1 is not None:
         for collectable in level.collectables1:
            if collectable.pathName == targetPathName:
               level.collectables1.remove(collectable)
               print(f"Clearing removal of {collectable.pathName}")
               break
      for collectable in level.collectables2:
         if collectable.pathName == targetPathName:
            level.collectables2.remove(collectable)

            instanceName = collectable.pathName
            (rootObject, rotation, position, details) = sav_data.somersloop.SOMERSLOOPS[collectable.pathName]

            newActor = sav_parse.ActorHeader()
            newActor.typePath = sav_parse.SOMERSLOOP
            newActor.rootObject = rootObject
            newActor.instanceName = instanceName
            newActor.flags = 0
            newActor.needTransform = False
            newActor.rotation = list(rotation)
            newActor.position = list(position)
            newActor.scale = [1.600000023841858, 1.600000023841858, 1.600000023841858]
            newActor.wasPlacedInLevel = True
            level.actorAndComponentObjectHeaders.append(newActor)

            newObject = sav_parse.Object()
            newObject.instanceName = instanceName
            newObject.objectGameVersion = parsedSave.saveFileInfo.saveVersion
            newObject.shouldMigrateObjectRefsToPersistentFlag = False
            nullParentObjectReference = sav_parse.ObjectReference()
            newObject.actorReferenceAssociations = [nullParentObjectReference, []]
            newObject.properties    = []
            newObject.propertyTypes = []
            newObject.actorSpecificInfo = None
            newObject.perObjectVersionData = None
            level.objects.append(newObject)

            print(f"Restored Somersloop {instanceName} at {position}")
            return True

   return False

def addMercerSphere(levels, targetPathName: str) -> bool:
   # For those items present in (both) collectables1 and collectables2, remove those,
   # and replace the original ActorHeader and Object.  Nothing unique is saved in the Object.

   for level in levels:
      if level.collectables1 is not None:
         for collectable in level.collectables1:
            if collectable.pathName == targetPathName:
               level.collectables1.remove(collectable)
               print(f"Clearing removal of sphere {collectable.pathName}")
               break

      for collectable in level.collectables2:
         if collectable.pathName == targetPathName:
            level.collectables2.remove(collectable)

            instanceName = collectable.pathName
            (rootObject, rotation, position, details) = sav_data.mercerSphere.MERCER_SPHERES[collectable.pathName]

            newActor = sav_parse.ActorHeader()
            newActor.typePath = sav_parse.MERCER_SPHERE
            newActor.rootObject = rootObject
            newActor.instanceName = instanceName
            newActor.flags = 0
            newActor.needTransform = False
            newActor.rotation = list(rotation)
            newActor.position = list(position)
            newActor.scale = [2.700000047683716, 2.6999998092651367, 2.6999998092651367]
            newActor.wasPlacedInLevel = True
            level.actorAndComponentObjectHeaders.append(newActor)

            newObject = sav_parse.Object()
            newObject.instanceName = instanceName
            newObject.objectGameVersion = parsedSave.saveFileInfo.saveVersion
            newObject.shouldMigrateObjectRefsToPersistentFlag = False
            nullParentObjectReference = sav_parse.ObjectReference()
            newObject.actorReferenceAssociations = [nullParentObjectReference, []]
            newObject.properties    = []
            newObject.propertyTypes = []
            newObject.actorSpecificInfo = None
            newObject.perObjectVersionData = None
            level.objects.append(newObject)

            print(f"Restored Mercer Sphere {instanceName} at {position}")
            return True

   return False

def addMercerShrine(levels, targetPathName: str) -> bool:
   # For those items present in (both) collectables1 and collectables2, remove those,
   # and replace the original ActorHeader and Object.  Nothing unique is saved in the Object.

   for level in levels:
      if level.collectables1 is not None:
         for collectable in level.collectables1:
            if collectable.pathName == targetPathName:
               level.collectables1.remove(collectable)
               print(f"Clearing removal of shrine {collectable.pathName}")
               break

      for collectable in level.collectables2:
         if collectable.pathName == targetPathName:
            level.collectables2.remove(collectable)

            # This loop is here because the same entry might be present multiple
            #   times.  Is this an error?  It was observed when a save from
            #   v1.0 without the duplication was opened/resaved in v1.1.1.6.
            for duplicate in level.collectables2:
               if duplicate.pathName == targetPathName:
                  print(f"Removing duplicate removed entry for {targetPathName}")
                  level.collectables2.remove(duplicate)

            instanceName = collectable.pathName
            (rootObject, rotation, position, scale) = sav_data.mercerSphere.MERCER_SHRINES[collectable.pathName]

            newActor = sav_parse.ActorHeader()
            newActor.typePath = sav_parse.MERCER_SHRINE
            newActor.rootObject = rootObject
            newActor.instanceName = instanceName
            newActor.flags = 0
            newActor.needTransform = False
            newActor.rotation = list(rotation)
            newActor.position = list(position)
            newActor.scale = [scale, scale, scale]
            newActor.wasPlacedInLevel = True
            level.actorAndComponentObjectHeaders.append(newActor)

            newObject = sav_parse.Object()
            newObject.instanceName = instanceName
            newObject.objectGameVersion = parsedSave.saveFileInfo.saveVersion
            newObject.shouldMigrateObjectRefsToPersistentFlag = False
            nullParentObjectReference = sav_parse.ObjectReference()
            newObject.actorReferenceAssociations = [nullParentObjectReference, []]
            newObject.properties    = []
            newObject.propertyTypes = []
            newObject.actorSpecificInfo = None
            newObject.perObjectVersionData = None
            level.objects.append(newObject)

            print(f"Restored Mercer Shrine {instanceName} at {position}")
            return True

   return False

def removeInstance(levels: list, humanReadableName: str, rootObject, targetInstanceName: str, position = None) -> bool:

   removedObjectCollectionReference = sav_parse.ObjectReference(rootObject, targetInstanceName)

   for level in levels:
      for actorOrComponentObjectHeader in level.actorAndComponentObjectHeaders:
         if actorOrComponentObjectHeader.instanceName == targetInstanceName:
            level.actorAndComponentObjectHeaders.remove(actorOrComponentObjectHeader)
            for object in level.objects:
               if object.instanceName == targetInstanceName:
                  level.objects.remove(object)
                  if level.collectables1 is None:
                     level.collectables1 = []
                  level.collectables1.append(removedObjectCollectionReference)
                  level.collectables2.append(removedObjectCollectionReference)
                  print(f"Removed {humanReadableName} {targetInstanceName} at {position}")
                  return True

   # If present, removed above.  If removed, return False.
   for level in levels:
      for collectable in level.collectables2:
         if collectable.pathName == targetInstanceName:
            return False

   # If execution gets here, the object isn't present in the save, so add it.
   # This has only been observed when collectables1 is missing, so can't just append.
   for level in levels:
      if level.levelName == rootObject:
         print(f"Removed {humanReadableName} {targetInstanceName} at {position} (unvisited)")
         if level.collectables1 is not None:
            level.collectables1.append(removedObjectCollectionReference)
         level.collectables2.append(removedObjectCollectionReference)
         return True

   print(f"CAUTION: Failed to remove {humanReadableName} {targetInstanceName} at {position}")
   return False

def removeSomersloop(levels, targetInstanceName: str) -> bool:
   (rootObject, rotation, position, details) = sav_data.somersloop.SOMERSLOOPS[targetInstanceName]
   print(f"Removing Somersloop {targetInstanceName} at {position}")
   return removeInstance(levels, "Somersloops", rootObject, targetInstanceName, position)

def removeMercerSphere(levels, targetInstanceName: str) -> bool:
   (rootObject, rotation, position, details) = sav_data.mercerSphere.MERCER_SPHERES[targetInstanceName]
   print(f"Removing Mercer Sphere {targetInstanceName} at {position}")
   return removeInstance(levels, "Mercer Sphere", rootObject, targetInstanceName, position)

def removeMercerShrine(levels, targetInstanceName: str) -> bool:
   (rootObject, rotation, position, scale) = sav_data.mercerSphere.MERCER_SHRINES[targetInstanceName]
   print(f"Removing Mercer Shrine {targetInstanceName} at {position}")
   return removeInstance(levels, "Mercer Shrine", rootObject, targetInstanceName, position)

def addMapMarker(levels, markerName: str, markerLocation: list[float, float, float] | tuple[float, float, float], markerIconId_key: str, markerColor: list[float, float, float] | tuple[float, float, float] = (0.6, 0.6, 0.6), markerViewDistance: sav_data.data.ECompassViewDistance = sav_data.data.ECompassViewDistance.CVD_Mid, scale: float = 1.0, subcategory: str = "") -> bool:
   if len(markerLocation) != 3:
      print(f"ERROR: Invalid markerLocation passed to addMapMarker: {markerLocation}")
      return False
   if len(markerColor) != 3:
      print(f"ERROR: Invalid markerColor passed to addMapMarker: {markerColor}")
      return False
   for level in levels:
      for object in level.objects:
         if object.instanceName == "Persistent_Level:PersistentLevel.MapManager":
            mapMarkers = sav_parse.getPropertyValue(object.properties, "mMapMarkers")
            if mapMarkers is not None:

               if isinstance(ENFORCE_MAP_MARKER_LIMIT, int) and ENFORCE_MAP_MARKER_LIMIT > 0 and len(mapMarkers) >= ENFORCE_MAP_MARKER_LIMIT:
                  print(f"Skipping map marker {markerName} at {markerLocation} due to marker limit of {ENFORCE_MAP_MARKER_LIMIT}")
                  return False

               if object.objectGameVersion < 53:
                  newMarker = [[["markerGuid", uuid.uuid4().bytes],
                                ["Location", [
                                 [["X", markerLocation[0]], ["Y", markerLocation[1]], ["Z", markerLocation[2]]],
                                 [["X", "DoubleProperty", 0], ["Y", "DoubleProperty", 0], ["Z", "DoubleProperty", 0]]]],
                                ["Name", markerName],
                                ["CategoryName", subcategory], # This is called "Subcategory" in-game
                                ["MapMarkerType", ["ERepresentationType", "ERepresentationType::RT_MapMarker"]],
                                ["IconID", sav_data.data.ICON_NAMES_TO_IDS[markerIconId_key]],
                                ["Color", [markerColor[0], markerColor[1], markerColor[2], 1.0]],
                                ["Scale", scale],
                                ["compassViewDistance", ["ECompassViewDistance", f"ECompassViewDistance::{markerViewDistance.name}"]],
                                ["MarkerPlacedByAccountID", ""]],
                               [["markerGuid", "StructProperty", 0, "Guid", None, 0],
                                ["Location", "StructProperty", 0, "Vector_NetQuantize", None, 0],
                                ["Name", "StrProperty", 0], ["CategoryName", "StrProperty", 0],
                                ["MapMarkerType", "EnumProperty", 0],
                                ["IconID", "IntProperty", 0],
                                ["Color", "StructProperty", 0, "LinearColor", None, 0],
                                ["Scale", "FloatProperty", 0],
                                ["compassViewDistance", "EnumProperty", 0],
                                ["MarkerPlacedByAccountID", "StrProperty", 0]]]
               else:
                  newMarker = [[["markerGuid", uuid.uuid4().bytes],
                                ["Location",[
                                 [["X", markerLocation[0]], ["Y", markerLocation[1]], ["Z", markerLocation[2]]],
                                 [["X", "DoubleProperty", 0], ["Y", "DoubleProperty", 0], ["Z", "DoubleProperty", 0]]]],
                                ["Name", markerName],
                                ["CategoryName", subcategory], # This is called "Subcategory" in-game
                                ["MapMarkerType", ["ERepresentationType", "ERepresentationType::RT_MapMarker"]],
                                ["IconID", sav_data.data.ICON_NAMES_TO_IDS[markerIconId_key]],
                                ["Color", [markerColor[0], markerColor[1], markerColor[2], 1.0]],
                                ["Scale", scale],
                                ["compassViewDistance", ["ECompassViewDistance", f"ECompassViewDistance::{markerViewDistance.name}"]],
                                ["lastEditedBy", b'\x06\x00\x00\x00\x00']],
                               [["markerGuid", "StructProperty", 1, "Guid", ["/Script/CoreUObject"], 8],
                                ["Location", "StructProperty", 1, "Vector_NetQuantize", ["/Script/Engine"], 0],
                                ["Name", "StrProperty", 0],
                                ["CategoryName", "StrProperty", 0],
                                ["MapMarkerType", "EnumProperty", 2, "ERepresentationType", ["/Script/FactoryGame"]],
                                ["IconID", "IntProperty", 0],
                                ["Color", "StructProperty", 1, "LinearColor", ["/Script/CoreUObject"], 8],
                                ["Scale", "FloatProperty", 0],
                                ["compassViewDistance", "EnumProperty", 2, "ECompassViewDistance", ["/Script/FactoryGame"]],
                                ["lastEditedBy", "StructProperty", 1, "PlayerInfoHandle", ["/Script/FactoryGame"], 8]]]
               mapMarkers.append(newMarker)
               return True
   return False

class ChangeResultEnum(enum.Enum):
   NO_CHANGE = 0
   CHANGE = 1
   ERROR = 2

def setNodeType(originalNodeName, nodeType, nodePurity):

   LIQUID_OIL = "/Game/FactoryGame/Resource/RawResources/CrudeOil/Desc_LiquidOil.Desc_LiquidOil_C"
   ITEM_NODE_TYPES = {
      "Coal": "/Game/FactoryGame/Resource/RawResources/Coal/Desc_Coal.Desc_Coal_C",
      "Bauxite": "/Game/FactoryGame/Resource/RawResources/OreBauxite/Desc_OreBauxite.Desc_OreBauxite_C",
      "Copper Ore": "/Game/FactoryGame/Resource/RawResources/OreCopper/Desc_OreCopper.Desc_OreCopper_C",
      "Caterium Ore": "/Game/FactoryGame/Resource/RawResources/OreGold/Desc_OreGold.Desc_OreGold_C",
      "Crude Oil": LIQUID_OIL,
      "Iron Ore": "/Game/FactoryGame/Resource/RawResources/OreIron/Desc_OreIron.Desc_OreIron_C",
      "Uranium": "/Game/FactoryGame/Resource/RawResources/OreUranium/Desc_OreUranium.Desc_OreUranium_C",
      "Raw Quartz": "/Game/FactoryGame/Resource/RawResources/RawQuartz/Desc_RawQuartz.Desc_RawQuartz_C",
      "SAM Ore": "/Game/FactoryGame/Resource/RawResources/SAM/Desc_SAM.Desc_SAM_C",
      "Limestone": "/Game/FactoryGame/Resource/RawResources/Stone/Desc_Stone.Desc_Stone_C",
      "Sulfur": "/Game/FactoryGame/Resource/RawResources/Sulfur/Desc_Sulfur.Desc_Sulfur_C"}
   FRACKING_NODE_TYPES = {
      "Crude Oil": LIQUID_OIL,
      "Nitrogen Gas": "/Game/FactoryGame/Resource/RawResources/NitrogenGas/Desc_NitrogenGas.Desc_NitrogenGas_C",
      "Water": "/Game/FactoryGame/Resource/RawResources/Water/Desc_Water.Desc_Water_C"}
   NODE_PURITIES = {"Impure": "RP_Impure", "Normal": "RP_Normal", "Pure": "RP_Pure"}

   if nodeType in ITEM_NODE_TYPES:
      requestedTypeIsFrackingFlag = False
      nodeType = ITEM_NODE_TYPES[nodeType]
   elif nodeType in FRACKING_NODE_TYPES:
      requestedTypeIsFrackingFlag = True
      nodeType = FRACKING_NODE_TYPES[nodeType]
   else:
      return (ChangeResultEnum.ERROR, f"ERROR: Invalid node type '{nodeType}' for node {originalNodeName}")

   if nodePurity is not None:
      if nodePurity not in NODE_PURITIES:
         return (ChangeResultEnum.ERROR, f"ERROR: Invalid node purity '{nodePurity}'")
      nodePurity = NODE_PURITIES[nodePurity]

   nodeName = f"Persistent_Level:PersistentLevel.{originalNodeName}"

   level = parsedSave.levels[-1]
   for actorOrComponentObjectHeader in level.actorAndComponentObjectHeaders:
      if isinstance(actorOrComponentObjectHeader, sav_parse.ActorHeader) and \
            actorOrComponentObjectHeader.typePath in ("/Game/FactoryGame/Resource/BP_ResourceNode.BP_ResourceNode_C",
                                                      "/Game/FactoryGame/Resource/BP_FrackingCore.BP_FrackingCore_C",
                                                      "/Game/FactoryGame/Resource/BP_FrackingSatellite.BP_FrackingSatellite_C") and \
            actorOrComponentObjectHeader.instanceName == nodeName:
         # Note is confirmed to be the correct typePath, so continue
         for object in level.objects:
            if object.instanceName == nodeName:
               if nodeType != LIQUID_OIL:
                  requestedNodeIsFrackingFlag = actorOrComponentObjectHeader.typePath != "/Game/FactoryGame/Resource/BP_ResourceNode.BP_ResourceNode_C"
                  if requestedTypeIsFrackingFlag != requestedNodeIsFrackingFlag:
                     return (ChangeResultEnum.ERROR, f"ERROR: Mismatch between {originalNodeName} type {actorOrComponentObjectHeader.typePath} and new type {nodeType}")

               successType = ChangeResultEnum.NO_CHANGE
               successMessage = f"{object.instanceName}:"

               resourceClassOverride = sav_parse.getPropertyValue(object.properties, "mResourceClassOverride")
               if resourceClassOverride:
                  if resourceClassOverride.pathName != nodeType:
                     successMessage += f" Changed type from {sav_parse.pathNameToReadableName(resourceClassOverride.pathName)} to {sav_parse.pathNameToReadableName(nodeType)}."
                     resourceClassOverride.pathName = nodeType
                     successType = ChangeResultEnum.CHANGE
                  else:
                     successMessage += f" Type already {sav_parse.pathNameToReadableName(nodeType)}."
               else:
                  resourceClassOverride = sav_parse.ObjectReference("", nodeType)
                  object.properties.append(["mResourceClassOverride", resourceClassOverride])
                  object.propertyTypes.append(["mResourceClassOverride", "ObjectProperty", 0])
                  successMessage += f" Setting type to {sav_parse.pathNameToReadableName(nodeType)}."
                  successType = ChangeResultEnum.CHANGE

               purityOverride = sav_parse.getPropertyValue(object.properties, "mPurityOverride")
               if purityOverride:
                  if purityOverride[1] != nodePurity:
                     successMessage += f" Changed purity from {purityOverride[1]} to {nodePurity}."
                     purityOverride[1] = nodePurity
                     successType = ChangeResultEnum.CHANGE
                  else:
                     successMessage += f" Purity already {nodePurity}."
               elif actorOrComponentObjectHeader.typePath != "/Game/FactoryGame/Resource/BP_FrackingCore.BP_FrackingCore_C":
                  object.properties.append(["mPurityOverride", ["EResourcePurity", nodePurity]])
                  object.propertyTypes.append(["mPurityOverride", "ByteProperty", 1, "EResourcePurity", ["/Script/FactoryGame"]])
                  successMessage += f" Setting purity to {nodePurity}."
                  successType = ChangeResultEnum.CHANGE

               return (successType, successMessage)

   if nodeName not in sav_data.resourcePurity.RESOURCE_PURITY:
      return (ChangeResultEnum.ERROR, f"ERROR: Invalid node name '{originalNodeName}'")
   else:
      return (ChangeResultEnum.ERROR, f"ERROR: Node not found '{originalNodeName}'")

def addWaterExtractor(level, waterExtractorPosition, waterExtractorRotationInDegrees, waterVolume, incrementStatisticsSubsystemFlag = True):
   # Rotation is -180 to 180 degrees

   actorInsertionIdx = -1
   for idx in range(len(level.actorAndComponentObjectHeaders)):
      if isinstance(level.actorAndComponentObjectHeaders[idx], sav_parse.ComponentHeader):
         actorInsertionIdx = idx
         break

   if incrementStatisticsSubsystemFlag:
      for object in level.objects:
         if object.instanceName == "Persistent_Level:PersistentLevel.StatisticsSubsystem":
            for property in object.properties:
               if property[0] == "mActorsBuiltCount":
                  for items in property[1]:
                     if items[0].pathName == WATER_EXTRACTOR_TYPE:
                        for itemProperties in items[1]:
                           if itemProperties[0] == "Current":
                              itemProperties[1] += 1
                           elif itemProperties[0] == "CurrentMax":
                              itemProperties[1] += 1
                           elif itemProperties[0] == "Total":
                              itemProperties[1] += 1
                           elif itemProperties[0] == "BuiltPerPlayer" and len(itemProperties[1]) > 0:
                              firstBuilder = itemProperties[1][0]
                              firstBuilder[1] += 1
                        #print(f"Updated StatisticsSubsystem::{property[0]} for {items[0].pathName}")

   waterPumpActorHeader = sav_parse.ActorHeader()
   waterPumpActorHeader.typePath = WATER_EXTRACTOR_TYPE
   waterPumpActorHeader.rootObject = PERSISTENT_LEVEL
   waterPumpActorHeader.instanceName = f"Persistent_Level:PersistentLevel.Build_WaterPump_C_{uuid.uuid4().hex}"
   waterPumpActorHeader.flags = 8
   waterPumpActorHeader.needTransform = True
   waterPumpActorHeader.rotation = eulerToQuaternion((0, 0, degreesToRadians(waterExtractorRotationInDegrees))) # roll, pitch, yaw (rotation clockwise from zero=north; -180 to 180)
   waterPumpActorHeader.position = waterExtractorPosition
   waterPumpActorHeader.scale = [1.0, 1.0, 1.0]
   waterPumpActorHeader.wasPlacedInLevel = False
   level.actorAndComponentObjectHeaders.insert(actorInsertionIdx, waterPumpActorHeader)

   waterPumpActorObject = sav_parse.Object()
   waterPumpActorObject.instanceName = waterPumpActorHeader.instanceName
   waterPumpActorObject.objectGameVersion = 58
   waterPumpActorObject.shouldMigrateObjectRefsToPersistentFlag = False
   waterPumpActorObject.actorReferenceAssociations = [sav_parse.ObjectReference(PERSISTENT_LEVEL, "Persistent_Level:PersistentLevel.BuildableSubsystem"), [
      sav_parse.ObjectReference(PERSISTENT_LEVEL, f"{waterPumpActorHeader.instanceName}.FGPipeConnectionFactory"),
      sav_parse.ObjectReference(PERSISTENT_LEVEL, f"{waterPumpActorHeader.instanceName}.InventoryPotential"),
      sav_parse.ObjectReference(PERSISTENT_LEVEL, f"{waterPumpActorHeader.instanceName}.powerInfo"),
      sav_parse.ObjectReference(PERSISTENT_LEVEL, f"{waterPumpActorHeader.instanceName}.OutputInventory"),
      sav_parse.ObjectReference(PERSISTENT_LEVEL, f"{waterPumpActorHeader.instanceName}.PowerConnection")]]
   waterPumpActorObject.properties = fromJSON(
      [['mOutputInventory', {'levelName': 'Persistent_Level', 'pathName': f"{waterPumpActorHeader.instanceName}.OutputInventory"}],
       ['mExtractableResource', {'levelName': 'Persistent_Level', 'pathName': waterVolume}],
       ['mPowerInfo', {'levelName': 'Persistent_Level', 'pathName': f"{waterPumpActorHeader.instanceName}.powerInfo"}],
       ['mTimeSinceStartStopProducing', 3.3999999521443642e+38],
       ['mInventoryPotential', {'levelName': 'Persistent_Level', 'pathName': f"{waterPumpActorHeader.instanceName}.InventoryPotential"}],
       #['BuiltBy', {'jsonhexstr': '0600000000'}],
       ['mCustomizationData', [
        [['SwatchDesc', {'levelName': '', 'pathName': '/Game/FactoryGame/Buildable/-Shared/Customization/Swatches/SwatchDesc_Slot0.SwatchDesc_Slot0_C'}]],
        [['SwatchDesc', 'ObjectProperty', 0]]]],
       ['mBuiltWithRecipe', {'levelName': '', 'pathName': '/Game/FactoryGame/Recipes/Buildings/Recipe_WaterPump.Recipe_WaterPump_C'}]])
   waterPumpActorObject.propertyTypes = fromJSON(
      [['mOutputInventory', 'ObjectProperty', 0], ['mExtractableResource', 'ObjectProperty', 0], ['mPowerInfo', 'ObjectProperty', 0],
       ['mTimeSinceStartStopProducing', 'FloatProperty', 0], ['mInventoryPotential', 'ObjectProperty', 0],
       #['BuiltBy', 'StructProperty', 1, 'PlayerInfoHandle', ['/Script/FactoryGame'], 8],
       ['mCustomizationData', 'StructProperty', 1, 'FactoryCustomizationData', ['/Script/FactoryGame'], 0], ['mBuiltWithRecipe', 'ObjectProperty', 0]])
   waterPumpActorObject.actorSpecificInfo = None
   waterPumpActorObject.perObjectVersionData = None
   level.objects.insert(actorInsertionIdx, waterPumpActorObject)

   componentHeader = sav_parse.ComponentHeader()
   componentHeader.className = "/Script/FactoryGame.FGPipeConnectionFactory"
   componentHeader.rootObject = PERSISTENT_LEVEL
   componentHeader.instanceName = f"{waterPumpActorHeader.instanceName}.FGPipeConnectionFactory"
   componentHeader.flags = 0x200000
   componentHeader.parentActorName = waterPumpActorHeader.instanceName
   level.actorAndComponentObjectHeaders.append(componentHeader)
   componentObject = sav_parse.Object()
   componentObject.instanceName = componentHeader.instanceName
   componentObject.objectGameVersion = 58
   componentObject.shouldMigrateObjectRefsToPersistentFlag = False
   componentObject.actorReferenceAssociations = None
   componentObject.properties = []
   componentObject.propertyTypes = []
   componentObject.actorSpecificInfo = True
   componentObject.perObjectVersionData = None
   level.objects.append(componentObject)

   componentHeader = sav_parse.ComponentHeader()
   componentHeader.className = "/Script/FactoryGame.FGPowerConnectionComponent"
   componentHeader.rootObject = PERSISTENT_LEVEL
   componentHeader.instanceName = f"{waterPumpActorHeader.instanceName}.PowerConnection"
   componentHeader.flags = 0x200000
   componentHeader.parentActorName = waterPumpActorHeader.instanceName
   level.actorAndComponentObjectHeaders.append(componentHeader)
   componentObject = sav_parse.Object()
   componentObject.instanceName = componentHeader.instanceName
   componentObject.objectGameVersion = 58
   componentObject.shouldMigrateObjectRefsToPersistentFlag = False
   componentObject.actorReferenceAssociations = None
   componentObject.properties = []
   componentObject.propertyTypes = []
   componentObject.actorSpecificInfo = True
   componentObject.perObjectVersionData = None
   level.objects.append(componentObject)

   componentHeader = sav_parse.ComponentHeader()
   componentHeader.className = "/Script/FactoryGame.FGInventoryComponent"
   componentHeader.rootObject = PERSISTENT_LEVEL
   componentHeader.instanceName = f"{waterPumpActorHeader.instanceName}.OutputInventory"
   componentHeader.flags = 0x40008
   componentHeader.parentActorName = waterPumpActorHeader.instanceName
   level.actorAndComponentObjectHeaders.append(componentHeader)
   componentObject = sav_parse.Object()
   componentObject.instanceName = componentHeader.instanceName
   componentObject.objectGameVersion = 58
   componentObject.shouldMigrateObjectRefsToPersistentFlag = False
   componentObject.actorReferenceAssociations = None
   componentObject.properties = fromJSON([['mArbitrarySlotSizes', [200000]], ['mAllowedItemDescriptors', [{'levelName': '', 'pathName': '/Game/FactoryGame/Resource/RawResources/Water/Desc_Water.Desc_Water_C'}]]])
   componentObject.propertyTypes = [['mArbitrarySlotSizes', 'ArrayProperty', 1, 'IntProperty', 0, 0], ['mAllowedItemDescriptors', 'ArrayProperty', 1, 'ObjectProperty', 0, 0]]
   componentObject.actorSpecificInfo = True
   componentObject.perObjectVersionData = None
   level.objects.append(componentObject)

   componentHeader = sav_parse.ComponentHeader()
   componentHeader.className = "/Script/FactoryGame.FGPowerInfoComponent"
   componentHeader.rootObject = PERSISTENT_LEVEL
   componentHeader.instanceName = f"{waterPumpActorHeader.instanceName}.powerInfo"
   componentHeader.flags = 0x40008
   componentHeader.parentActorName = waterPumpActorHeader.instanceName
   level.actorAndComponentObjectHeaders.append(componentHeader)
   componentObject = sav_parse.Object()
   componentObject.instanceName = componentHeader.instanceName
   componentObject.objectGameVersion = 58
   componentObject.shouldMigrateObjectRefsToPersistentFlag = False
   componentObject.actorReferenceAssociations = None
   componentObject.properties = [['mTargetConsumption', 0.10000000149011612]]
   componentObject.propertyTypes = [['mTargetConsumption', 'FloatProperty', 0]]
   componentObject.actorSpecificInfo = True
   componentObject.perObjectVersionData = None
   level.objects.append(componentObject)

   componentHeader = sav_parse.ComponentHeader()
   componentHeader.className = "/Script/FactoryGame.FGInventoryComponent"
   componentHeader.rootObject = PERSISTENT_LEVEL
   componentHeader.instanceName = f"{waterPumpActorHeader.instanceName}.InventoryPotential"
   componentHeader.flags = 0x40008
   componentHeader.parentActorName = waterPumpActorHeader.instanceName
   level.actorAndComponentObjectHeaders.append(componentHeader)
   componentObject = sav_parse.Object()
   componentObject.instanceName = componentHeader.instanceName
   componentObject.objectGameVersion = 58
   componentObject.shouldMigrateObjectRefsToPersistentFlag = False
   componentObject.actorReferenceAssociations = None
   componentObject.properties = [['mArbitrarySlotSizes', [1, 1, 1]]]
   componentObject.propertyTypes = [['mArbitrarySlotSizes', 'ArrayProperty', 1, 'IntProperty', 0, 0]]
   componentObject.actorSpecificInfo = True
   componentObject.perObjectVersionData = None
   level.objects.append(componentObject)

def printUsage() -> None:
   print()
   print("USAGE:")
   print("   py sav_cli.py --info <save-filename>")
   print("   py sav_cli.py --to-json <save-filename> <output-json-filename>")
   print("   py sav_cli.py --from-json <input-json-filename> <new-save-filename>")
   print("   py sav_cli.py --set-session-name <new-session-name> <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --find-free-stuff [item] [save-filename]")
   print("   py sav_cli.py --list-players <save-filename>")
   print("   py sav_cli.py --list-player-inventory <player-num> <save-filename>")
   print("   py sav_cli.py --move-player <player-num> <x> <y> <z> <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --find-node <x> <y> [save-filename]")
   print("   py sav_cli.py --find-node-near <player-num> <save-filename>")
   print("   py sav_cli.py --set-node <name> <type> <purity> <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --export-node-types <save-filename> <output-json-filename>")
   print("   py sav_cli.py --import-node-types <original-save-filename> <input-json-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --export-player-inventory <player-num> <save-filename> <output-json-filename>")
   print("   py sav_cli.py --import-player-inventory <player-num> <original-save-filename> <input-json-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --tweak-player-inventory <player-num> <slot-index> <item> <quantity> <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --rotate-foundations <primary-color-hex-or-preset> <secondary-color-hex-or-preset> <clockwise-degrees> <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --clear-fog <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --export-hotbar <player-num> <save-filename> <output-json-filename>")
   print("   py sav_cli.py --import-hotbar <player-num> <original-save-filename> <input-json-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --change-num-inventory-slots <num-inventory-slots> <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --restore-somersloops <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --restore-mercer-spheres <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --export-somersloops <save-filename> <output-json-filename>")
   print("   py sav_cli.py --export-mercer-spheres <save-filename> <output-json-filename>")
   print("   py sav_cli.py --import-somersloops <original-save-filename> <input-json-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --import-mercer-spheres <original-save-filename> <input-json-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --remember-username <player-num> <username-alias>")
   print("   py sav_cli.py --list-vehicle-paths <save-filename>")
   print("   py sav_cli.py --export-vehicle-path <path-name> <save-filename> <output-json-filename>")
   print("   py sav_cli.py --import-vehicle-path <path-name> <original-save-filename> <input-json-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --export-dimensional-depot <save-filename> <output-json-filename>")
   print("   py sav_cli.py --reorder-dimensional-depot <original-save-filename> <input-json-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --adjust-dimensional-depot <original-save-filename> <item-name> <new-quantity> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --export-crash-sites <save-filename> <output-json-filename>")
   print("   py sav_cli.py --dismantle-crash-site <drop-pod-name> <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --list-map-markers <save-filename>")
   print("   py sav_cli.py --export-map-markers <save-filename> <output-json-filename>")
   print("   py sav_cli.py --remove-marker <marker-guid> <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --add-map-markers-json <original-save-filename> <input-json-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --add-map-markers-somersloops <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --add-map-markers-mercer-spheres <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --add-map-markers-hard-drives <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --add-map-markers-collectable <item> <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --blueprint --show <save-filename>")
   print("   py sav_cli.py --blueprint --sort <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --blueprint --export <save-filename> <output-json-filename>")
   print("   py sav_cli.py --blueprint --import <original-save-filename> <input-json-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --blueprint --add-category <category> <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --blueprint --add-subcategory <category> <subcategory> <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --blueprint --add-blueprint <category> <subcategory> <blueprint> <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --blueprint --remove-category <category> <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --blueprint --remove-subcategory <category> <subcategory> <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --blueprint --remove-blueprint <category> <subcategory> <blueprint> <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --blueprint --move-blueprint <old-category> <old-subcategory> <new-category> <new-subcategory> <blueprint> <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --blueprint --reset <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --resave-only <original-save-filename> <new-save-filename>")
   print("   py sav_cli.py --add-missing-items-to-sav_stack_sizes")
   print("   py sav_cli.py --list-crash-site-guards")
   print("   py sav_cli.py --add-water-extractor <original-save-filename> <new-save-filename>")
   print()

   # TODO: Add manipulation of cheat flags
   #    mapOptions ends in "?enableAdvancedGameSettings"
   #    isCreativeModeEnabled=True
   #    <Object: instanceName=Persistent_Level:PersistentLevel.GameRulesSubsystem
   #       properties=[[('mHasInitialized', True)]]
   #       properties=[[('mHasInitialized', False), ('mUnlockInstantAltRecipes', True), ('mDisableArachnidCreatures', True), ('mNoUnlockCost', True)]]
   #    <Object: instanceName=Persistent_Level:PersistentLevel.BP_GameState_C_2147478581
   #       ('mIsCreativeModeEnabled', False), ('mCheatNoPower', True), ('mCheatNoFuel', True), ('mCheatNoCost', True)
   #    <Object: instanceName=Persistent_Level:PersistentLevel.BP_PlayerState_C_2147195792
   #       ('mPlayerRules', ([('HasInitialized', True)], [('HasInitialized', 'BoolProperty', 0)]))
   #       ('mPlayerRules', ([('HasInitialized', True), ('NoBuildCost', True), ('FlightMode', True), ('GodMode', True)], [('HasInitialized', 'BoolProperty', 0), ('NoBuildCost', 'BoolProperty', 0), ('FlightMode', 'BoolProperty', 0), ('GodMode', 'BoolProperty', 0)]))

if __name__ == '__main__':

   if os.path.isfile(USERNAME_FILENAME):
      with open(USERNAME_FILENAME, "r") as fin:
         playerUsernames = json.load(fin)

   if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help")):
      printUsage()

   elif len(sys.argv) == 3 and sys.argv[1] == "--info" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]

      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)
         print(f"Save Header Type: {parsedSave.saveFileInfo.saveHeaderType}")
         print(f"Save Version: {parsedSave.saveFileInfo.saveVersion}")
         print(f"Build Version: {parsedSave.saveFileInfo.buildVersion}")
         print(f"Save Name: {parsedSave.saveFileInfo.saveName}")
         print(f"Map Name: {parsedSave.saveFileInfo.mapName}")
         print(f"Map Options: {parsedSave.saveFileInfo.mapOptions}")
         print(f"Session Name: {parsedSave.saveFileInfo.sessionName}")
         print(f"Play Duration: {parsedSave.saveFileInfo.playDurationInSeconds} seconds")
         print(f"Save Date Time: {parsedSave.saveFileInfo.saveDateTimeInTicks} ticks ({parsedSave.saveFileInfo.saveDatetime.strftime('%m/%d/%Y %I:%M:%S %p')})")
         print(f"Session Visibility: {parsedSave.saveFileInfo.sessionVisibility}")
         print(f"Editor Object Version: {parsedSave.saveFileInfo.editorObjectVersion}")
         print(f"Is Modded Save: {parsedSave.saveFileInfo.isModdedSave}")
         if not parsedSave.saveFileInfo.isModdedSave and len(parsedSave.saveFileInfo.modMetadata) > 0: # This should never happen
            print(f"Mod Metadata: {parsedSave.saveFileInfo.modMetadata}")
         print(f"Save Identifier: {parsedSave.saveFileInfo.saveIdentifier}")
         print(f"Save Data Hash: {parsedSave.saveFileInfo.saveDataHash}")
         print(f"Is Creative Mode Enabled: {parsedSave.saveFileInfo.isCreativeModeEnabled}")

         playerPaths = getPlayerPaths(parsedSave.levels)

         gameStateInstanceName = None
         for level in parsedSave.levels:
            for actorOrComponentObjectHeader in level.actorAndComponentObjectHeaders:
               if isinstance(actorOrComponentObjectHeader, sav_parse.ActorHeader) and actorOrComponentObjectHeader.typePath == "/Game/FactoryGame/-Shared/Blueprint/BP_GameState.BP_GameState_C":
                  gameStateInstanceName = actorOrComponentObjectHeader.instanceName

         for level in parsedSave.levels:
            for object in level.objects:

               if object.instanceName == "Persistent_Level:PersistentLevel.GameRulesSubsystem":
                  mStartingTier = sav_parse.getPropertyValue(object.properties, "mStartingTier")
                  if mStartingTier is not None:
                     print(f"Game Rules, mStartingTier: {mStartingTier}")
                  mUnlockInstantAltRecipes = sav_parse.getPropertyValue(object.properties, "mUnlockInstantAltRecipes")
                  if mUnlockInstantAltRecipes is not None:
                     print(f"Game Rules, mUnlockInstantAltRecipes: {mUnlockInstantAltRecipes}")
                  mUnlockAllMilestoneSchematics = sav_parse.getPropertyValue(object.properties, "mUnlockAllMilestoneSchematics")
                  if mUnlockAllMilestoneSchematics is not None:
                     print(f"Game Rules, mUnlockAllMilestoneSchematics: {mUnlockAllMilestoneSchematics}")
                  mUnlockAllResourceSinkSchematics = sav_parse.getPropertyValue(object.properties, "mUnlockAllResourceSinkSchematics")
                  if mUnlockAllResourceSinkSchematics is not None:
                     print(f"Game Rules, mUnlockAllResourceSinkSchematics: {mUnlockAllResourceSinkSchematics}")
                  mUnlockAllResearchSchematics = sav_parse.getPropertyValue(object.properties, "mUnlockAllResearchSchematics")
                  if mUnlockAllResearchSchematics is not None:
                     print(f"Game Rules, mUnlockAllResearchSchematics: {mUnlockAllResearchSchematics}")
                  mNoUnlockCost = sav_parse.getPropertyValue(object.properties, "mNoUnlockCost")
                  if mNoUnlockCost is not None:
                     print(f"Game Rules, mNoUnlockCost: {mNoUnlockCost}")

               elif object.instanceName == gameStateInstanceName:
                  mIsCreativeModeEnabled = sav_parse.getPropertyValue(object.properties, "mIsCreativeModeEnabled")
                  if mIsCreativeModeEnabled is not None:
                     print(f"Game State, mIsCreativeModeEnabled: {mIsCreativeModeEnabled}")
                  mCheatNoPower = sav_parse.getPropertyValue(object.properties, "mCheatNoPower")
                  if mCheatNoPower is not None:
                     print(f"Game State, mCheatNoPower: {mCheatNoPower}")
                  mCheatNoFuel = sav_parse.getPropertyValue(object.properties, "mCheatNoFuel")
                  if mCheatNoFuel is not None:
                     print(f"Game State, mCheatNoFuel: {mCheatNoFuel}")
                  mCheatNoCost = sav_parse.getPropertyValue(object.properties, "mCheatNoCost")
                  if mCheatNoCost is not None:
                     print(f"Game State, mCheatNoCost: {mCheatNoCost}")

                  # Game Modes
                  mEnergyCostMultiplier = sav_parse.getPropertyValue(object.properties, "mEnergyCostMultiplier")
                  if mEnergyCostMultiplier is not None:
                     print(f"Game State, mEnergyCostMultiplier: {mEnergyCostMultiplier}")
                  mPartsCostMultiplier = sav_parse.getPropertyValue(object.properties, "mPartsCostMultiplier")
                  if mPartsCostMultiplier is not None:
                     print(f"Game State, mPartsCostMultiplier: {mPartsCostMultiplier}")
                  mSpacePartsCostMultiplier = sav_parse.getPropertyValue(object.properties, "mSpacePartsCostMultiplier")
                  if mSpacePartsCostMultiplier is not None:
                     print(f"Game State, mSpacePartsCostMultiplier: {mSpacePartsCostMultiplier}")
                  mNodeRandomization = sav_parse.getPropertyValue(object.properties, "mNodeRandomization")
                  if mNodeRandomization is not None:
                     print(f"Game State, mNodeRandomization: {mNodeRandomization[1].lstrip('ENodeRandomizationMode::NRM_')}")
                  mNodePuritySettings = sav_parse.getPropertyValue(object.properties, "mNodePuritySettings")
                  if mNodePuritySettings is not None:
                     print(f"Game State, mNodePuritySettings: {mNodePuritySettings[1].lstrip('ENodePuritySettings::NPS_')}")
                  mNodeRandomizationSeed = sav_parse.getPropertyValue(object.properties, "mNodeRandomizationSeed")
                  if mNodeRandomizationSeed is not None:
                     print(f"Game State, mNodeRandomizationSeed: {mNodeRandomizationSeed}")

         print("Players:")
         for level in parsedSave.levels:
            for object in level.objects:
               for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
                  if object.instanceName == playerStateInstanceName:
                     playerName = getPlayerName(parsedSave.levels, characterPlayer)
                     if playerName is None:
                        print(f"   {characterPlayer}")
                     else:
                        print(f"   {characterPlayer} ({playerName})")

                     mPlayerRules = sav_parse.getPropertyValue(object.properties, "mPlayerRules")
                     if mPlayerRules is not None:
                        noBuildCost = sav_parse.getPropertyValue(mPlayerRules[0], "NoBuildCost")
                        if noBuildCost is not None:
                           print(f"      Player Rules, NoBuildCost: {noBuildCost}")
                        flightMode = sav_parse.getPropertyValue(mPlayerRules[0], "FlightMode")
                        if flightMode is not None:
                           print(f"      Player Rules, FlightMode: {flightMode}")
                        godMode = sav_parse.getPropertyValue(mPlayerRules[0], "GodMode")
                        if godMode is not None:
                           print(f"      Player Rules, GodMode: {godMode}")

         if parsedSave.saveFileInfo.isModdedSave:
            # modMetadata is of type str representing a JSON dict
            print(f"Mod Metadata:")
            jdata = json.loads(parsedSave.saveFileInfo.modMetadata)
            if "Mods" in jdata:
               for mod in jdata["Mods"]:
                  if "Name" in mod and "Version" in mod:
                     print(f"   {mod['Name']}, {mod['Version']}")

         crashSitesInSave, crashSitesNotOpened, crashSitesOpenWithDrive, crashSitesOpenAndEmpty, crashSitesDismantled = sav_to_html.getCrashSiteState(parsedSave.levels)

         print(f"{len(sav_data.crashSites.CRASH_SITES)} total crash sites on map.")
         print(f"   {len(crashSitesInSave) + len(crashSitesDismantled)} found in save file.")
         print(f"   {len(crashSitesNotOpened)} not opened.")
         print(f"   {len(crashSitesOpenWithDrive)} opened with hard drive.")
         print(f"   {len(crashSitesOpenAndEmpty)} opened and empty.")
         print(f"   {len(crashSitesDismantled)} dismantled.")

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

   elif len(sys.argv) == 4 and sys.argv[1] == "--to-json" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      outFilename = sys.argv[3]

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         jdata = {}
         jdata["saveFileInfo"] = toJSON(parsedSave.saveFileInfo)
         jdata["persistentLevelSaveObjectVersionData"] = toJSON(parsedSave.persistentLevelSaveObjectVersionData)
         jdata["partitions"] = toJSON(parsedSave.partitions)
         ldata = jdata["levels"] = {}
         for level in parsedSave.levels:
            ldata[level.levelName] = {
               "objectHeaders": toJSON(level.actorAndComponentObjectHeaders),
               "levelPersistentFlag": toJSON(level.levelPersistentFlag),
               "collectables1": toJSON(level.collectables1),
               "objects": toJSON(level.objects),
               "levelSaveVersion": toJSON(level.levelSaveVersion),
               "collectables2": toJSON(level.collectables2),
               "saveObjectVersionData": toJSON(level.saveObjectVersionData)}
         jdata["aLevelName"] = toJSON(parsedSave.aLevelName)
         jdata["dropPodObjectReferenceList"] = toJSON(parsedSave.dropPodObjectReferenceList)
         jdata["extraObjectReferenceList"] = toJSON(parsedSave.extraObjectReferenceList)

         print(f"Writing {outFilename}")
         with open(outFilename, "w") as fout:
            json.dump(jdata, fout, indent=2)

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

   elif len(sys.argv) == 4 and sys.argv[1] == "--from-json" and os.path.isfile(sys.argv[2]):
      jsonFilename = sys.argv[2]
      outFilename = sys.argv[3]

      print("Reading JSON")
      with open(jsonFilename, "r") as fin:
         jdata = json.load(fin)

      print("Parsing JSON")
      saveFileInfo = sav_parse.SaveFileInfo()
      saveFileInfo.saveHeaderType = jdata["saveFileInfo"]["saveHeaderType"]
      saveFileInfo.saveVersion = jdata["saveFileInfo"]["saveVersion"]
      saveFileInfo.buildVersion = jdata["saveFileInfo"]["buildVersion"]
      saveFileInfo.saveName = jdata["saveFileInfo"]["saveName"]
      saveFileInfo.mapName = jdata["saveFileInfo"]["mapName"]
      saveFileInfo.mapOptions = jdata["saveFileInfo"]["mapOptions"]
      saveFileInfo.sessionName = jdata["saveFileInfo"]["sessionName"]
      saveFileInfo.playDurationInSeconds = jdata["saveFileInfo"]["playDurationInSeconds"]
      saveFileInfo.saveDateTimeInTicks = jdata["saveFileInfo"]["saveDateTimeInTicks"]
      saveFileInfo.saveDatetime = datetime.datetime.fromtimestamp(saveFileInfo.saveDateTimeInTicks / sav_parse.TICKS_IN_SECOND - sav_parse.EPOCH_1_TO_1970)
      saveFileInfo.sessionVisibility = fromJSON(jdata["saveFileInfo"]["sessionVisibility"])
      saveFileInfo.editorObjectVersion = jdata["saveFileInfo"]["editorObjectVersion"]
      saveFileInfo.modMetadata = jdata["saveFileInfo"]["modMetadata"]
      saveFileInfo.isModdedSave = jdata["saveFileInfo"]["isModdedSave"]
      saveFileInfo.saveIdentifier = jdata["saveFileInfo"]["saveIdentifier"]
      saveFileInfo.saveDataHash = jdata["saveFileInfo"]["saveDataHash"]
      saveFileInfo.isCreativeModeEnabled = jdata["saveFileInfo"]["isCreativeModeEnabled"]
      persistentLevelSaveObjectVersionData = jdata["persistentLevelSaveObjectVersionData"]
      partitions = jdata["partitions"]
      aLevelName = jdata["aLevelName"]

      dropPodObjectReferenceList = []
      for objectReference in jdata["dropPodObjectReferenceList"]:
         dropPodObjectReferenceList.append(fromJSON(objectReference))

      extraObjectReferenceList = []
      for objectReference in jdata["extraObjectReferenceList"]:
         extraObjectReferenceList.append(fromJSON(objectReference))

      levels = []
      for level in jdata["levels"]:
         levelName = level
         if levelName == "null":
            levelName = None
         levelData = jdata["levels"][level]

         actorAndComponentObjectHeaders = []
         for objectHeaderJson in levelData["objectHeaders"]:
            if len(objectHeaderJson) == 9:
               objectHeaderCopy = sav_parse.ActorHeader()
               objectHeaderCopy.typePath = objectHeaderJson["typePath"]
               objectHeaderCopy.rootObject = objectHeaderJson["rootObject"]
               objectHeaderCopy.instanceName = objectHeaderJson["instanceName"]
               objectHeaderCopy.flags = objectHeaderJson["flags"]
               objectHeaderCopy.needTransform = objectHeaderJson["needTransform"]
               objectHeaderCopy.rotation = objectHeaderJson["rotation"]
               objectHeaderCopy.position = objectHeaderJson["position"]
               objectHeaderCopy.scale = objectHeaderJson["scale"]
               objectHeaderCopy.wasPlacedInLevel = objectHeaderJson["wasPlacedInLevel"]
            else:
               objectHeaderCopy = sav_parse.ComponentHeader()
               objectHeaderCopy.className = objectHeaderJson["className"]
               objectHeaderCopy.rootObject = objectHeaderJson["rootObject"]
               objectHeaderCopy.instanceName = objectHeaderJson["instanceName"]
               objectHeaderCopy.flags = objectHeaderJson["flags"]
               objectHeaderCopy.parentActorName = objectHeaderJson["parentActorName"]
            actorAndComponentObjectHeaders.append(objectHeaderCopy)

         levelPersistentFlag = levelData["levelPersistentFlag"]

         collectables1: list[sav_parse.ObjectReference] | None = None
         if levelData["collectables1"] is not None:
            collectables1 = []
            for objectReference in levelData["collectables1"]:
               collectables1.append(fromJSON(objectReference))

         objects = []
         for objectJson in levelData["objects"]:
            objectCopy = sav_parse.Object()
            objectCopy.instanceName = objectJson["instanceName"]
            objectCopy.objectGameVersion = objectJson["objectGameVersion"]
            objectCopy.shouldMigrateObjectRefsToPersistentFlag = objectJson["smortpFlag"]
            objectCopy.actorReferenceAssociations = None
            if objectJson["actorReferenceAssociations"] is not None:
               objectCopy.actorReferenceAssociations = [
                  fromJSON(objectJson["actorReferenceAssociations"]["parentObjectReference"]),
                  fromJSON(objectJson["actorReferenceAssociations"]["actorComponentReferences"])]
            objectCopy.properties = fromJSON(objectJson["properties"])
            objectCopy.propertyTypes = fromJSON(objectJson["propertyTypes"])
            objectCopy.actorSpecificInfo = fromJSON(objectJson["actorSpecificInfo"])
            objectCopy.perObjectVersionData = fromJSON(objectJson["perObjectVersionData"])
            objects.append(objectCopy)

         levelSaveVersion = levelData["levelSaveVersion"]

         collectables2 = []
         for objectReference in levelData["collectables2"]:
            collectables2.append(fromJSON(objectReference))

         saveObjectVersionData = fromJSON(levelData["saveObjectVersionData"])

         levels.append(sav_parse.Level(levelName, actorAndComponentObjectHeaders, levelPersistentFlag, collectables1, objects, levelSaveVersion, collectables2, saveObjectVersionData))

      print("Writing Save")
      try:
         sav_to_resave.saveFile(sav_parse.ParsedSave(saveFileInfo, persistentLevelSaveObjectVersionData, partitions, levels, aLevelName, dropPodObjectReferenceList, extraObjectReferenceList), outFilename)
         print("Validating Save")
         parsedSave = sav_parse.readFullSaveFile(outFilename)
         print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating save to '{outFilename}': {error}")

   elif len(sys.argv) in (5, 6) and sys.argv[1] == "--set-session-name" and os.path.isfile(sys.argv[3]):
      newSessionName = sys.argv[2]
      savFilename = sys.argv[3]
      outFilename = sys.argv[4]
      changeTimeFlag = True
      if len(sys.argv) == 6 and sys.argv[5] == "--same-time":
         changeTimeFlag = False

      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)
      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      parsedSave.saveFileInfo.sessionName = newSessionName

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (2, 3, 4) and sys.argv[1] == "--find-free-stuff" and (len(sys.argv) < 4 or os.path.isfile(sys.argv[3])):

      if len(sys.argv) == 2:
         for item in sav_data.freeStuff.FREE_DROPPED_ITEMS:
            total = 0
            for (quantity, position, instanceName) in sav_data.freeStuff.FREE_DROPPED_ITEMS[item]:
               total += quantity
            print(f"{total} x {sav_parse.pathNameToReadableName(item)}")
      else:

         itemName = sys.argv[2]

         droppedInstances = {}
         for item in sav_data.freeStuff.FREE_DROPPED_ITEMS:
            if sav_parse.pathNameToReadableName(item) == itemName:
               for idx in range(len(sav_data.freeStuff.FREE_DROPPED_ITEMS[item])):
                  (quantity, position, instanceName) = sav_data.freeStuff.FREE_DROPPED_ITEMS[item][idx]
                  droppedInstances[instanceName] = (quantity, position)
               break
         if len(droppedInstances) == 0:
            print(f"No {itemName}")
         else:

            if len(sys.argv) == 4:
               savFilename = sys.argv[3]
               try:
                  parsedSave = sav_parse.readFullSaveFile(savFilename)
                  for level in parsedSave.levels:
                     if level.collectables1 is not None:
                        for collectable in level.collectables1:
                           if collectable.pathName in droppedInstances:
                              del droppedInstances[collectable.pathName]
               except Exception as error:
                  raise Exception(f"ERROR: While processing '{savFilename}': {error}")

            total = 0
            for instanceName in droppedInstances:
               (quantity, position) = droppedInstances[instanceName]
               print(f"{quantity} x {itemName} at {position}")
               total += quantity

            if pilAvailableFlag:
               MAP_BASENAME_FREE_ITEM = "save_free.png"
               if os.path.isfile(sav_to_html.MAP_BASENAME_BLANK):
                  imageFont = ImageFont.truetype(sav_to_html.FONT_FILENAME, sav_to_html.MAP_FONT_SIZE)
                  smallFont = ImageFont.truetype(sav_to_html.FONT_FILENAME, 400/sav_to_html.MAP_DESCALE)
                  diImage = Image.open(sav_to_html.MAP_BASENAME_BLANK)
                  diDraw = ImageDraw.Draw(diImage)
                  for instanceName in droppedInstances:
                     (quantity, position) = droppedInstances[instanceName]
                     posX = sav_to_html.adjPos(position[0], False)
                     posY = sav_to_html.adjPos(position[1], True)
                     diDraw.ellipse((posX-2, posY-2, posX+2, posY+2), fill=(255,255,0))
                     diDraw.text((posX, posY), str(quantity), font=smallFont, fill=(0,0,0))
                  if len(sys.argv) == 4:
                     diDraw.text(sav_to_html.MAP_TEXT_POSITION, parsedSave.saveFileInfo.saveDatetime.strftime(f"{total} free {itemName}\n{parsedSave.saveFileInfo.sessionName} %m/%d/%Y %I:%M:%S %p"), font=imageFont, fill=(0,0,0))
                  else:
                     diDraw.text(sav_to_html.MAP_TEXT_POSITION, f"All {total} free {itemName}", font=imageFont, fill=(0,0,0))
                  imageFilename = MAP_BASENAME_FREE_ITEM
                  diImage.crop(sav_to_html.CROP_SETTINGS).save(imageFilename)
                  sav_to_html.chown(imageFilename)

   elif len(sys.argv) == 3 and sys.argv[1] == "--list-players" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(parsedSave.levels)
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            characterPosition = None
            for level in parsedSave.levels:
               for actorOrComponentObjectHeader in level.actorAndComponentObjectHeaders:
                  if actorOrComponentObjectHeader.instanceName == characterPlayer:
                     characterPosition = actorOrComponentObjectHeader.position
            playerName = getPlayerName(parsedSave.levels, characterPlayer)
            if playerName is None:
               print(f"{characterPlayer} at {characterPosition}")
            else:
               print(f"{characterPlayer} ({playerName}) at {characterPosition}")
      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

   elif len(sys.argv) == 4 and sys.argv[1] == "--list-player-inventory" and os.path.isfile(sys.argv[3]):
      playerId = sys.argv[2]
      savFilename = sys.argv[3]
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(parsedSave.levels)

         playerInventory = None
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            if characterPlayerMatch(characterPlayer, playerId, parsedSave.levels):
               playerInventory = inventoryPath

         if playerInventory is None:
            print(f"Unable to match player '{playerId}'", file=sys.stderr)
            exit(1)

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == playerInventory:
                  inventoryStacks = sav_parse.getPropertyValue(object.properties, "mInventoryStacks")
                  if inventoryStacks:
                     for idx in range(len(inventoryStacks)):
                        item = inventoryStacks[idx][0]
                        if item[0][0] == "Item" and item[1][0] == "NumItems":
                           itemName = item[0][1][0]
                           if len(itemName) == 0:
                              print(f"[{str(idx).rjust(2)}] Empty")
                           else:
                              if CHECK_ITEMS_FOR_PLAYER_INVENTORY and itemName not in sav_data.data.ITEMS_FOR_PLAYER_INVENTORY:
                                 print(f"{itemName} not found in sav_data.data.ITEMS_FOR_PLAYER_INVENTORY.  Recommend adding to support --import-player-inventory and --tweak-player-inventory functions.")
                              itemName = sav_parse.pathNameToReadableName(itemName)
                              itemQuantity = item[1][1]

                              extraInformation = item[0][1][1]
                              extraInformationStr = ""
                              if isinstance(extraInformation, list):
                                 # Jetpack:  ('/Script/FactoryGame.FGJetPackItemState', [('CurrentFuel', 1.0), ('CurrentFuelType', 2), ('SelectedFuelType', 0)], [('CurrentFuel', 'FloatProperty', 0), ('CurrentFuelType', 'IntProperty', 0), ('SelectedFuelType', 'IntProperty', 0)])
                                 # Chainsaw: ('/Script/FactoryGame.FGChainsawItemState', [('EnergyStored', 79.14283752441406)], [('EnergyStored', 'FloatProperty', 0)])
                                 extraInformationStr = f": {sav_parse.toString(extraInformation[1])}"

                              print(f"[{str(idx).rjust(2)}] {str(itemQuantity).rjust(3)} x {itemName}{extraInformationStr}")
      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

   elif len(sys.argv) in (8, 9) and sys.argv[1] == "--move-player" and os.path.isfile(sys.argv[6]):
      playerId = sys.argv[2]
      positionX = float(sys.argv[3])
      positionY = float(sys.argv[4])
      positionZ = float(sys.argv[5])
      savFilename = sys.argv[6]
      outFilename = sys.argv[7]
      changeTimeFlag = True
      if len(sys.argv) == 9 and sys.argv[8] == "--same-time":
         changeTimeFlag = False

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(parsedSave.levels)

         target = None
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            if characterPlayerMatch(characterPlayer, playerId, parsedSave.levels):
               level = parsedSave.levels[-1]
               for actorOrComponentObjectHeader in level.actorAndComponentObjectHeaders:
                  if isinstance(actorOrComponentObjectHeader, sav_parse.ActorHeader) and actorOrComponentObjectHeader.instanceName == characterPlayer:
                     print(f"Moving {characterPlayer} from {actorOrComponentObjectHeader.position} to {positionX},{positionY},{positionZ}")
                     actorOrComponentObjectHeader.position[0] = positionX
                     actorOrComponentObjectHeader.position[1] = positionY
                     actorOrComponentObjectHeader.position[2] = positionZ
                     modifiedFlag = True
                     break
               break

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print(f"Unable to match player '{playerId}'", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (4, 5) and sys.argv[1] == "--find-node" and (len(sys.argv) == 4 or os.path.isfile(sys.argv[4])):
      target = (float(sys.argv[2]), float(sys.argv[3]))

      try:

         if len(sys.argv) == 5:
            savFilename = sys.argv[4]
            parsedSave = sav_parse.readFullSaveFile(savFilename)

         closestNodeName = None
         closestNodeDistance = None
         closestNodePosition = None

         for nodeName in sav_data.resourcePurity.RESOURCE_PURITY:
            nodeType, nodePurity, nodePosition, nodeCore = sav_data.resourcePurity.RESOURCE_PURITY[nodeName]
            (x, y, _) = nodePosition
            distance = math.dist(target, (x / 100, y / 100))
            if closestNodeName is None or distance < closestNodeDistance:
               closestNodeName = nodeName
               closestNodeDistance = distance
               closestNodePosition = nodePosition

         print(f"{closestNodeName[33:]} is at {closestNodePosition} at a distance of {closestNodeDistance} meters.")

         nodeType, nodePurity, nodePosition, nodeCore = sav_data.resourcePurity.RESOURCE_PURITY[closestNodeName]
         nodePurity = nodePurity.name.capitalize()
         print(f"   Default setting: {nodePurity} {sav_parse.pathNameToReadableName(nodeType)}")

         if len(sys.argv) == 5:
            level = parsedSave.levels[-1]
            for object in level.objects:
               if object.instanceName == closestNodeName:
                  resourceClassOverride = sav_parse.getPropertyValue(object.properties, "mResourceClassOverride")
                  if resourceClassOverride:
                     nodeType = resourceClassOverride.pathName
                  purityOverride = sav_parse.getPropertyValue(object.properties, "mPurityOverride")
                  if purityOverride:
                     nodePurity = purityOverride[1][3:]
                  print(f"   Current setting: {nodePurity} {sav_parse.pathNameToReadableName(nodeType)}")

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

   elif len(sys.argv) == 4 and sys.argv[1] == "--find-node-near" and os.path.isfile(sys.argv[3]):
      playerId = sys.argv[2]
      savFilename = sys.argv[3]

      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(parsedSave.levels)

         target = None
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            if characterPlayerMatch(characterPlayer, playerId, parsedSave.levels):
               print(str((playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath)))

               level = parsedSave.levels[-1]
               for actorOrComponentObjectHeader in level.actorAndComponentObjectHeaders:
                  if isinstance(actorOrComponentObjectHeader, sav_parse.ActorHeader) and actorOrComponentObjectHeader.instanceName == characterPlayer:
                     target = actorOrComponentObjectHeader.position

               break

         if target is None:
            print(f"Unable to match player '{playerId}'", file=sys.stderr)
            exit(1)

         closestNodeName = None
         closestNodeDistance = None
         closestNodePosition = None

         for nodeName in sav_data.resourcePurity.RESOURCE_PURITY:
            nodeType, nodePurity, nodePosition, nodeCore = sav_data.resourcePurity.RESOURCE_PURITY[nodeName]
            distance = math.dist(target, nodePosition)
            if closestNodeName is None or distance < closestNodeDistance:
               closestNodeName = nodeName
               closestNodeDistance = distance
               closestNodePosition = nodePosition

         print(f"{closestNodeName[33:]} is at {closestNodePosition} at a distance of {closestNodeDistance} meters.")

         nodeType, nodePurity, nodePosition, nodeCore = sav_data.resourcePurity.RESOURCE_PURITY[closestNodeName]
         nodePurity = nodePurity.name.capitalize()
         print(f"   Default setting: {nodePurity} {sav_parse.pathNameToReadableName(nodeType)}")

         level = parsedSave.levels[-1]
         for object in level.objects:
            if object.instanceName == closestNodeName:
               resourceClassOverride = sav_parse.getPropertyValue(object.properties, "mResourceClassOverride")
               if resourceClassOverride:
                  nodeType = resourceClassOverride.pathName
               purityOverride = sav_parse.getPropertyValue(object.properties, "mPurityOverride")
               if purityOverride:
                  nodePurity = purityOverride[1][3:]
               print(f"   Current setting: {nodePurity} {sav_parse.pathNameToReadableName(nodeType)}")

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

   elif len(sys.argv) in (7, 8) and sys.argv[1] == "--set-node" and os.path.isfile(sys.argv[5]):
      nodeName = sys.argv[2]
      nodeType = sys.argv[3]
      nodePurity = sys.argv[4]
      savFilename = sys.argv[5]
      outFilename = sys.argv[6]
      changeTimeFlag = True
      if len(sys.argv) == 8 and sys.argv[7] == "--same-time":
         changeTimeFlag = False

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         (resultStatus, resultMessage) = setNodeType(nodeName, nodeType, nodePurity)
         modifiedFlag = resultStatus == ChangeResultEnum.CHANGE
         print(resultMessage)

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: Failed to find node '{originalNodeName}' to modify.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) == 4 and sys.argv[1] == "--export-node-types" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      outFilename = sys.argv[3]

      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         # Note: Fracking Cores have mResourceClassOverride, but don't have mPurityOverride

         nodeListing = {}

         PURITY_TRANSLATION = {
            sav_data.resourcePurity.Purity.IMPURE: "Impure",
            sav_data.resourcePurity.Purity.NORMAL: "Normal",
            sav_data.resourcePurity.Purity.PURE: "Pure"}
         # One might ask, why loop over RESOURCE_PURITY instead of just check it inside the level.objects loop below.
         # The reason is specifically because of the nodeCore isn't lookup'able in RESOURCE_PURITY.
         for nodeName in sav_data.resourcePurity.RESOURCE_PURITY:
            nodeType, nodePurity, nodePosition, nodeCore = sav_data.resourcePurity.RESOURCE_PURITY[nodeName]
            if nodeType != "Desc_Geyser_C":
               nodeListing[nodeName] = (sav_parse.pathNameToReadableName(nodeType), PURITY_TRANSLATION[nodePurity], "Absent")
               if nodeCore is not None:
                  if nodeCore not in nodeListing:
                     nodeListing[nodeCore] = (sav_parse.pathNameToReadableName(nodeType), None, "Absent")

         nodes = []
         level = parsedSave.levels[-1]
         for actorOrComponentObjectHeader in level.actorAndComponentObjectHeaders:
            if isinstance(actorOrComponentObjectHeader, sav_parse.ActorHeader) and \
                  actorOrComponentObjectHeader.typePath in ("/Game/FactoryGame/Resource/BP_ResourceNode.BP_ResourceNode_C",
                                                            "/Game/FactoryGame/Resource/BP_FrackingCore.BP_FrackingCore_C",
                                                            "/Game/FactoryGame/Resource/BP_FrackingSatellite.BP_FrackingSatellite_C"):
               nodes.append(actorOrComponentObjectHeader.instanceName)
         for object in level.objects:
            if object.instanceName in nodes:
               nodeType = None
               nodePurity = None
               if object.instanceName in nodeListing:
                  (nodeType, nodePurity, _) = nodeListing[object.instanceName]
               resourceClassOverride = sav_parse.getPropertyValue(object.properties, "mResourceClassOverride")
               if resourceClassOverride:
                  nodeType = sav_parse.pathNameToReadableName(resourceClassOverride.pathName)
               if nodeType is None:
                  print(f"Skipping export of {object.instanceName} since the node type is unknown.")
               else:
                  purityOverride = sav_parse.getPropertyValue(object.properties, "mPurityOverride")
                  if purityOverride:
                     nodePurity = purityOverride[1][3:]
                  nodeListing[object.instanceName] = (nodeType, nodePurity, "Present")

         jdata = {}
         for nodePathName in sorted(nodeListing.keys()):
            jdata[nodePathName[33:]] = nodeListing[nodePathName]

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      print(f"Writing {outFilename}")
      with open(outFilename, "w") as fout:
         json.dump(jdata, fout, indent=2)

   elif len(sys.argv) in (5, 6) and sys.argv[1] == "--import-node-types" and os.path.isfile(sys.argv[2]) and os.path.isfile(sys.argv[3]):
      savFilename = sys.argv[2]
      inFilename = sys.argv[3]
      outFilename = sys.argv[4]
      changeTimeFlag = True
      if len(sys.argv) == 6 and sys.argv[5] == "--same-time":
         changeTimeFlag = False

      with open(inFilename, "r") as fin:
         jdata = json.load(fin)

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         for nodeName in jdata:
            nodeType, nodePurity = jdata[nodeName][:2]
            (resultStatus, resultMessage) = setNodeType(nodeName, nodeType, nodePurity)
            print(resultMessage)

            if resultStatus == ChangeResultEnum.ERROR:
               exit(1)
            elif resultStatus == ChangeResultEnum.CHANGE:
               modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: All resource nodes already match json.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) == 5 and sys.argv[1] == "--export-player-inventory" and os.path.isfile(sys.argv[3]):
      playerId = sys.argv[2]
      savFilename = sys.argv[3]
      outFilename = sys.argv[4]

      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(parsedSave.levels)

         playerInventory = None
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            if characterPlayerMatch(characterPlayer, playerId, parsedSave.levels):
               playerInventory = inventoryPath

         if playerInventory is None:
            print(f"Unable to match player '{playerId}'", file=sys.stderr)
            exit(1)

         inventoryContents: list[list | None] = []

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == playerInventory:
                  inventoryStacks = sav_parse.getPropertyValue(object.properties, "mInventoryStacks")
                  if inventoryStacks:
                     for idx in range(len(inventoryStacks)):
                        item = inventoryStacks[idx][0]
                        if item[0][0] == "Item" and item[1][0] == "NumItems":
                           itemName = item[0][1][0]
                           if len(itemName) == 0:
                              inventoryContents.append(None)
                           elif isinstance(item[0][1][1], list):
                              inventoryContents.append([itemName, item[1][1], item[0][1][1][0], item[0][1][1][1]])
                           else:
                              inventoryContents.append([itemName, item[1][1]])

         with open(outFilename, "w") as fout:
            json.dump(inventoryContents, fout, indent=2)

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

   elif len(sys.argv) in (6, 7) and sys.argv[1] == "--import-player-inventory" and os.path.isfile(sys.argv[3]) and os.path.isfile(sys.argv[4]):
      playerId = sys.argv[2]
      savFilename = sys.argv[3]
      inFilename = sys.argv[4]
      outFilename = sys.argv[5]
      changeTimeFlag = True
      if len(sys.argv) == 7 and sys.argv[6] == "--same-time":
         changeTimeFlag = False

      with open(inFilename, "r") as fin:
         importedInventoryContents: list[list | None] = json.load(fin)

      for inventoryContent in importedInventoryContents:
         if inventoryContent is not None:
            itemPathName = inventoryContent[0]
            if itemPathName not in sav_data.data.ITEMS_FOR_PLAYER_INVENTORY:
               print(f"ERROR: {itemPathName} not a valid item path name.")
               exit(1)

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(parsedSave.levels)

         playerInventory = None
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            if characterPlayerMatch(characterPlayer, playerId, parsedSave.levels):
               playerInventory = inventoryPath

         if playerInventory is None:
            print(f"Unable to match player '{playerId}'")
            exit(1)

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == playerInventory:
                  inventoryStacks = sav_parse.getPropertyValue(object.properties, "mInventoryStacks")
                  if inventoryStacks:
                     for idx in range(len(inventoryStacks)):
                        if idx < len(importedInventoryContents):
                           print(f"Replacing {sav_parse.toString(inventoryStacks[idx][0])}")
                           if importedInventoryContents[idx] is None:
                              inventoryStacks[idx][0][0] = ["Item", ["", 1]]
                              inventoryStacks[idx][0][1] = ["NumItems", 0]
                              print(f"Setting player {playerInventory}'s inventory slot {idx} to be Empty")
                           elif len(importedInventoryContents[idx]) == 2:
                              (itemPathName, itemQuantity) = importedInventoryContents[idx]
                              inventoryStacks[idx][0][0] = ["Item", [itemPathName, 1]]
                              inventoryStacks[idx][0][1] = ["NumItems", itemQuantity]
                              print(f"Setting player {playerInventory}'s inventory slot {idx} to include {itemQuantity} x {sav_parse.pathNameToReadableName(itemPathName)}")
                           elif len(importedInventoryContents[idx]) == 4:
                              (itemPathName, itemQuantity, itemPropName, itemProps) = importedInventoryContents[idx]
                              if itemPropName == "/Script/FactoryGame.FGJetPackItemState":
                                 inventoryStacks[idx][0][0] = ["Item", [itemPathName, [itemPropName, itemProps, [['CurrentFuel', 'FloatProperty', 0], ['CurrentFuelType', 'IntProperty', 0], ['SelectedFuelType', 'IntProperty', 0]]]]]
                              if itemPropName == "/Script/FactoryGame.FGChainsawItemState":
                                 inventoryStacks[idx][0][0] = ["Item", [itemPathName, [itemPropName, itemProps, [['EnergyStored', 'FloatProperty', 0]]]]]
                              inventoryStacks[idx][0][1] = ["NumItems", itemQuantity]
                              print(f"Setting player {playerInventory}'s inventory slot {idx} to include {itemQuantity} x {sav_parse.pathNameToReadableName(itemPathName)} with {sav_parse.toString(itemProps)}")
                           modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: Failed to find inventory slot to modify.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (8, 9) and sys.argv[1] == "--tweak-player-inventory" and os.path.isfile(sys.argv[6]):
      playerId = sys.argv[2]
      tweakSlotIdx = int(sys.argv[3])
      tweakItemName = sys.argv[4]
      tweakQuantity = int(sys.argv[5])
      savFilename = sys.argv[6]
      outFilename = sys.argv[7]
      changeTimeFlag = True
      if len(sys.argv) == 9 and sys.argv[8] == "--same-time":
         changeTimeFlag = False

      if tweakItemName not in sav_data.data.ITEMS_FOR_PLAYER_INVENTORY:
         for className in sav_data.readableNames.READABLE_PATH_NAME_CORRECTIONS:
            if tweakItemName == sav_data.readableNames.READABLE_PATH_NAME_CORRECTIONS[className]:
               suffixSearch = f".{className}"
               for pathName in sav_data.data.ITEMS_FOR_PLAYER_INVENTORY:
                  if pathName.endswith(suffixSearch):
                     print(f"Using '{pathName}' for {tweakItemName}")
                     tweakItemName = pathName
                     break
               break

         if tweakItemName not in sav_data.data.ITEMS_FOR_PLAYER_INVENTORY:
            print(f"ERROR: {tweakItemName} not a valid item path name.")
            exit(1)

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(parsedSave.levels)

         playerInventory = None
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            if characterPlayerMatch(characterPlayer, playerId, parsedSave.levels):
               playerInventory = inventoryPath

         if playerInventory is None:
            print(f"Unable to match player '{playerId}'")
            exit(1)

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == playerInventory:
                  inventoryStacks = sav_parse.getPropertyValue(object.properties, "mInventoryStacks")
                  if inventoryStacks:
                     for idx in range(len(inventoryStacks)):
                        if idx == tweakSlotIdx:
                           print(f"Replacing {sav_parse.toString(inventoryStacks[idx][0])}")
                           inventoryStacks[idx][0][0] = ["Item", [tweakItemName, 1]]
                           inventoryStacks[idx][0][1] = ["NumItems", tweakQuantity]
                           print(f"Setting player {playerInventory}'s inventory slot {tweakSlotIdx} to include {tweakQuantity} x {sav_parse.pathNameToReadableName(tweakItemName)}")
                           modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: Failed to find inventory slot to modify.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (7, 8) and sys.argv[1] == "--rotate-foundations" and os.path.isfile(sys.argv[5]):
      colorPrimary = sys.argv[2]
      colorSecondary = sys.argv[3]
      clockwiseInDegrees = float(sys.argv[4]) # Game allows for small rotation in 10 degree increments
      savFilename = sys.argv[5]
      outFilename = sys.argv[6]
      changeTimeFlag = True
      if len(sys.argv) == 8 and sys.argv[7] == "--same-time":
         changeTimeFlag = False

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName.startswith("Persistent_Level:PersistentLevel.BP_GameState_C_"):
                  playerGlobalColorPresets = sav_parse.getPropertyValue(object.properties, "mPlayerGlobalColorPresets")
                  if playerGlobalColorPresets is not None:
                     for color in playerGlobalColorPresets:
                        presetName = sav_parse.getPropertyValue(color[0], "PresetName")
                        if presetName is not None:
                           presetName = presetName[3]
                           colorValue = sav_parse.getPropertyValue(color[0], "Color")
                           if colorValue is not None:
                              if colorPrimary == presetName:
                                 colorPrimary = lcTupleToSrgbHex(colorValue)
                                 print(f"Using primary color {colorPrimary}")
                              if colorSecondary == presetName:
                                 colorSecondary = lcTupleToSrgbHex(colorValue)
                                 print(f"Using secondary color {colorSecondary}")

         colorPrimary = colorPrimary.lower()
         colorSecondary = colorSecondary.lower()

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.LightweightBuildableSubsystem":
                  for lightweightBuildable in object.actorSpecificInfo:
                     if isinstance(lightweightBuildable, list):
                        (buildItemPathName, lightweightBuildableInstances) = lightweightBuildable
                        for (rotationQuaternion, position, swatchLevelPath, patternLevelPath, (primaryColor, secondaryColor), paintFinishLevelPath, patternRotation, recipeLevelPath, blueprintProxyLevelPath, lightweightDataProperty, serviceProvider, playerInfoTableIndex) in lightweightBuildableInstances:
                           if lcTupleToSrgbHex(primaryColor) == colorPrimary and lcTupleToSrgbHex(secondaryColor) == colorSecondary:
                              euler = quaternionToEuler(rotationQuaternion)
                              oldYaw = euler[2]
                              euler[2] += degreesToRadians(clockwiseInDegrees)
                              if euler[2] > math.pi:
                                 euler[2] -= 2 * math.pi
                              elif euler[2] < -math.pi:
                                 euler[2] += 2 * math.pi
                              print(f"Rotated foundation {buildItemPathName} from {radiansToDegrees(oldYaw)} to {radiansToDegrees(euler[2])}.")
                              newRotationQuaternion = eulerToQuaternion(euler)
                              for idx in range(4):
                                 rotationQuaternion[idx] = newRotationQuaternion[idx]
                              modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: Failed to find foundations to modify.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (4, 5) and sys.argv[1] == "--clear-fog" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      outFilename = sys.argv[3]
      changeTimeFlag = True
      if len(sys.argv) == 5 and sys.argv[4] == "--same-time":
         changeTimeFlag = False

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.MapManager":
                  fogOfWarRawData = sav_parse.getPropertyValue(object.properties, "mFogOfWarRawData")
                  if fogOfWarRawData is not None and len(fogOfWarRawData) == 1048576:
                     for idx in range(262144):
                        fogOfWarRawData[idx*4+0] = 0
                        fogOfWarRawData[idx*4+1] = 0
                        fogOfWarRawData[idx*4+2] = 255
                        fogOfWarRawData[idx*4+3] = 255
                     modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: Failed to find mFogOfWarRawData property to modify.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) == 5 and sys.argv[1] == "--export-hotbar" and os.path.isfile(sys.argv[3]):
      playerId = sys.argv[2]
      savFilename = sys.argv[3]
      outFilename = sys.argv[4]
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(parsedSave.levels)

         playerState = None
         playerCharacter = None
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            if characterPlayerMatch(characterPlayer, playerId, parsedSave.levels):
               playerState = playerStateInstanceName
               playerCharacter = characterPlayer

         if playerState is None:
            print(f"Unable to match player '{playerId}'", file=sys.stderr)
            exit(1)

         playerName = None
         if playerCharacter is not None:
            playerName = getPlayerName(parsedSave.levels, playerCharacter)

         print()
         if playerName is None:
            print(f"===== {playerId} =====")
         else:
            print(f"===== {playerName} ({playerId}) =====")
         print()

         playersHotbars: dict[str, int] = {}
         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == playerState:
                  playerHotbars = sav_parse.getPropertyValue(object.properties, "mPlayerHotbars")
                  if playerHotbars is not None:
                     for hotbarIdx in range(len(playerHotbars)):
                        playersHotbars[playerHotbars[hotbarIdx].pathName] = hotbarIdx

         playersHotbarItems: dict[str, tuple[int, int]] = {}
         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName in playersHotbars:
                  shortcuts = sav_parse.getPropertyValue(object.properties, "mShortcuts")
                  if shortcuts is not None:
                     for hotbarItemIdx in range(len(shortcuts)):
                        hotbarIdx = playersHotbars[object.instanceName]
                        item = shortcuts[hotbarItemIdx].pathName
                        if len(item) > 0:
                           #print(f"[{hotbarIdx}][{hotbarItemIdx}] {item}")
                           playersHotbarItems[item] = (hotbarIdx, hotbarItemIdx)

         hotbarContents: dict[int, dict[int, str | None]] = {}
         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName in playersHotbarItems:
                  (hotbarIdx, hotbarItemIdx) = playersHotbarItems[object.instanceName]
                  hotbarItem = None
                  recipeToActivate = sav_parse.getPropertyValue(object.properties, "mRecipeToActivate")
                  if recipeToActivate is not None:
                     hotbarItem = recipeToActivate.pathName
                     print(f"[{hotbarIdx}][{hotbarItemIdx}] Recipe: {hotbarItem}")
                  else:
                     customizationRecipeToActivate = sav_parse.getPropertyValue(object.properties, "mCustomizationRecipeToActivate")
                     if customizationRecipeToActivate is not None:
                        hotbarItem = customizationRecipeToActivate.pathName
                        print(f"[{hotbarIdx}][{hotbarItemIdx}] Customization Recipe: {hotbarItem}")
                     else:
                        emoteToActivate = sav_parse.getPropertyValue(object.properties, "mEmoteToActivate")
                        if emoteToActivate is not None:
                           hotbarItem = emoteToActivate.pathName
                           print(f"[{hotbarIdx}][{hotbarItemIdx}] Emote: {hotbarItem}")
                        else:
                           blueprintName = sav_parse.getPropertyValue(object.properties, "mBlueprintName")
                           if blueprintName is not None:
                              hotbarItem = blueprintName
                              print(f"[{hotbarIdx}][{hotbarItemIdx}] Blueprint: {hotbarItem}")
                           else:
                              print(f"object={sav_parse.toString(object.properties)}")

                  if hotbarIdx not in hotbarContents:
                     hotbarContents[hotbarIdx] = {}
                  hotbarContents[hotbarIdx][hotbarItemIdx] = hotbarItem

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      with open(outFilename, "w") as fout:
         json.dump(hotbarContents, fout, indent=2)

   elif len(sys.argv) in (6, 7) and sys.argv[1] == "--import-hotbar" and os.path.isfile(sys.argv[3]) and os.path.isfile(sys.argv[4]):
      playerId = sys.argv[2]
      savFilename = sys.argv[3]
      inFilename = sys.argv[4]
      outFilename = sys.argv[5]
      changeTimeFlag = True
      if len(sys.argv) == 7 and sys.argv[6] == "--same-time":
         changeTimeFlag = False

      with open(inFilename, "r") as fin:
         hotbarContents_strKeys: dict[str, dict[str, str]] = json.load(fin)

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(parsedSave.levels)

         playerState = None
         playerCharacter = None
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            if characterPlayerMatch(characterPlayer, playerId, parsedSave.levels):
               playerState = playerStateInstanceName
               playerCharacter = characterPlayer

         if playerCharacter is None:
            print(f"Unable to match player '{playerId}'", file=sys.stderr)
            exit(1)

         playerName = getPlayerName(parsedSave.levels, playerCharacter)

         print()
         if playerName is None:
            print(f"===== {playerId} =====")
         else:
            print(f"===== {playerName} ({playerId}) =====")
         print()

         playersHotbars = {}
         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == playerState:
                  playerHotbars = sav_parse.getPropertyValue(object.properties, "mPlayerHotbars")
                  if playerHotbars is not None:
                     for hotbarIdx in range(len(playerHotbars)):
                        playersHotbars[playerHotbars[hotbarIdx].pathName] = hotbarIdx

         objectsToRemove = []
         objectsToAdd = []
         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName in playersHotbars:
                  shortcuts = sav_parse.getPropertyValue(object.properties, "mShortcuts")
                  if shortcuts is not None:
                     for hotbarItemIdx in range(len(shortcuts)):
                        hotbarIdx = playersHotbars[object.instanceName]

                        replacementHotbarItem = None
                        replacementHotbarItemNewClassName = None
                        replacementHotbarItemNewParentName = None
                        replacementHotbarItemNewInstanceName = None
                        hotbarIdxStr = str(hotbarIdx)
                        if hotbarIdxStr in hotbarContents_strKeys:
                           hotbarItemIdxStr = str(hotbarItemIdx)
                           if hotbarItemIdxStr in hotbarContents_strKeys[hotbarIdxStr]:
                              replacementHotbarItem = hotbarContents_strKeys[hotbarIdxStr][hotbarItemIdxStr]

                              if replacementHotbarItem is None:
                                 continue
                              elif replacementHotbarItem.startswith("/Game/FactoryGame/Buildable/-Shared/Customization/"):
                                 replacementHotbarItemNewClassName = "FGFactoryCustomizationShortcut"
                              elif replacementHotbarItem.startswith("/Game/FactoryGame/Emotes/"):
                                 replacementHotbarItemNewClassName = "FGEmoteShortcut"
                              elif replacementHotbarItem.startswith("/Game/FactoryGame/"):
                                 replacementHotbarItemNewClassName = "FGRecipeShortcut"
                              else: # Blueprint
                                 replacementHotbarItemNewClassName = "FGBlueprintShortcut"

                              replacementHotbarItemNewParentName = object.instanceName
                              replacementHotbarItemNewInstanceName = f"{replacementHotbarItemNewParentName}.{replacementHotbarItemNewClassName}_{uuid.uuid4().hex}"

                        item = shortcuts[hotbarItemIdx].pathName
                        if len(item) == 0:
                           if replacementHotbarItem is None or replacementHotbarItemNewClassName is None or replacementHotbarItemNewParentName is None or replacementHotbarItemNewInstanceName is None:
                              print(f"[{hotbarIdx}][{hotbarItemIdx}] is currently empty and should remain empty") # No change
                           else:
                              print(f"[{hotbarIdx}][{hotbarItemIdx}] is currently empty and should be replaced with {replacementHotbarItem}") # Need to add an Object
                              objectsToAdd.append((hotbarItemIdx, replacementHotbarItemNewInstanceName, replacementHotbarItemNewClassName, replacementHotbarItemNewParentName, replacementHotbarItem))
                              shortcuts[hotbarItemIdx].levelName = "Persistent_Level"
                              shortcuts[hotbarItemIdx].pathName = replacementHotbarItemNewInstanceName
                              modifiedFlag = True
                        else:
                           if replacementHotbarItem is None or replacementHotbarItemNewClassName is None or replacementHotbarItemNewParentName is None or replacementHotbarItemNewInstanceName is None:
                              print(f"[{hotbarIdx}][{hotbarItemIdx}] currently contains {item} and should be removed.") # Set this reference to empty, and remove the Object
                              objectsToRemove.append(item)
                              shortcuts[hotbarItemIdx].levelName = ""
                              shortcuts[hotbarItemIdx].pathName = ""
                              modifiedFlag = True
                           else:
                              hotbarItem = None
                              persistentLevel = parsedSave.levels[-1]
                              for persistentLevelObject in persistentLevel.objects:
                                 if persistentLevelObject.instanceName == item:
                                    recipeToActivate = sav_parse.getPropertyValue(persistentLevelObject.properties, "mRecipeToActivate")
                                    if recipeToActivate is not None:
                                       hotbarItem = recipeToActivate.pathName
                                    else:
                                       customizationRecipeToActivate = sav_parse.getPropertyValue(persistentLevelObject.properties, "mCustomizationRecipeToActivate")
                                       if customizationRecipeToActivate is not None:
                                          hotbarItem = customizationRecipeToActivate.pathName
                                       else:
                                          emoteToActivate = sav_parse.getPropertyValue(persistentLevelObject.properties, "mEmoteToActivate")
                                          if emoteToActivate is not None:
                                             hotbarItem = emoteToActivate.pathName
                                          else:
                                             blueprintName = sav_parse.getPropertyValue(persistentLevelObject.properties, "mBlueprintName")
                                             if blueprintName is not None:
                                                hotbarItem = blueprintName

                              if hotbarItem == replacementHotbarItem:
                                 print(f"[{hotbarIdx}][{hotbarItemIdx}] currently contains {item} representing {hotbarItem} which already matches {replacementHotbarItem}") # No change
                              else:
                                 print(f"[{hotbarIdx}][{hotbarItemIdx}] currently contains {item} representing {hotbarItem} should be replaced with {replacementHotbarItem}") # Delete/Add
                                 objectsToRemove.append(item)
                                 objectsToAdd.append((hotbarItemIdx, replacementHotbarItemNewInstanceName, replacementHotbarItemNewClassName, replacementHotbarItemNewParentName, replacementHotbarItem))
                                 shortcuts[hotbarItemIdx].pathName = replacementHotbarItemNewInstanceName
                                 modifiedFlag = True

         level = parsedSave.levels[-1]
         for actorOrComponentObjectHeader in level.actorAndComponentObjectHeaders:
            if isinstance(actorOrComponentObjectHeader, sav_parse.ComponentHeader) and actorOrComponentObjectHeader.instanceName in objectsToRemove:
               level.actorAndComponentObjectHeaders.remove(actorOrComponentObjectHeader)
               print(f"Removed object {actorOrComponentObjectHeader.instanceName}")
         for object in level.objects:
            if object.instanceName in objectsToRemove:
               level.objects.remove(object)
               print(f"Removed {object.instanceName}")

         for (hotbarItemIdx, replacementHotbarItemNewInstanceName, replacementHotbarItemNewClassName, replacementHotbarItemNewParentName, replacementHotbarItem) in objectsToAdd:
            #print(f"Adding {replacementHotbarItemNewInstanceName} with {replacementHotbarItem}")

            #<ComponentHeader: className=/Script/FactoryGame.FGRecipeShortcut, rootObject=Persistent_Level, instanceName=Persistent_Level:PersistentLevel.BP_PlayerState_C_2147448362.FGPlayerHotbar_2147448352.FGRecipeShortcut_2147448312, parentActorName=Persistent_Level:PersistentLevel.BP_PlayerState_C_2147448362.FGPlayerHotbar_2147448352>
            #<ComponentHeader: className=/Script/FactoryGame.FGEmoteShortcut, rootObject=Persistent_Level, instanceName=Persistent_Level:PersistentLevel.BP_PlayerState_C_2147354924.FGPlayerHotbar_2147354914.FGEmoteShortcut_2147354903, parentActorName=Persistent_Level:PersistentLevel.BP_PlayerState_C_2147354924.FGPlayerHotbar_2147354914>
            #<ComponentHeader: className=/Script/FactoryGame.FGBlueprintShortcut, rootObject=Persistent_Level, instanceName=Persistent_Level:PersistentLevel.BP_PlayerState_C_2147448362.FGPlayerHotbar_2147448352.FGBlueprintShortcut_2147448315, parentActorName=Persistent_Level:PersistentLevel.BP_PlayerState_C_2147448362.FGPlayerHotbar_2147448352>
            newComponentHeader = sav_parse.ComponentHeader()
            newComponentHeader.className = f"/Script/FactoryGame.{replacementHotbarItemNewClassName}"
            newComponentHeader.rootObject = "Persistent_Level"
            newComponentHeader.instanceName = replacementHotbarItemNewInstanceName
            newComponentHeader.flags = 0
            newComponentHeader.parentActorName = replacementHotbarItemNewParentName
            level.actorAndComponentObjectHeaders.append(newComponentHeader)
            #print(f"Created new component header {newComponentHeader.instanceName}")

            #<Object: instanceName=Persistent_Level:PersistentLevel.BP_PlayerState_C_2147448362.FGPlayerHotbar_2147448361.FGRecipeShortcut_2147448341, objectGameVersion=46, flag=0, actorReferenceAssociations=n/a, properties=[[('mRecipeToActivate', <ObjectReference: levelName=, pathName=/Game/FactoryGame/Recipes/Buildings/Recipe_Workshop.Recipe_Workshop_C>), ('mShortcutIndex', 5)]], actorSpecificInfo=[None]>
            #<Object: instanceName=Persistent_Level:PersistentLevel.BP_PlayerState_C_2147195792.FGPlayerHotbar_2147195782.FGEmoteShortcut_2147195772, objectGameVersion=46, flag=0, actorReferenceAssociations=n/a, properties=[[('mEmoteToActivate', <ObjectReference: levelName=, pathName=/Game/FactoryGame/Emotes/Emote_Heart.Emote_Heart_C>)]], actorSpecificInfo=[None]>
            #<Object: instanceName=Persistent_Level:PersistentLevel.BP_PlayerState_C_2147448362.FGPlayerHotbar_2147448352.FGBlueprintShortcut_2147448316, objectGameVersion=46, flag=0, actorReferenceAssociations=n/a, properties=[[('mBlueprintName', 'Conveyor Poles 05 Hypertube Half'), ('mShortcutIndex', 1)]], actorSpecificInfo=[None]>
            newObject = sav_parse.Object()
            newObject.instanceName = replacementHotbarItemNewInstanceName
            newObject.objectGameVersion = parsedSave.saveFileInfo.saveVersion
            newObject.shouldMigrateObjectRefsToPersistentFlag = False
            newObject.actorReferenceAssociations = None

            if replacementHotbarItemNewClassName == "FGRecipeShortcut":
               newRecipeObjectReference = sav_parse.ObjectReference("", replacementHotbarItem)
               newObject.properties    = [("mRecipeToActivate", newRecipeObjectReference), ("mShortcutIndex", hotbarItemIdx)]
               newObject.propertyTypes = [("mRecipeToActivate", "ObjectProperty", 0),      ("mShortcutIndex", "IntProperty", 0)]
            elif replacementHotbarItemNewClassName == "FGFactoryCustomizationShortcut":
               newRecipeObjectReference = sav_parse.ObjectReference("", replacementHotbarItem)
               newObject.properties    = [("mCustomizationRecipeToActivate", newRecipeObjectReference), ("mShortcutIndex", hotbarItemIdx)]
               newObject.propertyTypes = [("mCustomizationRecipeToActivate", "ObjectProperty", 0),      ("mShortcutIndex", "IntProperty", 0)]
            elif replacementHotbarItemNewClassName == "FGEmoteShortcut":
               newRecipeObjectReference = sav_parse.ObjectReference("", replacementHotbarItem)
               newObject.properties    = [("mEmoteToActivate", newRecipeObjectReference), ("mShortcutIndex", hotbarItemIdx)]
               newObject.propertyTypes = [("mEmoteToActivate", "ObjectProperty", 0),      ("mShortcutIndex", "IntProperty", 0)]
            elif replacementHotbarItemNewClassName == "FGBlueprintShortcut":
               newObject.properties    = [("mBlueprintName", replacementHotbarItem), ("mShortcutIndex", hotbarItemIdx)]
               newObject.propertyTypes = [("mBlueprintName", "StrProperty", 0),      ("mShortcutIndex", "IntProperty", 0)]

            newObject.actorSpecificInfo = None
            newObject.perObjectVersionData = None
            level.objects.append(newObject)
            print(f"Created new object {newObject.instanceName} containing {replacementHotbarItem}")

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("No hotbar changes needed.")
         exit(2)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
            print("NOTE: If any recipes are added to your hotbar that have not been unlocked, they will not appear in-game until they are unlocked.  Once unlocked, the recipe(s) will appear on your hotbar instantly.")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (5, 6) and sys.argv[1] == "--change-num-inventory-slots" and os.path.isfile(sys.argv[3]):
      newNumInventorySlots = int(sys.argv[2])
      savFilename = sys.argv[3]
      outFilename = sys.argv[4]
      changeTimeFlag = True
      if len(sys.argv) == 6 and sys.argv[5] == "--same-time":
         changeTimeFlag = False

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.unlockSubsystem":
                  for idx in range(len(object.properties)): # setPropertyValue
                     (haystackPropertyName, propertyValue) = object.properties[idx]
                     if haystackPropertyName == "mNumTotalInventorySlots":
                        if propertyValue >= newNumInventorySlots:
                           print(f"WARNING: Decreasing inventory from {propertyValue} to {newNumInventorySlots}")
                        print(f"Changing number of inventory slots from {propertyValue} to {newNumInventorySlots}")
                        object.properties[idx] = [haystackPropertyName, newNumInventorySlots]
                        modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: Failed to find mFogOfWarRawData property to modify.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (4, 5) and sys.argv[1] == "--restore-somersloops" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      outFilename = sys.argv[3]
      changeTimeFlag = True
      if len(sys.argv) == 5 and sys.argv[4] == "--same-time":
         changeTimeFlag = False

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)
         for targetPathName in sav_data.somersloop.SOMERSLOOPS:
            if addSomersloop(parsedSave.levels, targetPathName):
               modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: All Somersloops already present.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (4, 5) and sys.argv[1] == "--restore-mercer-spheres" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      outFilename = sys.argv[3]
      changeTimeFlag = True
      if len(sys.argv) == 5 and sys.argv[4] == "--same-time":
         changeTimeFlag = False

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)
         for targetPathName in sav_data.mercerSphere.MERCER_SPHERES:
            if addMercerSphere(parsedSave.levels, targetPathName):
               modifiedFlag = True
         for targetPathName in sav_data.mercerSphere.MERCER_SHRINES:
            if addMercerShrine(parsedSave.levels, targetPathName):
               modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: All Mercer Spheres already present.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) == 4 and sys.argv[1] == "--export-somersloops" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      outFilename = sys.argv[3]

      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         # Assume True because that's accurate if the Object exists or the it's not in the save at all.
         jdata = {"Somersloops": {}}
         for pathName in sav_data.somersloop.SOMERSLOOPS:
            jdata["Somersloops"][pathName] = True

         for level in parsedSave.levels:
            # Checking collectables2 because the object can be in collectables2 when collectables1 is None
            for collectable in level.collectables2:
               if collectable.pathName in sav_data.somersloop.SOMERSLOOPS:
                  jdata["Somersloops"][collectable.pathName] = False

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      print(f"Writing {outFilename}")
      with open(outFilename, "w") as fout:
         json.dump(jdata, fout, indent=2)

   elif len(sys.argv) == 4 and sys.argv[1] == "--export-mercer-spheres" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      outFilename = sys.argv[3]

      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         # Assume True because that's accurate if the Object exists or the it's not in the save at all.
         jdata = {"MercerSpheres": {}, "MercerShrines": {}}
         for pathName in sav_data.mercerSphere.MERCER_SPHERES:
            jdata["MercerSpheres"][pathName] = True
         for pathName in sav_data.mercerSphere.MERCER_SHRINES:
            jdata["MercerShrines"][pathName] = True

         for level in parsedSave.levels:
            # Checking collectables2 because the object can be in collectables2 when collectables1 is None
            for collectable in level.collectables2:
               if collectable.pathName in sav_data.mercerSphere.MERCER_SPHERES:
                  jdata["MercerSpheres"][collectable.pathName] = False
               elif collectable.pathName in sav_data.mercerSphere.MERCER_SHRINES:
                  jdata["MercerShrines"][collectable.pathName] = False

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      print(f"Writing {outFilename}")
      with open(outFilename, "w") as fout:
         json.dump(jdata, fout, indent=2)

   elif len(sys.argv) in (5, 6) and sys.argv[1] == "--import-somersloops" and os.path.isfile(sys.argv[2]) and os.path.isfile(sys.argv[3]):
      savFilename = sys.argv[2]
      inFilename = sys.argv[3]
      outFilename = sys.argv[4]
      changeTimeFlag = True
      if len(sys.argv) == 6 and sys.argv[5] == "--same-time":
         changeTimeFlag = False

      with open(inFilename, "r") as fin:
         jdata = json.load(fin)

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         if "Somersloops" in jdata:
            for pathName in jdata["Somersloops"]:
               if jdata["Somersloops"][pathName]:
                  if addSomersloop(parsedSave.levels, pathName):
                     modifiedFlag = True
               else:
                  if removeSomersloop(parsedSave.levels, pathName):
                     modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: All Somersloops already match json.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (5, 6) and sys.argv[1] == "--import-mercer-spheres" and os.path.isfile(sys.argv[2]) and os.path.isfile(sys.argv[3]):
      savFilename = sys.argv[2]
      inFilename = sys.argv[3]
      outFilename = sys.argv[4]
      changeTimeFlag = True
      if len(sys.argv) == 6 and sys.argv[5] == "--same-time":
         changeTimeFlag = False

      with open(inFilename, "r") as fin:
         jdata = json.load(fin)

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         if "MercerSpheres" in jdata:
            for pathName in jdata["MercerSpheres"]:
               if jdata["MercerSpheres"][pathName]:
                  if addMercerSphere(parsedSave.levels, pathName):
                     modifiedFlag = True
               else:
                  if removeMercerSphere(parsedSave.levels, pathName):
                     modifiedFlag = True

         if "MercerShrines" in jdata:
            for pathName in jdata["MercerShrines"]:
               if jdata["MercerShrines"][pathName]:
                  if addMercerShrine(parsedSave.levels, pathName):
                     modifiedFlag = True
               else:
                  if removeMercerShrine(parsedSave.levels, pathName):
                     modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: All Mercer Spheres already match json.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) == 4 and sys.argv[1] == "--remember-username":
      playerId = sys.argv[2]
      playerUsername = sys.argv[3]

      if len(playerUsername) == 0:
         if playerId in playerUsernames:
            print(f"Removing '{playerUsernames[playerId]}' for {playerId}")
            del playerUsernames[playerId]
      else:
         if playerId in playerUsernames:
            print(f"Replacing '{playerUsernames[playerId]}' with '{playerUsername}' for {playerId}")
         else:
            print(f"Setting '{playerUsername}' for {playerId}")
         playerUsernames[playerId] = playerUsername

      with open(USERNAME_FILENAME, "w") as fout:
         json.dump(playerUsernames, fout, indent=2)

   elif len(sys.argv) == 3 and sys.argv[1] == "--list-vehicle-paths" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]

      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         level = parsedSave.levels[-1]

         for object1 in level.objects:
            if object1.instanceName == "Persistent_Level:PersistentLevel.VehicleSubsystem":
               savedPaths = sav_parse.getPropertyValue(object1.properties, "mSavedPaths")
               if savedPaths is not None:
                  for savedPath in savedPaths:

                     foundPathNameFlag = False
                     for object2 in level.objects:
                        if object2.instanceName == savedPath.pathName:
                           foundPathNameFlag = True
                           pathName = sav_parse.getPropertyValue(object2.properties, "mPathName")
                           if pathName is None:
                              print("CAUTION: Missing mPathName property for save path {savedPath.pathName}")
                           else:
                              targetList = sav_parse.getPropertyValue(object2.properties, "mTargetList")
                              if targetList is None:
                                 print(f"CAUTION: Missing mTargetList property for save path '{pathName}' ({savedPath.pathName})")
                              else:

                                 foundTargetListFlag = False
                                 for object3 in level.objects:
                                    if object3.instanceName == targetList.pathName:
                                       foundTargetListFlag = True
                                       first = sav_parse.getPropertyValue(object3.properties, "mFirst")
                                       if first is None:
                                          print(f"CAUTION: Missing mFirst property for target list {targetList.pathName} for save path '{pathName}' ({savedPath.pathName})")
                                       else:
                                          last = sav_parse.getPropertyValue(object3.properties, "mLast")
                                          if last is None:
                                             print(f"CAUTION: Missing mLast property for target list {targetList.pathName} for save path '{pathName}' ({savedPath.pathName})")
                                          else:
                                             vehicleType = sav_parse.getPropertyValue(object3.properties, "mVehicleType")
                                             if vehicleType is None:
                                                print(f"CAUTION: Missing mVehicleType property for target list {targetList.pathName} for save path '{pathName}' ({savedPath.pathName})")
                                             else:
                                                pathFuelConsumption = sav_parse.getPropertyValue(object3.properties, "mPathFuelConsumption")
                                                if pathFuelConsumption is None:
                                                   print(f"CAUTION: Missing mPathFuelConsumption property for target list {targetList.pathName} for save path '{pathName}' ({savedPath.pathName})")
                                                else:
                                                   targetListNextWaypoint = first.pathName
                                                   targetListLastWaypoint = last.pathName

                                                   waypointCount = 0
                                                   for object4 in level.objects:
                                                      if targetListNextWaypoint is not None and object4.instanceName == targetListNextWaypoint:
                                                         waypointCount += 1
                                                         next = sav_parse.getPropertyValue(object4.properties, "mNext")
                                                         if next is not None:
                                                            targetListNextWaypoint = next.pathName
                                                         elif object4.instanceName != targetListLastWaypoint:
                                                            print("ERROR: Failed to follow the full vehicle path '{pathName}'.", file=sys.stderr)
                                                            exit(1)
                                          print(f"{pathName}:  {waypointCount} waypoints for {sav_parse.pathNameToReadableName(vehicleType.pathName)} consuming {pathFuelConsumption} fuel.")
                                 if not foundTargetListFlag:
                                    print(f"CAUTION: Unable to find target list {targetList.pathName} for save path '{pathName}' ({savedPath.pathName})")
                     if not foundPathNameFlag:
                        print(f"CAUTION: Unable to find save path {savedPath.pathName}")

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

   elif len(sys.argv) == 5 and sys.argv[1] == "--export-vehicle-path" and os.path.isfile(sys.argv[3]):
      savedPathName = sys.argv[2]
      savFilename = sys.argv[3]
      outFilename = sys.argv[4]

      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)
         level = parsedSave.levels[-1]

         savedPathList = []
         for object in level.objects:
            if object.instanceName == "Persistent_Level:PersistentLevel.VehicleSubsystem":
               savedPaths = sav_parse.getPropertyValue(object.properties, "mSavedPaths")
               if savedPaths is not None:
                  for savedPath in savedPaths:
                     savedPathList.append(savedPath.pathName)

         jdata = {}
         targetListPathName = None
         for object in level.objects:
            if object.instanceName in savedPathList:
               pathName = sav_parse.getPropertyValue(object.properties, "mPathName")
               if pathName is not None and pathName == savedPathName:
                  jdata["mPathName"] = pathName
                  targetList = sav_parse.getPropertyValue(object.properties, "mTargetList")
                  if targetList is None:
                     print(f"ERROR: Saved path {object.instanceName} is missing a mTargetList property")
                     exit(1)
                  targetListPathName = targetList.pathName
         if targetListPathName is None:
            print(f"ERROR: Failed to find a saved path with name '{savedPathName}'.")
            exit(1)

         targetListNextWaypoint = None
         targetListLastWaypoint = None
         for object in level.objects:
            if object.instanceName == targetListPathName:
               first = sav_parse.getPropertyValue(object.properties, "mFirst")
               if first is None:
                  print(f"ERROR: Target list {object.instanceName} is missing a mFirst property.")
                  exit(1)
               last = sav_parse.getPropertyValue(object.properties, "mLast")
               if last is None:
                  print(f"ERROR: Target list {object.instanceName} is missing a mLast property.")
                  exit(1)
               vehicleType = sav_parse.getPropertyValue(object.properties, "mVehicleType")
               if vehicleType is None:
                  print(f"ERROR: Target list {object.instanceName} is missing a mVehicleType property.")
                  exit(1)
               pathFuelConsumption = sav_parse.getPropertyValue(object.properties, "mPathFuelConsumption")
               if pathFuelConsumption is None:
                  print(f"ERROR: Target list {object.instanceName} is missing a mPathFuelConsumption property.")
                  exit(1)
               targetListNextWaypoint = first.pathName
               targetListLastWaypoint = last.pathName
               jdata["mVehicleType"] = vehicleType.pathName
               jdata["mPathFuelConsumption"] = pathFuelConsumption

         if targetListNextWaypoint is None:
            print(f"ERROR: Failed to find target list {targetListPathName}")
            exit(1)

         targetListWaypoints = []
         for object in level.objects:
            if targetListNextWaypoint is not None and object.instanceName == targetListNextWaypoint:
               # The final element has no mNext or mWaitTime, just mTargetSpeed=0.
               # So no details are being preserved for the final waypoint.
               next = sav_parse.getPropertyValue(object.properties, "mNext")
               targetSpeed = sav_parse.getPropertyValue(object.properties, "mTargetSpeed")
               waitTime = sav_parse.getPropertyValue(object.properties, "mWaitTime") # Only the first element seems to have mWaitTime
               targetListWaypoints.append((object.instanceName, targetSpeed, waitTime))
               if next is not None:
                  targetListNextWaypoint = next.pathName
               elif object.instanceName != targetListLastWaypoint:
                  print("ERROR: Failed to follow the full vehicle path.", file=sys.stderr)
                  exit(1)

         targetList = jdata["mTargetList"] = []
         for (waypointPathName, targetSpeed, waitTime) in targetListWaypoints:
            for actorOrComponentObjectHeader in level.actorAndComponentObjectHeaders:
               if actorOrComponentObjectHeader.instanceName == waypointPathName:
                  targetList.append((actorOrComponentObjectHeader.position, actorOrComponentObjectHeader.rotation, targetSpeed, waitTime))

         print(f"Saving {len(targetList)} waypoints to {outFilename}")
         with open(outFilename, "w") as fout:
            json.dump(jdata, fout, indent=2)

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

   elif len(sys.argv) in (6, 7) and sys.argv[1] == "--import-vehicle-path" and os.path.isfile(sys.argv[3]) and os.path.isfile(sys.argv[4]):
      newSavePathName = sys.argv[2]
      savFilename = sys.argv[3]
      inFilename = sys.argv[4]
      outFilename = sys.argv[5]
      changeTimeFlag = True
      if len(sys.argv) == 7 and sys.argv[6] == "--same-time":
         changeTimeFlag = False

      with open(inFilename, "r") as fin:
         jdata = json.load(fin)
      if len(jdata["mTargetList"]) == 0:
         print(f"ERROR: {inFilename} contains no mTargetList points.", file=sys.stderr)
         exit(1)

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)
         level = parsedSave.levels[-1]

         newDrivingTargetList = f"Persistent_Level:PersistentLevel.FGDrivingTargetList_{uuid.uuid4().hex}"
         newSavedWheeledVehiclePath = f"Persistent_Level:PersistentLevel.FGSavedWheeledVehiclePath_{uuid.uuid4().hex}"
         newVehicleTargetPoints = []
         for _ in range(len(jdata["mTargetList"])):
            newVehicleTargetPoints.append(f"Persistent_Level:PersistentLevel.BP_VehicleTargetPoint_C_{uuid.uuid4().hex}")

         for object in level.objects:
            if object.instanceName == "Persistent_Level:PersistentLevel.VehicleSubsystem":
               savedPaths = sav_parse.getPropertyValue(object.properties, "mSavedPaths")
               if savedPaths is not None:
                  print(f"Adding {len(newVehicleTargetPoints)} points as {newSavedWheeledVehiclePath} to VehicleSubsystem")
                  objectReference = sav_parse.ObjectReference("Persistent_Level", newSavedWheeledVehiclePath)
                  savedPaths.append(objectReference)
                  modifiedFlag = True

         actorHeader = sav_parse.ActorHeader()
         actorHeader.typePath = "/Script/FactoryGame.FGDrivingTargetList"
         actorHeader.rootObject = "Persistent_Level"
         actorHeader.instanceName = newDrivingTargetList
         actorHeader.flags = 0
         actorHeader.needTransform = False
         actorHeader.rotation = [0.0, 0.0, 0.0, 1.0]
         actorHeader.position = [0.0, 0.0, 0.0]
         actorHeader.scale = [1.0, 1.0, 1.0]
         actorHeader.wasPlacedInLevel = False
         level.actorAndComponentObjectHeaders.append(actorHeader)

         object = sav_parse.Object()
         object.instanceName = newDrivingTargetList
         object.objectGameVersion = parsedSave.saveFileInfo.saveVersion
         object.shouldMigrateObjectRefsToPersistentFlag = False
         parentObjectReference = sav_parse.ObjectReference("Persistent_Level", "Persistent_Level:PersistentLevel.VehicleSubsystem")
         object.actorReferenceAssociations = [parentObjectReference, []]
         firstObjectReference = sav_parse.ObjectReference("Persistent_Level", newVehicleTargetPoints[0])
         lastObjectReference = sav_parse.ObjectReference("Persistent_Level", newVehicleTargetPoints[-1])
         vehicleObjectReference = sav_parse.ObjectReference("", jdata["mVehicleType"])
         object.properties = [
            ["mFirst", firstObjectReference],
            ["mLast", lastObjectReference],
            ["mVehicleType", vehicleObjectReference],
            ["mPathFuelConsumption", jdata["mPathFuelConsumption"]]]
         object.propertyTypes = [
            ["mFirst", "ObjectProperty", 0],
            ["mLast", "ObjectProperty", 0],
            ["mVehicleType", "ObjectProperty", 0],
            ["mPathFuelConsumption", "FloatProperty", 0]]
         object.actorSpecificInfo = None
         object.perObjectVersionData = None
         level.objects.append(object)

         for idx in range(len(newVehicleTargetPoints)):
            actorHeader = sav_parse.ActorHeader()
            actorHeader.typePath = "/Game/FactoryGame/Buildable/Vehicle/BP_VehicleTargetPoint.BP_VehicleTargetPoint_C"
            actorHeader.rootObject = "Persistent_Level"
            actorHeader.instanceName = newVehicleTargetPoints[idx]
            actorHeader.flags = 0
            actorHeader.needTransform = False
            actorHeader.rotation = jdata["mTargetList"][idx][1]
            actorHeader.position = jdata["mTargetList"][idx][0]
            actorHeader.scale = [1.0, 1.0, 1.0]
            actorHeader.wasPlacedInLevel = False
            level.actorAndComponentObjectHeaders.append(actorHeader)

            object = sav_parse.Object()
            object.instanceName = newVehicleTargetPoints[idx]
            object.objectGameVersion = parsedSave.saveFileInfo.saveVersion
            object.shouldMigrateObjectRefsToPersistentFlag = False
            parentObjectReference = sav_parse.ObjectReference("Persistent_Level", newDrivingTargetList)
            object.actorReferenceAssociations = [parentObjectReference, []]
            object.properties = []
            object.propertyTypes = []
            if idx+1 < len(newVehicleTargetPoints):
               nextObjectReference = sav_parse.ObjectReference("Persistent_Level", newVehicleTargetPoints[idx+1])
               object.properties.append(["mNext", nextObjectReference])
               object.propertyTypes.append(["mNext", "ObjectProperty", 0])
            if jdata["mTargetList"][idx][3] is not None:
               object.properties.append(["mWaitTime", jdata["mTargetList"][idx][3]])
               object.propertyTypes.append(["mWaitTime", "FloatProperty", 0])
            object.properties.append(["mTargetSpeed", jdata["mTargetList"][idx][2]])
            object.propertyTypes.append(["mTargetSpeed", "IntProperty", 0])
            object.actorSpecificInfo = None
            object.perObjectVersionData = None
            level.objects.append(object)

         actorHeader = sav_parse.ActorHeader()
         actorHeader.typePath = "/Script/FactoryGame.FGSavedWheeledVehiclePath"
         actorHeader.rootObject = "Persistent_Level"
         actorHeader.instanceName = newSavedWheeledVehiclePath
         actorHeader.flags = 0
         actorHeader.needTransform = False
         actorHeader.rotation = [0.0, 0.0, 0.0, 1.0]
         actorHeader.position = [0.0, 0.0, 0.0]
         actorHeader.scale = [1.0, 1.0, 1.0]
         actorHeader.wasPlacedInLevel = False
         level.actorAndComponentObjectHeaders.append(actorHeader)

         object = sav_parse.Object()
         object.instanceName = newSavedWheeledVehiclePath
         object.objectGameVersion = parsedSave.saveFileInfo.saveVersion
         object.shouldMigrateObjectRefsToPersistentFlag = False
         parentObjectReference = sav_parse.ObjectReference()
         object.actorReferenceAssociations = [parentObjectReference, []]
         firstObjectReference = sav_parse.ObjectReference("Persistent_Level", newVehicleTargetPoints[0])
         lastObjectReference = sav_parse.ObjectReference("Persistent_Level", newVehicleTargetPoints[-1])
         listObjectReference = sav_parse.ObjectReference("Persistent_Level", newDrivingTargetList)
         object.properties = [
            ["mPathName", newSavePathName],
            ["mTargetList", listObjectReference]]
         object.propertyTypes = [
            ["mPathName", "StrProperty", 0],
            ["mTargetList", "ObjectProperty", 0]]
         object.actorSpecificInfo = None
         object.perObjectVersionData = None
         level.objects.append(object)

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: Failed to find VehicleSubsystem to modify.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) == 4 and sys.argv[1] == "--export-dimensional-depot" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      outFilename = sys.argv[3]

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         jdata = []
         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.CentralStorageSubsystem":
                  storedItems = sav_parse.getPropertyValue(object.properties, "mStoredItems")
                  if storedItems is not None:
                     for storedItem in storedItems:
                        itemClass = sav_parse.getPropertyValue(storedItem[0], "ItemClass")
                        if itemClass is not None:
                           amount = sav_parse.getPropertyValue(storedItem[0], "amount", True)
                           if amount is not None:
                              itemName = sav_parse.pathNameToReadableName(itemClass.pathName)
                              print(f"{itemName}, {amount}")
                              jdata.append((itemName, amount))

         if len(jdata) == 0:
            print("No items found in dimensional depot")

         print(f"Writing {outFilename}")
         with open(outFilename, "w") as fout:
            json.dump(jdata, fout, indent=2)

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

   elif len(sys.argv) in (5, 6) and sys.argv[1] == "--reorder-dimensional-depot" and os.path.isfile(sys.argv[2]) and os.path.isfile(sys.argv[3]):
      savFilename = sys.argv[2]
      inFilename = sys.argv[3]
      outFilename = sys.argv[4]
      changeTimeFlag = True
      if len(sys.argv) == 6 and sys.argv[5] == "--same-time":
         changeTimeFlag = False

      with open(inFilename, "r") as fin:
         jdata = json.load(fin)

      # Acceptable input either a list of strings, or a list of (string, int)
      # This for-loop takes the (string, int) and makes them just strings.
      for idx in range(len(jdata)):
         if isinstance(jdata[idx], list) and len(jdata[idx]) > 0:
            jdata[idx] = jdata[idx][0]
      print(jdata)

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.CentralStorageSubsystem":
                  storedItems = sav_parse.getPropertyValue(object.properties, "mStoredItems")
                  if storedItems is not None:
                     destIdx = 0
                     for nextItem in jdata:
                        for srcIdx in range(len(storedItems)):
                           if srcIdx < destIdx:
                              next # Can't be this one
                           storedItem = storedItems[srcIdx]
                           itemClass = sav_parse.getPropertyValue(storedItem[0], "ItemClass")
                           if itemClass is not None:
                              readableName = sav_parse.pathNameToReadableName(itemClass.pathName)
                              if readableName == nextItem:
                                 # Found
                                 if srcIdx > destIdx:
                                    # Swap
                                    storedItems[srcIdx] = storedItems[destIdx]
                                    storedItems[destIdx] = storedItem
                                    modifiedFlag = True
                                 destIdx += 1
                                 next

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("Nothing reordered.", file=sys.stderr)
         exit(0)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (6, 7) and sys.argv[1] == "--adjust-dimensional-depot" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      targetItemName = sys.argv[3]
      newItemQuantity = int(sys.argv[4])
      outFilename = sys.argv[5]
      changeTimeFlag = True
      if len(sys.argv) == 7 and sys.argv[6] == "--same-time":
         changeTimeFlag = False

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.CentralStorageSubsystem":
                  storedItems = sav_parse.getPropertyValue(object.properties, "mStoredItems")
                  if storedItems is not None:
                     for storedItem in storedItems:
                        itemClass = sav_parse.getPropertyValue(storedItem[0], "ItemClass")
                        if itemClass is not None:
                           itemName = sav_parse.pathNameToReadableName(itemClass.pathName)
                           if itemName == targetItemName:
                              for idx in range(len(storedItem[0])): # setPropertyValue where storedItem[0] is the property list
                                 (haystackPropertyName, propertyValue) = storedItem[0][idx]
                                 if haystackPropertyName.casefold() == "amount":
                                    if propertyValue == newItemQuantity:
                                       print("{haystackPropertyName} quantity already {propertyValue}")
                                    else:
                                       storedItem[0][idx] = [haystackPropertyName, newItemQuantity]
                                       modifiedFlag = True
                                       break

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("Nothing adjusted.", file=sys.stderr)
         exit(0)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) == 4 and sys.argv[1] == "--export-crash-sites" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      outFilename = sys.argv[3]

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         crashSitesInSave, crashSitesNotOpened, crashSitesOpenWithDrive, crashSitesOpenAndEmpty, crashSitesDismantled = sav_to_html.getCrashSiteState(parsedSave.levels)

         print(f"{len(sav_data.crashSites.CRASH_SITES)} total crash sites on map.")
         print(f"   {len(crashSitesInSave) + len(crashSitesDismantled)} found in save file.")
         print(f"   {len(crashSitesNotOpened)} not opened.")
         print(f"   {len(crashSitesOpenWithDrive)} opened with hard drive.")
         print(f"   {len(crashSitesOpenAndEmpty)} opened and empty.")
         print(f"   {len(crashSitesDismantled)} dismantled.")

         jdata = {}
         for crashSite in crashSitesOpenAndEmpty:
            jdata[crashSite] = "IN_SAVE_OPEN_EMPTY"
         for crashSite in crashSitesOpenWithDrive:
            jdata[crashSite] = "IN_SAVE_OPEN_FULL"
         for crashSite in crashSitesInSave:
            if crashSite not in crashSitesOpenAndEmpty and crashSite not in crashSitesOpenWithDrive:
               jdata[crashSite] = "IN_SAVE_CLOSED"
         for crashSite in sav_data.crashSites.CRASH_SITES:
            if crashSite not in crashSitesInSave:
               if crashSite in crashSitesDismantled:
                  jdata[crashSite] = "DISMANTLED"
               else:
                  jdata[crashSite] = "NOT_IN_SAVE"

         print(f"Writing {outFilename}")
         with open(outFilename, "w") as fout:
            json.dump(dict(sorted(jdata.items())), fout, indent=2)

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

   elif len(sys.argv) in (5, 6) and sys.argv[1] == "--dismantle-crash-site" and os.path.isfile(sys.argv[3]):
      # From states IN_SAVE_CLOSED or IN_SAVE_OPEN_FULL or IN_SAVE_OPEN_EMPTY --> to DISMANTLED

      dropPodShortName = sys.argv[2]
      dropPodPathName = f"Persistent_Level:PersistentLevel.{dropPodShortName}"
      if dropPodPathName not in sav_data.crashSites.CRASH_SITES:
         print(f"ERROR: Invalid crash site name '{dropPodPathName}'")
         exit(1)
      savFilename = sys.argv[3]
      outFilename = sys.argv[4]
      changeTimeFlag = True
      if len(sys.argv) == 6 and sys.argv[5] == "--same-time":
         changeTimeFlag = False

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         for level in parsedSave.levels:
            for idx in range(len(level.actorAndComponentObjectHeaders)):
               actorOrComponentObjectHeader = level.actorAndComponentObjectHeaders[idx]
               if isinstance(actorOrComponentObjectHeader, sav_parse.ActorHeader):
                  if actorOrComponentObjectHeader.instanceName == dropPodPathName:
                     object = level.objects[idx]
                     if object.instanceName == dropPodPathName:
                        if level.collectables1 is None:
                           level.collectables1 = []
                        if level.collectables2 is None:
                           level.collectables2 = []
                        del level.actorAndComponentObjectHeaders[idx]
                        del level.objects[idx]
                        objectReference = sav_parse.ObjectReference(sav_data.crashSites.CRASH_SITES[dropPodPathName][0], dropPodPathName)
                        level.collectables1.append(objectReference)
                        level.collectables2.append(objectReference)
                        print(f"Crash site {dropPodShortName} removed")
                        modifiedFlag = True
                        break

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print(f"ERROR: Failed to find locked crash site {dropPodShortName} to remove.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) == 3 and sys.argv[1] == "--list-map-markers" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]

      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.MapManager":
                  mapMarkers = sav_parse.getPropertyValue(object.properties, "mMapMarkers")
                  if mapMarkers is not None:
                     for mapMarker in mapMarkers:

                        markerGuid = sav_parse.getPropertyValue(mapMarker[0], "markerGuid")
                        if markerGuid is not None:
                           markerGuid = uuid.UUID(bytes=markerGuid)

                        name = sav_parse.getPropertyValue(mapMarker[0], "Name")

                        location = sav_parse.getPropertyValue(mapMarker[0], "Location")
                        if location is not None:
                           x = sav_parse.getPropertyValue(location[0], "X")
                           y = sav_parse.getPropertyValue(location[0], "Y")
                           z = sav_parse.getPropertyValue(location[0], "Z")
                           location = None
                           if x is not None and y is not None and z is not None:
                              location = (x, y, z)

                        scale = sav_parse.getPropertyValue(mapMarker[0], "Scale")

                        compassViewDistance = sav_parse.getPropertyValue(mapMarker[0], "compassViewDistance")
                        if compassViewDistance is not None:
                           if compassViewDistance[0] == "ECompassViewDistance":
                              compassViewDistance = compassViewDistance[1][len("ECompassViewDistance::"):]
                              for cvd in sav_data.data.COMPASS_VIEW_DISTANCES__ENUM_TO_NAME:
                                 if cvd.name == compassViewDistance:
                                    compassViewDistance = sav_data.data.COMPASS_VIEW_DISTANCES__ENUM_TO_NAME[cvd]

                        iconID = sav_parse.getPropertyValue(mapMarker[0], "IconID")
                        if iconID in sav_data.data.ICON_IDS_TO_NAMES:
                           iconID = sav_data.data.ICON_IDS_TO_NAMES[iconID]

                        print(f"{markerGuid} '{name}' at {location} scale={scale} distance={compassViewDistance} icon={iconID}")

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

   elif len(sys.argv) == 4 and sys.argv[1] == "--export-map-markers" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      outFilename = sys.argv[3]

      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         jdata = []
         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.MapManager":
                  mapMarkers = sav_parse.getPropertyValue(object.properties, "mMapMarkers")
                  if mapMarkers is not None:
                     for mapMarker in mapMarkers:

                        markerGuid = sav_parse.getPropertyValue(mapMarker[0], "markerGuid")
                        if markerGuid is not None:
                           markerGuid = uuid.UUID(bytes=markerGuid)

                        name = sav_parse.getPropertyValue(mapMarker[0], "Name")

                        categoryName = sav_parse.getPropertyValue(mapMarker[0], "CategoryName")

                        location = sav_parse.getPropertyValue(mapMarker[0], "Location")
                        if location is not None:
                           x = sav_parse.getPropertyValue(location[0], "X")
                           y = sav_parse.getPropertyValue(location[0], "Y")
                           z = sav_parse.getPropertyValue(location[0], "Z")
                           location = None
                           if x is not None and y is not None and z is not None:
                              location = (x, y, z)

                        scale = sav_parse.getPropertyValue(mapMarker[0], "Scale")

                        compassViewDistance = sav_parse.getPropertyValue(mapMarker[0], "compassViewDistance")
                        if compassViewDistance is not None:
                           if compassViewDistance[0] == "ECompassViewDistance":
                              compassViewDistance = compassViewDistance[1][len("ECompassViewDistance::"):]
                              for cvd in sav_data.data.COMPASS_VIEW_DISTANCES__ENUM_TO_NAME:
                                 if cvd.name == compassViewDistance:
                                    compassViewDistance = sav_data.data.COMPASS_VIEW_DISTANCES__ENUM_TO_NAME[cvd]

                        iconID = sav_parse.getPropertyValue(mapMarker[0], "IconID")
                        if iconID in sav_data.data.ICON_IDS_TO_NAMES:
                           iconID = sav_data.data.ICON_IDS_TO_NAMES[iconID]

                        color = sav_parse.getPropertyValue(mapMarker[0], "Color")

                        jdata.append({
                           "guid": str(markerGuid),
                           "Name": name,
                           "Subcategory": categoryName,
                           "Location": location,
                           "Scale": scale,
                           "compassViewDistance": compassViewDistance,
                           "IconName": iconID,
                           "Color": color
                           })

         print(f"Writing {outFilename}")
         with open(outFilename, "w") as fout:
            json.dump(jdata, fout, indent=2)

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

   elif len(sys.argv) in (5, 6) and sys.argv[1] == "--remove-marker" and os.path.isfile(sys.argv[3]):
      targetMarkerGuid = uuid.UUID(sys.argv[2])
      savFilename = sys.argv[3]
      outFilename = sys.argv[4]
      changeTimeFlag = True
      if len(sys.argv) == 6 and sys.argv[5] == "--same-time":
         changeTimeFlag = False

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.MapManager":
                  mapMarkers = sav_parse.getPropertyValue(object.properties, "mMapMarkers")
                  if mapMarkers is not None:
                     for idx in range(len(mapMarkers)):

                        markerGuid = sav_parse.getPropertyValue(mapMarkers[idx][0], "markerGuid")
                        if markerGuid is not None and uuid.UUID(bytes=markerGuid) == targetMarkerGuid:

                           name = sav_parse.getPropertyValue(mapMarkers[idx][0], "Name")
                           del mapMarkers[idx]
                           print(f"Removed map marker '{name}'")
                           modifiedFlag = True
                           break

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: Failed to find marker GUID to remove.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (5, 6) and sys.argv[1] == "--add-map-markers-json" and os.path.isfile(sys.argv[2]) and os.path.isfile(sys.argv[3]):
      savFilename = sys.argv[2]
      inFilename = sys.argv[3]
      outFilename = sys.argv[4]
      changeTimeFlag = True
      if len(sys.argv) == 5 and sys.argv[4] == "--same-time":
         changeTimeFlag = False

      with open(inFilename, "r") as fin:
         jdata = json.load(fin)

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         for newMarker in jdata:
            if "Location" in newMarker and len(newMarker["Location"]) == 3:
               markerLocation = newMarker["Location"]

               markerName = "New Marker"
               if "Name" in newMarker:
                  markerName = newMarker["Name"]

               markerSubcategory = ""
               if "Subcategory" in newMarker:
                  markerSubcategory = newMarker["Subcategory"]

               markerColor = (0.6, 0.6, 0.6) # Float RGB (up to 1.0)
               if "Color" in newMarker:
                  markerColor = newMarker["Color"]

               markerIconId_key = sav_data.data.ICON_NAMES_TO_IDS["Home House"]
               if "IconName" in newMarker and newMarker["IconName"] in sav_data.data.ICON_NAMES_TO_IDS:
                  markerIconId_key = newMarker["IconName"]

               markerViewDistance = sav_data.data.ECompassViewDistance.CVD_Mid
               if "compassViewDistance" in newMarker and newMarker["compassViewDistance"] in sav_data.data.COMPASS_VIEW_DISTANCES__NAME_TO_ENUM:
                  markerViewDistance = sav_data.data.COMPASS_VIEW_DISTANCES__NAME_TO_ENUM[newMarker["compassViewDistance"]]

               scale = 1.0
               if "Scale" in newMarker:
                  scale = newMarker["Scale"]

               if addMapMarker(parsedSave.levels, markerName, markerLocation, markerIconId_key, markerColor, markerViewDistance, scale, markerSubcategory):
                  print(f"Added '{markerName}' at {markerLocation}")
                  modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: Either no valid marker in json or mMapMarkers not found in save.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (4, 5) and sys.argv[1] == "--add-map-markers-somersloops" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      outFilename = sys.argv[3]
      changeTimeFlag = True
      if len(sys.argv) == 5 and sys.argv[4] == "--same-time":
         changeTimeFlag = False

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         uncollectedSomersloops = {}
         for pathName in sav_data.somersloop.SOMERSLOOPS:
            uncollectedSomersloops[pathName] = True

         for level in parsedSave.levels:
            for collectable in level.collectables2:
               if collectable.pathName in sav_data.somersloop.SOMERSLOOPS:
                  del uncollectedSomersloops[collectable.pathName]
         if len(uncollectedSomersloops) == 0:
            print("No uncollected somersloops")
            exit(0)

         markerColor = (sav_to_html.MAP_COLOR_UNCOLLECTED_SOMERSLOOP[0]/255, sav_to_html.MAP_COLOR_UNCOLLECTED_SOMERSLOOP[1]/255, sav_to_html.MAP_COLOR_UNCOLLECTED_SOMERSLOOP[2]/255)
         for somersloopName in uncollectedSomersloops:
            shortName = somersloopName[somersloopName.rfind(".")+1:]
            markerLocation = sav_data.somersloop.SOMERSLOOPS[somersloopName][2]

            if addMapMarker(parsedSave.levels, f"sloop {shortName}", markerLocation, "Road Arrow Down", markerColor, sav_data.data.ECompassViewDistance.CVD_Near, UNCOLLECTED_MAP_MARKER_SCALE, "Somersloops"):
               print(f"Added {shortName} at {markerLocation}")
               modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: No save generated.  (Maybe too many markers or no mMapMarkers in save.)", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (4, 5) and sys.argv[1] == "--add-map-markers-mercer-spheres" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      outFilename = sys.argv[3]
      changeTimeFlag = True
      if len(sys.argv) == 5 and sys.argv[4] == "--same-time":
         changeTimeFlag = False

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         uncollectedMercerSpheres = {}
         for pathName in sav_data.mercerSphere.MERCER_SPHERES:
            uncollectedMercerSpheres[pathName] = True

         for level in parsedSave.levels:
            for collectable in level.collectables2:
               if collectable.pathName in sav_data.mercerSphere.MERCER_SPHERES:
                  del uncollectedMercerSpheres[collectable.pathName]
         if len(uncollectedMercerSpheres) == 0:
            print("No uncollected mercer spheres")
            exit(0)

         markerColor = (sav_to_html.MAP_COLOR_UNCOLLECTED_MERCER_SPHERE[0]/255, sav_to_html.MAP_COLOR_UNCOLLECTED_MERCER_SPHERE[1]/255, sav_to_html.MAP_COLOR_UNCOLLECTED_MERCER_SPHERE[2]/255)
         for mercerSphereName in uncollectedMercerSpheres:
            shortName = mercerSphereName[mercerSphereName.rfind(".")+1:]
            markerLocation = sav_data.mercerSphere.MERCER_SPHERES[mercerSphereName][2]

            if addMapMarker(parsedSave.levels, f"sphere {shortName}", markerLocation, "Road Arrow Down", markerColor, sav_data.data.ECompassViewDistance.CVD_Near, UNCOLLECTED_MAP_MARKER_SCALE, "Mercer Spheres"):
               print(f"Added {shortName} at {markerLocation}")
               modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: No save generated.  (Maybe too many markers or no mMapMarkers in save.)", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (4, 5) and sys.argv[1] == "--add-map-markers-hard-drives" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      outFilename = sys.argv[3]
      changeTimeFlag = True
      if len(sys.argv) == 5 and sys.argv[4] == "--same-time":
         changeTimeFlag = False

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         _, crashSitesNotOpened, crashSitesOpenWithDrive, crashSitesOpenAndEmpty, _ = sav_to_html.getCrashSiteState(parsedSave.levels)

         markerColorOpenWithDrive = (sav_to_html.MAP_COLOR_CRASH_SITE_OPEN_W_DRIVE[0]/255, sav_to_html.MAP_COLOR_CRASH_SITE_OPEN_W_DRIVE[1]/255, sav_to_html.MAP_COLOR_CRASH_SITE_OPEN_W_DRIVE[2]/255)
         for crashSite in crashSitesOpenWithDrive:
            shortName = crashSite[crashSite.rfind(".")+1:]
            markerLocation = sav_data.crashSites.CRASH_SITES[crashSite][2]

            if addMapMarker(parsedSave.levels, f"hd {shortName}", markerLocation, "Road Arrow Down", markerColorOpenWithDrive, sav_data.data.ECompassViewDistance.CVD_Near, UNCOLLECTED_MAP_MARKER_SCALE, "Crash Site (Open)"):
               print(f"Added {shortName} at {markerLocation} [Open w/drive]")
               modifiedFlag = True

         markerColorUnopened = (sav_to_html.MAP_COLOR_CRASH_SITE_UNOPENED[0]/255, sav_to_html.MAP_COLOR_CRASH_SITE_UNOPENED[1]/255, sav_to_html.MAP_COLOR_CRASH_SITE_UNOPENED[2]/255)
         for crashSite in crashSitesNotOpened:
            shortName = crashSite[crashSite.rfind(".")+1:]
            markerLocation = sav_data.crashSites.CRASH_SITES[crashSite][2]

            if addMapMarker(parsedSave.levels, f"hd {shortName}", markerLocation, "Road Arrow Down", markerColorUnopened, sav_data.data.ECompassViewDistance.CVD_Near, UNCOLLECTED_MAP_MARKER_SCALE, "Crash Site"):
               print(f"Added {shortName} at {markerLocation} [Closed]")
               modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: No save generated.  (Maybe too many markers or no mMapMarkers in save.)", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (5, 6) and sys.argv[1] == "--add-map-markers-collectable" and os.path.isfile(sys.argv[3]):
      itemName = sys.argv[2]
      savFilename = sys.argv[3]
      outFilename = sys.argv[4]
      changeTimeFlag = True
      if len(sys.argv) == 6 and sys.argv[5] == "--same-time":
         changeTimeFlag = False

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         MARKER_COLOR = (0.2, 0.2, 0.2)
         possibleCollectableName = f"Persistent_Level:PersistentLevel.{itemName}"

         if possibleCollectableName in sav_data.crashSites.CRASH_SITES:
            crashSite = sav_data.crashSites.CRASH_SITES[possibleCollectableName]
            position = crashSite[2]
            if addMapMarker(parsedSave.levels, f"hd {itemName}", position, "Road Arrow Down", MARKER_COLOR, sav_data.data.ECompassViewDistance.CVD_Near, UNCOLLECTED_MAP_MARKER_SCALE, "Crash Site"):
               print(f"Added Crash Site {itemName} at {position}")
               modifiedFlag = True

         elif possibleCollectableName in sav_data.somersloop.SOMERSLOOPS:
            somersloop = sav_data.somersloop.SOMERSLOOPS[possibleCollectableName]
            position = somersloop[2]
            if addMapMarker(parsedSave.levels, f"sloop {itemName}", position, "Road Arrow Down", MARKER_COLOR, sav_data.data.ECompassViewDistance.CVD_Near, UNCOLLECTED_MAP_MARKER_SCALE, "Somersloops"):
               print(f"Added Somersloop {itemName} at {position}")
               modifiedFlag = True

         elif possibleCollectableName in sav_data.mercerSphere.MERCER_SPHERES:
            mercerSphere = sav_data.mercerSphere.MERCER_SPHERES[possibleCollectableName]
            position = mercerSphere[2]
            if addMapMarker(parsedSave.levels, f"sphere {itemName}", position, "Road Arrow Down", MARKER_COLOR, sav_data.data.ECompassViewDistance.CVD_Near, UNCOLLECTED_MAP_MARKER_SCALE, "Mercer Spheres"):
               print(f"Added Mercer Sphere {itemName} at {position}")
               modifiedFlag = True

         else:
            for item in sav_data.freeStuff.FREE_DROPPED_ITEMS:
               if sav_parse.pathNameToReadableName(item) == itemName:
                  for idx in range(len(sav_data.freeStuff.FREE_DROPPED_ITEMS[item])):
                     (quantity, position, _) = sav_data.freeStuff.FREE_DROPPED_ITEMS[item][idx]
                     if addMapMarker(parsedSave.levels, f"{itemName} x{quantity}", position, "Road Arrow Down", MARKER_COLOR, sav_data.data.ECompassViewDistance.CVD_Near, UNCOLLECTED_MAP_MARKER_SCALE, "Free Stuff"):
                        print(f"Added {quantity}x {itemName} at {position}")
                        modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print(f"ERROR: Item {itemName} not found.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) == 4 and sys.argv[1] == "--blueprint" and sys.argv[2] == "--show" and os.path.isfile(sys.argv[3]):
      savFilename = sys.argv[3]

      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords is not None:
                     for category in blueprintCategoryRecords:
                        categoryName = sav_parse.getPropertyValue(category[0], "CategoryName")
                        if categoryName is not None:

                           iconID = sav_parse.getPropertyValue(category[0], "IconID")
                           if iconID is None:
                              iconID = -1

                           menuPriority = sav_parse.getPropertyValue(category[0], "MenuPriority")
                           if menuPriority is None:
                              menuPriority = 0.0

                           isUndefined = sav_parse.getPropertyValue(category[0], "IsUndefined")
                           if isUndefined is None:
                              isUndefined = False

                           subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
                           if subCategoryRecords is not None:
                              print(f"=== Category: {categoryName} === idx={menuPriority}, icon={iconID}, undefined={isUndefined}")
                              for subcategory in subCategoryRecords:
                                 subCategoryName = sav_parse.getPropertyValue(subcategory[0], "SubCategoryName")
                                 if subCategoryName is not None:

                                    subMenuPriority = sav_parse.getPropertyValue(subcategory[0], "MenuPriority")
                                    if subMenuPriority is None:
                                       subMenuPriority = 0.0

                                    subIsUndefined = sav_parse.getPropertyValue(subcategory[0], "IsUndefined")
                                    if subIsUndefined is None:
                                       subIsUndefined = False

                                    blueprintNames = sav_parse.getPropertyValue(subcategory[0], "BlueprintNames")
                                    if blueprintNames is not None:
                                       print(f"   --- Subcategory: {subCategoryName} --- idx={subMenuPriority}, undefined={subIsUndefined}")
                                       for blueprintName in blueprintNames:
                                          print(f"      {blueprintName}")

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

   elif len(sys.argv) in (5, 6) and sys.argv[1] == "--blueprint" and sys.argv[2] == "--sort" and os.path.isfile(sys.argv[3]):
      savFilename = sys.argv[3]
      outFilename = sys.argv[4]
      changeTimeFlag = True
      if len(sys.argv) == 6 and sys.argv[5] == "--same-time":
         changeTimeFlag = False

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords is not None:
                     for category in blueprintCategoryRecords:
                        categoryName = sav_parse.getPropertyValue(category[0], "CategoryName")
                        if categoryName is not None:
                           subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
                           if subCategoryRecords is not None:
                              for subcategory in subCategoryRecords:
                                 subCategoryName = sav_parse.getPropertyValue(subcategory[0], "SubCategoryName")
                                 if subCategoryName is not None:
                                    blueprintNames = sav_parse.getPropertyValue(subcategory[0], "BlueprintNames")
                                    if blueprintNames is not None:
                                       blueprintNames.sort(reverse=False)
                                       modifiedFlag = True

                     if modifiedFlag:
                        orderBlueprintCategoryMenuPriorities(blueprintCategoryRecords)

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: Failed to find subcategories to modify.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) == 5 and sys.argv[1] == "--blueprint" and sys.argv[2] == "--export" and os.path.isfile(sys.argv[3]):
      savFilename = sys.argv[3]
      outFilename = sys.argv[4]

      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         categoryStructure = {}

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords is not None:
                     for category in blueprintCategoryRecords:
                        categoryName = sav_parse.getPropertyValue(category[0], "CategoryName")
                        if categoryName is not None:
                           iconID = sav_parse.getPropertyValue(category[0], "IconID")
                           if iconID is None:
                              iconID = -1
                           subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
                           subcategoryStructure = {}
                           if subCategoryRecords is not None:
                              for subcategory in subCategoryRecords:
                                 subCategoryName = sav_parse.getPropertyValue(subcategory[0], "SubCategoryName")
                                 if subCategoryName is not None:
                                    blueprintNames = sav_parse.getPropertyValue(subcategory[0], "BlueprintNames")
                                    if blueprintNames is not None:
                                       subcategoryStructure[subCategoryName] = blueprintNames
                           categoryStructure[categoryName] = {"Icon": iconID, "Subcategories": subcategoryStructure}

         with open(outFilename, "w") as fout:
            json.dump(categoryStructure, fout, indent=2)

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

   elif len(sys.argv) in (6, 7) and sys.argv[1] == "--blueprint" and sys.argv[2] == "--import" and os.path.isfile(sys.argv[3]) and os.path.isfile(sys.argv[4]):
      savFilename = sys.argv[3]
      inFilename = sys.argv[4]
      outFilename = sys.argv[5]
      changeTimeFlag = True
      if len(sys.argv) == 7 and sys.argv[6] == "--same-time":
         changeTimeFlag = False

      with open(inFilename, "r") as fin:
         categoryStructure = json.load(fin)

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords is not None:

                     existingCategories = []
                     for category in blueprintCategoryRecords:
                        categoryName = sav_parse.getPropertyValue(category[0], "CategoryName")
                        if categoryName is not None:
                           existingCategories.append(categoryName)
                     for categoryName in categoryStructure:
                        if categoryName not in existingCategories:
                           newCategory = getBlankCategory(object.objectGameVersion, categoryName, categoryStructure[categoryName]["Icon"])
                           subCategoryRecords = sav_parse.getPropertyValue(newCategory[0], "SubCategoryRecords")
                           del subCategoryRecords[0] # Remove blank categories "Undefined" subcategory
                           blueprintCategoryRecords.append(newCategory)
                           modifiedFlag = True

                     for category in blueprintCategoryRecords:
                        categoryName = sav_parse.getPropertyValue(category[0], "CategoryName")
                        if categoryName is not None and categoryName in categoryStructure:
                           subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
                           if subCategoryRecords is not None:
                              subcategoryStructure = categoryStructure[categoryName]["Subcategories"]
                              for subcategory in subCategoryRecords:
                                 subCategoryName = sav_parse.getPropertyValue(subcategory[0], "SubCategoryName")
                                 if subCategoryName is not None and subCategoryName in subcategoryStructure:
                                    blueprintNames = sav_parse.getPropertyValue(subcategory[0], "BlueprintNames")
                                    if blueprintNames is not None:
                                       for blueprintName in blueprintNames:
                                          if blueprintName in subcategoryStructure[subCategoryName]:
                                             subcategoryStructure[subCategoryName].remove(blueprintName)
                                       for blueprintName in subcategoryStructure[subCategoryName]:
                                          blueprintNames.append(blueprintName)
                                          modifiedFlag = True
                                       del subcategoryStructure[subCategoryName]
                              for subcategoryName in subcategoryStructure:
                                 newSubcategory = getBlankSubcategory(object.objectGameVersion, subcategoryName)
                                 blueprintNames = sav_parse.getPropertyValue(newSubcategory[0], "BlueprintNames")
                                 for blueprintName in subcategoryStructure[subcategoryName]:
                                    blueprintNames.append(blueprintName)
                                 subCategoryRecords.append(newSubcategory)
                                 modifiedFlag = True
                              del categoryStructure[categoryName]

                     if modifiedFlag:
                        orderBlueprintCategoryMenuPriorities(blueprintCategoryRecords)

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: Failed to find blueprint category records to modify.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (6, 7) and sys.argv[1] == "--blueprint" and sys.argv[2] == "--add-category" and os.path.isfile(sys.argv[4]):
      categoryToAdd = sys.argv[3]
      savFilename = sys.argv[4]
      outFilename = sys.argv[5]
      changeTimeFlag = True
      if len(sys.argv) == 7 and sys.argv[6] == "--same-time":
         changeTimeFlag = False

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords is not None:
                     blueprintCategoryRecords.append(getBlankCategory(object.objectGameVersion, categoryToAdd))
                     modifiedFlag = True
                     orderBlueprintCategoryMenuPriorities(blueprintCategoryRecords)
                     break

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: Failed to find blueprint category records to modify.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (7, 8) and sys.argv[1] == "--blueprint" and sys.argv[2] == "--add-subcategory" and os.path.isfile(sys.argv[5]):
      categoryToAddIn = sys.argv[3]
      subcategoryToAdd = sys.argv[4]
      savFilename = sys.argv[5]
      outFilename = sys.argv[6]
      changeTimeFlag = True
      if len(sys.argv) == 8 and sys.argv[7] == "--same-time":
         changeTimeFlag = False

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords is not None:
                     for category in blueprintCategoryRecords:
                        categoryName = sav_parse.getPropertyValue(category[0], "CategoryName")
                        if categoryName is not None and categoryName == categoryToAddIn:
                           subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
                           if subCategoryRecords is not None:
                              subCategoryRecords.append(getBlankSubcategory(object.objectGameVersion, subcategoryToAdd))
                              modifiedFlag = True
                           break

                     if modifiedFlag:
                        orderBlueprintCategoryMenuPriorities(blueprintCategoryRecords)

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print(f"ERROR: Failed to find category '{categoryToAddIn}' to modify.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (8, 9) and sys.argv[1] == "--blueprint" and sys.argv[2] == "--add-blueprint" and os.path.isfile(sys.argv[6]):
      categoryToAddIn = sys.argv[3]
      subcategoryToAddIn = sys.argv[4]
      blueprint = sys.argv[5]
      savFilename = sys.argv[6]
      outFilename = sys.argv[7]
      changeTimeFlag = True
      if len(sys.argv) == 9 and sys.argv[8] == "--same-time":
         changeTimeFlag = False

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords is not None:
                     for category in blueprintCategoryRecords:
                        categoryName = sav_parse.getPropertyValue(category[0], "CategoryName")
                        if categoryName is not None and categoryName == categoryToAddIn:
                           subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
                           if subCategoryRecords is not None:
                              print(f"=== Category: {categoryName} ===")
                              for subcategory in subCategoryRecords:
                                 subCategoryName = sav_parse.getPropertyValue(subcategory[0], "SubCategoryName")
                                 if subCategoryName is not None and subCategoryName == subcategoryToAddIn:
                                    blueprintNames = sav_parse.getPropertyValue(subcategory[0], "BlueprintNames")
                                    if blueprintNames is not None:
                                       blueprintNames.append(blueprint)
                                       modifiedFlag = True
                                    break

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print(f"ERROR: Failed to find category '{categoryToAddIn}', subcategory '{subcategoryToAddIn}' to modify.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (6, 7) and sys.argv[1] == "--blueprint" and sys.argv[2] == "--remove-category" and os.path.isfile(sys.argv[4]):
      categoryToRemove = sys.argv[3]
      savFilename = sys.argv[4]
      outFilename = sys.argv[5]
      changeTimeFlag = True
      if len(sys.argv) == 7 and sys.argv[6] == "--same-time":
         changeTimeFlag = False

      modifiedFlag = False
      numberOfBlueprints = 0
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords is not None:
                     for category in blueprintCategoryRecords:
                        categoryName = sav_parse.getPropertyValue(category[0], "CategoryName")
                        if categoryName is not None and categoryName == categoryToRemove:
                           subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
                           if subCategoryRecords is not None:
                              for subcategory in subCategoryRecords:
                                 subCategoryName = sav_parse.getPropertyValue(subcategory[0], "SubCategoryName")
                                 if subCategoryName is not None:
                                    blueprintNames = sav_parse.getPropertyValue(subcategory[0], "BlueprintNames")
                                    numberOfBlueprints += len(blueprintNames)
                           if numberOfBlueprints == 0:
                              blueprintCategoryRecords.remove(category)
                              modifiedFlag = True
                           break

                     if modifiedFlag:
                        orderBlueprintCategoryMenuPriorities(blueprintCategoryRecords)

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         if numberOfBlueprints == 0:
            print(f"ERROR: Failed to find category '{categoryToRemove}' to remove.", file=sys.stderr)
         else:
            print(f"ERROR: Category '{categoryToRemove}' contains {numberOfBlueprints} blueprints.  Must be empty to remove.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (7, 8) and sys.argv[1] == "--blueprint" and sys.argv[2] == "--remove-subcategory" and os.path.isfile(sys.argv[5]):
      categoryToRemoveIn = sys.argv[3]
      subcategoryToRemove = sys.argv[4]
      savFilename = sys.argv[5]
      outFilename = sys.argv[6]
      changeTimeFlag = True
      if len(sys.argv) == 8 and sys.argv[7] == "--same-time":
         changeTimeFlag = False

      modifiedFlag = False
      numberOfBlueprints = 0
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords is not None:
                     for category in blueprintCategoryRecords:
                        categoryName = sav_parse.getPropertyValue(category[0], "CategoryName")
                        if categoryName is not None and categoryName == categoryToRemoveIn:
                           subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
                           if subCategoryRecords is not None:
                              for subcategory in subCategoryRecords:
                                 subCategoryName = sav_parse.getPropertyValue(subcategory[0], "SubCategoryName")
                                 if subCategoryName is not None and subCategoryName == subcategoryToRemove:
                                    blueprintNames = sav_parse.getPropertyValue(subcategory[0], "BlueprintNames")
                                    if blueprintNames is not None:
                                       numberOfBlueprints = len(blueprintNames)
                                       if numberOfBlueprints == 0:
                                          subCategoryRecords.remove(subcategory)
                                          modifiedFlag = True
                                    break

                     if modifiedFlag:
                        orderBlueprintCategoryMenuPriorities(blueprintCategoryRecords)

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         if numberOfBlueprints == 0:
            print(f"ERROR: Failed to find category '{categoryToRemoveIn}', subcategory '{subcategoryToRemove}' to remove.", file=sys.stderr)
         else:
            print(f"ERROR: Subcategory '{subcategoryToRemove}' contains {numberOfBlueprints} blueprints.  Must be empty to remove.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (8, 9) and sys.argv[1] == "--blueprint" and sys.argv[2] == "--remove-blueprint" and os.path.isfile(sys.argv[6]):
      categoryToRemoveIn = sys.argv[3]
      subcategoryToRemoveIn = sys.argv[4]
      blueprintToRemove = sys.argv[5]
      savFilename = sys.argv[6]
      outFilename = sys.argv[7]
      changeTimeFlag = True
      if len(sys.argv) == 9 and sys.argv[8] == "--same-time":
         changeTimeFlag = False

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords is not None:
                     for category in blueprintCategoryRecords:
                        categoryName = sav_parse.getPropertyValue(category[0], "CategoryName")
                        if categoryName is not None and categoryName == categoryToRemoveIn:
                           subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
                           if subCategoryRecords is not None:
                              for subcategory in subCategoryRecords:
                                 subCategoryName = sav_parse.getPropertyValue(subcategory[0], "SubCategoryName")
                                 if subCategoryName is not None and subCategoryName == subcategoryToRemoveIn:
                                    blueprintNames = sav_parse.getPropertyValue(subcategory[0], "BlueprintNames")
                                    if blueprintNames is not None:
                                       if blueprintToRemove in blueprintNames:
                                          blueprintNames.remove(blueprintToRemove)
                                          modifiedFlag = True
                                    break

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print(f"ERROR: Failed to find blueprint '{blueprintToRemove}' to remove.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (10, 11) and sys.argv[1] == "--blueprint" and sys.argv[2] == "--move-blueprint" and os.path.isfile(sys.argv[8]):
      oldCategory = sys.argv[3]
      oldSubcategory = sys.argv[4]
      newCategory = sys.argv[5]
      newSubcategory = sys.argv[6]
      blueprintToMove = sys.argv[7]
      savFilename = sys.argv[8]
      outFilename = sys.argv[9]
      changeTimeFlag = True
      if len(sys.argv) == 11 and sys.argv[10] == "--same-time":
         changeTimeFlag = False

      modifiedCount = 0
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords is not None:
                     for category in blueprintCategoryRecords:
                        categoryName = sav_parse.getPropertyValue(category[0], "CategoryName")
                        if categoryName is not None and categoryName == oldCategory:
                           subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
                           if subCategoryRecords is not None:
                              for subcategory in subCategoryRecords:
                                 subCategoryName = sav_parse.getPropertyValue(subcategory[0], "SubCategoryName")
                                 if subCategoryName is not None and subCategoryName == oldSubcategory:
                                    blueprintNames = sav_parse.getPropertyValue(subcategory[0], "BlueprintNames")
                                    if blueprintNames is not None:
                                       if blueprintToMove in blueprintNames:
                                          blueprintNames.remove(blueprintToMove)
                                          modifiedCount += 1
                        if categoryName is not None and categoryName == newCategory:
                           subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
                           if subCategoryRecords is not None:
                              for subcategory in subCategoryRecords:
                                 subCategoryName = sav_parse.getPropertyValue(subcategory[0], "SubCategoryName")
                                 if subCategoryName is not None and subCategoryName == newSubcategory:
                                    blueprintNames = sav_parse.getPropertyValue(subcategory[0], "BlueprintNames")
                                    if blueprintNames is not None:
                                       blueprintNames.append(blueprintToMove)
                                       modifiedCount += 1

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if modifiedCount != 2:
         print("ERROR: Failed to move blueprint.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (5, 6) and sys.argv[1] == "--blueprint" and sys.argv[2] == "--reset" and os.path.isfile(sys.argv[3]):
      savFilename = sys.argv[3]
      outFilename = sys.argv[4]
      changeTimeFlag = True
      if len(sys.argv) == 6 and sys.argv[5] == "--same-time":
         changeTimeFlag = False

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords is not None:
                     blueprintCategoryRecords[:] = []
                     modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: Failed to find blueprint category records to modify.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) == 4 and sys.argv[1] == "--resave-only" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      outFilename = sys.argv[3]

      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)
      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      try:
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) == 2 and sys.argv[1] == "--add-missing-items-to-sav_stack_sizes":
      # Cross-checks contents item-stack-size file against sav_data.data.ITEMS_FOR_PLAYER_INVENTORY
      # using sav_data.readableNames.READABLE_PATH_NAME_CORRECTIONS as a translation between the two.

      ITEM_STACK_SIZE_FILENAME = "sav_stack_sizes.json"

      itemStackSizes: dict[str, int | None] = {}
      if os.path.isfile(ITEM_STACK_SIZE_FILENAME):
         with open(ITEM_STACK_SIZE_FILENAME, "r") as fin:
            itemStackSizes = json.load(fin)

      print()
      print("Items missing from sav_data.readableNames.READABLE_PATH_NAME_CORRECTIONS")
      noneFoundFlag = True
      inventoryItemsMissingNameCorrections = []
      for fullPathName in sav_data.data.ITEMS_FOR_PLAYER_INVENTORY:
         pos = fullPathName.rfind(".")
         if pos != -1:
            pathName = fullPathName[pos+1:]
            if pathName not in sav_data.readableNames.READABLE_PATH_NAME_CORRECTIONS:
               noneFoundFlag = False
               print(f'   "{fullPathName}",')
               inventoryItemsMissingNameCorrections.append(fullPathName)
      if noneFoundFlag:
         print("   None")
      else:
         print("if you're going to add these entries, you'll need to determine the in-game name.")

      print()
      print(f"Items missing from {ITEM_STACK_SIZE_FILENAME}")
      itemAddCount = 0
      missingItems = itemStackSizes.copy()
      for pathName in sav_data.data.ITEMS_FOR_PLAYER_INVENTORY:
         readableName = sav_parse.pathNameToReadableName(pathName)
         if readableName not in itemStackSizes:
            if pathName not in inventoryItemsMissingNameCorrections:
               itemAddCount += 1
               itemStackSizes[readableName] = None
               print(f'   Added "{readableName}"')
         else:
            del missingItems[readableName]
      if itemAddCount == 0:
         print("   None")
      else:
         with open(ITEM_STACK_SIZE_FILENAME, "w", newline="\n") as fout:
            json.dump(itemStackSizes, fout, indent=2)
         print(f"{itemAddCount} items added to {ITEM_STACK_SIZE_FILENAME}.  You should fill in the stack limits.")

      print()
      print("Items missing from sav_data.data.ITEMS_FOR_PLAYER_INVENTORY")
      if len(missingItems) == 0:
         print("   None")
      else:
         print("If you're going to add these entries, you'll need to determine the full path names.")
         for readableName in missingItems:
            print(f'   {readableName}')
         # Add item to in-game inventory, save, and parse with:
         #    py sav_parse.py <save>
         # Use the partial path name found for the readable names above in readableNames.py
         # and review <save>-dump.txt

   elif len(sys.argv) == 2 and sys.argv[1] == "--list-crash-site-guards":

      # This is the order of the crash sites in https://satisfactory.wiki.gg/wiki/Crash_Site
      print("\nThis information was gathered empirically.  It is being printed in the order of the Wiki to enhance the Wiki, not because it was derived from the Wiki.\n")
      for shortName in ("BP_DropPod1_4", "BP_DropPod5_6", "BP_DropPod21_2", "BP_DropPod22", "BP_DropPod23", "BP_DropPod43_2", "BP_DropPod_C_12", "BP_DropPod_C_8", "BP_DropPod1_8", "BP_DropPod4_6", "BP_DropPod40_1163", "BP_DropPod2_5", "BP_DropPod1_3", "BP_DropPod3_5", "BP_DropPod16_4595", "BP_DropPod41_8375", "BP_DropPod33", "BP_DropPod17_7892", "BP_DropPod34", "BP_DropPod7_5615", "BP_DropPod15_821", "BP_DropPod18", "BP_DropPod6_2102", "BP_DropPod5_740", "BP_DropPod_C_UAID_04421A9713F020A401_1123860977", "BP_DropPod_C_UAID_04421A9713F020A401_1502230978", "BP_DropPod_C_UAID_04421A9713F01FA401_2123550800", "BP_DropPod9_1568", "BP_DropPod3_8348", "BP_DropPod2_1325", "BP_DropPod4_13058", "BP_DropPod_1145", "BP_DropPod_C_7", "BP_DropPod3", "BP_DropPod_C_3", "BP_DropPod_C_0", "BP_DropPod26", "BP_DropPod36_UAID_40B076DF2F79496001_1121515405", "BP_DropPod36", "BP_DropPod37", "BP_DropPod38", "BP_DropPod39", "BP_DropPod39_UAID_40B076DF2F79F35F01_1355966267", "BP_DropPod35", "BP_DropPod4_7", "BP_DropPod44_10", "BP_DropPod25", "BP_DropPod3_8", "BP_DropPod2", "BP_DropPod3_1", "BP_DropPod12", "BP_DropPod1_0", "BP_DropPod_C_4", "BP_DropPod3_2", "BP_DropPod11_2", "BP_DropPod_C_10", "BP_DropPod5_13", "BP_DropPod4_12", "BP_DropPod1_22", "BP_DropPod_C_9", "BP_DropPod2_10", "BP_DropPod6_27", "BP_DropPod3_11", "BP_DropPod3_24", "BP_DropPod5_26", "BP_DropPod2_23", "BP_DropPod1", "BP_DropPod1_1", "BP_DropPod1_2", "BP_DropPod1_9", "BP_DropPod2_0", "BP_DropPod2_1", "BP_DropPod2_2", "BP_DropPod2_6", "BP_DropPod2_11", "BP_DropPod3_12", "BP_DropPod3_3", "BP_DropPod3_4", "BP_DropPod3_7", "BP_DropPod4", "BP_DropPod4_1", "BP_DropPod4_4", "BP_DropPod4_9", "BP_DropPod4_25", "BP_DropPod4_8033", "BP_DropPod5", "BP_DropPod5_9", "BP_DropPod5_10", "BP_DropPod6", "BP_DropPod7", "BP_DropPod8", "BP_DropPod9", "BP_DropPod10", "BP_DropPod13", "BP_DropPod14_389", "BP_DropPod19", "BP_DropPod20", "BP_DropPod24_1", "BP_DropPod27_20823", "BP_DropPod28_23787", "BP_DropPod29_27444", "BP_DropPod30_6998", "BP_DropPod31", "BP_DropPod32_1", "BP_DropPod42", "BP_DropPod42_5", "BP_DropPod45_6", "BP_DropPod_C_1", "BP_DropPod_C_2", "BP_DropPod_C_5", "BP_DropPod_C_6", "BP_DropPod_C_11", "BP_DropPod_C_UAID_04421A9713F03B7C01_1559404536", "BP_DropPod_C_UAID_04421A9713F03B7C01_1712034537", "BP_DropPod_C_UAID_04421A9713F03B7C01_1807913538", "BP_DropPod_C_UAID_04421A9713F03C7C01_1131248715", "BP_DropPod_C_UAID_04421A9713F0486401_1144991453", "BP_DropPod_C_UAID_04421A9713F0FF6301_1123988602"):
         longName = f"Persistent_Level:PersistentLevel.{shortName}"
         if longName in sav_data.crashSites.CRASH_SITES:
            crashSite = sav_data.crashSites.CRASH_SITES[longName]
            details = sav_data.crashSites.CRASH_SITES[longName][3]

            guards = ""
            if "gas" in details:
               if details["gas"] != "Desc_StingerElite_C":
                  sourceName = sav_parse.pathNameToReadableName(details["gas"])
                  guards += f", {sourceName}s"
            if "sentry" in details:
               sentry = details["sentry"]
               for type in sentry:
                  mobQuantity = type[1]
                  mobName = sav_parse.pathNameToReadableName(type[0])
                  if mobQuantity == 1:
                     if mobName[0] == "A" or mobName[0] == "E":
                        mobQuantity = "an"
                     else:
                        mobQuantity = "a"
                  else:
                     mobName += "s"
                  guards += f", {mobQuantity} {mobName}"

            if len(guards) == 0:
               print(f"{shortName}")
            else:
               guards = guards[2:]
               loc = guards.rfind(",")
               if loc != -1:
                  guards = guards[:loc] + " and" + guards[loc+1:]
               print(f"{shortName}  Guarded by {guards}")
         else:
            print(f"Unknown crash site {shortName}")

   elif len(sys.argv) in (4, 5) and sys.argv[1] == "--add-water-extractor" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      outFilename = sys.argv[3]
      changeTimeFlag = True
      if len(sys.argv) == 5 and sys.argv[4] == "--same-time":
         changeTimeFlag = False

      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)
      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      addWaterExtractor(parsedSave.levels[-1], [-75173.3515625, 232295.75, -2630], -45.0, "Persistent_Level:PersistentLevel.FGWaterVolume78")

      try:
         if changeTimeFlag:
            parsedSave.saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(parsedSave, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            parsedSave = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   else:
      print(f"ERROR: Did not understand {len(sys.argv)} arguments: {sys.argv}", file=sys.stderr)
      printUsage()
      exit(1)

   exit(0)
