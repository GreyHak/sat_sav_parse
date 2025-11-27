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

import glob
import json
import os
import sys

import sav_parse
import sav_data.data

try:
   from PIL import Image, ImageDraw, ImageFont
   pilAvailableFlag = True
except ModuleNotFoundError:
   pilAvailableFlag = False
   print("Python Pillow (PIL) library not available.  Not generating maps.")

DEFAULT_OUTPUT_DIR = "."
DEFAULT_HTML_BASENAME = "save.html"
FONT_FILENAME = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf" # The library automatically adjusts to "C:\Windows\Fonts\DejaVuSerif.ttf" on Windows.

MAP_DESCALE = 20
MAP_BASENAME_BLANK = f"blank_map{str(MAP_DESCALE).zfill(2)}.png"
MAP_BASENAME_SLUGS          = "save_slug.png"
MAP_BASENAME_HARD_DRIVES    = "save_hd.png"
MAP_BASENAME_SOMERSLOOP     = "save_somersloop.png"
MAP_BASENAME_MERCER_SPHERE  = "save_mercer_sphere.png"
MAP_BASENAME_SOME_MERC_SPH  = "save_somersloop_and_mercer_sphere.png"
MAP_BASENAME_COLLECTABLES   = "save_all_collectables.png"
MAP_BASENAME_POWER          = "save_power.png"
MAP_BASENAME_RESOURCE_NODES = "save_nodes.png"

MAP_RESOURCE_NODE_CIRCLE_SIZE_UNUSED = 3
MAP_RESOURCE_NODE_CIRCLE_SIZE_USED = 2
MAP_COLOR_TEXT = (0,0,0)
MAP_COLOR_SLUG_BLUE = (0,0,255)
MAP_COLOR_SLUG_YELLOW = (255,255,0)
MAP_COLOR_SLUG_PURPLE = (192,0,192)
MAP_COLOR_CRASH_SITE_UNOPENED = (0,0,255)
MAP_COLOR_CRASH_SITE_OPEN_W_DRIVE = (0,255,0)
MAP_COLOR_CRASH_SITE_OPEN_EMPTY = (255,255,255)
MAP_COLOR_CRASH_SITE_DISMANTLED = (0,255,255)
MAP_COLOR_UNCOLLECTED_SOMERSLOOP = (244,56,69)
MAP_COLOR_UNCOLLECTED_MERCER_SPHERE = (78,16,113)
MAP_COLOR_POWER_LINE = (22,47,101)
MAP_COLOR_NODE_PURITY = {
   sav_data.resourcePurity.Purity.IMPURE: (210,52,48),
   sav_data.resourcePurity.Purity.NORMAL: (242,100,24),
   sav_data.resourcePurity.Purity.PURE: (128,177,57),
}
MAP_COLOR_NODE_TYPE = {
   None: (255,255,255),
   "Desc_Coal_C": (80,80,80),
   "Desc_Geyser_C": (192,192,255),
   "Desc_LiquidOil_C": (20,20,20),
   "Desc_LiquidOilWell_C": (20,20,20),
   "Desc_NitrogenGas_C": (232,229,196),
   "Desc_OreBauxite_C": (200,140,114),
   "Desc_OreCopper_C": (149,93,87),
   "Desc_OreGold_C": (210,188,150),
   "Desc_OreIron_C": (111,80,93),
   "Desc_OreUranium_C": (94,141,82),
   "Desc_RawQuartz_C": (221,154,201),
   "Desc_SAM_C": (110,46,169),
   "Desc_Stone_C": (191,178,168),
   "Desc_Sulfur_C": (205,191,102),
   "Desc_Water_C": (165,204,223),
}

MAP_FONT_SIZE = 760/MAP_DESCALE
MAP_TEXT_POSITION = (4400/MAP_DESCALE, 4300/MAP_DESCALE)
CROP_SETTINGS = (4096/MAP_DESCALE, 4096/MAP_DESCALE, 36864/MAP_DESCALE, 36864/MAP_DESCALE)
def adjPos(pos, yFlag):
   newPos = (pos / 22.887 + (18282.5,20480)[yFlag]) / MAP_DESCALE
   return newPos

def addSlugs(slugDraw, slugs, fill=None, outline=None):
   for slug in slugs:
      coord = slugs[slug]
      posX = adjPos(coord[0], False)
      posY = adjPos(coord[1], True)
      slugDraw.ellipse((posX-2, posY-2, posX+2, posY+2), fill=fill, outline=outline)

def chown(filename: str):
   try:
      if os.path.isfile(filename):
         fid = os.open(filename, os.O_RDONLY)
         os.fchown(fid, 1000, 1000)
         os.close(fid)
   except Exception as error:
      pass

