#!/usr/bin/env python3
# This file is part of the Satisfactory Save Parser distribution
#                                  (https://github.com/GreyHak/sat_sav_parse).
# Copyright (c) 2026 GreyHak (github.com/GreyHak).
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

import zlib
import string
import struct
import sav_parse
import sav_to_resave
from sav_data.data import CONVEYOR_BELTS, POWER_LINE

def parseBlueprint(sbpFile: str):
   with open(sbpFile, "rb") as fin:
      data = fin.read()
      offset = 0

      (offset, headerVersion) = sav_parse.parseUint32(offset, data)
      if headerVersion != 2:
         return f"Unsupported header version {headerVersion}"
      (offset, saveVersion) = sav_parse.parseUint32(offset, data)
      if saveVersion != 51 and saveVersion != 52 and saveVersion != 53 and saveVersion != 58:
         return f"Unsupported save version {saveVersion}"
      (offset, buildVersion) = sav_parse.parseUint32(offset, data)
      (offset, designerDimensionX) = sav_parse.parseUint32(offset, data)
      if designerDimensionX != 4 and designerDimensionX != 5 and designerDimensionX != 6:
         return f"Invalid designer dimension {designerDimensionX}"
      (offset, designerDimensionY) = sav_parse.parseUint32(offset, data)
      if designerDimensionY != designerDimensionX:
         raise sav_parse.ParseError(f"Designer Y dimension {designerDimensionY} doesn't match designer X dimension {designerDimensionX}")
      (offset, designerDimensionZ) = sav_parse.parseUint32(offset, data)
      if designerDimensionZ != designerDimensionX:
         raise sav_parse.ParseError(f"Designer Z dimension {designerDimensionZ} doesn't match designer X dimension {designerDimensionX}")

      ingredients = []
      (offset, ingredientCount) = sav_parse.parseUint32(offset, data)
      for idx in range(ingredientCount):
         (offset, item) = sav_parse.parseObjectReference(offset, data)
         (offset, itemCount) = sav_parse.parseUint32(offset, data)
         ingredients.append([itemCount, item])

      buildableRecipes = []
      (offset, buildableCount) = sav_parse.parseUint32(offset, data)
      for idx in range(buildableCount):
         (offset, buildingRecipe) = sav_parse.parseObjectReference(offset, data)
         buildableRecipes.append(buildingRecipe)

      saveObjectVersionData = None
      objectUE5Version = 0
      if saveVersion >= 53:
         (offset, saveObjectVersionData) = sav_parse.parseSaveObjectVersionData(offset, data)
         objectUE5Version = sav_parse.getUE5VersionFromObjectVersionData(saveObjectVersionData)

      decompressedData = b""
      while offset < len(data):
         offset = sav_parse.confirmBasicType(offset, data, sav_parse.parseUint32, 0x9e2a83c1)  # unrealEnginePackageSignature
         offset = sav_parse.confirmBasicType(offset, data, sav_parse.parseUint32, 0x22222222)  # chunkHeaderVersion
         offset = sav_parse.confirmBasicType(offset, data, sav_parse.parseUint32, 0x20000) # maxUncompressedChunkContentSize
         offset = sav_parse.confirmBasicType(offset, data, sav_parse.parseUint32, 0)
         offset = sav_parse.confirmBasicType(offset, data, sav_parse.parseUint8, 3) # compressionAlgorithmCode

         (offset, currentChunkCompressedLength1) = sav_parse.parseUint64(offset, data)   # 1957379 = 0x1DDE03
         (offset, currentChunkUncompressedLength1) = sav_parse.parseUint64(offset, data) # 0x2000000
         (offset, currentChunkCompressedLength2) = sav_parse.parseUint64(offset, data)   # 1957379
         (offset, currentChunkUncompressedLength2) = sav_parse.parseUint64(offset, data) # 0x2000000
         if currentChunkCompressedLength1 != currentChunkCompressedLength2:
            raise sav_parse.ParseError(f"Compressed size mismatch")
         if currentChunkUncompressedLength1 != currentChunkUncompressedLength2:
            raise sav_parse.ParseError(f"Uncompressed size mismatch")

         dData = zlib.decompress(data[offset:offset+currentChunkCompressedLength1])
         decompressedData += dData
         offset += currentChunkCompressedLength1
      data = decompressedData
      #with open("C:\\temp\\decompress.txt", "wb") as fdump:
      #   fdump.write(decompressedData)
      offset = 0

      (offset, fullSize) = sav_parse.parseUint32(offset, data)

      (offset, objectHeadersSize) = sav_parse.parseUint32(offset, data)
      (offset, actorAndComponentCount) = sav_parse.parseUint32(offset, data)
      actorAndComponentObjectHeaders = []
      for idx in range(actorAndComponentCount):
         (offset, headerType) = sav_parse.parseUint32(offset, data)
         if headerType == 1:
            objectHeader = sav_parse.ActorHeader()
         elif headerType == 0:
            objectHeader = sav_parse.ComponentHeader()
         else:
            raise sav_parse.ParseError(f"Invalid headerType {headerType}")
         offset = objectHeader.parse(offset, data)
         actorAndComponentObjectHeaders.append(objectHeader)

      (offset, allObjectsSize) = sav_parse.parseUint32(offset, data)
      if offset + allObjectsSize != len(data):
         raise sav_parse.ParseError(f"Unexpected total object size {allObjectsSize}")
      (offset, objectCount) = sav_parse.parseUint32(offset, data)
      if objectCount != actorAndComponentCount:
         raise sav_parse.ParseError(f"Object count {objectCount} doesn't match header count {actorAndComponentCount}")

      objects = []
      for idx in range(objectCount):
         (offset, objectSize) = sav_parse.parseUint32(offset, data)
         objectStartOffset = offset

         if isinstance(actorAndComponentObjectHeaders[idx], sav_parse.ActorHeader):
            (offset, mainObject) = sav_parse.parseObjectReference(offset, data)
            (offset, count) = sav_parse.parseUint32(offset, data)
            objectList = []
            for jdx in range(count):
               (offset, object) = sav_parse.parseObjectReference(offset, data)
               objectList.append(object)
            if objectUE5Version >= 1011:
               offset = sav_parse.confirmBasicType(offset, data, sav_parse.parseUint8, 0) # = serializationControl
            (offset, properties, propertyTypes) = sav_parse.parseProperties(saveVersion, offset, data, objectUE5Version)
            offset = sav_parse.confirmBasicType(offset, data, sav_parse.parseUint32, 0)
            extras = None
            if actorAndComponentObjectHeaders[idx].typePath in POWER_LINE:
               (offset, object1) = sav_parse.parseObjectReference(offset, data)
               (offset, object2) = sav_parse.parseObjectReference(offset, data)
               extras = [object1, object2]
            elif actorAndComponentObjectHeaders[idx].typePath in CONVEYOR_BELTS:
               offset = sav_parse.confirmBasicType(offset, data, sav_parse.parseUint32, 0)
            objects.append([mainObject, objectList, properties, propertyTypes, extras])

         else:
            if objectUE5Version >= 1011:
               offset = sav_parse.confirmBasicType(offset, data, sav_parse.parseUint8, 0) # = serializationControl
            (offset, properties, propertyTypes) = sav_parse.parseProperties(saveVersion, offset, data, objectUE5Version)
            offset = sav_parse.confirmBasicType(offset, data, sav_parse.parseUint32, 0)
            offset = sav_parse.confirmBasicType(offset, data, sav_parse.parseUint32, 0)
            objects.append([properties, propertyTypes])
         if offset != objectStartOffset + objectSize:
            raise sav_parse.ParseError(f"Position at the end of object mismatch: type {type(actorAndComponentObjectHeaders[idx])}, expected {objectStartOffset + objectSize}, actual {offset}, delta {objectStartOffset + objectSize - offset}")

      if offset != len(data):
         raise sav_parse.ParseError(f"Position at the end of data mismatch: data {len(data)}, parsing {offset}")

   return [[headerVersion, saveVersion, buildVersion, saveObjectVersionData], [designerDimensionX, ingredients, buildableRecipes], actorAndComponentObjectHeaders, objects]

