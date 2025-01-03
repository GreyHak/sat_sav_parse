#!/usr/bin/python3
# This file is part of the Satisfactory Save Parser distribution
#                                  (https://github.com/GreyHak/sat_sav_parse).
# Copyright (c) 2024 GreyHak (github.com/GreyHak).
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

import os
import sys
import json
import math
import uuid
import datetime
import sav_parse
import sav_to_resave
import sav_data_somersloop
import sav_data_mercerSphere
import sav_data_free

try:
   import sav_to_html
   from PIL import Image, ImageDraw, ImageFont
   pilAvailableFlag = True
except ModuleNotFoundError:
   pilAvailableFlag = False

VERIFY_CREATED_SAVE_FILES = False
USERNAME_FILENAME = "sav_cli_usernames.json"

def getBlankCategory(categoryName, iconId = -1):
   return [[['CategoryName', categoryName], ['IconID', iconId], ['MenuPriority', 0.0], ['IsUndefined', False], ['SubCategoryRecords', [[[['SubCategoryName', 'Undefined'], ['MenuPriority', 0.0], ['IsUndefined', 1], ['BlueprintNames', []]], [['SubCategoryName', 'StrProperty', 0], ['MenuPriority', 'FloatProperty', 0], ['IsUndefined', 'ByteProperty', 0], ['BlueprintNames', ['ArrayProperty', 'StrProperty'], 0]]]]]], [['CategoryName', 'StrProperty', 0], ['IconID', 'IntProperty', 0], ['MenuPriority', 'FloatProperty', 0], ['IsUndefined', 'BoolProperty', 0], ['SubCategoryRecords', ['ArrayProperty', 'StructProperty', 'BlueprintSubCategoryRecord'], 0]]]

def getBlankSubcategory(subcategoryName):
   return [[['SubCategoryName', subcategoryName], ['MenuPriority', 0.0], ['IsUndefined', 0], ['BlueprintNames', []]], [['SubCategoryName', 'StrProperty', 0], ['MenuPriority', 'FloatProperty', 0], ['IsUndefined', 'ByteProperty', 0], ['BlueprintNames', ['ArrayProperty', 'StrProperty'], 0]]]

playerUsernames = {}

def getPlayerPaths(levels):
   playerPaths = [] # = (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath)

   playerStateInstances = []
   for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
      for actorOrComponentObjectHeader in actorAndComponentObjectHeaders:
         # "/Game/FactoryGame/Character/Player/BP_PlayerState.BP_PlayerState_C" leads to ShoppingListComponent, FGPlayerHotbar_*
         # This gives the "mOwnedPawn" property which gives the Char_Player_C.  These are different numbers.
         # "/Game/FactoryGame/Character/Player/Char_Player.Char_Player_C" leads to BodySlot, HeadSlot, HealthComponent, LegsSlot, BackSlot, ArmSlot, inventory
         if isinstance(actorOrComponentObjectHeader, sav_parse.ActorHeader) and actorOrComponentObjectHeader.typePath == "/Game/FactoryGame/Character/Player/BP_PlayerState.BP_PlayerState_C":
            playerStateInstances.append(actorOrComponentObjectHeader.instanceName)

   playerCharacterInstances = {} # Looked up by playerCharacter for the playerState value
   for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
      for object in objects:
         if object.instanceName in playerStateInstances:
            # mPlayerHotbars, mCurrentHotbarIndex, mBuildableSubCategoryDefaultMatDesc, mMaterialSubCategoryDefaultMatDesc, mNewRecipes, mPlayerRules, mOwnedPawn,
            # mHasReceivedInitialItems, mVisitedAreas, mCustomColorData, mRememberedFirstTimeEquipmentClasses, mCollapsedMapCategories, mNumObservedInventorySlots,
            # mShoppingListComponent, mOpenedWidgetsPersistent, mPlayerSpecificSchematics
            ownedPawn = sav_parse.getPropertyValue(object.properties, "mOwnedPawn")
            if ownedPawn != None:
               playerHotbars = sav_parse.getPropertyValue(object.properties, "mPlayerHotbars")
               if playerHotbars != None:
                  playerCharacterInstances[ownedPawn.pathName] = (object.instanceName)

   for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
      for object in objects:
         if object.instanceName in playerCharacterInstances:
            inventory = sav_parse.getPropertyValue(object.properties, "mInventory")
            if inventory != None:
               armsEquipmentSlot = sav_parse.getPropertyValue(object.properties, "mArmsEquipmentSlot")
               if armsEquipmentSlot != None:
                  backEquipmentSlot = sav_parse.getPropertyValue(object.properties, "mBackEquipmentSlot")
                  if backEquipmentSlot != None:
                     legsEquipmentSlot = sav_parse.getPropertyValue(object.properties, "mLegsEquipmentSlot")
                     if legsEquipmentSlot != None:
                        headEquipmentSlot = sav_parse.getPropertyValue(object.properties, "mHeadEquipmentSlot")
                        if headEquipmentSlot != None:
                           bodyEquipmentSlot = sav_parse.getPropertyValue(object.properties, "mBodyEquipmentSlot")
                           if bodyEquipmentSlot != None:
                              healthComponent = sav_parse.getPropertyValue(object.properties, "mHealthComponent")
                              if healthComponent != None:
                                 (playerStateInstanceName) = playerCharacterInstances[object.instanceName]
                                 playerPaths.append((playerStateInstanceName, object.instanceName, inventory.pathName, armsEquipmentSlot.pathName, backEquipmentSlot.pathName, legsEquipmentSlot.pathName, headEquipmentSlot.pathName, bodyEquipmentSlot.pathName, healthComponent.pathName))

   return playerPaths

def getPlayerName(levels, playerCharacter):
   global playerUsernames
   loc = playerCharacter.rfind("_")
   playerId = playerCharacter[loc+1:]
   if playerId in playerUsernames:
      return playerUsernames[playerId]

   for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
      for object in objects:
         if object.instanceName == playerCharacter:
            cachedPlayerName = sav_parse.getPropertyValue(object.properties, "mCachedPlayerName")
            if cachedPlayerName != None:
               return cachedPlayerName
   return None

def characterPlayerMatch(characterPlayer, playerId):
   return characterPlayer == f"Persistent_Level:PersistentLevel.Char_Player_C_{playerId}"

def orderBlueprintCategoryMenuPriorities(blueprintCategoryRecords):
   for categoryIdx in range(len(blueprintCategoryRecords)):
      category = blueprintCategoryRecords[categoryIdx]
      for propertyIdx in range(len(category[0])):
         if category[0][propertyIdx][0] == "MenuPriority":
            # Must preserve the same propertyIdx because the property type is at this index
            category[0][propertyIdx] = [category[0][propertyIdx][0], float(categoryIdx)]
      subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
      if subCategoryRecords != None:
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
def lcToSRGBFloat(linearCol):
   if linearCol <= 0.0031308:
      return linearCol * 12.92
   else:
      return pow(abs(linearCol), 1.0/2.4) * 1.055 - 0.055

# Converts a luminance component (a linear measure of light) an sRGB component from 0 to 255
def lcToSRGBInt(linearCol):
   return max(0, min(255, round(lcToSRGBFloat(linearCol) * 255)))

def lcTupleToSrgbHex(linearCTuple):
   srgb = ""
   for i in range(3):
      srgb += "{:x}".format(lcToSRGBInt(linearCTuple[i])).zfill(2)
   return srgb

def radiansToDegrees(radians):
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
   if object == None or isinstance(object, (str, int, float, bool, complex)):
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
      if object.actorReferenceAssociations != None:
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
   if object == None or isinstance(object, (str, int, float, bool, complex)):
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