CURRENT_DEPOT_STACK_LIMIT = 5
ITEM_STACK_SIZE_FILENAME = "sav_stack_sizes.json"
itemStackSizes: dict[str, int | None] = {}
VALID_STACK_SIZES = (500, 200, 100, 50) # In reducing order
def getStackSize(itemName: str, itemCount: int) -> int | None:
   global itemStackSizes
   if len(itemStackSizes) == 0 and os.path.isfile(ITEM_STACK_SIZE_FILENAME):
      with open(ITEM_STACK_SIZE_FILENAME, "r") as fin:
         itemStackSizes = json.load(fin)

   derivedStackSize = None
   if itemCount != 0:
      for validStackSize in VALID_STACK_SIZES:
         if ((itemCount / CURRENT_DEPOT_STACK_LIMIT) % validStackSize) == 0:
            derivedStackSize = validStackSize
            break

   knownStackSize = None
   if itemName in itemStackSizes:
      knownStackSize = itemStackSizes[itemName]
   else:
      itemStackSizes[itemName] = None

   if derivedStackSize is None and knownStackSize is None:
      return None

   if knownStackSize is not None:
      if derivedStackSize is None or knownStackSize > derivedStackSize:
         return knownStackSize

   itemStackSizes[itemName] = derivedStackSize
   with open(ITEM_STACK_SIZE_FILENAME, "w", newline="\n") as fout:
      json.dump(itemStackSizes, fout, indent=2)
   return derivedStackSize

