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

   playerCharacterInstances = {}
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

def printUsage():
   print()
   print("USAGE:")
   print("   py sav_cli.py --find-free-stuff [item] [save-filename]")
   print("   py sav_cli.py --list-players <save-filename>")
   print("   py sav_cli.py --list-player-inventory <player-state-num> <save-filename>")
   print("   py sav_cli.py --export-player-inventory <player-state-num> <save-filename> <output-json-filename>")
   print("   py sav_cli.py --import-player-inventory <player-state-num> <original-save-filename> <input-json-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --tweak-player-inventory <player-state-num> <slot-index> <item> <quantity> <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --rotate-foundations <primary-color-hex-or-preset> <secondary-color-hex-or-preset> <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --clear-fog <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --export-hotbar <player-state-num> <save-filename> <output-json-filename>")
   print("   py sav_cli.py --import-hotbar <player-state-num> <original-save-filename> <input-json-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --change-num-inventory-slots <num-inventory-slots> <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --restore-somersloops <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --restore-mercer-spheres <original-save-filename> <new-save-filename> [--same-time]")
   print("   py sav_cli.py --remember-username <player-state-num> <username-alias>")
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

   if len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
      printUsage()

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
                  (saveFileInfo, headhex, grids, levels) = sav_parse.readFullSaveFile(savFilename)
                  for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
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
         (saveFileInfo, headhex, grids, levels) = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(levels)
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            playerName = getPlayerName(levels, characterPlayer)
            if playerName == None:
               print(playerStateInstanceName)
            else:
               print(f"{playerStateInstanceName} ({playerName})")
      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

   elif len(sys.argv) == 4 and sys.argv[1] == "--list-player-inventory" and os.path.isfile(sys.argv[3]):
      playerId = sys.argv[2]
      savFilename = sys.argv[3]
      try:
         (saveFileInfo, headhex, grids, levels) = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(levels)

         playerInventory = None
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            if playerId in playerStateInstanceName:
               playerInventory = inventoryPath

         if playerInventory == None:
            print("Unable to match player '{playerId}'", file=sys.stderr)
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
                              if extraInformation != None:
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
         (saveFileInfo, headhex, grids, levels) = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(levels)

         playerInventory = None
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            if playerId in playerStateInstanceName:
               playerInventory = inventoryPath

         if playerInventory == None:
            print("Unable to match player '{playerId}'", file=sys.stderr)
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
                           elif item[0][1][1] == None:
                              inventoryContents.append((itemName, item[1][1]))
                           else:
                              inventoryContents.append((itemName, item[1][1], item[0][1][1][0], item[0][1][1][1]))

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      with open(outFilename, "w") as fout:
         json.dump(inventoryContents, fout, indent=2)

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
         (saveFileInfo, headhex, grids, levels) = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(levels)

         playerInventory = None
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            if playerId in playerStateInstanceName:
               playerInventory = inventoryPath

         if playerInventory == None:
            print("Unable to match player '{playerId}'")
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
                              inventoryStacks[idx][0][0] = ("Item", ("", None))
                              inventoryStacks[idx][0][1] = ("NumItems", 0)
                              print(f"Setting player {playerInventory}'s inventory slot {idx} to be Empty")
                           elif len(inventoryContents[idx]) == 2:
                              (itemPathName, itemQuantity) = inventoryContents[idx]
                              inventoryStacks[idx][0][0] = ("Item", (itemPathName, None))
                              inventoryStacks[idx][0][1] = ("NumItems", itemQuantity)
                              print(f"Setting player {playerInventory}'s inventory slot {idx} to include {itemQuantity} x {sav_parse.pathNameToReadableName(itemPathName)}")
                           elif len(inventoryContents[idx]) == 4:
                              (itemPathName, itemQuantity, itemPropName, itemProps) = inventoryContents[idx]
                              if itemPropName == "/Script/FactoryGame.FGJetPackItemState":
                                 inventoryStacks[idx][0][0] = ("Item", (itemPathName, (itemPropName, itemProps, [('CurrentFuel', 'FloatProperty', 0), ('CurrentFuelType', 'IntProperty', 0), ('SelectedFuelType', 'IntProperty', 0)])))
                              if itemPropName == "/Script/FactoryGame.FGChainsawItemState":
                                 inventoryStacks[idx][0][0] = ("Item", (itemPathName, (itemPropName, itemProps, [('EnergyStored', 'FloatProperty', 0)])))
                              inventoryStacks[idx][0][1] = ("NumItems", itemQuantity)
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
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels) = sav_parse.readFullSaveFile(outFilename)
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
         print(f"ERROR: {tweakItemName} not a valid item path name.")
         exit(1)

      modifiedFlag = False
      try:
         (saveFileInfo, headhex, grids, levels) = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(levels)

         playerInventory = None
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            if playerId in playerStateInstanceName:
               playerInventory = inventoryPath

         if playerInventory == None:
            print("Unable to match player '{playerId}'")
            exit(1)

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName == playerInventory:
                  inventoryStacks = sav_parse.getPropertyValue(object.properties, "mInventoryStacks")
                  if inventoryStacks:
                     for idx in range(len(inventoryStacks)):
                        if idx == tweakSlotIdx:
                           print(f"Replacing {sav_parse.toString(inventoryStacks[idx][0])}")
                           inventoryStacks[idx][0][0] = ("Item", (tweakItemName, None))
                           inventoryStacks[idx][0][1] = ("NumItems", tweakQuantity)
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
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels) = sav_parse.readFullSaveFile(outFilename)
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
         (saveFileInfo, headhex, grids, levels) = sav_parse.readFullSaveFile(savFilename)

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
                     for (rotationQuaternion, position, swatchPathName, (primaryColor, secondaryColor), recipePathName, blueprintProxyLevelPath) in lightweightBuildableInstances:
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
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels) = sav_parse.readFullSaveFile(outFilename)
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
         (saveFileInfo, headhex, grids, levels) = sav_parse.readFullSaveFile(savFilename)

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
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels) = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) == 5 and sys.argv[1] == "--export-hotbar" and os.path.isfile(sys.argv[3]):
      playerId = sys.argv[2]
      savFilename = sys.argv[3]
      outFilename = sys.argv[4]
      try:
         (saveFileInfo, headhex, grids, levels) = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(levels)

         playerState = None
         playerCharacter = None
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            if playerId in playerStateInstanceName:
               playerState = playerStateInstanceName
               playerCharacter = characterPlayer

         if playerState == None:
            print("Unable to match player '{playerId}'", file=sys.stderr)
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

      addIndex = 3000000000  # This number is arbitrary.  What would be a better choice?
      modifiedFlag = False
      try:
         (saveFileInfo, headhex, grids, levels) = sav_parse.readFullSaveFile(savFilename)
         playerPaths = getPlayerPaths(levels)

         #names = []
         #for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
         #   for actorOrComponentObjectHeader in actorAndComponentObjectHeaders:
         #      names.append(actorOrComponentObjectHeader.instanceName)
         #   for object in objects:
         #      names.append(object.instanceName)
         #for name in names:
         #   name = name[-10:]
         #   print(name)
         #exit(1)

         playerState = None
         playerCharacter = None
         for (playerStateInstanceName, characterPlayer, inventoryPath, armsPath, backPath, legsPath, headPath, bodyPath, healthPath) in playerPaths:
            if playerId in playerStateInstanceName:
               playerState = playerStateInstanceName
               playerCharacter = characterPlayer

         if playerState == None:
            print("Unable to match player '{playerId}'", file=sys.stderr)
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
                              replacementHotbarItemNewInstanceName = f"{replacementHotbarItemNewParentName}.{replacementHotbarItemNewClassName}_{addIndex}"
                              addIndex += 1

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
            newComponentHeader.validFlag = True
            actorAndComponentObjectHeaders.append(newComponentHeader)
            #print(f"Created new component header {newComponentHeader.instanceName}")

            #<Object: instanceName=Persistent_Level:PersistentLevel.BP_PlayerState_C_2147448362.FGPlayerHotbar_2147448361.FGRecipeShortcut_2147448341, objectGameVersion=46, flag=0, actorReferenceAssociations=n/a, properties=[[('mRecipeToActivate', <ObjectReference: levelName=, pathName=/Game/FactoryGame/Recipes/Buildings/Recipe_Workshop.Recipe_Workshop_C>), ('mShortcutIndex', 5)]], actorSpecificInfo=[None]>
            #<Object: instanceName=Persistent_Level:PersistentLevel.BP_PlayerState_C_2147195792.FGPlayerHotbar_2147195782.FGEmoteShortcut_2147195772, objectGameVersion=46, flag=0, actorReferenceAssociations=n/a, properties=[[('mEmoteToActivate', <ObjectReference: levelName=, pathName=/Game/FactoryGame/Emotes/Emote_Heart.Emote_Heart_C>)]], actorSpecificInfo=[None]>
            #<Object: instanceName=Persistent_Level:PersistentLevel.BP_PlayerState_C_2147448362.FGPlayerHotbar_2147448352.FGBlueprintShortcut_2147448316, objectGameVersion=46, flag=0, actorReferenceAssociations=n/a, properties=[[('mBlueprintName', 'Conveyor Poles 05 Hypertube Half'), ('mShortcutIndex', 1)]], actorSpecificInfo=[None]>
            newObject = sav_parse.Object()
            newObject.instanceName = replacementHotbarItemNewInstanceName
            newObject.objectGameVersion = 46
            newObject.flag = 0
            newObject.actorReferenceAssociations = None

            if replacementHotbarItemNewClassName == "FGRecipeShortcut":
               newRecipeObjectReference = sav_parse.ObjectReference()
               newRecipeObjectReference.levelName = ""
               newRecipeObjectReference.pathName = replacementHotbarItem
               newRecipeObjectReference.validFlag = True
               newObject.properties    = [("mRecipeToActivate", newRecipeObjectReference), ("mShortcutIndex", hotbarItemIdx)]
               newObject.propertyTypes = [("mRecipeToActivate", "ObjectProperty", 0),      ("mShortcutIndex", "IntProperty", 0)]
            elif replacementHotbarItemNewClassName == "FGEmoteShortcut":
               newRecipeObjectReference = sav_parse.ObjectReference()
               newRecipeObjectReference.levelName = ""
               newRecipeObjectReference.pathName = replacementHotbarItem
               newRecipeObjectReference.validFlag = True
               newObject.properties    = [("mEmoteToActivate", newRecipeObjectReference), ("mShortcutIndex", hotbarItemIdx)]
               newObject.propertyTypes = [("mEmoteToActivate", "ObjectProperty", 0),      ("mShortcutIndex", "IntProperty", 0)]
            elif replacementHotbarItemNewClassName == "FGBlueprintShortcut":
               newObject.properties    = [("mBlueprintName", replacementHotbarItem), ("mShortcutIndex", hotbarItemIdx)]
               newObject.propertyTypes = [("mBlueprintName", "StrProperty", 0),      ("mShortcutIndex", "IntProperty", 0)]

            newObject.actorSpecificInfo = None
            newObject.validFlag = True
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
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels) = sav_parse.readFullSaveFile(outFilename)
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
         (saveFileInfo, headhex, grids, levels) = sav_parse.readFullSaveFile(savFilename)

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for object in objects:
               if object.instanceName == "Persistent_Level:PersistentLevel.unlockSubsystem":
                  for idx in range(len(object.properties)):
                     (haystackPropertyName, propertyValue) = object.properties[idx]
                     if haystackPropertyName == "mNumTotalInventorySlots":
                        if propertyValue >= newNumInventorySlots:
                           print(f"WARNING: Decreasing inventory from {propertyValue} to {newNumInventorySlots}")
                        print(f"Changing number of inventory slots from {propertyValue} to {newNumInventorySlots}")
                        object.properties[idx] = ("mNumTotalInventorySlots", newNumInventorySlots)
                        modifiedFlag = True

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: Failed to find mFogOfWarRawData property to modify.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels) = sav_parse.readFullSaveFile(outFilename)
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
         (saveFileInfo, headhex, grids, levels) = sav_parse.readFullSaveFile(savFilename)

         # For those items present in (both) collectables1 and collectables2, remove those,
         # and replace the original ActorHeader and Object.  Nothing unique is saved in the Object.

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            for collectable in collectables1:
               if collectable.pathName in sav_data_somersloop.SOMERSLOOPS:
                  collectables1.remove(collectable)
                  print(f"Clearing removal of {collectable.pathName}")
            for collectable in collectables2:
               if collectable.pathName in sav_data_somersloop.SOMERSLOOPS:
                  collectables2.remove(collectable)

                  instanceName = collectable.pathName
                  (rootObject, rotation, position) = sav_data_somersloop.SOMERSLOOPS[collectable.pathName]

                  newActor = sav_parse.ActorHeader()
                  newActor.typePath = sav_parse.SOMERSLOOP
                  newActor.rootObject = rootObject
                  newActor.instanceName = instanceName
                  newActor.needTransform = 0
                  newActor.rotation = rotation
                  newActor.position = position
                  newActor.scale = (1.600000023841858, 1.600000023841858, 1.600000023841858)
                  newActor.wasPlacedInLevel = 1
                  newActor.validFlag = True
                  actorAndComponentObjectHeaders.append(newActor)

                  newObject = sav_parse.Object()
                  newObject.instanceName = instanceName
                  newObject.objectGameVersion = 46
                  newObject.flag = 0
                  nullParentObjectReference = sav_parse.ObjectReference()
                  nullParentObjectReference.levelName = ""
                  nullParentObjectReference.pathName = ""
                  nullParentObjectReference.validFlag = True
                  newObject.actorReferenceAssociations = (nullParentObjectReference, [])
                  newObject.properties    = []
                  newObject.propertyTypes = []
                  newObject.actorSpecificInfo = None
                  newObject.validFlag = True
                  objects.append(newObject)

                  modifiedFlag = True
                  print(f"Restored Somersloop {instanceName} at {position}")

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: All Somersloops already present.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels) = sav_parse.readFullSaveFile(outFilename)
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
         (saveFileInfo, headhex, grids, levels) = sav_parse.readFullSaveFile(savFilename)

         # For those items present in (both) collectables1 and collectables2, remove those,
         # and replace the original ActorHeader and Object.  Nothing unique is saved in the Object.

         for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
            removeCollectables = []
            for collectable in collectables1:
               if collectable.pathName in sav_data_mercerSphere.MERCER_SPHERES:
                  removeCollectables.append(collectable)
                  print(f"Clearing removal of sphere {collectable.pathName}")
               elif collectable.pathName in sav_data_mercerSphere.MERCER_SHRINES:
                  removeCollectables.append(collectable)
                  print(f"Clearing removal of shrine {collectable.pathName}")
            [collectables1.remove(x) for x in removeCollectables]

            removeCollectables = []
            for collectable in collectables2:
               if collectable.pathName in sav_data_mercerSphere.MERCER_SPHERES:
                  removeCollectables.append(collectable)

                  instanceName = collectable.pathName
                  (rootObject, rotation, position) = sav_data_mercerSphere.MERCER_SPHERES[collectable.pathName]

                  newActor = sav_parse.ActorHeader()
                  newActor.typePath = sav_parse.MERCER_SPHERE
                  newActor.rootObject = rootObject
                  newActor.instanceName = instanceName
                  newActor.needTransform = 0
                  newActor.rotation = rotation
                  newActor.position = position
                  newActor.scale = (2.700000047683716, 2.6999998092651367, 2.6999998092651367)
                  newActor.wasPlacedInLevel = 1
                  newActor.validFlag = True
                  actorAndComponentObjectHeaders.append(newActor)

                  newObject = sav_parse.Object()
                  newObject.instanceName = instanceName
                  newObject.objectGameVersion = 46
                  newObject.flag = 0
                  nullParentObjectReference = sav_parse.ObjectReference()
                  nullParentObjectReference.levelName = ""
                  nullParentObjectReference.pathName = ""
                  nullParentObjectReference.validFlag = True
                  newObject.actorReferenceAssociations = (nullParentObjectReference, [])
                  newObject.properties    = []
                  newObject.propertyTypes = []
                  newObject.actorSpecificInfo = None
                  newObject.validFlag = True
                  objects.append(newObject)

                  modifiedFlag = True
                  print(f"Restored Mercer Sphere {instanceName} at {position}")

               elif collectable.pathName in sav_data_mercerSphere.MERCER_SHRINES:
                  removeCollectables.append(collectable)

                  instanceName = collectable.pathName
                  (rootObject, rotation, position, scale) = sav_data_mercerSphere.MERCER_SHRINES[collectable.pathName]

                  newActor = sav_parse.ActorHeader()
                  newActor.typePath = sav_parse.MERCER_SHRINE
                  newActor.rootObject = rootObject
                  newActor.instanceName = instanceName
                  newActor.needTransform = 0
                  newActor.rotation = rotation
                  newActor.position = position
                  newActor.scale = (scale, scale, scale)
                  newActor.wasPlacedInLevel = 1
                  newActor.validFlag = True
                  actorAndComponentObjectHeaders.append(newActor)

                  newObject = sav_parse.Object()
                  newObject.instanceName = instanceName
                  newObject.objectGameVersion = 46
                  newObject.flag = 0
                  nullParentObjectReference = sav_parse.ObjectReference()
                  nullParentObjectReference.levelName = ""
                  nullParentObjectReference.pathName = ""
                  nullParentObjectReference.validFlag = True
                  newObject.actorReferenceAssociations = (nullParentObjectReference, [])
                  newObject.properties    = []
                  newObject.propertyTypes = []
                  newObject.actorSpecificInfo = None
                  newObject.validFlag = True
                  objects.append(newObject)

                  modifiedFlag = True
                  print(f"Restored Mercer Shrine {instanceName} at {position}")
            [collectables2.remove(x) for x in removeCollectables]

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

      if not modifiedFlag:
         print("ERROR: All Mercer Spheres already present.", file=sys.stderr)
         exit(1)

      try:
         if changeTimeFlag:
            saveFileInfo.saveDateTimeInTicks += sav_parse.TICKS_IN_SECOND
         sav_to_resave.saveFile(saveFileInfo, headhex, grids, levels, outFilename)
         if VERIFY_CREATED_SAVE_FILES:
            (saveFileInfo, headhex, grids, levels) = sav_parse.readFullSaveFile(outFilename)
            print("Validation successful")
      except Exception as error:
         raise Exception(f"ERROR: While validating resave of '{savFilename}' to '{outFilename}': {error}")

   elif len(sys.argv) == 4 and sys.argv[1] == "-remember-username":
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

   else:
      print(f"ERROR: Did not understand {len(sys.argv)} arguments: {sys.argv}", file=sys.stderr)
      printUsage()
      exit(1)

   exit(0)