def addSomersloop(levels, targetPathName):
   # For those items present in (both) collectables1 and collectables2, remove those,
   # and replace the original ActorHeader and Object.  Nothing unique is saved in the Object.

   for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
      if collectables1 != None:
         for collectable in collectables1:
            if collectable.pathName == targetPathName:
               collectables1.remove(collectable)
               print(f"Clearing removal of {collectable.pathName}")
               break
      for collectable in collectables2:
         if collectable.pathName == targetPathName:
            collectables2.remove(collectable)

            instanceName = collectable.pathName
            (rootObject, rotation, position) = sav_data_somersloop.SOMERSLOOPS[collectable.pathName]

            newActor = sav_parse.ActorHeader()
            newActor.typePath = sav_parse.SOMERSLOOP
            newActor.rootObject = rootObject
            newActor.instanceName = instanceName
            newActor.needTransform = False
            newActor.rotation = rotation
            newActor.position = position
            newActor.scale = [1.600000023841858, 1.600000023841858, 1.600000023841858]
            newActor.wasPlacedInLevel = 1
            actorAndComponentObjectHeaders.append(newActor)

            newObject = sav_parse.Object()
            newObject.instanceName = instanceName
            newObject.objectGameVersion = 46
            newObject.shouldMigrateObjectRefsToPersistentFlag = False
            nullParentObjectReference = sav_parse.ObjectReference()
            nullParentObjectReference.levelName = ""
            nullParentObjectReference.pathName = ""
            newObject.actorReferenceAssociations = [nullParentObjectReference, []]
            newObject.properties    = []
            newObject.propertyTypes = []
            newObject.actorSpecificInfo = None
            objects.append(newObject)

            print(f"Restored Somersloop {instanceName} at {position}")
            return True

   return False

def addMercerSphere(levels, targetPathName):
   # For those items present in (both) collectables1 and collectables2, remove those,
   # and replace the original ActorHeader and Object.  Nothing unique is saved in the Object.

   for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
      if collectables1 != None:
         for collectable in collectables1:
            if collectable.pathName == targetPathName:
               collectables1.remove(collectable)
               print(f"Clearing removal of sphere {collectable.pathName}")
               break

      for collectable in collectables2:
         if collectable.pathName == targetPathName:
            collectables2.remove(collectable)

            instanceName = collectable.pathName
            (rootObject, rotation, position) = sav_data_mercerSphere.MERCER_SPHERES[collectable.pathName]

            newActor = sav_parse.ActorHeader()
            newActor.typePath = sav_parse.MERCER_SPHERE
            newActor.rootObject = rootObject
            newActor.instanceName = instanceName
            newActor.needTransform = False
            newActor.rotation = rotation
            newActor.position = position
            newActor.scale = [2.700000047683716, 2.6999998092651367, 2.6999998092651367]
            newActor.wasPlacedInLevel = 1
            actorAndComponentObjectHeaders.append(newActor)

            newObject = sav_parse.Object()
            newObject.instanceName = instanceName
            newObject.objectGameVersion = 46
            newObject.shouldMigrateObjectRefsToPersistentFlag = False
            nullParentObjectReference = sav_parse.ObjectReference()
            nullParentObjectReference.levelName = ""
            nullParentObjectReference.pathName = ""
            newObject.actorReferenceAssociations = [nullParentObjectReference, []]
            newObject.properties    = []
            newObject.propertyTypes = []
            newObject.actorSpecificInfo = None
            objects.append(newObject)

            print(f"Restored Mercer Sphere {instanceName} at {position}")
            return True

   return False

def addMercerShrine(levels, targetPathName):
   # For those items present in (both) collectables1 and collectables2, remove those,
   # and replace the original ActorHeader and Object.  Nothing unique is saved in the Object.

   for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
      if collectables1 != None:
         for collectable in collectables1:
            if collectable.pathName == targetPathName:
               collectables1.remove(collectable)
               print(f"Clearing removal of shrine {collectable.pathName}")
               break

      for collectable in collectables2:
         if collectable.pathName == targetPathName:
            collectables2.remove(collectable)

            instanceName = collectable.pathName
            (rootObject, rotation, position, scale) = sav_data_mercerSphere.MERCER_SHRINES[collectable.pathName]

            newActor = sav_parse.ActorHeader()
            newActor.typePath = sav_parse.MERCER_SHRINE
            newActor.rootObject = rootObject
            newActor.instanceName = instanceName
            newActor.needTransform = False
            newActor.rotation = rotation
            newActor.position = position
            newActor.scale = [scale, scale, scale]
            newActor.wasPlacedInLevel = 1
            actorAndComponentObjectHeaders.append(newActor)

            newObject = sav_parse.Object()
            newObject.instanceName = instanceName
            newObject.objectGameVersion = 46
            newObject.shouldMigrateObjectRefsToPersistentFlag = False
            nullParentObjectReference = sav_parse.ObjectReference()
            nullParentObjectReference.levelName = ""
            nullParentObjectReference.pathName = ""
            newObject.actorReferenceAssociations = [nullParentObjectReference, []]
            newObject.properties    = []
            newObject.propertyTypes = []
            newObject.actorSpecificInfo = None
            objects.append(newObject)

            print(f"Restored Mercer Shrine {instanceName} at {position}")
            return True

   return False

def removeInstance(levels, humanReadableName, rootObject, targetInstanceName, position=None):

   removedObjectCollectionReference = sav_parse.ObjectReference()
   removedObjectCollectionReference.levelName = rootObject
   removedObjectCollectionReference.pathName = targetInstanceName

   for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
      for actorOrComponentObjectHeader in actorAndComponentObjectHeaders:
         if actorOrComponentObjectHeader.instanceName == targetInstanceName:
            actorAndComponentObjectHeaders.remove(actorOrComponentObjectHeader)
            for object in objects:
               if object.instanceName == targetInstanceName:
                  objects.remove(object)
                  collectables1.append(removedObjectCollectionReference)
                  collectables2.append(removedObjectCollectionReference)
                  print(f"Removed {humanReadableName} {targetInstanceName} at {position}")
                  return True

   # If present, removed above.  If removed, return False.
   for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
      for collectable in collectables2:
         if collectable.pathName == targetInstanceName:
            return False
   # If got gets here, the object isn't present in the save, so add it.
   # This has only been observed when collectables1 is missing, so can't just append.
   for levelIdx in range(len(levels)):
      (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) = levels[levelIdx]
      if levelName == rootObject:
         print(f"Removed {humanReadableName} {targetInstanceName} at {position} (unvisited)")
         if collectables1 != None:
            collectables1.append(removedObjectCollectionReference)
         collectables2.append(removedObjectCollectionReference)
         return True
   print(f"CAUTION: Failed to remove {humanReadableName} {targetInstanceName} at {position}")
   return False

def removeSomersloop(levels, targetInstanceName):
   (rootObject, rotation, position) = sav_data_somersloop.SOMERSLOOPS[targetInstanceName]
   return removeInstance(levels, "Somersloops", rootObject, targetInstanceName, position)

def removeMercerSphere(levels, targetInstanceName):
   (rootObject, rotation, position) = sav_data_mercerSphere.MERCER_SPHERES[targetInstanceName]
   return removeInstance(levels, "Mercer Sphere", rootObject, targetInstanceName, position)

def removeMercerShrine(levels, targetInstanceName):
   (rootObject, rotation, position, scale) = sav_data_mercerSphere.MERCER_SHRINES[targetInstanceName]
   return removeInstance(levels, "Mercer Shrine", rootObject, targetInstanceName, position)

