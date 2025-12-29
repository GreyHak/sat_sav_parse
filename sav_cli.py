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

def getBlankCategory(categoryName: str, iconId: int = -1) -> list:
   return [[['CategoryName', categoryName], ['IconID', iconId], ['MenuPriority', 0.0], ['IsUndefined', False], ['SubCategoryRecords', [[[['SubCategoryName', 'Undefined'], ['MenuPriority', 0.0], ['IsUndefined', 1], ['BlueprintNames', []]], [['SubCategoryName', 'StrProperty', 0], ['MenuPriority', 'FloatProperty', 0], ['IsUndefined', 'ByteProperty', 0], ['BlueprintNames', ['ArrayProperty', 'StrProperty'], 0]]]]]], [['CategoryName', 'StrProperty', 0], ['IconID', 'IntProperty', 0], ['MenuPriority', 'FloatProperty', 0], ['IsUndefined', 'BoolProperty', 0], ['SubCategoryRecords', ['ArrayProperty', 'StructProperty', 'BlueprintSubCategoryRecord'], 0]]]

def getBlankSubcategory(subcategoryName: str) -> list:
   return [[['SubCategoryName', subcategoryName], ['MenuPriority', 0.0], ['IsUndefined', 0], ['BlueprintNames', []]], [['SubCategoryName', 'StrProperty', 0], ['MenuPriority', 'FloatProperty', 0], ['IsUndefined', 'ByteProperty', 0], ['BlueprintNames', ['ArrayProperty', 'StrProperty'], 0]]]

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
              "actorSpecificInfo": toJSON(object.actorSpecificInfo)}

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
      objectReference = sav_parse.ObjectReference()
      objectReference.levelName = object["levelName"]
      objectReference.pathName = object["pathName"]
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
            (rootObject, rotation, position) = sav_data.somersloop.SOMERSLOOPS[collectable.pathName]

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
            nullParentObjectReference.levelName = ""
            nullParentObjectReference.pathName = ""
            newObject.actorReferenceAssociations = [nullParentObjectReference, []]
            newObject.properties    = []
            newObject.propertyTypes = []
            newObject.actorSpecificInfo = None
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
            (rootObject, rotation, position) = sav_data.mercerSphere.MERCER_SPHERES[collectable.pathName]

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
            nullParentObjectReference.levelName = ""
            nullParentObjectReference.pathName = ""
            newObject.actorReferenceAssociations = [nullParentObjectReference, []]
            newObject.properties    = []
            newObject.propertyTypes = []
            newObject.actorSpecificInfo = None
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
            nullParentObjectReference.levelName = ""
            nullParentObjectReference.pathName = ""
            newObject.actorReferenceAssociations = [nullParentObjectReference, []]
            newObject.properties    = []
            newObject.propertyTypes = []
            newObject.actorSpecificInfo = None
            level.objects.append(newObject)

            print(f"Restored Mercer Shrine {instanceName} at {position}")
            return True

   return False

def removeInstance(levels: list, humanReadableName: str, rootObject, targetInstanceName: str, position = None) -> bool:

   removedObjectCollectionReference = sav_parse.ObjectReference()
   removedObjectCollectionReference.levelName = rootObject
   removedObjectCollectionReference.pathName = targetInstanceName

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
   (rootObject, rotation, position) = sav_data.somersloop.SOMERSLOOPS[targetInstanceName]
   print(f"Removing Somersloop {targetInstanceName} at {position}")
   return removeInstance(levels, "Somersloops", rootObject, targetInstanceName, position)

def removeMercerSphere(levels, targetInstanceName: str) -> bool:
   (rootObject, rotation, position) = sav_data.mercerSphere.MERCER_SPHERES[targetInstanceName]
   print(f"Removing Mercer Sphere {targetInstanceName} at {position}")
   return removeInstance(levels, "Mercer Sphere", rootObject, targetInstanceName, position)

def removeMercerShrine(levels, targetInstanceName: str) -> bool:
   (rootObject, rotation, position, scale) = sav_data.mercerSphere.MERCER_SHRINES[targetInstanceName]
   print(f"Removing Mercer Shrine {targetInstanceName} at {position}")
   return removeInstance(levels, "Mercer Shrine", rootObject, targetInstanceName, position)