def generateHTML(savFilename: str, outputDir: str = DEFAULT_OUTPUT_DIR, htmlBasename: str = DEFAULT_HTML_BASENAME):
   htmlFilename = f"{outputDir}/{htmlBasename}"
   try:
      parsedSave = sav_parse.readFullSaveFile(savFilename)
      #htmlFilename = f"save_{parsedSave.saveFileInfo.sessionName}_{parsedSave.saveFileInfo.saveDatetime.strftime('%Y%m%d-%H%M%S')}.html"

      uncollectedPowerSlugsBlue = sav_data.slug.POWER_SLUGS_BLUE.copy()
      uncollectedPowerSlugsYellow = sav_data.slug.POWER_SLUGS_YELLOW.copy()
      uncollectedPowerSlugsPurple = sav_data.slug.POWER_SLUGS_PURPLE.copy()
      uncollectedSomersloops = sav_data.somersloop.SOMERSLOOPS.copy()
      uncollectedMercerSpheres = sav_data.mercerSphere.MERCER_SPHERES.copy()

      activeSchematic = None
      activeSchematicShortName = None
      activeSchematicDescription = None
      numBuildables = 0
      buildablesMap: dict[str, int] = {}
      minerInstances = []
      minerTypesInstanceAndPositions = []
      minedResourceActors = {}
      numCollectedSlugsMk1 = 0
      numCollectedSlugsMk2 = 0
      numCollectedSlugsMk3 = 0
      crashSiteInstances = {}
      crashSitesDismantled = []
      numCreaturesKilled = 0
      creaturesKilled = []
      gamePhase = "Default"
      pointProgressLines = ""
      unlockCount_hardDrives = 0
      unlockCount_awesomeShop = 0
      unlockRemaining_awesomeShop = list(sav_data.data.UNLOCK_PATHS__AWESOME_SHOP)
      unlockCount_mam = 0
      unlockRemaining_mam = list(sav_data.data.UNLOCK_PATHS__MAM)
      unlockCount_hubTiers = 0
      unlockCount_special = 0
      dimensionalDepotContents = []
      powerLines = {}
      wireLines = []
      for level in parsedSave.levels:
         for actorOrComponentObjectHeader in level.actorAndComponentObjectHeaders:
            if isinstance(actorOrComponentObjectHeader, sav_parse.ActorHeader):
               typePath = actorOrComponentObjectHeader.typePath
               if "/Buildable/" in typePath or "/Build_" in typePath: # "/Buildable/" ensures vehicles are included.  "/Build_" ensures FICSMAS buildables are included.
                  numBuildables += 1
                  if typePath in buildablesMap:
                     buildablesMap[typePath] += 1
                  else:
                     buildablesMap[typePath] = 1
                  if typePath in sav_data.data.MINERS:
                     minerInstances.append(actorOrComponentObjectHeader.instanceName)
                     minerTypesInstanceAndPositions.append((typePath, actorOrComponentObjectHeader.instanceName, actorOrComponentObjectHeader.position))
               if typePath in sav_data.data.MINED_RESOURCES:
                  resourceType = None
                  purity = None
                  if actorOrComponentObjectHeader.instanceName in sav_data.resourcePurity.RESOURCE_PURITY: # Won't be found for BP_FrackingCore_C
                     (resourceType, purity) = sav_data.resourcePurity.RESOURCE_PURITY[actorOrComponentObjectHeader.instanceName]
                  minedResourceActors[actorOrComponentObjectHeader.instanceName] = (actorOrComponentObjectHeader.position, resourceType, purity)
               elif typePath == sav_data.data.CRASH_SITE:
                  crashSiteInstances[actorOrComponentObjectHeader.instanceName] = actorOrComponentObjectHeader.position
               elif typePath == sav_data.data.POWER_LINE:
                  powerLines[actorOrComponentObjectHeader.instanceName] = actorOrComponentObjectHeader.position
         for object in level.objects:
            if object.instanceName == "Persistent_Level:PersistentLevel.StatisticsSubsystem":
               creaturesKilledCount = sav_parse.getPropertyValue(object.properties, "mCreaturesKilledCount")
               if creaturesKilledCount is not None:
                  for creature in creaturesKilledCount:
                     (levelPathName, killCount) = creature
                     creaturesKilled.append((levelPathName.pathName, killCount))
                     numCreaturesKilled += killCount
            elif object.instanceName == "Persistent_Level:PersistentLevel.GamePhaseManager":
               currentGamePhase = sav_parse.getPropertyValue(object.properties, "mCurrentGamePhase")
               if currentGamePhase is not None:
                  if currentGamePhase.pathName == sav_data.data.FINAL_PROJECT_ASSEMBLY_PHASE_7: # mTargetGamePhase will be phase 1
                     gamePhase = "<b>Project Assembly Completed.</b>"
                  else:
                     gamePhase = f"<b>{sav_parse.pathNameToReadableName(currentGamePhase.pathName)}</b>"
                     targetGamePhase = sav_parse.getPropertyValue(object.properties, "mTargetGamePhase")
                     if targetGamePhase is not None:
                        targetGamePhase = targetGamePhase.pathName
                        if targetGamePhase == sav_data.data.FINAL_PROJECT_ASSEMBLY_PHASE_6:
                           gamePhase = "<b>Project Assembly Complete[ing]</b>"
                        else:
                           gamePhase += f" toward <b>{sav_parse.pathNameToReadableName(targetGamePhase)}</b>"
                           targetGamePhasePaidOffCosts = sav_parse.getPropertyValue(object.properties, "mTargetGamePhasePaidOffCosts")
                           if targetGamePhasePaidOffCosts is not None:
                              gamePhase = f'{gamePhase}. Already supplied:\n<ul style="margin-top:0px">\n'
                              cost = targetGamePhasePaidOffCosts
                              alreadySupplied = {}
                              for costItem in cost:
                                 itemCostClass = sav_parse.getPropertyValue(costItem[0], "ItemClass")
                                 if itemCostClass is not None:
                                    amountSupplied = sav_parse.getPropertyValue(costItem[0], "Amount")
                                    if amountSupplied is not None:
                                       itemName = itemCostClass.pathName
                                       itemName = sav_parse.pathNameToReadableName(itemName)
                                       alreadySupplied[itemName] = amountSupplied
                              if targetGamePhase not in sav_data.data.PROJECT_ASSEMBLY_COSTS:
                                 gamePhase = f"{gamePhase}<li>ERROR: {targetGamePhase} not in PROJECT_ASSEMBLY_COSTS</li>\n"
                              else:
                                 for itemName in sav_data.data.PROJECT_ASSEMBLY_COSTS[targetGamePhase]:
                                    totalCost = sav_data.data.PROJECT_ASSEMBLY_COSTS[targetGamePhase][itemName]
                                    if itemName in alreadySupplied:
                                       amountSupplied = alreadySupplied[itemName]
                                    else:
                                       amountSupplied = 0
                                    gamePhase = f"{gamePhase}<li>{amountSupplied}/{totalCost} x {itemName} ({round(amountSupplied/totalCost*100,1)}% complete)</li>\n"
                              gamePhase = f"{gamePhase}</ul>\n"
            elif object.instanceName == "Persistent_Level:PersistentLevel.ResourceSinkSubsystem":
               totalPoints = sav_parse.getPropertyValue(object.properties, "mTotalPoints")
               if totalPoints is not None:
                  if len(totalPoints) == 2:
                     (totalPointsFromItems, totalPointsFromDna) = totalPoints
                     pointProgressLines += f"<li>Total Points: {totalPointsFromItems} from items, {totalPointsFromDna} from DNA</li>\n"
               currentPointLevels = sav_parse.getPropertyValue(object.properties, "mCurrentPointLevels")
               if currentPointLevels is not None:
                  if len(currentPointLevels) == 2:
                     (pointsEarnedFromItems, pointsEarnedFromDna) = currentPointLevels
                     pointProgressLines += f"<li>Total Coupons Earned: {pointsEarnedFromItems + pointsEarnedFromDna}</li>\n"
               numResourceSinkCoupons = sav_parse.getPropertyValue(object.properties, "mNumResourceSinkCoupons")
               if numResourceSinkCoupons is not None:
                  pointProgressLines += f"<li>Number of coupons available in sink: {numResourceSinkCoupons}</li>\n"
            elif object.instanceName == "Persistent_Level:PersistentLevel.schematicManager":
               activeSchematic = sav_parse.getPropertyValue(object.properties, "mActiveSchematic")
               if activeSchematic is not None:
                  activeSchematic = activeSchematic.pathName
                  activeSchematicShortName = sav_parse.pathNameToReadableName(activeSchematic)
                  activeSchematicDescription = f"<b>{activeSchematicShortName}</b>."
               purchasedSchematics = sav_parse.getPropertyValue(object.properties, "mPurchasedSchematics")
               if purchasedSchematics is not None:
                  for purchasedSchematic in purchasedSchematics:
                     if purchasedSchematic.pathName in sav_data.data.UNLOCK_PATHS__HARD_DRIVES:
                        unlockCount_hardDrives += 1
                     elif purchasedSchematic.pathName in sav_data.data.UNLOCK_PATHS__AWESOME_SHOP:
                        unlockCount_awesomeShop += 1
                        unlockRemaining_awesomeShop.remove(purchasedSchematic.pathName)
                     elif purchasedSchematic.pathName in sav_data.data.UNLOCK_PATHS__MAM:
                        unlockCount_mam += 1
                        unlockRemaining_mam.remove(purchasedSchematic.pathName)
                     elif purchasedSchematic.pathName in sav_data.data.UNLOCK_PATHS__HUB_TIERS:
                        unlockCount_hubTiers += 1
                     elif purchasedSchematic.pathName in sav_data.data.UNLOCK_PATHS__SPECIAL:
                        unlockCount_special += 1
            elif object.instanceName == "Persistent_Level:PersistentLevel.CentralStorageSubsystem":
               storedItems = sav_parse.getPropertyValue(object.properties, "mStoredItems")
               if storedItems is not None:
                  for storedItem in storedItems:
                     itemClass = sav_parse.getPropertyValue(storedItem[0], "ItemClass")
                     if itemClass is not None:
                        amount = sav_parse.getPropertyValue(storedItem[0], "amount")
                        if amount is not None:
                           itemName = sav_parse.pathNameToReadableName(itemClass.pathName)
                           dimensionalDepotContents.append((amount, itemName))
            elif object.instanceName in powerLines:
               wireInstances = sav_parse.getPropertyValue(object.properties, "mWireInstances")
               if wireInstances is not None:
                  for (name, position) in wireInstances[0][0]:
                     if name == "Locations":
                        wireLines.append((powerLines[object.instanceName], position))
         if level.collectables1 is not None:
            for collectable in level.collectables1:  # Quantity should match collectables2
               if collectable.pathName in uncollectedPowerSlugsBlue:
                  numCollectedSlugsMk1 += 1
                  del uncollectedPowerSlugsBlue[collectable.pathName]
               elif collectable.pathName in uncollectedPowerSlugsYellow:
                  numCollectedSlugsMk2 += 1
                  del uncollectedPowerSlugsYellow[collectable.pathName]
               elif collectable.pathName in uncollectedPowerSlugsPurple:
                  numCollectedSlugsMk3 += 1
                  del uncollectedPowerSlugsPurple[collectable.pathName]
               elif collectable.pathName in uncollectedSomersloops:
                  del uncollectedSomersloops[collectable.pathName]
               elif collectable.pathName in uncollectedMercerSpheres:
                  del uncollectedMercerSpheres[collectable.pathName]
               elif collectable.pathName in sav_data.crashSites.CRASH_SITES:
                  crashSitesDismantled.append(collectable.pathName)

      crashSitesOpenWithDrive = []
      crashSitesUnopenedKeys = list(crashSiteInstances.keys())
      numOpenAndEmptyCrashSites = 0
      numOpenAndFullCrashSites = 0
      crashSiteInventoryPathName = {}

      numMinedResources = 0
      minedResources = []
      for level in parsedSave.levels:
         for object in level.objects:
            if object.instanceName in minerInstances:
               if sav_parse.getPropertyValue(object.properties, "mExtractableResource") is not None:
                  numMinedResources += 1
                  extractableResource = sav_parse.getPropertyValue(object.properties, "mExtractableResource")
                  if extractableResource is not None:
                     minedResources.append(extractableResource.pathName)
            elif object.instanceName in crashSiteInstances:
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
                     crashSitesOpenWithDrive.append(crashSiteInstances[object.instanceName])
            elif object.instanceName == "Persistent_Level:PersistentLevel.schematicManager":
               paidOffSchematics = sav_parse.getPropertyValue(object.properties, "mPaidOffSchematic")
               if paidOffSchematics is not None:
                  for paidOffSchematic in paidOffSchematics:
                     paidOffSchematic_schematic = sav_parse.getPropertyValue(paidOffSchematic[0], "schematic")
                     itemCostForActiveSchematic = sav_parse.getPropertyValue(paidOffSchematic[0], "ItemCost")
                     if paidOffSchematic_schematic is not None and itemCostForActiveSchematic is not None and paidOffSchematic_schematic.pathName == activeSchematic:
                        activeSchematicDescription = f'{activeSchematicDescription} Already supplied:\n<ul style="margin-top:0px">\t\n'
                        if activeSchematicShortName not in sav_data.data.MILESTONE_COSTS:
                           activeSchematicDescription = f"{activeSchematicDescription}<li>ERROR: {activeSchematicShortName} not in MILESTONE_COSTS</li>\n"
                        else:
                           alreadySupplied = {}
                           for itemCost in itemCostForActiveSchematic:
                              itemClass = sav_parse.getPropertyValue(itemCost[0], "ItemClass")
                              if itemClass is not None:
                                 amountSupplied = sav_parse.getPropertyValue(itemCost[0], "Amount")
                                 if amountSupplied is not None:
                                    itemName = itemClass.pathName
                                    itemName = sav_parse.pathNameToReadableName(itemName)
                                    alreadySupplied[itemName] = amountSupplied
                           for itemName in sav_data.data.MILESTONE_COSTS[activeSchematicShortName]:
                              totalCost = sav_data.data.MILESTONE_COSTS[activeSchematicShortName][itemName]
                              if itemName in alreadySupplied:
                                 amountSupplied = alreadySupplied[itemName]
                              else:
                                 amountSupplied = 0
                              activeSchematicDescription = f"{activeSchematicDescription}<li>{amountSupplied}/{totalCost} x {itemName} ({round(amountSupplied/totalCost*100,1)}% complete)</li>\n"
                        activeSchematicDescription = f"{activeSchematicDescription}</ul>\n"
               elif activeSchematicDescription is not None:
                  activeSchematicDescription = f"{activeSchematicDescription}<p>\n"

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
                           crashSitesOpenWithDrive.append(crashSiteInstances[crashSiteInventoryPathName[object.instanceName]])

      creatingMapImagesFlag = pilAvailableFlag and os.path.isfile(MAP_BASENAME_BLANK)

      lines  = "<!DOCTYPE html>\n"  # This allows the font setting to apply to the table
      lines += "<html>\n"
      lines += f"<head><title>Save file details: {parsedSave.saveFileInfo.sessionName}</title></head>\n"
      lines += "<body>\n"
      lines += "<style>ul { list-style-type: circle; margin-top: 0 }</style>\n"
      lines += "<font size=5>\n"
      lines += "<table align=center><th><td>\n"

      lines += f"Session Name: {parsedSave.saveFileInfo.sessionName}<br>\n"
      lines += f"Save Date: {parsedSave.saveFileInfo.saveDatetime.strftime('%m/%d/%Y %I:%M:%S %p')}<br>\n"

      SECONDS_IN_MINUTE = 60
      SECONDS_IN_HOUR = 60 * SECONDS_IN_MINUTE
      playTimeHours = int(parsedSave.saveFileInfo.playDurationInSeconds / SECONDS_IN_HOUR)
      playTimeMinutes = (parsedSave.saveFileInfo.playDurationInSeconds - playTimeHours * SECONDS_IN_HOUR) / SECONDS_IN_MINUTE
      lines += f'Play Time: {playTimeHours} hours, {round(playTimeMinutes,1)} minutes<p style="margin-bottom:0px">\n'
      if len(sav_parse.satisfactoryCalculatorInteractiveMapExtras):
         lines += f'File suspected of having been saved by satisfactory-calculator.com/en/interactive-map for {len(sav_parse.satisfactoryCalculatorInteractiveMapExtras)} reasons.<p style="margin-bottom:0px">\n'

      lines += f'Game Phase: {gamePhase}<p style="margin-bottom:0px">\n'

      if activeSchematicDescription is not None:
         lines += f'Active Milestone: {activeSchematicDescription}'

      lines += f'Mining {numMinedResources} of {len(minedResourceActors)} resources'
      if creatingMapImagesFlag:
         lines += f' (<a href="{MAP_BASENAME_RESOURCE_NODES}">map</a>).\n<a href="{MAP_BASENAME_POWER}">Map of Power Lines.</a><p>\n'
      else:
         lines += ".<p>\n"

      TOTAL_NUM_SLUGS = len(sav_data.slug.POWER_SLUGS_BLUE) + len(sav_data.slug.POWER_SLUGS_YELLOW) + len(sav_data.slug.POWER_SLUGS_PURPLE)
      totalNumCollectedSlugs = numCollectedSlugsMk1 + numCollectedSlugsMk2 + numCollectedSlugsMk3
      lines += f"{totalNumCollectedSlugs} of {TOTAL_NUM_SLUGS} slugs collected.\n"
      lines += f"{numCollectedSlugsMk1} of {len(sav_data.slug.POWER_SLUGS_BLUE)} blue.\n"
      lines += f"{numCollectedSlugsMk2} of {len(sav_data.slug.POWER_SLUGS_YELLOW)} yellow.\n"
      lines += f"{numCollectedSlugsMk3} of {len(sav_data.slug.POWER_SLUGS_PURPLE)} purple."
      if creatingMapImagesFlag:
         lines += f'\n<a href="{MAP_BASENAME_SLUGS}">Map of remaining slugs.</a>'
      lines += "<p>\n"

      lines += f"{len(uncollectedSomersloops)} Somersloops remaining ({round(len(uncollectedSomersloops)/len(sav_data.somersloop.SOMERSLOOPS)*100,1)}% of {len(sav_data.somersloop.SOMERSLOOPS)})."
      if creatingMapImagesFlag:
         lines += f' <a href="{MAP_BASENAME_SOMERSLOOP}">map</a>'
      lines += "<br>\n"

      lines += f"{len(uncollectedMercerSpheres)} Mercer Spheres remaining ({round(len(uncollectedMercerSpheres)/len(sav_data.mercerSphere.MERCER_SPHERES)*100,1)}% of {len(sav_data.mercerSphere.MERCER_SPHERES)})."
      if creatingMapImagesFlag:
         lines += f' <a href="{MAP_BASENAME_MERCER_SPHERE}">map</a>'

      if creatingMapImagesFlag:
         lines += f' (<a href="{MAP_BASENAME_SOME_MERC_SPH}">both</a>)'
         lines += f' (<a href="{MAP_BASENAME_COLLECTABLES}">all collectables</a>)'
      lines += "<p>\n"

      numCrashSitesNotOpened = len(crashSiteInstances) - numOpenAndEmptyCrashSites - numOpenAndFullCrashSites
      numCrashSitesDismantled = len(crashSitesDismantled)
      lines += f"Of {len(sav_data.crashSites.CRASH_SITES)} crash sites total, " +\
               f"{numOpenAndEmptyCrashSites} {('are','is')[numOpenAndEmptyCrashSites == 1]} open and empty, " +\
               f"{numCrashSitesNotOpened} {('have','has')[numCrashSitesNotOpened == 1]} not been opened, " +\
               f"{numOpenAndFullCrashSites} {('are','is')[numOpenAndFullCrashSites == 1]} open with a drive available, " +\
               f"{numCrashSitesDismantled} {('have','has')[numCrashSitesDismantled == 1]} been dismantled.\r\n"
      if creatingMapImagesFlag:
         lines += f'<a href="{MAP_BASENAME_HARD_DRIVES}">Map of hard drives.</a>'
      lines += '<p style="margin-bottom:0px">\n'

      lines += "Unlock Progress:\n"
      lines += '<ul style="margin-top:0px">\n'
      lines += f"<li>HUB Tiers: {unlockCount_hubTiers} of {len(sav_data.data.UNLOCK_PATHS__HUB_TIERS)}</li>\n"
      lines += f"<li>MAM: {unlockCount_mam} of {len(sav_data.data.UNLOCK_PATHS__MAM)}</li>\n"
      #lines += str(unlockRemaining_mam) # Research_AO_Hog and Research_AO_Spitter remain, but they're clearly unlocked
      lines += f"<li>Awesome Shop: {unlockCount_awesomeShop} of {len(sav_data.data.UNLOCK_PATHS__AWESOME_SHOP)}</li>\n"
      #lines += str(unlockRemaining_awesomeShop) # TODO: Why ResourceSink_Checkmark???  My calculation is the same as satisfactory-calculator, but not the game
      lines += f"<li>Hard Drives: {unlockCount_hardDrives} of {len(sav_data.data.UNLOCK_PATHS__HARD_DRIVES)}</li>\n"
      lines += f"<li>Special: {unlockCount_special} of {len(sav_data.data.UNLOCK_PATHS__SPECIAL)}</li>\n"
      lines += "</ul>\n"

      if len(pointProgressLines) > 0:
         lines += "Sink Point Progress:\n"
         lines += '<ul style="margin-top:0px">\n'
         lines += pointProgressLines
         lines += "</ul>\n"

      if len(dimensionalDepotContents) > 0:
         lines += "Dimensional Depot Contains:\n"
         lines += '<ul style="margin-top:0px">\n'
         dimensionalDepotContents.sort(key=lambda x: x[1])
         for (itemCount, itemName) in dimensionalDepotContents:
            stackSize = getStackSize(itemName, itemCount)
            if stackSize is None:
               lines += f"<li>{itemCount} x {itemName}</li>\n"
            else:
               lines += f"<li>{itemCount} x {itemName} ({round(itemCount/(stackSize*CURRENT_DEPOT_STACK_LIMIT)*100,1)}%)</li>\n"
         lines += "</ul>\n"

      if len(buildablesMap) > 0:
         lines += f"{numBuildables} current built items:\n"
         lines += '<ul style="margin-top:0px">\n'
         buildables: list[tuple] = []
         for buildableStr in buildablesMap:
            buildables.append((buildablesMap[buildableStr], buildableStr))
         buildables.sort(reverse=True, key=lambda x: x[0])
         for buildableTuple in buildables:
            shortName = sav_parse.pathNameToReadableName(buildableTuple[1])
            lines += f"<li>{buildableTuple[0]} x {shortName}</li>\n"
         lines += "</ul>\n"

      if numCreaturesKilled > 0:
         lines += f"{numCreaturesKilled} creatures killed:\n"
         lines += '<ul style="margin-top:0px">\n'
         creaturesKilled.sort(reverse=True, key=lambda x: x[1])
         for creature in creaturesKilled:
            shortName = sav_parse.pathNameToReadableName(creature[0])
            lines += f"<li>{creature[1]} x {shortName}</li>\n"
         lines += f"<li>Flying Crab Hatchers not tracked as of v1.1.1.7</li>\n"
         lines += "</ul>\n"

      lines += "</td></th></table>\n"
      lines += "</body>\n"
      lines += "</html>\n"

      with open(htmlFilename, "w") as fout:
         fout.write(lines)
      chown(htmlFilename)

      if creatingMapImagesFlag:
         Image.MAX_IMAGE_PIXELS = 1700000000

         try:
            imageFont = ImageFont.truetype(FONT_FILENAME, MAP_FONT_SIZE)
            # Testing has shown that, if this font load fails, imageFont is None
            # which cases the drawn text to be present, just with a tiny font.
            # User feedback has reported that it threw OSError.
         except:
            imageFont = None

         if imageFont is None:
            print("CAUTION: An error occured loading the font file.  Please update the FONT_FILENAME variable to point at a font installed on your system.  If you need a .ttf file, can you can get from https://github.com/kiwi0fruit/open-fonts")

         origImage = Image.open(MAP_BASENAME_BLANK)

         smImage = origImage.copy()
         smDraw = ImageDraw.Draw(smImage)

         smsImage = origImage.copy()
         smsDraw = ImageDraw.Draw(smsImage)

         slugImage = origImage.copy()
         slugDraw = ImageDraw.Draw(slugImage)
         addSlugs(slugDraw, uncollectedPowerSlugsBlue, MAP_COLOR_SLUG_BLUE)
         addSlugs(slugDraw, uncollectedPowerSlugsYellow, MAP_COLOR_SLUG_YELLOW)
         addSlugs(slugDraw, uncollectedPowerSlugsPurple, MAP_COLOR_SLUG_PURPLE)
         addSlugs(smsDraw, uncollectedPowerSlugsBlue, outline=MAP_COLOR_SLUG_BLUE)
         addSlugs(smsDraw, uncollectedPowerSlugsYellow, outline=MAP_COLOR_SLUG_YELLOW)
         addSlugs(smsDraw, uncollectedPowerSlugsPurple, outline=MAP_COLOR_SLUG_PURPLE)
         slugDraw.text(MAP_TEXT_POSITION, parsedSave.saveFileInfo.saveDatetime.strftime(f"Uncollected Slugs\n{parsedSave.saveFileInfo.sessionName} %m/%d/%Y %I:%M:%S %p"), font=imageFont, fill=MAP_COLOR_TEXT)
         imageFilename = f"{outputDir}/{MAP_BASENAME_SLUGS}"
         slugImage.crop(CROP_SETTINGS).save(imageFilename)
         chown(imageFilename)

         hdImage = origImage.copy()
         hdDraw = ImageDraw.Draw(hdImage)
         for key in crashSiteInstances:
            coord = crashSiteInstances[key]
            posX = adjPos(coord[0], False)
            posY = adjPos(coord[1], True)
            hdDraw.ellipse((posX-2, posY-2, posX+2, posY+2), fill=MAP_COLOR_CRASH_SITE_OPEN_EMPTY)
         for key in crashSitesUnopenedKeys:
            coord = crashSiteInstances[key]
            posX = adjPos(coord[0], False)
            posY = adjPos(coord[1], True)
            hdDraw.ellipse((posX-2, posY-2, posX+2, posY+2), fill=MAP_COLOR_CRASH_SITE_UNOPENED)
            smsDraw.ellipse((posX-2, posY-2, posX+2, posY+2), fill=MAP_COLOR_CRASH_SITE_UNOPENED)
         for coord in crashSitesOpenWithDrive:
            if coord is not None:
               posX = adjPos(coord[0], False)
               posY = adjPos(coord[1], True)
               hdDraw.ellipse((posX-2, posY-2, posX+2, posY+2), fill=MAP_COLOR_CRASH_SITE_OPEN_W_DRIVE)
               smsDraw.ellipse((posX-2, posY-2, posX+2, posY+2), fill=MAP_COLOR_CRASH_SITE_OPEN_W_DRIVE)
         for key in crashSitesDismantled:
            coord = sav_data.crashSites.CRASH_SITES[key][2]
            posX = adjPos(coord[0], False)
            posY = adjPos(coord[1], True)
            hdDraw.ellipse((posX-2, posY-2, posX+2, posY+2), fill=MAP_COLOR_CRASH_SITE_DISMANTLED)
            smsDraw.ellipse((posX-2, posY-2, posX+2, posY+2), fill=MAP_COLOR_CRASH_SITE_DISMANTLED)
         hdDraw.text(MAP_TEXT_POSITION, parsedSave.saveFileInfo.saveDatetime.strftime(f"Hard drives\n{parsedSave.saveFileInfo.sessionName} %m/%d/%Y %I:%M:%S %p"), font=imageFont, fill=MAP_COLOR_TEXT)
         imageFilename = f"{outputDir}/{MAP_BASENAME_HARD_DRIVES}"
         hdImage.crop(CROP_SETTINGS).save(imageFilename)
         chown(imageFilename)

         ssImage = origImage.copy()
         ssDraw = ImageDraw.Draw(ssImage)
         for instanceName in uncollectedSomersloops:
            (rootObject, rotation, position) = uncollectedSomersloops[instanceName]
            posX = adjPos(position[0], False)
            posY = adjPos(position[1], True)
            ssDraw.ellipse((posX-2, posY-2, posX+2, posY+2), fill=MAP_COLOR_UNCOLLECTED_SOMERSLOOP)
            smDraw.ellipse((posX-2, posY-2, posX+2, posY+2), fill=MAP_COLOR_UNCOLLECTED_SOMERSLOOP)
            smsDraw.ellipse((posX-2, posY-2, posX+2, posY+2), fill=MAP_COLOR_UNCOLLECTED_SOMERSLOOP)
         ssDraw.text(MAP_TEXT_POSITION, parsedSave.saveFileInfo.saveDatetime.strftime(f"Uncollected Somersloops\n{parsedSave.saveFileInfo.sessionName} %m/%d/%Y %I:%M:%S %p"), font=imageFont, fill=MAP_COLOR_TEXT)
         imageFilename = f"{outputDir}/{MAP_BASENAME_SOMERSLOOP}"
         ssImage.crop(CROP_SETTINGS).save(imageFilename)
         chown(imageFilename)

         msImage = origImage.copy()
         msDraw = ImageDraw.Draw(msImage)
         for instanceName in uncollectedMercerSpheres:
            (rootObject, rotation, position) = uncollectedMercerSpheres[instanceName]
            posX = adjPos(position[0], False)
            posY = adjPos(position[1], True)
            msDraw.ellipse((posX-2, posY-2, posX+2, posY+2), fill=MAP_COLOR_UNCOLLECTED_MERCER_SPHERE)
            smDraw.ellipse((posX-2, posY-2, posX+2, posY+2), fill=MAP_COLOR_UNCOLLECTED_MERCER_SPHERE)
            smsDraw.ellipse((posX-2, posY-2, posX+2, posY+2), fill=MAP_COLOR_UNCOLLECTED_MERCER_SPHERE)
         msDraw.text(MAP_TEXT_POSITION, parsedSave.saveFileInfo.saveDatetime.strftime(f"Uncollected Mercer Spheres\n{parsedSave.saveFileInfo.sessionName} %m/%d/%Y %I:%M:%S %p"), font=imageFont, fill=MAP_COLOR_TEXT)
         imageFilename = f"{outputDir}/{MAP_BASENAME_MERCER_SPHERE}"
         msImage.crop(CROP_SETTINGS).save(imageFilename)
         chown(imageFilename)

         smDraw.text(MAP_TEXT_POSITION, parsedSave.saveFileInfo.saveDatetime.strftime(f"Uncollected Somersloops & Mercer Spheres\n{parsedSave.saveFileInfo.sessionName} %m/%d/%Y %I:%M:%S %p"), font=imageFont, fill=MAP_COLOR_TEXT)
         imageFilename = f"{outputDir}/{MAP_BASENAME_SOME_MERC_SPH}"
         smImage.crop(CROP_SETTINGS).save(imageFilename)
         chown(imageFilename)

         smsDraw.text(MAP_TEXT_POSITION, parsedSave.saveFileInfo.saveDatetime.strftime(f"Uncollected Somersloops & Mercer Spheres &\nSlugs & Crash Sites\n{parsedSave.saveFileInfo.sessionName} %m/%d/%Y %I:%M:%S %p"), font=imageFont, fill=MAP_COLOR_TEXT)
         imageFilename = f"{outputDir}/{MAP_BASENAME_COLLECTABLES}"
         smsImage.crop(CROP_SETTINGS).save(imageFilename)
         chown(imageFilename)

         plImage = origImage.copy()
         plDraw = ImageDraw.Draw(plImage)
         for (src, dst) in wireLines:
            possX = adjPos(src[0], False)
            posdX = adjPos(dst[0], False)
            possY = adjPos(src[1], True)
            posdY = adjPos(dst[1], True)
            plDraw.line(((possX, possY), (posdX, posdY)), fill=MAP_COLOR_POWER_LINE, width=2)
         plDraw.text(MAP_TEXT_POSITION, parsedSave.saveFileInfo.saveDatetime.strftime(f"Power Lines\n{parsedSave.saveFileInfo.sessionName} %m/%d/%Y %I:%M:%S %p"), font=imageFont, fill=MAP_COLOR_TEXT)
         imageFilename = f"{outputDir}/{MAP_BASENAME_POWER}"
         plImage.crop(CROP_SETTINGS).save(imageFilename)
         chown(imageFilename)

         rnImage = origImage.copy()
         rnDraw = ImageDraw.Draw(rnImage)
         for instanceName in minedResourceActors:
            (position, type, purity) = minedResourceActors[instanceName]
            posX = adjPos(position[0], False)
            posY = adjPos(position[1], True)

            sz = MAP_RESOURCE_NODE_CIRCLE_SIZE_UNUSED
            if instanceName in minedResources:
               sz = MAP_RESOURCE_NODE_CIRCLE_SIZE_USED

            if purity in MAP_COLOR_NODE_PURITY:
               rnDraw.ellipse((posX-sz, posY-sz, posX+sz, posY+sz), fill=MAP_COLOR_NODE_PURITY[purity])

            sz -= 1

            if type in MAP_COLOR_NODE_TYPE:
               rnDraw.ellipse((posX-sz, posY-sz, posX+sz, posY+sz), fill=MAP_COLOR_NODE_TYPE[type])
         rnDraw.text(MAP_TEXT_POSITION, parsedSave.saveFileInfo.saveDatetime.strftime(f"Resource Nodes\n{parsedSave.saveFileInfo.sessionName} %m/%d/%Y %I:%M:%S %p"), font=imageFont, fill=MAP_COLOR_TEXT)
         imageFilename = f"{outputDir}/{MAP_BASENAME_RESOURCE_NODES}"
         rnImage.crop(CROP_SETTINGS).save(imageFilename)
         chown(imageFilename)

   except Exception as error:
      with open(htmlFilename, "w") as fout:
         fout.write(f"<html><head><title>Error parsing save</title></head><body>{error}</body></html>")
      raise Exception(f"ERROR: While processing '{savFilename}': {error}")

if __name__ == '__main__':

   if len(sys.argv) <= 1 or len(sys.argv[1]) == 0:
      allSaveFiles = []
      if "LOCALAPPDATA" in os.environ:
         allSaveFiles = glob.glob(f"{os.environ['LOCALAPPDATA']}/FactoryGame/Saved/SaveGames/*/*.sav")
      if len(allSaveFiles) == 0:
         print("ERROR: No .sav file specified.")
         exit(1)
      savFilename = max(allSaveFiles, key=os.path.getmtime)
   else:
      savFilename = sys.argv[1]

   if not os.path.isfile(savFilename):
      print(f"ERROR: Save file does not exist: '{savFilename}'", file=sys.stderr)
      exit(1)

   outputDir = DEFAULT_OUTPUT_DIR
   if len(sys.argv) > 2:
      outputDir = sys.argv[2]

   htmlBasename = DEFAULT_HTML_BASENAME
   if len(sys.argv) > 3:
      htmlBasename = sys.argv[3]

   generateHTML(savFilename, outputDir, htmlBasename)

   exit(0)