def printUsage():
   print()
   print("USAGE:")
   print("   py sav_cli.py --info <save-filename>")
   print("   py sav_cli.py --to-json <save-filename> <output-json-filename>")
   print("   py sav_cli.py --from-json <input-json-filename> <new-save-filename>")
   print("   py sav_cli.py --set-session-name <new-session-name> <original-save-filename> <new-save-filename>")
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
      saveFileInfo = sav_parse.readSaveFileInfo(savFilename)
      print(f"Save Header Type: {saveFileInfo.saveHeaderType}")
      print(f"Save Version: {saveFileInfo.saveVersion}")
      print(f"Build Version: {saveFileInfo.buildVersion}")
      print(f"MapName: {saveFileInfo.mapName}")
      print(f"Map Options: {saveFileInfo.mapOptions}")
      print(f"Session Name: {saveFileInfo.sessionName}")
      print(f"Play Duration: {saveFileInfo.playDurationInSeconds} seconds")
      print(f"Save Date Time: {saveFileInfo.saveDateTimeInTicks} ticks ({saveFileInfo.saveDatetime.strftime('%m/%d/%Y %I:%M:%S %p')})")
      print(f"Session Visibility: {saveFileInfo.sessionVisibility}")
      print(f"Editor Object Version: {saveFileInfo.editorObjectVersion}")
      print(f"Mod Metadata: {saveFileInfo.modMetadata}")
      print(f"Is Modded Save: {saveFileInfo.isModdedSave}")
      print(f"Persistent Save Identifier: {saveFileInfo.persistentSaveIdentifier}")
      print(f"Random: {saveFileInfo.random}")
      print(f"Cheat Flag: {saveFileInfo.cheatFlag}")

   elif len(sys.argv) == 4 and sys.argv[1] == "--to-json" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      outFilename = sys.argv[3]

      modifiedFlag = False
      try:
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)

         jdata = {}
         jdata["saveFileInfo"] = toJSON(saveFileInfo)
         jdata["headhex"] = toJSON(headhex)
         jdata["grids"] = toJSON(grids)
         ldata = jdata["levels"] = {}
         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            ldata[levelName] = {
               "objectHeaders": toJSON(actorAndComponentObjectHeaders),
               "collectables1": toJSON(collectables1),
               "objects": toJSON(objects),
               "collectables2": toJSON(collectables2)}
         jdata["extraObjectReferenceList"] = toJSON(extraObjectReferenceList)

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
            if len(objectHeaderJson) == 8:
               objectHeaderCopy = sav_parse.ActorHeader()
               objectHeaderCopy.typePath = objectHeaderJson["typePath"]
               objectHeaderCopy.rootObject = objectHeaderJson["rootObject"]
               objectHeaderCopy.instanceName = objectHeaderJson["instanceName"]
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
               objectHeaderCopy.parentActorName = objectHeaderJson["parentActorName"]
            actorAndComponentObjectHeaders.append(objectHeaderCopy)

         collectables1 = None
         if levelData["collectables1"] != None:
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
            if objectJson["actorReferenceAssociations"] != None:
               objectCopy.actorReferenceAssociations = [fromJSON(objectJson["actorReferenceAssociations"]["parentObjectReference"]), fromJSON(objectJson["actorReferenceAssociations"]["actorComponentReferences"])]
            objectCopy.properties = fromJSON(objectJson["properties"])
            objectCopy.propertyTypes = fromJSON(objectJson["propertyTypes"])
            objectCopy.actorSpecificInfo = fromJSON(objectJson["actorSpecificInfo"])
            objects.append(objectCopy)

         collectables2 = []
         for objectReference in levelData["collectables2"]:
            collectables2.append(fromJSON(objectReference))

         levels.append([levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2])

      print("Writing Save")
      try:
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         print("Validating Save")
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
         print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating save to '{outFilename}': {error}")

   elif len(sys.argv) == 5 and sys.argv[1] == "--set-session-name" and os.path.isfile(sys.argv[3]):
      newSessionName = sys.argv[2]
      savFilename = sys.argv[3]
      outFilename = sys.argv[4]

      try:
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)
      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      saveFileInfo.sessionName = newSessionName

      try:
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (2, 3, 4) and sys.argv[1] == "--find-free-stuff" and (len(sys.argv) < 4 or os.path.isfile(sys.argv[3])):

      if len(sys.argv) == 2:
         for item in sav_data_free.FREE_DROPPED_ITEMS:
            total = 0
            for (quantity, position, instanceName) in sav_data_free.FREE_DROPPED_ITEMS[item]:
               total += quantity
            print(f"{total} x {sav_parse.pathNameToReadableName(item)}")
      else:

         itemName = sys.argv[2]

         droppedInstances = {}
         for item in sav_data_free.FREE_DROPPED_ITEMS:
            if sav_parse.pathNameToReadableName(item) == itemName:
               for idx in range(len(sav_data_free.FREE_DROPPED_ITEMS[item])):
                  (quantity, position, instanceName) = sav_data_free.FREE_DROPPED_ITEMS[item][idx]
                  droppedInstances[instanceName] = (quantity, position)
               break
         if len(droppedInstances) == 0:
            print(f"No {itemName}")
         else:

            if len(sys.argv) == 4:
               savFilename = sys.argv[3]
               try:
                  (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)
                  for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
                     if collectables1 != None:
                        for collectable in collectables1:
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
                     diDraw.text(sav_to_html.MAP_TEXT_1, saveFileInfo.saveDatetime.strftime(f"{total} free {itemName} from save %m/%d/%Y %I:%M:%S %p"), font=imageFont, fill=(50,50,50))
                     diDraw.text(sav_to_html.MAP_TEXT_2, saveFileInfo.sessionName, font=imageFont, fill=(0,0,0))
                  else:
                     diDraw.text(sav_to_html.MAP_TEXT_1, f"All {total} free {itemName}", font=imageFont, fill=(0,0,0))
                  imageFilename = MAP_BASENAME_FREE_ITEM
                  diImage.crop(sav_to_html.CROP_SETTINGS).save(imageFilename)
                  sav_to_html.chown(imageFilename)

   elif len(sys.argv) == 3 and sys.argv[1] == "--list-players" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      try:
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(levels)
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            playerName = getPlayerName(levels, characterPlayer)
            if playerName == None:
               print(characterPlayer)
            else:
               print(f"{characterPlayer} ({playerName})")
      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

   elif len(sys.argv) == 4 and sys.argv[1] == "--list-player-inventory" and os.path.isfile(sys.argv[3]):
      playerId = sys.argv[2]
      savFilename = sys.argv[3]
      try:
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(levels)

         playerInventory = None
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            if characterPlayerMatch(characterPlayer, playerId):
               playerInventory = inventoryPath

         if playerInventory == None:
            print(f"Unable to match player '{playerId}'", file=sys.stderr)
            exit(1)

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
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
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(levels)

         playerInventory = None
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            if characterPlayerMatch(characterPlayer, playerId):
               playerInventory = inventoryPath

         if playerInventory == None:
            print(f"Unable to match player '{playerId}'", file=sys.stderr)
            exit(1)

         inventoryContents = []

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
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
         inventoryContents = json.load(fin)

      for inventoryContent in inventoryContents:
         if inventoryContent != None:
            itemPathName = inventoryContent[0]
            if itemPathName not in sav_parse.ITEMS_FOR_PLAYER_INVENTORY:
               print(f"ERROR: {itemPathName} not a valid item path name.")
               exit(1)

      modifiedFlag = False
      try:
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(levels)

         playerInventory = None
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            if characterPlayerMatch(characterPlayer, playerId):
               playerInventory = inventoryPath

         if playerInventory == None:
            print(f"Unable to match player '{playerId}'")
            exit(1)

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName == playerInventory:
                  inventoryStacks = sav_parse.getPropertyValue(object.properties, "mInventoryStacks")
                  if inventoryStacks:
                     for idx in range(len(inventoryStacks)):
                        if idx < len(inventoryContents):
                           print(f"Replacing {sav_parse.toString(inventoryStacks[idx][0])}")
                           if inventoryContents[idx] == None:
                              inventoryStacks[idx][0][0] = ["Item", ["", 1]]
                              inventoryStacks[idx][0][1] = ["NumItems", 0]
                              print(f"Setting player {playerInventory}'s inventory slot {idx} to be Empty")
                           elif len(inventoryContents[idx]) == 2:
                              (itemPathName, itemQuantity) = inventoryContents[idx]
                              inventoryStacks[idx][0][0] = ["Item", [itemPathName, 1]]
                              inventoryStacks[idx][0][1] = ["NumItems", itemQuantity]
                              print(f"Setting player {playerInventory}'s inventory slot {idx} to include {itemQuantity} x {sav_parse.pathNameToReadableName(itemPathName)}")
                           elif len(inventoryContents[idx]) == 4:
                              (itemPathName, itemQuantity, itemPropName, itemProps) = inventoryContents[idx]
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
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
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

      if tweakItemName not in sav_parse.ITEMS_FOR_PLAYER_INVENTORY:
         for className in sav_parse.READABLE_PATH_NAME_CORRECTIONS:
            if tweakItemName == sav_parse.READABLE_PATH_NAME_CORRECTIONS[className]:
               suffixSearch = f".{className}"
               for pathName in sav_parse.ITEMS_FOR_PLAYER_INVENTORY:
                  if pathName.endswith(suffixSearch):
                     print(f"Using '{pathName}' for {tweakItemName}")
                     tweakItemName = pathName
                     break
               break

         if tweakItemName not in sav_parse.ITEMS_FOR_PLAYER_INVENTORY:
            print(f"ERROR: {tweakItemName} not a valid item path name.")
            exit(1)

      modifiedFlag = False
      try:
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(levels)

         playerInventory = None
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            if characterPlayerMatch(characterPlayer, playerId):
               playerInventory = inventoryPath

         if playerInventory == None:
            print(f"Unable to match player '{playerId}'")
            exit(1)

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
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
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
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
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName.startswith("Persistent_Level:PersistentLevel.BP_GameState_C_"):
                  playerGlobalColorPresets = sav_parse.getPropertyValue(object.properties, "mPlayerGlobalColorPresets")
                  if playerGlobalColorPresets != None:
                     for color in playerGlobalColorPresets:
                        presetName = sav_parse.getPropertyValue(color[0], "PresetName")
                        if presetName != None:
                           presetName = presetName[3]
                           colorValue = sav_parse.getPropertyValue(color[0], "Color")
                           if colorValue != None:
                              if colorPrimary == presetName:
                                 colorPrimary = lcTupleToSrgbHex(colorValue)
                                 print(f"Using primary color {colorPrimary}")
                              if colorSecondary == presetName:
                                 colorSecondary = lcTupleToSrgbHex(colorValue)
                                 print(f"Using secondary color {colorSecondary}")

         colorPrimary = colorPrimary.lower()
         colorSecondary = colorSecondary.lower()

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.LightweightBuildableSubsystem":
                  for (buildItemPathName, lightweightBuildableInstances) in object.actorSpecificInfo:
                     for (rotationQuaternion, position, swatchPathName, patternDescNumber, (primaryColor, secondaryColor), somethingData, maybeIndex, recipePathName, blueprintProxyLevelPath) in lightweightBuildableInstances:
                        if lcTupleToSrgbHex(primaryColor) == colorPrimary and lcTupleToSrgbHex(secondaryColor) == colorSecondary:
                           euler = quaternionToEuler(rotationQuaternion)
                           oldYaw = euler[2]
                           euler[2] += math.pi/180
                           if euler[2] > math.pi:
                              math.pi -= 2 * math.pi
                           elif euler[2] < -math.pi:
                              math.pi += 2 * math.pi
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
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
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
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.MapManager":
                  fogOfWarRawData = sav_parse.getPropertyValue(object.properties, "mFogOfWarRawData")
                  if fogOfWarRawData != None and len(fogOfWarRawData) == 1048576:
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
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) == 5 and sys.argv[1] == "--export-hotbar" and os.path.isfile(sys.argv[3]):
      playerId = sys.argv[2]
      savFilename = sys.argv[3]
      outFilename = sys.argv[4]
      try:
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(levels)

         playerState = None
         playerCharacter = None
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            if characterPlayerMatch(characterPlayer, playerId):
               playerState = playerStateInstanceName
               playerCharacter = characterPlayer

         if playerState == None:
            print(f"Unable to match player '{playerId}'", file=sys.stderr)
            exit(1)

         playerName = getPlayerName(levels, playerCharacter)

         print()
         if playerName == None:
            print(f"===== {playerId} =====")
         else:
            print(f"===== {playerName} ({playerId}) =====")
         print()

         playersHotbars = {}
         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName == playerState:
                  playerHotbars = sav_parse.getPropertyValue(object.properties, "mPlayerHotbars")
                  if playerHotbars != None:
                     for hotbarIdx in range(len(playerHotbars)):
                        playersHotbars[playerHotbars[hotbarIdx].pathName] = hotbarIdx

         playersHotbarItems = {}
         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName in playersHotbars:
                  shortcuts = sav_parse.getPropertyValue(object.properties, "mShortcuts")
                  if shortcuts != None:
                     for hotbarItemIdx in range(len(shortcuts)):
                        hotbarIdx = playersHotbars[object.instanceName]
                        item = shortcuts[hotbarItemIdx].pathName
                        if len(item) > 0:
                           #print(f"[{hotbarIdx}][{hotbarItemIdx}] {item}")
                           playersHotbarItems[item] = (hotbarIdx, hotbarItemIdx)

         hotbarContents = {}
         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName in playersHotbarItems:
                  (hotbarIdx, hotbarItemIdx) = playersHotbarItems[object.instanceName]
                  hotbarItem = None
                  recipeToActivate = sav_parse.getPropertyValue(object.properties, "mRecipeToActivate")
                  if recipeToActivate != None:
                     hotbarItem = recipeToActivate.pathName
                     print(f"[{hotbarIdx}][{hotbarItemIdx}] Recipe: {hotbarItem}")
                  else:
                     emoteToActivate = sav_parse.getPropertyValue(object.properties, "mEmoteToActivate")
                     if emoteToActivate != None:
                        hotbarItem = emoteToActivate.pathName
                        print(f"[{hotbarIdx}][{hotbarItemIdx}] Emote: {hotbarItem}")
                     else:
                        blueprintName = sav_parse.getPropertyValue(object.properties, "mBlueprintName")
                        if blueprintName != None:
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
         hotbarContents = json.load(fin)

      modifiedFlag = False
      try:
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(levels)

         playerState = None
         playerCharacter = None
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            if characterPlayerMatch(characterPlayer, playerId):
               playerState = playerStateInstanceName
               playerCharacter = characterPlayer

         if playerState == None:
            print(f"Unable to match player '{playerId}'", file=sys.stderr)
            exit(1)

         playerName = getPlayerName(levels, playerCharacter)

         print()
         if playerName == None:
            print(f"===== {playerId} =====")
         else:
            print(f"===== {playerName} ({playerId}) =====")
         print()

         playersHotbars = {}
         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName == playerState:
                  playerHotbars = sav_parse.getPropertyValue(object.properties, "mPlayerHotbars")
                  if playerHotbars != None:
                     for hotbarIdx in range(len(playerHotbars)):
                        playersHotbars[playerHotbars[hotbarIdx].pathName] = hotbarIdx

         objectsToRemove = []
         objectsToAdd = []
         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName in playersHotbars:
                  shortcuts = sav_parse.getPropertyValue(object.properties, "mShortcuts")
                  if shortcuts != None:
                     for hotbarItemIdx in range(len(shortcuts)):
                        hotbarIdx = playersHotbars[object.instanceName]

                        replacementHotbarItem = None
                        replacementHotbarItemNewClassName = None
                        replacementHotbarItemNewParentName = None
                        replacementHotbarItemNewInstanceName = None
                        hotbarIdxStr = str(hotbarIdx)
                        if hotbarIdxStr in hotbarContents:
                           hotbarItemIdxStr = str(hotbarItemIdx)
                           if hotbarItemIdxStr in hotbarContents[hotbarIdxStr]:
                              replacementHotbarItem = hotbarContents[hotbarIdxStr][hotbarItemIdxStr]

                              if replacementHotbarItem.startswith("/Game/FactoryGame/Recipes/"):
                                 replacementHotbarItemNewClassName = "FGRecipeShortcut"
                              elif replacementHotbarItem.startswith("/Game/FactoryGame/Emotes/"):
                                 replacementHotbarItemNewClassName = "FGEmoteShortcut"
                              else: # Blueprint
                                 replacementHotbarItemNewClassName = "FGBlueprintShortcut"

                              replacementHotbarItemNewParentName = object.instanceName
                              replacementHotbarItemNewInstanceName = f"{replacementHotbarItemNewParentName}.{replacementHotbarItemNewClassName}_{uuid.uuid4().hex}"

                        item = shortcuts[hotbarItemIdx].pathName
                        if len(item) == 0:
                           if replacementHotbarItem == None:
                              print(f"[{hotbarIdx}][{hotbarItemIdx}] is currently empty and should remain empty") # No change
                           else:
                              print(f"[{hotbarIdx}][{hotbarItemIdx}] is currently empty and should be replaced with {replacementHotbarItem}") # Need to add an Object
                              objectsToAdd.append((hotbarItemIdx, replacementHotbarItemNewInstanceName, replacementHotbarItemNewClassName, replacementHotbarItemNewParentName, replacementHotbarItem))
                              shortcuts[hotbarItemIdx].levelName = "Persistent_Level"
                              shortcuts[hotbarItemIdx].pathName = replacementHotbarItemNewInstanceName
                              modifiedFlag = True
                        else:
                           if replacementHotbarItem == None:
                              print(f"[{hotbarIdx}][{hotbarItemIdx}] currently contains {item} and should be removed.") # Set this reference to empty, and remove the Object
                              objectsToRemove.append(item)
                              shortcuts[hotbarItemIdx].levelName = ""
                              shortcuts[hotbarItemIdx].pathName = ""
                              modifiedFlag = True
                           else:
                              hotbarItem = None
                              (levelNameXX, actorAndComponentObjectHeadersXX, collectables1XX, objectsXX, collectables2XX) = levels[-1]
                              for objectXX in objectsXX:
                                 if objectXX.instanceName == item:
                                    recipeToActivate = sav_parse.getPropertyValue(objectXX.properties, "mRecipeToActivate")
                                    if recipeToActivate != None:
                                       hotbarItem = recipeToActivate.pathName
                                    else:
                                       emoteToActivate = sav_parse.getPropertyValue(objectXX.properties, "mEmoteToActivate")
                                       if emoteToActivate != None:
                                          hotbarItem = emoteToActivate.pathName
                                       else:
                                          blueprintName = sav_parse.getPropertyValue(objectXX.properties, "mBlueprintName")
                                          if blueprintName != None:
                                             hotbarItem = blueprintName

                              if hotbarItem == replacementHotbarItem:
                                 print(f"[{hotbarIdx}][{hotbarItemIdx}] currently contains {item} representing {hotbarItem} which already matches {replacementHotbarItem}") # No change
                              else:
                                 print(f"[{hotbarIdx}][{hotbarItemIdx}] currently contains {item} representing {hotbarItem} should be replaced with {replacementHotbarItem}") # Delete/Add
                                 objectsToRemove.append(item)
                                 objectsToAdd.append((hotbarItemIdx, replacementHotbarItemNewInstanceName, replacementHotbarItemNewClassName, replacementHotbarItemNewParentName, replacementHotbarItem))
                                 shortcuts[hotbarItemIdx].pathName = replacementHotbarItemNewInstanceName
                                 modifiedFlag = True

         (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) = levels[-1]
         for actorOrComponentObjectHeader in actorAndComponentObjectHeaders:
            if isinstance(actorOrComponentObjectHeader, sav_parse.ComponentHeader) and actorOrComponentObjectHeader.instanceName in objectsToRemove:
               actorAndComponentObjectHeaders.remove(actorOrComponentObjectHeader)
               print(f"Removed object {actorOrComponentObjectHeader.instanceName}")
         for object in objects:
            if object.instanceName in objectsToRemove:
               objects.remove(object)
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
            newComponentHeader.parentActorName = replacementHotbarItemNewParentName
            actorAndComponentObjectHeaders.append(newComponentHeader)
            #print(f"Created new component header {newComponentHeader.instanceName}")

            #<Object: instanceName=Persistent_Level:PersistentLevel.BP_PlayerState_C_2147448362.FGPlayerHotbar_2147448361.FGRecipeShortcut_2147448341, objectGameVersion=46, flag=0, actorReferenceAssociations=n/a, properties=[[('mRecipeToActivate', <ObjectReference: levelName=, pathName=/Game/FactoryGame/Recipes/Buildings/Recipe_Workshop.Recipe_Workshop_C>), ('mShortcutIndex', 5)]], actorSpecificInfo=[None]>
            #<Object: instanceName=Persistent_Level:PersistentLevel.BP_PlayerState_C_2147195792.FGPlayerHotbar_2147195782.FGEmoteShortcut_2147195772, objectGameVersion=46, flag=0, actorReferenceAssociations=n/a, properties=[[('mEmoteToActivate', <ObjectReference: levelName=, pathName=/Game/FactoryGame/Emotes/Emote_Heart.Emote_Heart_C>)]], actorSpecificInfo=[None]>
            #<Object: instanceName=Persistent_Level:PersistentLevel.BP_PlayerState_C_2147448362.FGPlayerHotbar_2147448352.FGBlueprintShortcut_2147448316, objectGameVersion=46, flag=0, actorReferenceAssociations=n/a, properties=[[('mBlueprintName', 'Conveyor Poles 05 Hypertube Half'), ('mShortcutIndex', 1)]], actorSpecificInfo=[None]>
            newObject = sav_parse.Object()
            newObject.instanceName = replacementHotbarItemNewInstanceName
            newObject.objectGameVersion = 46
            newObject.shouldMigrateObjectRefsToPersistentFlag = False
            newObject.actorReferenceAssociations = None

            if replacementHotbarItemNewClassName == "FGRecipeShortcut":
               newRecipeObjectReference = sav_parse.ObjectReference()
               newRecipeObjectReference.levelName = ""
               newRecipeObjectReference.pathName = replacementHotbarItem
               newObject.properties    = [("mRecipeToActivate", newRecipeObjectReference), ("mShortcutIndex", hotbarItemIdx)]
               newObject.propertyTypes = [("mRecipeToActivate", "ObjectProperty", 0),      ("mShortcutIndex", "IntProperty", 0)]
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
            objects.append(newObject)
            print(f"Created new object {newObject.instanceName} containing {replacementHotbarItem}")

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("No hotbar changes needed.")
         exit(2)

      try:
         if changeTimeFlag:
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
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
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.unlockSubsystem":
                  for idx in range(len(object.properties)):
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
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
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
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)
         for targetPathName in sav_data_somersloop.SOMERSLOOPS:
            if addSomersloop(levels, targetPathName):
               modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: All Somersloops already present.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
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
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)
         for targetPathName in sav_data_mercerSphere.MERCER_SPHERES:
            if addMercerSphere(levels, targetPathName):
               modifiedFlag = True
         for targetPathName in sav_data_mercerSphere.MERCER_SHRINES:
            if addMercerShrine(levels, targetPathName):
               modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: All Mercer Spheres already present.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (4, 5) and sys.argv[1] == "--export-somersloops" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      outFilename = sys.argv[3]

      try:
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)

         # Assume True because that's accurate if the Object exists or the it's not in the save at all.
         jdata = {"Somersloops": {}}
         for pathName in sav_data_somersloop.SOMERSLOOPS:
            jdata["Somersloops"][pathName] = True

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            # Checking collectables2 because the object can be in collectables2 when collectables1 is None
            for collectable in collectables2:
               if collectable.pathName in sav_data_somersloop.SOMERSLOOPS:
                  jdata["Somersloops"][collectable.pathName] = False

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      print(f"Writing {outFilename}")
      with open(outFilename, "w") as fout:
         json.dump(jdata, fout, indent=2)

   elif len(sys.argv) in (4, 5) and sys.argv[1] == "--export-mercer-spheres" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      outFilename = sys.argv[3]

      try:
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)

         # Assume True because that's accurate if the Object exists or the it's not in the save at all.
         jdata = {"MercerSpheres": {}, "MercerShrines": {}}
         for pathName in sav_data_mercerSphere.MERCER_SPHERES:
            jdata["MercerSpheres"][pathName] = True
         for pathName in sav_data_mercerSphere.MERCER_SHRINES:
            jdata["MercerShrines"][pathName] = True

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            # Checking collectables2 because the object can be in collectables2 when collectables1 is None
            for collectable in collectables2:
               if collectable.pathName in sav_data_mercerSphere.MERCER_SPHERES:
                  jdata["MercerSpheres"][collectable.pathName] = False
               elif collectable.pathName in sav_data_mercerSphere.MERCER_SHRINES:
                  jdata["MercerShrines"][collectable.pathName] = False

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      print(f"Writing {outFilename}")
      with open(outFilename, "w") as fout:
         json.dump(jdata, fout, indent=2)

   elif len(sys.argv) in (4, 5) and sys.argv[1] == "--import-somersloops" and os.path.isfile(sys.argv[2]) and os.path.isfile(sys.argv[3]):
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
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)

         if "Somersloops" in jdata:
            for pathName in jdata["Somersloops"]:
               if jdata["Somersloops"][pathName]:
                  if addSomersloop(levels, pathName):
                     modifiedFlag = True
               else:
                  if removeSomersloop(levels, pathName):
                     modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: All Somersloops already match json.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) in (4, 5) and sys.argv[1] == "--import-mercer-spheres" and os.path.isfile(sys.argv[2]) and os.path.isfile(sys.argv[3]):
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
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)

         if "MercerSpheres" in jdata:
            for pathName in jdata["MercerSpheres"]:
               if jdata["MercerSpheres"][pathName]:
                  if addMercerSphere(levels, pathName):
                     modifiedFlag = True
               else:
                  if removeMercerSphere(levels, pathName):
                     modifiedFlag = True

         if "MercerShrines" in jdata:
            for pathName in jdata["MercerShrines"]:
               if jdata["MercerShrines"][pathName]:
                  if addMercerShrine(levels, pathName):
                     modifiedFlag = True
               else:
                  if removeMercerShrine(levels, pathName):
                     modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: All Mercer Spheres already match json.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
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
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)

         (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) = levels[-1]

         for object1 in objects:
            if object1.instanceName == "Persistent_Level:PersistentLevel.VehicleSubsystem":
               savedPaths = sav_parse.getPropertyValue(object1.properties, "mSavedPaths")
               if savedPaths != None:
                  for savedPath in savedPaths:

                     foundPathNameFlag = False
                     for object2 in objects:
                        if object2.instanceName == savedPath.pathName:
                           foundPathNameFlag = True
                           pathName = sav_parse.getPropertyValue(object2.properties, "mPathName")
                           if pathName == None:
                              print("CAUTION: Missing mPathName property for save path {savedPath.pathName}")
                           else:
                              targetList = sav_parse.getPropertyValue(object2.properties, "mTargetList")
                              if targetList == None:
                                 print(f"CAUTION: Missing mTargetList property for save path '{pathName}' ({savedPath.pathName})")
                              else:

                                 foundTargetListFlag = False
                                 for object3 in objects:
                                    if object3.instanceName == targetList.pathName:
                                       foundTargetListFlag = True
                                       first = sav_parse.getPropertyValue(object3.properties, "mFirst")
                                       if first == None:
                                          print(f"CAUTION: Missing mFirst property for target list {targetList.pathName} for save path '{pathName}' ({savedPath.pathName})")
                                       else:
                                          last = sav_parse.getPropertyValue(object3.properties, "mLast")
                                          if last == None:
                                             print(f"CAUTION: Missing mLast property for target list {targetList.pathName} for save path '{pathName}' ({savedPath.pathName})")
                                          else:
                                             vehicleType = sav_parse.getPropertyValue(object3.properties, "mVehicleType")
                                             if vehicleType == None:
                                                print(f"CAUTION: Missing mVehicleType property for target list {targetList.pathName} for save path '{pathName}' ({savedPath.pathName})")
                                             else:
                                                pathFuelConsumption = sav_parse.getPropertyValue(object3.properties, "mPathFuelConsumption")
                                                if pathFuelConsumption == None:
                                                   print(f"CAUTION: Missing mPathFuelConsumption property for target list {targetList.pathName} for save path '{pathName}' ({savedPath.pathName})")
                                                else:
                                                   targetListNextWaypoint = first.pathName
                                                   targetListLastWaypoint = last.pathName

                                                   waypointCount = 0
                                                   for object4 in objects:
                                                      if targetListNextWaypoint != None and object4.instanceName == targetListNextWaypoint:
                                                         waypointCount += 1
                                                         next = sav_parse.getPropertyValue(object4.properties, "mNext")
                                                         if next != None:
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
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)
         (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) = levels[-1]

         savedPathList = []
         for object in objects:
            if object.instanceName == "Persistent_Level:PersistentLevel.VehicleSubsystem":
               savedPaths = sav_parse.getPropertyValue(object.properties, "mSavedPaths")
               if savedPaths != None:
                  for savedPath in savedPaths:
                     savedPathList.append(savedPath.pathName)

         jdata = {}
         targetListPathName = None
         for object in objects:
            if object.instanceName in savedPathList:
               pathName = sav_parse.getPropertyValue(object.properties, "mPathName")
               if pathName != None and pathName == savedPathName:
                  jdata["mPathName"] = pathName
                  targetList = sav_parse.getPropertyValue(object.properties, "mTargetList")
                  if targetList == None:
                     print(f"ERROR: Saved path {object.instanceName} is missing a mTargetList property")
                     exit(1)
                  targetListPathName = targetList.pathName
         if targetListPathName == None:
            print(f"ERROR: Failed to find a saved path with name '{savedPathName}'.")
            exit(1)

         targetListNextWaypoint = None
         targetListLastWaypoint = None
         for object in objects:
            if object.instanceName == targetListPathName:
               first = sav_parse.getPropertyValue(object.properties, "mFirst")
               if first == None:
                  print(f"ERROR: Target list {object.instanceName} is missing a mFirst property.")
                  exit(1)
               last = sav_parse.getPropertyValue(object.properties, "mLast")
               if last == None:
                  print(f"ERROR: Target list {object.instanceName} is missing a mLast property.")
                  exit(1)
               vehicleType = sav_parse.getPropertyValue(object.properties, "mVehicleType")
               if vehicleType == None:
                  print(f"ERROR: Target list {object.instanceName} is missing a mVehicleType property.")
                  exit(1)
               pathFuelConsumption = sav_parse.getPropertyValue(object.properties, "mPathFuelConsumption")
               if pathFuelConsumption == None:
                  print(f"ERROR: Target list {object.instanceName} is missing a mPathFuelConsumption property.")
                  exit(1)
               targetListNextWaypoint = first.pathName
               targetListLastWaypoint = last.pathName
               jdata["mVehicleType"] = vehicleType.pathName
               jdata["mPathFuelConsumption"] = pathFuelConsumption

         if targetListNextWaypoint == None:
            print(f"ERROR: Failed to find target list {targetListPathName}")
            exit(1)

         targetListWaypoints = []
         for object in objects:
            if targetListNextWaypoint != None and object.instanceName == targetListNextWaypoint:
               # The final element has no mNext or mWaitTime, just mTargetSpeed=0.
               # So no details are being preserved for the final waypoint.
               next = sav_parse.getPropertyValue(object.properties, "mNext")
               targetSpeed = sav_parse.getPropertyValue(object.properties, "mTargetSpeed")
               waitTime = sav_parse.getPropertyValue(object.properties, "mWaitTime") # Only the first element seems to have mWaitTime
               targetListWaypoints.append((object.instanceName, targetSpeed, waitTime))
               if next != None:
                  targetListNextWaypoint = next.pathName
               elif object.instanceName != targetListLastWaypoint:
                  print("ERROR: Failed to follow the full vehicle path.", file=sys.stderr)
                  exit(1)

         targetList = jdata["mTargetList"] = []
         for (waypointPathName, targetSpeed, waitTime) in targetListWaypoints:
            for actorOrComponentObjectHeader in actorAndComponentObjectHeaders:
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
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)
         (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) = levels[-1]

         newDrivingTargetList = f"Persistent_Level:PersistentLevel.FGDrivingTargetList_{uuid.uuid4().hex}"
         newSavedWheeledVehiclePath = f"Persistent_Level:PersistentLevel.FGSavedWheeledVehiclePath_{uuid.uuid4().hex}"
         newVehicleTargetPoints = []
         for _ in range(len(jdata["mTargetList"])):
            newVehicleTargetPoints.append(f"Persistent_Level:PersistentLevel.BP_VehicleTargetPoint_C_{uuid.uuid4().hex}")

         for object in objects:
            if object.instanceName == "Persistent_Level:PersistentLevel.VehicleSubsystem":
               savedPaths = sav_parse.getPropertyValue(object.properties, "mSavedPaths")
               if savedPaths != None:
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
         actorHeader.needTransform = False
         actorHeader.rotation = [0.0, 0.0, 0.0, 1.0]
         actorHeader.position = [0.0, 0.0, 0.0]
         actorHeader.scale = [1.0, 1.0, 1.0]
         actorHeader.wasPlacedInLevel = False
         actorAndComponentObjectHeaders.append(actorHeader)

         object = sav_parse.Object()
         object.instanceName = newDrivingTargetList
         object.objectGameVersion = 46
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
         objects.append(object)

         for idx in range(len(newVehicleTargetPoints)):
            actorHeader = sav_parse.ActorHeader()
            actorHeader.typePath = "/Game/FactoryGame/Buildable/Vehicle/BP_VehicleTargetPoint.BP_VehicleTargetPoint_C"
            actorHeader.rootObject = "Persistent_Level"
            actorHeader.instanceName = newVehicleTargetPoints[idx]
            actorHeader.needTransform = False
            actorHeader.rotation = jdata["mTargetList"][idx][1]
            actorHeader.position = jdata["mTargetList"][idx][0]
            actorHeader.scale = [1.0, 1.0, 1.0]
            actorHeader.wasPlacedInLevel = False
            actorAndComponentObjectHeaders.append(actorHeader)

            object = sav_parse.Object()
            object.instanceName = newVehicleTargetPoints[idx]
            object.objectGameVersion = 46
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
            if jdata["mTargetList"][idx][3] != None:
               object.properties.append(["mWaitTime", jdata["mTargetList"][idx][3]])
               object.propertyTypes.append(["mWaitTime", "FloatProperty", 0])
            object.properties.append(["mTargetSpeed", jdata["mTargetList"][idx][2]])
            object.propertyTypes.append(["mTargetSpeed", "IntProperty", 0])
            object.actorSpecificInfo = None
            objects.append(object)

         actorHeader = sav_parse.ActorHeader()
         actorHeader.typePath = "/Script/FactoryGame.FGSavedWheeledVehiclePath"
         actorHeader.rootObject = "Persistent_Level"
         actorHeader.instanceName = newSavedWheeledVehiclePath
         actorHeader.needTransform = False
         actorHeader.rotation = [0.0, 0.0, 0.0, 1.0]
         actorHeader.position = [0.0, 0.0, 0.0]
         actorHeader.scale = [1.0, 1.0, 1.0]
         actorHeader.wasPlacedInLevel = False
         actorAndComponentObjectHeaders.append(actorHeader)

         object = sav_parse.Object()
         object.instanceName = newSavedWheeledVehiclePath
         object.objectGameVersion = 46
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
         objects.append(object)

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: Failed to find VehicleSubsystem to modify.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) == 4 and sys.argv[1] == "--blueprint" and sys.argv[2] == "--show" and os.path.isfile(sys.argv[3]):
      savFilename = sys.argv[3]

      try:
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords != None:
                     for category in blueprintCategoryRecords:
                        categoryName = sav_parse.getPropertyValue(category[0], "CategoryName")
                        if categoryName != None:

                           iconID = sav_parse.getPropertyValue(category[0], "IconID")
                           if iconID == None:
                              iconID = -1

                           menuPriority = sav_parse.getPropertyValue(category[0], "MenuPriority")
                           if menuPriority == None:
                              menuPriority = 0.0

                           isUndefined = sav_parse.getPropertyValue(category[0], "IsUndefined")
                           if isUndefined == None:
                              isUndefined = False

                           subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
                           if subCategoryRecords != None:
                              print(f"=== Category: {categoryName} === idx={menuPriority}, icon={iconID}, undefined={isUndefined}")
                              for subcategory in subCategoryRecords:
                                 subCategoryName = sav_parse.getPropertyValue(subcategory[0], "SubCategoryName")
                                 if subCategoryName != None:

                                    subMenuPriority = sav_parse.getPropertyValue(subcategory[0], "MenuPriority")
                                    if subMenuPriority == None:
                                       subMenuPriority = 0.0

                                    subIsUndefined = sav_parse.getPropertyValue(subcategory[0], "IsUndefined")
                                    if subIsUndefined == None:
                                       subIsUndefined = False

                                    blueprintNames = sav_parse.getPropertyValue(subcategory[0], "BlueprintNames")
                                    if blueprintNames != None:
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
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords != None:
                     for category in blueprintCategoryRecords:
                        categoryName = sav_parse.getPropertyValue(category[0], "CategoryName")
                        if categoryName != None:
                           subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
                           if subCategoryRecords != None:
                              for subcategory in subCategoryRecords:
                                 subCategoryName = sav_parse.getPropertyValue(subcategory[0], "SubCategoryName")
                                 if subCategoryName != None:
                                    blueprintNames = sav_parse.getPropertyValue(subcategory[0], "BlueprintNames")
                                    if blueprintNames != None:
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
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) == 5 and sys.argv[1] == "--blueprint" and sys.argv[2] == "--export" and os.path.isfile(sys.argv[3]):
      savFilename = sys.argv[3]
      outFilename = sys.argv[4]

      try:
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)

         categoryStructure = {}

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords != None:
                     for category in blueprintCategoryRecords:
                        categoryName = sav_parse.getPropertyValue(category[0], "CategoryName")
                        if categoryName != None:
                           iconID = sav_parse.getPropertyValue(category[0], "IconID")
                           if iconID == None:
                              iconID = -1
                           subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
                           subcategoryStructure = {}
                           if subCategoryRecords != None:
                              for subcategory in subCategoryRecords:
                                 subCategoryName = sav_parse.getPropertyValue(subcategory[0], "SubCategoryName")
                                 if subCategoryName != None:
                                    blueprintNames = sav_parse.getPropertyValue(subcategory[0], "BlueprintNames")
                                    if blueprintNames != None:
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
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords != None:

                     existingCategories = []
                     for category in blueprintCategoryRecords:
                        categoryName = sav_parse.getPropertyValue(category[0], "CategoryName")
                        if categoryName != None:
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
                        if categoryName != None and categoryName in categoryStructure:
                           subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
                           if subCategoryRecords != None:
                              subcategoryStructure = categoryStructure[categoryName]["Subcategories"]
                              for subcategory in subCategoryRecords:
                                 subCategoryName = sav_parse.getPropertyValue(subcategory[0], "SubCategoryName")
                                 if subCategoryName != None and subCategoryName in subcategoryStructure:
                                    blueprintNames = sav_parse.getPropertyValue(subcategory[0], "BlueprintNames")
                                    if blueprintNames != None:
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
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
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
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords != None:
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
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
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
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords != None:
                     for category in blueprintCategoryRecords:
                        categoryName = sav_parse.getPropertyValue(category[0], "CategoryName")
                        if categoryName != None and categoryName == categoryToAddIn:
                           subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
                           if subCategoryRecords != None:
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
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
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
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords != None:
                     for category in blueprintCategoryRecords:
                        categoryName = sav_parse.getPropertyValue(category[0], "CategoryName")
                        if categoryName != None and categoryName == categoryToAddIn:
                           subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
                           if subCategoryRecords != None:
                              print(f"=== Category: {categoryName} ===")
                              for subcategory in subCategoryRecords:
                                 subCategoryName = sav_parse.getPropertyValue(subcategory[0], "SubCategoryName")
                                 if subCategoryName != None and subCategoryName == subcategoryToAddIn:
                                    blueprintNames = sav_parse.getPropertyValue(subcategory[0], "BlueprintNames")
                                    if blueprintNames != None:
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
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
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
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords != None:
                     for category in blueprintCategoryRecords:
                        categoryName = sav_parse.getPropertyValue(category[0], "CategoryName")
                        if categoryName != None and categoryName == categoryToRemove:
                           subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
                           if subCategoryRecords != None:
                              for subcategory in subCategoryRecords:
                                 subCategoryName = sav_parse.getPropertyValue(subcategory[0], "SubCategoryName")
                                 if subCategoryName != None:
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
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
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
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords != None:
                     for category in blueprintCategoryRecords:
                        categoryName = sav_parse.getPropertyValue(category[0], "CategoryName")
                        if categoryName != None and categoryName == categoryToRemoveIn:
                           subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
                           if subCategoryRecords != None:
                              for subcategory in subCategoryRecords:
                                 subCategoryName = sav_parse.getPropertyValue(subcategory[0], "SubCategoryName")
                                 if subCategoryName != None and subCategoryName == subcategoryToRemove:
                                    blueprintNames = sav_parse.getPropertyValue(subcategory[0], "BlueprintNames")
                                    if blueprintNames != None:
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
            print(f"ERROR: Failed to find category '{categoryToRemove}', subcategory '{subcategoryToRemove}' to remove.", file=sys.stderr)
         else:
            print(f"ERROR: Subcategory '{subcategoryToRemove}' contains {numberOfBlueprints} blueprints.  Must be empty to remove.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
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
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords != None:
                     for category in blueprintCategoryRecords:
                        categoryName = sav_parse.getPropertyValue(category[0], "CategoryName")
                        if categoryName != None and categoryName == categoryToRemoveIn:
                           subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
                           if subCategoryRecords != None:
                              for subcategory in subCategoryRecords:
                                 subCategoryName = sav_parse.getPropertyValue(subcategory[0], "SubCategoryName")
                                 if subCategoryName != None and subCategoryName == subcategoryToRemoveIn:
                                    blueprintNames = sav_parse.getPropertyValue(subcategory[0], "BlueprintNames")
                                    if blueprintNames != None:
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
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
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
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords != None:
                     for category in blueprintCategoryRecords:
                        categoryName = sav_parse.getPropertyValue(category[0], "CategoryName")
                        if categoryName != None and categoryName == oldCategory:
                           subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
                           if subCategoryRecords != None:
                              for subcategory in subCategoryRecords:
                                 subCategoryName = sav_parse.getPropertyValue(subcategory[0], "SubCategoryName")
                                 if subCategoryName != None and subCategoryName == oldSubcategory:
                                    blueprintNames = sav_parse.getPropertyValue(subcategory[0], "BlueprintNames")
                                    if blueprintNames != None:
                                       if blueprintToMove in blueprintNames:
                                          blueprintNames.remove(blueprintToMove)
                                          modifiedCount += 1
                        if categoryName != None and categoryName == newCategory:
                           subCategoryRecords = sav_parse.getPropertyValue(category[0], "SubCategoryRecords")
                           if subCategoryRecords != None:
                              for subcategory in subCategoryRecords:
                                 subCategoryName = sav_parse.getPropertyValue(subcategory[0], "SubCategoryName")
                                 if subCategoryName != None and subCategoryName == newSubcategory:
                                    blueprintNames = sav_parse.getPropertyValue(subcategory[0], "BlueprintNames")
                                    if blueprintNames != None:
                                       blueprintNames.append(blueprintToMove)
                                       modifiedCount += 1

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if modifiedCount != 2:
         print("ERROR: Failed to move blueprint.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
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
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.BlueprintSubsystem":
                  blueprintCategoryRecords = sav_parse.getPropertyValue(object.properties, "mBlueprintCategoryRecords")
                  if blueprintCategoryRecords != None:
                     blueprintCategoryRecords[:] = []
                     modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: Failed to find blueprint category records to modify.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) == 4 and sys.argv[1] == "--resave-only" and os.path.isfile(sys.argv[2]):
      savFilename = sys.argv[2]
      outFilename = sys.argv[3]

      try:
         (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(savFilename)
      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      try:
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, extraObjectReferenceList, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels, extraObjectReferenceList) = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   else:
      print(f"ERROR: Did not understand {len(sys.argv)} arguments: {sys.argv}", file=sys.stderr)
      printUsage()
      exit(1)

   exit(0)