def resaveBlueprint(sbpFile, blueprint):
   versions, summary, objectHeaders, objects = blueprint
   headerVersion, saveVersion, buildVersion, saveObjectVersionData = versions
   designerDimension, ingredients, buildableRecipes = summary

   objectUE5Version = 0
   if saveVersion >= 53:
      objectUE5Version = sav_parse.getUE5VersionFromObjectVersionData(saveObjectVersionData)

   with open(sbpFile, "wb") as fout:
      dataOH = sav_to_resave.addHeaders(objectHeaders)

      dataObjs = bytearray()
      dataObjs.extend(sav_to_resave.addUint32(len(objects)))
      for idx in range(len(objects)):
         dataObj = bytearray()
         if isinstance(objectHeaders[idx], sav_parse.ActorHeader):
            mainObject, objectList, properties, propertyTypes, extras = objects[idx]
            dataObj.extend(sav_to_resave.addObjectReference(mainObject))
            dataObj.extend(sav_to_resave.addUint32(len(objectList)))
            for subobj in objectList:
               dataObj.extend(sav_to_resave.addObjectReference(subobj))
            if objectUE5Version >= 1011:
               dataObj.extend(sav_to_resave.addUint8(0))
            dataObj.extend(sav_to_resave.addProperties(saveVersion, objectUE5Version, properties, propertyTypes))
            dataObj.extend(sav_to_resave.addUint32(0))
            if objectHeaders[idx].typePath in POWER_LINE:
               dataObj.extend(sav_to_resave.addObjectReference(extras[0]))
               dataObj.extend(sav_to_resave.addObjectReference(extras[1]))
            elif objectHeaders[idx].typePath in CONVEYOR_BELTS:
               dataObj.extend(sav_to_resave.addUint32(0))

         else:
            properties, propertyTypes = objects[idx]
            if objectUE5Version >= 1011:
               dataObj.extend(sav_to_resave.addUint8(0))
            dataObj.extend(sav_to_resave.addProperties(saveVersion, objectUE5Version, properties, propertyTypes))
            dataObj.extend(sav_to_resave.addUint32(0))
            dataObj.extend(sav_to_resave.addUint32(0))

         dataObjs.extend(sav_to_resave.addUint32(len(dataObj)))
         dataObjs.extend(dataObj)

      rdata = bytearray()
      rdata.extend(sav_to_resave.addUint32(len(dataOH)))
      rdata.extend(dataOH)
      rdata.extend(sav_to_resave.addUint32(len(dataObjs)))
      rdata.extend(dataObjs)
      rdata = sav_to_resave.addUint32(len(rdata)) + rdata

      sdata = bytearray()
      sdata.extend(sav_to_resave.addUint32(headerVersion))
      sdata.extend(sav_to_resave.addUint32(saveVersion))
      sdata.extend(sav_to_resave.addUint32(buildVersion))
      sdata.extend(sav_to_resave.addUint32(designerDimension))
      sdata.extend(sav_to_resave.addUint32(designerDimension))
      sdata.extend(sav_to_resave.addUint32(designerDimension))

      sdata.extend(sav_to_resave.addUint32(len(ingredients)))
      for itemCount, item in ingredients:
         sdata.extend(sav_to_resave.addObjectReference(item))
         sdata.extend(sav_to_resave.addUint32(itemCount))

      sdata.extend(sav_to_resave.addUint32(len(buildableRecipes)))
      for buildableRecipe in buildableRecipes:
         sdata.extend(sav_to_resave.addObjectReference(buildableRecipe))

      if saveVersion >= 53:
         sdata.extend(sav_to_resave.addSaveObjectVersionData(saveObjectVersionData))

      MAXIMUM_CHUNK_SIZE = 0x20000
      dataOffset = 0
      while dataOffset < len(rdata):

         chunkSize = MAXIMUM_CHUNK_SIZE
         if dataOffset + chunkSize > len(rdata):
            chunkSize = len(rdata) - dataOffset

         cdata = zlib.compress(rdata[dataOffset:dataOffset+chunkSize])

         sdata.extend(sav_to_resave.addUint32(0x9e2a83c1))
         sdata.extend(sav_to_resave.addUint32(0x22222222))
         sdata.extend(sav_to_resave.addUint32(MAXIMUM_CHUNK_SIZE))
         sdata.extend(sav_to_resave.addUint32(0))
         sdata.extend(sav_to_resave.addUint8(3))

         sdata.extend(sav_to_resave.addUint64(len(cdata)))
         sdata.extend(sav_to_resave.addUint64(chunkSize))
         sdata.extend(sav_to_resave.addUint64(len(cdata)))
         sdata.extend(sav_to_resave.addUint64(chunkSize))
         sdata.extend(cdata)

         dataOffset += chunkSize

      fout.write(sdata)