def addMapMarker(levels, markerName: str, markerLocation: list[float, float, float] | tuple[float, float, float], markerIconId_key: str, markerColor: list[float, float, float] | tuple[float, float, float] = (0.6, 0.6, 0.6), markerViewDistance: sav_data.data.ECompassViewDistance = sav_data.data.ECompassViewDistance.CVD_Mid, scale: float = 1.0) -> bool:
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

               markerPlacedByAccountID = "0666C4A20501001001"
               if len(mapMarkers) > 0:
                  markerPlacedByAccountID = sav_parse.getPropertyValue(mapMarkers[0][0], "MarkerPlacedByAccountID")

               newMarker = [[["markerGuid", uuid.uuid4().bytes], ["Location", [[["X", markerLocation[0]], ["Y", markerLocation[1]], ["Z", markerLocation[2]]], [["X", "DoubleProperty", 0], ["Y", "DoubleProperty", 0], ["Z", "DoubleProperty", 0]]]],
                             ["Name", markerName], ["CategoryName", ""], ["MapMarkerType", ["ERepresentationType", "ERepresentationType::RT_MapMarker"]],
                             ["IconID", sav_data.data.ICON_IDS[markerIconId_key]], ["Color", [markerColor[0], markerColor[1], markerColor[2], 1.0]], ["Scale", scale],
                             ["compassViewDistance", ["ECompassViewDistance", f"ECompassViewDistance::{markerViewDistance.name}"]], ["MarkerPlacedByAccountID", markerPlacedByAccountID]], [["markerGuid", ["StructProperty", "Guid"], 0], ["Location", ["StructProperty", "Vector_NetQuantize"], 0], ["Name", "StrProperty", 0], ["CategoryName", "StrProperty", 0], ["MapMarkerType", "EnumProperty", 0], ["IconID", "IntProperty", 0], ["Color", ["StructProperty", "LinearColor"], 0], ["Scale", "FloatProperty", 0], ["compassViewDistance", "EnumProperty", 0], ["MarkerPlacedByAccountID", "StrProperty", 0]]]
               mapMarkers.append(newMarker)
               return True
   return False

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
   print("   py sav_cli.py --export-player-inventory <player-num> <save-filename> <output-json-filename>")
   print("   py sav_cli.py --import-player-inventory <player-num> <original-save-filename> <input-json-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --tweak-player-inventory <player-num> <slot-index> <item> <quantity> <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --rotate-foundations <primary-color-hex-or-preset> <secondary-color-hex-or-preset> <original-save-filename> <new-save-filename> [--same-time]")
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
   print("   py sav_cli.py --list-map-markers <save-filename>")
   print("   py sav_cli.py --add-map-markers-json <original-save-filename> <input-json-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --add-map-markers-somersloops <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --add-map-markers-mercer-spheres <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --add-map-markers-hard-drives <original-save-filename> <new-save-filename> [--same-time]")
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
   print()

   # TODO: Add manipulation of cheat flags
   #    mapOptions ends in "?enableAdvancedGameSettings"
   #    cheatFlag=True
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
         print(f"Persistent Save Identifier: {parsedSave.saveFileInfo.persistentSaveIdentifier}")
         print(f"Random: {parsedSave.saveFileInfo.random}")
         print(f"Cheat Flag: {parsedSave.saveFileInfo.cheatFlag}")

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

         crashSitesInSave = []
         for level in parsedSave.levels:
            for actorOrComponentObjectHeader in level.actorAndComponentObjectHeaders:
               if isinstance(actorOrComponentObjectHeader, sav_parse.ActorHeader):
                  if actorOrComponentObjectHeader.typePath == sav_data.data.CRASH_SITE:
                     crashSitesInSave.append(actorOrComponentObjectHeader.instanceName)
         crashSitesUnopenedKeys = crashSitesInSave.copy()
         numOpenAndEmptyCrashSites = 0
         numOpenAndFullCrashSites = 0
         crashSiteInventoryPathName = {}
         crashSitesDismantled = []
         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName in crashSitesInSave:
                  hasBeenOpened = sav_parse.getPropertyValue(object.properties, "mHasBeenOpened")
                  if hasBeenOpened is not None and hasBeenOpened:
                     crashSitesUnopenedKeys.remove(object.instanceName)
                     hasBeenLooted = sav_parse.getPropertyValue(object.properties, "mHasBeenLooted")
                     if hasBeenLooted is None:
                        crashSiteInventoryPathName[f"{object.instanceName}.Inventory2"] = object.instanceName # v1.0 doesn't use the "mInventory" property anymore.  Any open, but unlooted droppods from Update 8 will be empty in v1.0.
                        hasBeenLooted = True # If inventory isn't found, the droppod has been looted, so assuming that here.
                     if hasBeenLooted:
                        numOpenAndEmptyCrashSites += 1
                     else: # This case has not been observed
                        numOpenAndFullCrashSites += 1
            if level.collectables1 is not None:
               for collectable in level.collectables1:  # Quantity should match collectables2
                  if collectable.pathName in sav_data.crashSites.CRASH_SITES:
                     crashSitesDismantled.append(collectable.pathName)
         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName in crashSiteInventoryPathName:
                  inventoryStacks = sav_parse.getPropertyValue(object.properties, "mInventoryStacks")
                  if inventoryStacks is not None:
                     item = sav_parse.getPropertyValue(inventoryStacks[0][0], "Item")
                     if item is not None:
                        if len(item) == 2 and isinstance(item[0], str):
                           if item[0] == "/Game/FactoryGame/Resource/Environment/CrashSites/Desc_HardDrive.Desc_HardDrive_C" and item[1] != 0:
                              numOpenAndEmptyCrashSites -= 1
                              numOpenAndFullCrashSites += 1
                              # Use inventory object to get droppod object to get location
         numCrashSitesNotOpened = len(crashSitesInSave) - numOpenAndEmptyCrashSites - numOpenAndFullCrashSites
         print(f"{len(sav_data.crashSites.CRASH_SITES)} total crash sites on map.")
         print(f"   {len(crashSitesInSave) + len(crashSitesDismantled)} found in save file.")
         print(f"   {numCrashSitesNotOpened} not opened.")
         print(f"   {numOpenAndFullCrashSites} opened with hard drive.")
         print(f"   {numOpenAndEmptyCrashSites} opened and empty.")
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
         jdata["headhex"] = toJSON(parsedSave.headhex)
         jdata["grids"] = toJSON(parsedSave.grids)
         ldata = jdata["levels"] = {}
         for level in parsedSave.levels:
            ldata[level.levelName] = {
               "objectHeaders": toJSON(level.actorAndComponentObjectHeaders),
               "levelPersistentFlag": toJSON(level.levelPersistentFlag),
               "collectables1": toJSON(level.collectables1),
               "objects": toJSON(level.objects),
               "levelSaveVersion": toJSON(level.levelSaveVersion),
               "collectables2": toJSON(level.collectables2)}
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
      saveFileInfo.persistentSaveIdentifier = jdata["saveFileInfo"]["persistentSaveIdentifier"]
      saveFileInfo.random = jdata["saveFileInfo"]["random"]
      saveFileInfo.cheatFlag = jdata["saveFileInfo"]["cheatFlag"]
      headhex = jdata["headhex"]
      grids = jdata["grids"]
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
            objects.append(objectCopy)

         levelSaveVersion = levelData["levelSaveVersion"]

         collectables2 = []
         for objectReference in levelData["collectables2"]:
            collectables2.append(fromJSON(objectReference))

         levels.append(sav_parse.Level(levelName, actorAndComponentObjectHeaders, levelPersistentFlag, collectables1, objects, levelSaveVersion, collectables2))

      print("Writing Save")
      try:
         sav_to_resave.saveFile(sav_parse.ParsedSave(saveFileInfo, headhex, grids, levels, aLevelName, dropPodObjectReferenceList, extraObjectReferenceList), outFilename)
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

   elif len(sys.argv) in (6, 7) and sys.argv[1] == "--rotate-foundations" and os.path.isfile(sys.argv[4]):
      colorPrimary = sys.argv[2]
      colorSecondary = sys.argv[3]
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
                        for (rotationQuaternion, position, swatchPathName, patternDescNumber, (primaryColor, secondaryColor), somethingData, maybeIndex, recipePathName, blueprintProxyLevelPath, beamLength) in lightweightBuildableInstances:
                           if lcTupleToSrgbHex(primaryColor) == colorPrimary and lcTupleToSrgbHex(secondaryColor) == colorSecondary:
                              euler = quaternionToEuler(rotationQuaternion)
                              oldYaw = euler[2]
                              euler[2] += math.pi/180
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

                              if replacementHotbarItem.startswith("/Game/FactoryGame/Buildable/-Shared/Customization/"):
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
               newRecipeObjectReference = sav_parse.ObjectReference()
               newRecipeObjectReference.levelName = ""
               newRecipeObjectReference.pathName = replacementHotbarItem
               newObject.properties    = [("mRecipeToActivate", newRecipeObjectReference), ("mShortcutIndex", hotbarItemIdx)]
               newObject.propertyTypes = [("mRecipeToActivate", "ObjectProperty", 0),      ("mShortcutIndex", "IntProperty", 0)]
            elif replacementHotbarItemNewClassName == "FGFactoryCustomizationShortcut":
               newRecipeObjectReference = sav_parse.ObjectReference()
               newRecipeObjectReference.levelName = ""
               newRecipeObjectReference.pathName = replacementHotbarItem
               newObject.properties    = [("mCustomizationRecipeToActivate", newRecipeObjectReference), ("mShortcutIndex", hotbarItemIdx)]
               newObject.propertyTypes = [("mCustomizationRecipeToActivate", "ObjectProperty", 0),      ("mShortcutIndex", "IntProperty", 0)]
            elif replacementHotbarItemNewClassName == "FGEmoteShortcut":
               newRecipeObjectReference = sav_parse.ObjectReference()
               newRecipeObjectReference.levelName = ""
               newRecipeObjectReference.pathName = replacementHotbarItem
               newObject.properties    = [("mEmoteToActivate", newRecipeObjectReference), ("mShortcutIndex", hotbarItemIdx)]
               newObject.propertyTypes = [("mEmoteToActivate", "ObjectProperty", 0),      ("mShortcutIndex", "IntProperty", 0)]
            elif replacementHotbarItemNewClassName == "FGBlueprintShortcut":
               newObject.properties    = [("mBlueprintName", replacementHotbarItem), ("mShortcutIndex", hotbarItemIdx)]
               newObject.propertyTypes = [("mBlueprintName", "StrProperty", 0),      ("mShortcutIndex", "IntProperty", 0)]

            newObject.actorSpecificInfo = None
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
                  objectReference = sav_parse.ObjectReference()
                  objectReference.levelName = "Persistent_Level"
                  objectReference.pathName = newSavedWheeledVehiclePath
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
         parentObjectReference = sav_parse.ObjectReference()
         parentObjectReference.levelName = "Persistent_Level"
         parentObjectReference.pathName = "Persistent_Level:PersistentLevel.VehicleSubsystem"
         object.actorReferenceAssociations = [parentObjectReference, []]
         firstObjectReference = sav_parse.ObjectReference()
         firstObjectReference.levelName = "Persistent_Level"
         firstObjectReference.pathName = newVehicleTargetPoints[0]
         lastObjectReference = sav_parse.ObjectReference()
         lastObjectReference.levelName = "Persistent_Level"
         lastObjectReference.pathName = newVehicleTargetPoints[-1]
         vehicleObjectReference = sav_parse.ObjectReference()
         vehicleObjectReference.levelName = ""
         vehicleObjectReference.pathName = jdata["mVehicleType"]
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
            parentObjectReference = sav_parse.ObjectReference()
            parentObjectReference.levelName = "Persistent_Level"
            parentObjectReference.pathName = newDrivingTargetList
            object.actorReferenceAssociations = [parentObjectReference, []]
            object.properties = []
            object.propertyTypes = []
            if idx+1 < len(newVehicleTargetPoints):
               nextObjectReference = sav_parse.ObjectReference()
               nextObjectReference.levelName = "Persistent_Level"
               nextObjectReference.pathName = newVehicleTargetPoints[idx+1]
               object.properties.append(["mNext", nextObjectReference])
               object.propertyTypes.append(["mNext", "ObjectProperty", 0])
            if jdata["mTargetList"][idx][3] is not None:
               object.properties.append(["mWaitTime", jdata["mTargetList"][idx][3]])
               object.propertyTypes.append(["mWaitTime", "FloatProperty", 0])
            object.properties.append(["mTargetSpeed", jdata["mTargetList"][idx][2]])
            object.propertyTypes.append(["mTargetSpeed", "IntProperty", 0])
            object.actorSpecificInfo = None
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
         parentObjectReference.levelName = ""
         parentObjectReference.pathName = ""
         object.actorReferenceAssociations = [parentObjectReference, []]
         firstObjectReference = sav_parse.ObjectReference()
         firstObjectReference.levelName = "Persistent_Level"
         firstObjectReference.pathName = newVehicleTargetPoints[0]
         lastObjectReference = sav_parse.ObjectReference()
         lastObjectReference.levelName = "Persistent_Level"
         lastObjectReference.pathName = newVehicleTargetPoints[-1]
         listObjectReference = sav_parse.ObjectReference()
         listObjectReference.levelName = "Persistent_Level"
         listObjectReference.pathName = newDrivingTargetList
         object.properties = [
            ["mPathName", newSavePathName],
            ["mTargetList", listObjectReference]]
         object.propertyTypes = [
            ["mPathName", "StrProperty", 0],
            ["mTargetList", "ObjectProperty", 0]]
         object.actorSpecificInfo = None
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
                           amount = sav_parse.getPropertyValue(storedItem[0], "Amount")
                           if amount is not None:
                              itemName = sav_parse.pathNameToReadableName(itemClass.pathName)
                              print(f"{itemName}, {amount}")
                              jdata.append((itemName, amount))

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
                                 if haystackPropertyName == "Amount":
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

   elif len(sys.argv) == 4 and sys.argv[1] == "--export-crash-sites" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      outFilename = sys.argv[3]

      modifiedFlag = False
      try:
         parsedSave = sav_parse.readFullSaveFile(savFilename)

         crashSitesInSave = []
         for level in parsedSave.levels:
            for actorOrComponentObjectHeader in level.actorAndComponentObjectHeaders:
               if isinstance(actorOrComponentObjectHeader, sav_parse.ActorHeader):
                  if actorOrComponentObjectHeader.typePath == sav_data.data.CRASH_SITE:
                     crashSitesInSave.append(actorOrComponentObjectHeader.instanceName)
         crashSitesOpenWithDrive = []
         crashSitesUnopenedKeys = crashSitesInSave.copy()
         openAndEmptyCrashSites = []
         openAndFullCrashSites = []
         crashSiteInventoryPathName = {} # Maps inventory instance path name to crash site instance path name
         crashSitesDismantled = []
         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName in crashSitesInSave:
                  hasBeenOpened = sav_parse.getPropertyValue(object.properties, "mHasBeenOpened")
                  if hasBeenOpened is not None and hasBeenOpened:
                     crashSitesUnopenedKeys.remove(object.instanceName)
                     hasBeenLooted = sav_parse.getPropertyValue(object.properties, "mHasBeenLooted")
                     if hasBeenLooted is None:
                        crashSiteInventoryPathName[f"{object.instanceName}.Inventory2"] = object.instanceName # v1.0 doesn't use the "mInventory" property anymore.  Any open, but unlooted droppods from Update 8 will be empty in v1.0.
                        hasBeenLooted = True # If inventory isn't found, the droppod has been looted, so assuming that here.
                     if hasBeenLooted:
                        openAndEmptyCrashSites.append(object.instanceName)
                     else: # This case has not been observed
                        openAndFullCrashSites.append(object.instanceName)
                        crashSitesOpenWithDrive.append(object.instanceName)
            if level.collectables1 is not None:
               for collectable in level.collectables1:  # Quantity should match collectables2
                  if collectable.pathName in sav_data.crashSites.CRASH_SITES:
                     crashSitesDismantled.append(collectable.pathName)
         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName in crashSiteInventoryPathName:
                  inventoryStacks = sav_parse.getPropertyValue(object.properties, "mInventoryStacks")
                  if inventoryStacks is not None:
                     item = sav_parse.getPropertyValue(inventoryStacks[0][0], "Item")
                     if item is not None:
                        if len(item) == 2 and isinstance(item[0], str):
                           if item[0] == "/Game/FactoryGame/Resource/Environment/CrashSites/Desc_HardDrive.Desc_HardDrive_C" and item[1] != 0:
                              crashSiteInstancePathName = crashSiteInventoryPathName[object.instanceName]
                              openAndEmptyCrashSites.remove(crashSiteInstancePathName)
                              openAndFullCrashSites.append(crashSiteInstancePathName)
                              # Use inventory object to get droppod object to get location
                              crashSitesOpenWithDrive.append(crashSiteInstancePathName)
         numCrashSitesNotOpened = len(crashSitesInSave) - len(openAndEmptyCrashSites) - len(openAndFullCrashSites)
         print(f"{len(sav_data.crashSites.CRASH_SITES)} total crash sites on map.")
         print(f"   {len(crashSitesInSave) + len(crashSitesDismantled)} found in save file.")
         print(f"   {numCrashSitesNotOpened} not opened.")
         print(f"   {len(openAndFullCrashSites)} opened with hard drive.")
         print(f"   {len(openAndEmptyCrashSites)} opened and empty.")
         print(f"   {len(crashSitesDismantled)} dismantled.")

         jdata = {}
         for crashSite in openAndEmptyCrashSites:
            jdata[crashSite] = "IN_SAVE_OPEN_EMPTY"
         for crashSite in openAndFullCrashSites:
            jdata[crashSite] = "IN_SAVE_OPEN_FULL"
         for crashSite in crashSitesInSave:
            if crashSite not in openAndEmptyCrashSites and crashSite not in openAndFullCrashSites:
               jdata[crashSite] = "IN_SAVE_CLOSED"
         for crashSite in sav_data.crashSites.CRASH_SITES:
            if crashSite not in crashSitesInSave:
               if crashSite in crashSitesDismantled:
                  jdata[crashSite] = "DISMANTLED"
               else:
                  jdata[crashSite] = "NOT_IN_SAVE"

         print(f"Writing {outFilename}")
         with open(outFilename, "w") as fout:
            json.dump(jdata, fout, indent=2)

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

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
                        for iconName in sav_data.data.ICON_IDS:
                           if iconID == sav_data.data.ICON_IDS[iconName]:
                              iconID = iconName

                        print(f"{markerGuid} '{name}' at {location} scale={scale} distance={compassViewDistance} icon={iconID}")

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

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

               markerColor = (0.6, 0.6, 0.6) # Float RGB (up to 1.0)
               if "Color" in newMarker:
                  markerColor = newMarker["Color"]

               markerIconId_key = sav_data.data.ICON_IDS["Home House"]
               if "IconName" in newMarker and newMarker["IconName"] in sav_data.data.ICON_IDS:
                  markerIconId_key = newMarker["IconName"]

               markerViewDistance = sav_data.data.ECompassViewDistance.CVD_Mid
               if "compassViewDistance" in newMarker and newMarker["compassViewDistance"] in sav_data.data.COMPASS_VIEW_DISTANCES__NAME_TO_ENUM:
                  markerViewDistance = sav_data.data.COMPASS_VIEW_DISTANCES__NAME_TO_ENUM[newMarker["compassViewDistance"]]

               scale = 1.0
               if "Scale" in newMarker:
                  scale = newMarker["Scale"]

               if addMapMarker(parsedSave.levels, markerName, markerLocation, markerIconId_key, markerColor, markerViewDistance, scale):
                  print(f"Added {markerName} at {markerLocation}")
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

            if addMapMarker(parsedSave.levels, f"sloop {shortName}", markerLocation, "Road Arrow Down", markerColor, sav_data.data.ECompassViewDistance.CVD_Near, UNCOLLECTED_MAP_MARKER_SCALE):
               print(f"Added {shortName} at {markerLocation}")
               modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: Failed to find mMapMarkers in save.", file=sys.stderr)
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

            if addMapMarker(parsedSave.levels, f"sphere {shortName}", markerLocation, "Road Arrow Down", markerColor, sav_data.data.ECompassViewDistance.CVD_Near, UNCOLLECTED_MAP_MARKER_SCALE):
               print(f"Added {shortName} at {markerLocation}")
               modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: Failed to find mMapMarkers in save.", file=sys.stderr)
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

         crashSitesInSave = []
         for level in parsedSave.levels:
            for actorOrComponentObjectHeader in level.actorAndComponentObjectHeaders:
               if isinstance(actorOrComponentObjectHeader, sav_parse.ActorHeader):
                  if actorOrComponentObjectHeader.typePath == sav_data.data.CRASH_SITE:
                     crashSitesInSave.append(actorOrComponentObjectHeader.instanceName)
         crashSitesOpenWithDrive = []
         crashSitesUnopenedKeys = crashSitesInSave.copy()
         openAndEmptyCrashSites = []
         openAndFullCrashSites = []
         crashSiteInventoryPathName = {} # Maps inventory instance path name to crash site instance path name
         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName in crashSitesInSave:
                  hasBeenOpened = sav_parse.getPropertyValue(object.properties, "mHasBeenOpened")
                  if hasBeenOpened is not None and hasBeenOpened:
                     crashSitesUnopenedKeys.remove(object.instanceName)
                     hasBeenLooted = sav_parse.getPropertyValue(object.properties, "mHasBeenLooted")
                     if hasBeenLooted is None:
                        crashSiteInventoryPathName[f"{object.instanceName}.Inventory2"] = object.instanceName # v1.0 doesn't use the "mInventory" property anymore.  Any open, but unlooted droppods from Update 8 will be empty in v1.0.
                        hasBeenLooted = True # If inventory isn't found, the droppod has been looted, so assuming that here.
                     if hasBeenLooted:
                        openAndEmptyCrashSites.append(object.instanceName)
                     else: # This case has not been observed
                        openAndFullCrashSites.append(object.instanceName)
                        crashSitesOpenWithDrive.append(object.instanceName)
         for level in parsedSave.levels:
            for object in level.objects:
               if object.instanceName in crashSiteInventoryPathName:
                  inventoryStacks = sav_parse.getPropertyValue(object.properties, "mInventoryStacks")
                  if inventoryStacks is not None:
                     item = sav_parse.getPropertyValue(inventoryStacks[0][0], "Item")
                     if item is not None:
                        if len(item) == 2 and isinstance(item[0], str):
                           if item[0] == "/Game/FactoryGame/Resource/Environment/CrashSites/Desc_HardDrive.Desc_HardDrive_C" and item[1] != 0:
                              crashSiteInstancePathName = crashSiteInventoryPathName[object.instanceName]
                              openAndEmptyCrashSites.remove(crashSiteInstancePathName)
                              openAndFullCrashSites.append(crashSiteInstancePathName)
                              # Use inventory object to get droppod object to get location
                              crashSitesOpenWithDrive.append(crashSiteInstancePathName)

         markerColorOpenWithDrive = (sav_to_html.MAP_COLOR_CRASH_SITE_OPEN_W_DRIVE[0]/255, sav_to_html.MAP_COLOR_CRASH_SITE_OPEN_W_DRIVE[1]/255, sav_to_html.MAP_COLOR_CRASH_SITE_OPEN_W_DRIVE[2]/255)
         for crashSite in openAndFullCrashSites:
            shortName = crashSite[crashSite.rfind(".")+1:]
            markerLocation = sav_data.crashSites.CRASH_SITES[crashSite][2]

            if addMapMarker(parsedSave.levels, f"hd {shortName}", markerLocation, "Road Arrow Down", markerColorOpenWithDrive, sav_data.data.ECompassViewDistance.CVD_Near, UNCOLLECTED_MAP_MARKER_SCALE):
               print(f"Added {shortName} at {markerLocation} [Open w/drive]")
               modifiedFlag = True

         markerColorUnopened = (sav_to_html.MAP_COLOR_CRASH_SITE_UNOPENED[0]/255, sav_to_html.MAP_COLOR_CRASH_SITE_UNOPENED[1]/255, sav_to_html.MAP_COLOR_CRASH_SITE_UNOPENED[2]/255)
         for crashSite in crashSitesInSave:
            if crashSite not in openAndEmptyCrashSites and crashSite not in openAndFullCrashSites:
               shortName = crashSite[crashSite.rfind(".")+1:]
               markerLocation = sav_data.crashSites.CRASH_SITES[crashSite][2]

               if addMapMarker(parsedSave.levels, f"hd {shortName}", markerLocation, "Road Arrow Down", markerColorUnopened, sav_data.data.ECompassViewDistance.CVD_Near, UNCOLLECTED_MAP_MARKER_SCALE):
                  print(f"Added {shortName} at {markerLocation} [Closed]")
                  modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: Failed to find mMapMarkers in save.", file=sys.stderr)
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
                           newCategory = getBlankCategory(categoryName, categoryStructure[categoryName]["Icon"])
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
                                 newSubcategory = getBlankSubcategory(subcategoryName)
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
                     blueprintCategoryRecords.append(getBlankCategory(categoryToAdd))
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
                              subCategoryRecords.append(getBlankSubcategory(subcategoryToAdd))
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
         print("ERROR: Failed to find blueprint '{blueprintToRemove}' to remove.", file=sys.stderr)
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

   else:
      print(f"ERROR: Did not understand {len(sys.argv)} arguments: {sys.argv}", file=sys.stderr)
      printUsage()
      exit(1)

   exit(0)