def printBlueprintSummary(blueprint, sbpFile):
   versions, summary, objectHeaders, objects = blueprint
   headerVersion, saveVersion, buildVersion, saveObjectVersionData = versions
   designerDimension, ingredients, buildableRecipes = summary
   print(f"{headerVersion}, {saveVersion}, {buildVersion}, {designerDimension}x{designerDimension}x{designerDimension} with {len(ingredients)} ingredients, {len(buildableRecipes)} buildables, and {len(objects)} objects: {sbpFile}")
   for itemCount, item in sorted(ingredients, key=lambda l: l[0], reverse=True):
      print(f"   Ingredient {itemCount}x {sav_parse.pathNameToReadableName(item.pathName)}")
   for buildables in sorted(buildableRecipes, key=lambda l: sav_parse.pathNameToReadableName(l.pathName.replace("Recipe_", "Build_"))):
      buildingPathName = buildables.pathName.replace("Recipe_", "Build_")
      print(f"   Buildable {sav_parse.pathNameToReadableName(buildingPathName)}")

def parseBlueprintConfig(sbpcfgFile):
   with open(sbpcfgFile, "rb") as fin:
      data = fin.read()
      offset = 0

      (offset, version) = sav_parse.parseUint32(offset, data)
      (offset, description) = sav_parse.parseString(offset, data)
      (offset, iconId) = sav_parse.parseUint32(offset, data)
      iconColor = []
      for idx in range(4):
         (offset, color) = sav_parse.parseFloat(offset, data)
         iconColor.append(color)

      referencedIconLibrary = None
      iconLibraryType = None
      editors = None
      serviceProvider = None
      if version >= 3:
         (offset, referencedIconLibrary) = sav_parse.parseString(offset, data)
         (offset, iconLibraryType) = sav_parse.parseString(offset, data)

         if version == 4:
            editors = []
            (offset, editByCount) = sav_parse.parseUint32(offset, data)
            for idx in range(editByCount):
               (offset, accountId) = sav_parse.parseString(offset, data)
               (offset, displayName) = sav_parse.parseString(offset, data)
               (offset, platformName) = sav_parse.parseString(offset, data)
               editors.append([accountId, displayName, platformName])

         elif version == 6:
            # FPlayerInfoHandle
            (offset, serviceProvider) = sav_parse.parseUint8(offset, data)
            unpresentSaveVersion56AndBelowFlag = (len(data) - offset == 1)
            if unpresentSaveVersion56AndBelowFlag: # < 57
               version = (version, unpresentSaveVersion56AndBelowFlag)
               offset = sav_parse.confirmBasicType(offset, data, sav_parse.parseUint8, 0) # Legacy PlayerInfoTableIndex
            else: # >= 57
               offset = sav_parse.confirmBasicType(offset, data, sav_parse.parseUint32, 0) # PlayerInfoTableIndex

      if offset != len(data):
         raise sav_parse.ParseError(f"Unexpected file length {len(data)} > {offset}")

      return version, description, iconId, iconColor, referencedIconLibrary, iconLibraryType, editors, serviceProvider

def resaveBlueprintConfig(sbpcfgFile, config):

   version, description, iconId, iconColor, referencedIconLibrary, iconLibraryType, editors, serviceProvider = config

   if isinstance(version, (list, tuple)):
      # unpresentSaveVersion56AndBelowFlag here is always True
      version, unpresentSaveVersion56AndBelowFlag = version
   elif version >= 6:
      unpresentSaveVersion56AndBelowFlag = False
   else:
      unpresentSaveVersion56AndBelowFlag = None

   data = bytearray()
   data.extend(sav_to_resave.addUint32(version))
   data.extend(sav_to_resave.addString(description))
   data.extend(sav_to_resave.addUint32(iconId))
   for color in iconColor:
      data.extend(sav_to_resave.addFloat(color))

   if version >= 3:
      data.extend(sav_to_resave.addString(referencedIconLibrary))
      data.extend(sav_to_resave.addString(iconLibraryType))

      if version == 4:
         data.extend(sav_to_resave.addUint32(len(editors)))
         for accountId, displayName, platformName in editors:
            data.extend(sav_to_resave.addString(accountId))
            data.extend(sav_to_resave.addString(displayName))
            data.extend(sav_to_resave.addString(platformName))

      elif version == 6:
         data.extend(sav_to_resave.addUint8(serviceProvider))
         if unpresentSaveVersion56AndBelowFlag: # < 57
            data.extend(sav_to_resave.addUint8(0))
         else: # >= 57
            data.extend(sav_to_resave.addUint32(0))

   with open(sbpcfgFile, "wb") as fout:
      fout.write(data)

if __name__ == '__main__':
   import os
   import sys
   import pathlib
   import sav_data.data

   pathList = [f"{os.environ['LOCALAPPDATA']}\\FactoryGame\\Saved\\SaveGames\\blueprints"]
   if len(sys.argv) > 1:
      pathList = sys.argv[1:]

   fileList = []
   for path in pathList:
      if os.path.isdir(path):
         for path in pathlib.Path(path).glob('**/*.sbp*'):
            fileList.append(str(path))
      else:
         fileList.append(path)

   RESAVE_TEST = True
   TEST_OUTPUT_FILE_SBP = "C:\\temp\\resave.sbp"
   TEST_OUTPUT_FILE_SBPCFG = "C:\\temp\\resave.sbpcfg"

   for filepath in fileList:
      if filepath.endswith(".sbp"):
         blueprint = parseBlueprint(filepath)
         if isinstance(blueprint, str):
            print(blueprint)
         else:
            printBlueprintSummary(blueprint, filepath)
            if RESAVE_TEST:
               resaveBlueprint(TEST_OUTPUT_FILE_SBP, blueprint)
               parseBlueprint(TEST_OUTPUT_FILE_SBP)
      elif filepath.endswith(".sbpcfg"):
         config = parseBlueprintConfig(filepath)
         version, description, iconId, iconColor, referencedIconLibrary, iconLibraryType, editors, serviceProvider = config
         print(filepath)
         ICON_ID_NONE = 65535
         if iconId == ICON_ID_NONE:
            print(f"No icon with color {iconColor}")
         elif iconId in sav_data.data.ICON_IDS_TO_NAMES:
            print(f"Icon {iconId} ({sav_data.data.ICON_IDS_TO_NAMES[iconId]}) with color {iconColor}")
         else:
            print(f"Icon {iconId} with color {iconColor}")
         if len(description) > 0:
            print(f"Description:\n{description}")
         if editors is not None and len(editors) > 0:
            print(f"Created by {editors[0][1]}")
         if RESAVE_TEST:
            resaveBlueprintConfig(TEST_OUTPUT_FILE_SBPCFG, config)
            parseBlueprintConfig(TEST_OUTPUT_FILE_SBPCFG)
            with open(filepath, "rb") as finOriginal:
               with open(TEST_OUTPUT_FILE_SBPCFG, "rb") as finResave:
                  if finResave.read() != finOriginal.read():
                     raise sav_parse.ParseError(f"Resave check of {filepath} failed.")
      else:
         print(f"Unknown file extension {filepath}")
      print()
