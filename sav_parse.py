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

# References which aren't accurate for Satisfactory v1.0:
# - https://satisfactory.wiki.gg/wiki/Save_files#Save_file_format

#import json
#with open("en-Stable.json", "r") as fin: # https://static.satisfactory-calculator.com/data/json/mapData/en-Stable.json?v=1727270488
#   interactiveData = json.load(fin)
#resources = []
#for resourceCategory in interactiveData["options"]:
#   for resourceType in resourceCategory["options"]:
#      if "type" in resourceType:
#         nameOfResource = resourceType["type"]
#         for purity in resourceType["options"]:
#            if "purity" in purity:
#               nameOfPurity = purity["purity"]
#               for resource in purity["markers"]:
#                  resourcePathName = resource["pathName"]
#                  resources.append((resourcePathName, nameOfResource, nameOfPurity))
#resources.sort(key=lambda x: x[0])
#for (resourcePathName, nameOfResource, nameOfPurity) in resources:
#   print(f'   "{resourcePathName}": ("{nameOfResource}", Purity.{nameOfPurity.upper()}),')
#exit(0)

import datetime
import os
import struct
import sys
import zlib
import glob
import enum

PROGRESS_BAR_ENABLE_DECOMPRESS = True
PROGRESS_BAR_ENABLE_PARSE = True
PROGRESS_BAR_ENABLE_DUMP = True
PRINT_DEBUG = False

class Purity(enum.Enum):
   UNKNOWN = 0
   IMPURE = 1
   NORMAL = 2
   PURE = 3

RESOURCE_PURITY = {
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite10": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite100": ("Desc_Water_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite101": ("Desc_Water_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite102": ("Desc_Water_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite103_8": ("Desc_Water_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite108": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite109": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite11": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite110": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite111": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite112": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite113": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite114_7": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite115": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite116": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite117": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite118": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite119": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite12": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite120": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite121": ("Desc_Water_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite13": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite14": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite15": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite16": ("Desc_NitrogenGas_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite17": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite18_3": ("Desc_NitrogenGas_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite19": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite2": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite20": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite21": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite22": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite23_5": ("Desc_NitrogenGas_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite24": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite25": ("Desc_NitrogenGas_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite26": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite27": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite28": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite29": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite3": ("Desc_NitrogenGas_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite30": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite31": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite32": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite33": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite34": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite35": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite36": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite37": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite38": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite39": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite4": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite40": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite41": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite42": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite43": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite44": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite45": ("Desc_LiquidOilWell_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite46": ("Desc_LiquidOilWell_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite47": ("Desc_LiquidOilWell_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite48": ("Desc_LiquidOilWell_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite49": ("Desc_LiquidOilWell_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite5": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite50": ("Desc_LiquidOilWell_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite51_1": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite57": ("Desc_LiquidOilWell_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite58": ("Desc_Water_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite59": ("Desc_LiquidOilWell_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite6": ("Desc_NitrogenGas_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite60": ("Desc_LiquidOilWell_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite61": ("Desc_LiquidOilWell_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite61_UAID_40B076DF2F79D7DF01_1933830510": ("Desc_LiquidOilWell_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite61_UAID_40B076DF2F79D7DF01_2053713511": ("Desc_LiquidOilWell_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite61_UAID_40B076DF2F79D8DF01_1587984689": ("Desc_LiquidOilWell_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite61_UAID_40B076DF2F79D8DF01_1704280690": ("Desc_LiquidOilWell_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite61_UAID_40B076DF2F79D8DF01_1999134691": ("Desc_LiquidOilWell_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite61_UAID_40B076DF2F79D9DF01_1230935868": ("Desc_LiquidOilWell_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite62": ("Desc_LiquidOilWell_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite63": ("Desc_LiquidOilWell_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite64": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite65": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite66": ("Desc_Water_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite67": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite68": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite69": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite7": ("Desc_NitrogenGas_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite70": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite71": ("Desc_Water_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite72": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite73": ("Desc_Water_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite74": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite75": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite76": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite77": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite78": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite79": ("Desc_Water_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite8": ("Desc_NitrogenGas_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite80": ("Desc_Water_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite81": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite82": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite83": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite84": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite85": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite86": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite87": ("Desc_Water_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite88": ("Desc_Water_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite89": ("Desc_Water_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite9": ("Desc_NitrogenGas_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite90": ("Desc_Water_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite91": ("Desc_Water_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite92": ("Desc_Water_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite93": ("Desc_Water_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite94": ("Desc_Water_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite95": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite96": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite97": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite98": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite99": ("Desc_Water_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_FrackingSatellite_2": ("Desc_NitrogenGas_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode100": ("Desc_LiquidOil_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode101_1893": ("Desc_SAM_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode101_UAID_40B076DF2F79E6D901_1551800812": ("Desc_SAM_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode101_UAID_40B076DF2F79E7D901_2125168992": ("Desc_SAM_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode102_2068": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode103": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode104": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode105_2463": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode106": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode107": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode108": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode109": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode11": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode110": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode111_3367": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode112": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode113": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode114": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode115": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode116": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode117": ("Desc_OreCopper_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode118_4340": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode119": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode121_4877": ("Desc_OreGold_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode121_UAID_40B076DF2F7938DF01_2097772508": ("Desc_OreGold_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode122": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode123_5084": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode124_5785": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode125_5930": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode126_6409": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode127": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode128_5242": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode129": ("Desc_Coal_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode12_91": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode13": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode130": ("Desc_Coal_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode131": ("Desc_OreCopper_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode132_5908": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode133_6963": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode134_8590": ("Desc_OreGold_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode135": ("Desc_SAM_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode136": ("Desc_RawQuartz_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode136_UAID_40B076DF2F7975DF01_1587576239": ("Desc_RawQuartz_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode136_UAID_40B076DF2F7975DF01_1617269241": ("Desc_RawQuartz_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode136_UAID_40B076DF2F7975DF01_1622351243": ("Desc_RawQuartz_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode137_2248": ("Desc_RawQuartz_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode138_590": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode139_909": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode140": ("Desc_OreGold_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode141": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode142": ("Desc_OreGold_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode142_UAID_40B076DF2F79E8DD01_2087440367": ("Desc_OreGold_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode142_UAID_40B076DF2F79E9DD01_1434900545": ("Desc_OreGold_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode142_UAID_40B076DF2F79E9DD01_1872254547": ("Desc_OreGold_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode143_1543": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode144_1644": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode145_1749": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode146": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode147": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode148": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode149": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode14_609": ("Desc_LiquidOil_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode15": ("Desc_LiquidOil_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode150": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode151": ("Desc_LiquidOil_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode152_995": ("Desc_LiquidOil_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode153": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode154": ("Desc_LiquidOil_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode155": ("Desc_LiquidOil_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode156": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode157": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode158": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode159": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode16": ("Desc_LiquidOil_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode160": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode161": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode162_5199": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode163": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode164": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode165": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode166": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode167": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode168": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode169_UAID_40B076DF2F7939DE01_2083925623": ("Desc_OreGold_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode170_363": ("Desc_Sulfur_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode172": ("Desc_SAM_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode172_UAID_40B076DF2F79DFD901_1471130569": ("Desc_SAM_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode173": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode174": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode175": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode176_UAID_40B076DF2F793BDF01_1694110039": ("Desc_OreGold_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode177": ("Desc_Sulfur_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode178": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode179": ("Desc_OreCopper_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode180": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode181": ("Desc_Stone_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode182": ("Desc_Stone_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode184": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode185": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode186": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode187_0": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode188": ("Desc_OreCopper_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode189": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode190": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode191": ("Desc_Stone_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode192_0": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode193": ("Desc_Stone_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode194": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode195": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode196": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode197": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode198": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode199": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode200": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode201": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode202": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode203": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode204_0": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode205": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode206": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode207": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode208": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode209": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode20_3137": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode210": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode211": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode212": ("Desc_OreCopper_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode213": ("Desc_OreCopper_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode214": ("Desc_OreCopper_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode215": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode216": ("Desc_OreCopper_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode217": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode218": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode219": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode220": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode221": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode222": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode223": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode224": ("Desc_Stone_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode225": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode226": ("Desc_Stone_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode227": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode228": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode229": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode230": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode231": ("Desc_RawQuartz_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode232": ("Desc_RawQuartz_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode233": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode234": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode235": ("Desc_OreCopper_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode236": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode237": ("Desc_OreCopper_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode238": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode239": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode23_96": ("Desc_LiquidOil_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode240": ("Desc_OreGold_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode241": ("Desc_SAM_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode241_UAID_40B076DF2F7947D301_1723440520": ("Desc_SAM_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode24_97": ("Desc_LiquidOil_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode25_98": ("Desc_LiquidOil_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode26_99": ("Desc_LiquidOil_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode27_100": ("Desc_LiquidOil_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode28_101": ("Desc_LiquidOil_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode29_102": ("Desc_LiquidOil_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode30_103": ("Desc_LiquidOil_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode31_104": ("Desc_LiquidOil_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode32_105": ("Desc_LiquidOil_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode35": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode36": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode37_178": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode38_902": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode39": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode40": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode41_1099": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode426": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode427": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode42_1294": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode43": ("Desc_SAM_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode430": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode431": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode435_26": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode437_30": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode439_1": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode43_UAID_40B076DF2F7932D901_1711042113": ("Desc_SAM_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode43_UAID_40B076DF2F7936D401_1733397541": ("Desc_SAM_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode43_UAID_40B076DF2F793ED901_1532454233": ("Desc_SAM_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode43_UAID_40B076DF2F7941D901_1404601764": ("Desc_SAM_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode440": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode441": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode442": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode443": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode444_0": ("Desc_LiquidOil_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode445": ("Desc_OreCopper_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode446_1": ("Desc_LiquidOil_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode447": ("Desc_LiquidOil_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode448": ("Desc_LiquidOil_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode449": ("Desc_Coal_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode451": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode452": ("Desc_Coal_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode453": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode454": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode457": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode458": ("Desc_LiquidOil_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode459": ("Desc_LiquidOil_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode460": ("Desc_LiquidOil_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode461": ("Desc_Sulfur_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode462": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode462_UAID_40B076DF2F7902E201_1630060169": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode462_UAID_40B076DF2F7907E201_1624182051": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode462_UAID_40B076DF2F790CE201_2008279933": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode463": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode464": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode464_UAID_40B076DF2F790EE201_1850696287": ("Desc_Stone_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode464_UAID_40B076DF2F790FE201_1577140465": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode464_UAID_40B076DF2F7914E201_2026233335": ("Desc_Stone_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode464_UAID_40B076DF2F7915E201_1334543513": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode465": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode466": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode467": ("Desc_Sulfur_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode469": ("Desc_Coal_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode46_2284": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode474_UAID_40B076DF2F7983DF01_2128950703": ("Desc_RawQuartz_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode474_UAID_40B076DF2F798DDF01_1645035472": ("Desc_RawQuartz_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode474_UAID_40B076DF2F798EDF01_2134364650": ("Desc_RawQuartz_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode476": ("Desc_OreBauxite_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode477": ("Desc_OreBauxite_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode479": ("Desc_OreBauxite_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode47_3066": ("Desc_SAM_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode480": ("Desc_OreBauxite_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode481": ("Desc_OreBauxite_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode484": ("Desc_OreUranium_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode484_UAID_40B076DF2F79E0DF01_2091429101": ("Desc_OreUranium_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode485": ("Desc_OreBauxite_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode486": ("Desc_OreBauxite_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode487": ("Desc_OreGold_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode487_UAID_40B076DF2F7934DF01_1597642799": ("Desc_OreGold_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode488": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode489": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode49": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode490": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode491": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode492": ("Desc_OreCopper_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode493": ("Desc_OreCopper_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode494": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode495": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode496": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode497_1": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode498": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode499": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode500": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode501": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode502": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode503": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode504": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode505": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode506": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode507": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode508": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode509": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode510": ("Desc_Sulfur_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode511": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode512": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode513": ("Desc_OreCopper_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode514": ("Desc_OreCopper_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode515": ("Desc_OreCopper_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode516": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode517": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode518": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode519": ("Desc_SAM_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode519_UAID_40B076DF2F79D3D901_1586151453": ("Desc_SAM_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode520": ("Desc_RawQuartz_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode521": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode521_UAID_40B076DF2F79C3E101_1100698081": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode521_UAID_40B076DF2F79C3E101_1735462083": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode522": ("Desc_RawQuartz_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode523_UAID_40B076DF2F7987DF01_1117795413": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode524_UAID_40B076DF2F798ADF01_1172524943": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode528": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode529": ("Desc_OreBauxite_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode530": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode531": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode532": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode533": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode534": ("Desc_Stone_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode535": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode536": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode537": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode538": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode539": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode53_510": ("Desc_OreCopper_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode540": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode541": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode542": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode543": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode544": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode545": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode546": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode547": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode547_UAID_40B076DF2F79ADE101_1836911209": ("Desc_OreCopper_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode547_UAID_40B076DF2F79AEE101_1979010387": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode548": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode549": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode54_833": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode550": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode551": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode552": ("Desc_RawQuartz_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode553": ("Desc_Stone_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode554": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode555": ("Desc_Stone_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode556": ("Desc_Stone_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode557": ("Desc_Stone_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode558": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode559": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode55_1215": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode560": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode561": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode562": ("Desc_OreCopper_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode563": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode563_UAID_40B076DF2F79B7E101_1869159978": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode563_UAID_40B076DF2F79B8E101_1620414156": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode563_UAID_40B076DF2F79B9E101_1570060334": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode563_UAID_40B076DF2F79BBE101_1434258671": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode564": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode565_8": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode566": ("Desc_OreBauxite_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode567": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode568": ("Desc_OreBauxite_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode569": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode570": ("Desc_OreGold_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode571": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode573_UAID_40B076DF2F795EE801_1339162695": ("Desc_Coal_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode573_UAID_40B076DF2F796BE101_1963012602": ("Desc_Coal_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode573_UAID_40B076DF2F796FE101_1569477308": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode573_UAID_40B076DF2F7971E101_2069219665": ("Desc_Coal_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode573_UAID_40B076DF2F7972E101_1083579843": ("Desc_Coal_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode573_UAID_40B076DF2F7973E101_1125437021": ("Desc_Coal_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode573_UAID_40B076DF2F7974E101_1439035199": ("Desc_Coal_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode573_UAID_40B076DF2F7974E101_1674467201": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode573_UAID_40B076DF2F797DE001_1807610722": ("Desc_Coal_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode573_UAID_40B076DF2F7980E001_1705275252": ("Desc_Coal_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode573_UAID_40B076DF2F7981E001_1464253430": ("Desc_Coal_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode573_UAID_40B076DF2F7983E001_1088885785": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode573_UAID_40B076DF2F7983E001_1840982787": ("Desc_Coal_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode573_UAID_40B076DF2F7984E001_1384492965": ("Desc_Coal_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode573_UAID_40B076DF2F7984E001_1664435967": ("Desc_Coal_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode573_UAID_40B076DF2F79ACE101_1257410031": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode574": ("Desc_OreGold_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode575": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode576": ("Desc_OreUranium_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode577": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode578": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode579": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode57_UAID_40B076DF2F7935DF01_1413169977": ("Desc_RawQuartz_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode57_UAID_40B076DF2F7991DF01_1459615180": ("Desc_RawQuartz_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode580": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode581": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode582": ("Desc_Sulfur_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode583_1": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode584": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode585": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode586": ("Desc_Stone_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode587": ("Desc_Coal_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode588": ("Desc_RawQuartz_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode588_UAID_40B076DF2F79CEDF01_1910960903": ("Desc_RawQuartz_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode589": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode589_UAID_40B076DF2F79B1E101_1767545917": ("Desc_Stone_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode589_UAID_40B076DF2F79B2E101_1298360096": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode590": ("Desc_Coal_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode591": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode592": ("Desc_OreIron_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode593": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode594": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode595": ("Desc_OreBauxite_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode596": ("Desc_OreBauxite_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode597": ("Desc_OreBauxite_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode598_0": ("Desc_OreUranium_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode599": ("Desc_Coal_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode59_755": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode5_381": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode600": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode601": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode602": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode603": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode604": ("Desc_Coal_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode605": ("Desc_Coal_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode606": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode607": ("Desc_SAM_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode609": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode60_984": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode610": ("Desc_Coal_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode611": ("Desc_Coal_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode612": ("Desc_Coal_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode613": ("Desc_Sulfur_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode614": ("Desc_Coal_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode615": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode616": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode617": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode618": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode619": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode62": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode620": ("Desc_Coal_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode621": ("Desc_Coal_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode622": ("Desc_Coal_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode623": ("Desc_Coal_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode624": ("Desc_Sulfur_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode632": ("Desc_OreUranium_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode633": ("Desc_OreBauxite_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode634": ("Desc_OreBauxite_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode635": ("Desc_OreBauxite_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode636": ("Desc_OreBauxite_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode65_1865": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode66": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode67_2193": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode68_2514": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode69_UAID_A036BCACDEB0A7A601_1261875850": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode6_379": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode70_3132": ("Desc_OreGold_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode71_736": ("Desc_Sulfur_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode71_UAID_40B076DF2F7912DC01_2042985647": ("Desc_Sulfur_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode71_UAID_40B076DF2F7923DB01_2085455593": ("Desc_Sulfur_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode71_UAID_40B076DF2F7924DB01_1576108771": ("Desc_Sulfur_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode71_UAID_40B076DF2F7925DB01_1453678949": ("Desc_Sulfur_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode71_UAID_40B076DF2F7929DB01_1177072656": ("Desc_Sulfur_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode71_UAID_40B076DF2F797CDB01_1695622247": ("Desc_Sulfur_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode71_UAID_40B076DF2F79B9DB01_1490254983": ("Desc_Sulfur_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode72_998": ("Desc_OreGold_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode73_6071": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode74": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode75_6425": ("Desc_OreCopper_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode76": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode77": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode78_1097": ("Desc_SAM_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode7_380": ("Desc_Coal_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode80": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode81": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode82": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode83": ("Desc_OreCopper_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode83_UAID_40B076DF2F79FBE101_1618730935": ("Desc_OreCopper_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode83_UAID_40B076DF2F79FFE101_1122581639": ("Desc_OreCopper_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode84": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode85": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode86": ("Desc_LiquidOil_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode87": ("Desc_LiquidOil_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode88": ("Desc_LiquidOil_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode89": ("Desc_LiquidOil_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode90_482": ("Desc_OreIron_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode91_785": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode92": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode93_5": ("Desc_Stone_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode94_406": ("Desc_OreCopper_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode95_579": ("Desc_OreIron_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode96_886": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode97_1": ("Desc_Stone_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNode98": ("Desc_LiquidOil_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode99": ("Desc_SAM_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser10_3650": ("Desc_Geyser_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser11_3803": ("Desc_Geyser_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser12_3894": ("Desc_Geyser_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser13_3999": ("Desc_Geyser_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser14": ("Desc_Geyser_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser15": ("Desc_Geyser_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser18": ("Desc_Geyser_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser19": ("Desc_Geyser_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser2_581": ("Desc_Geyser_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser4_1615": ("Desc_Geyser_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser7_2873": ("Desc_Geyser_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser8": ("Desc_Geyser_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser9_3239": ("Desc_Geyser_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser_76": ("Desc_Geyser_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser_C_UAID_40B076DF2F792DE001_1228687627": ("Desc_Geyser_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser_C_UAID_40B076DF2F792EE001_1257671809": ("Desc_Geyser_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser_C_UAID_40B076DF2F792FE001_1083532997": ("Desc_Geyser_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser_C_UAID_40B076DF2F7967E001_1786196831": ("Desc_Geyser_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser_C_UAID_40B076DF2F796AE001_1661824368": ("Desc_Geyser_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser_C_UAID_40B076DF2F796AE001_1928280369": ("Desc_Geyser_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser_C_UAID_40B076DF2F796CE001_1156904726": ("Desc_Geyser_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser_C_UAID_40B076DF2F796DE001_2106907903": ("Desc_Geyser_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser_C_UAID_40B076DF2F796EE001_1440606080": ("Desc_Geyser_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser_C_UAID_40B076DF2F796FE001_1768243264": ("Desc_Geyser_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser_C_UAID_40B076DF2F7974E001_1257931119": ("Desc_Geyser_C", Purity.NORMAL),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser_C_UAID_40B076DF2F7975E001_2124245305": ("Desc_Geyser_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser_C_UAID_40B076DF2F797AE001_1940806190": ("Desc_Geyser_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser_C_UAID_40B076DF2F797AE001_2137062191": ("Desc_Geyser_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser_C_UAID_40B076DF2F79ADDD01_1447318011": ("Desc_Geyser_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser_C_UAID_40B076DF2F79ADDD01_1602669012": ("Desc_Geyser_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNodeGeyser_C_UAID_40B076DF2F79C7DB01_1750096454": ("Desc_Geyser_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode_700": ("Desc_Coal_C", Purity.PURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode_C_UAID_40B076DF2F794DE201_1841969367": ("Desc_OreCopper_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode_C_UAID_40B076DF2F794FE201_2126930721": ("Desc_OreCopper_C", Purity.IMPURE),
   "Persistent_Level:PersistentLevel.BP_ResourceNode_C_UAID_A036BCACDEB0A6A601_2086848673": ("Desc_OreCopper_C", Purity.PURE),
}

READABLE_PATH_NAME_CORRECTIONS = {
   # Project Assembly Phases
   "GP_Project_Assembly_Phase_0": "Phase 0: Onboarding",
   "GP_Project_Assembly_Phase_1": "Phase 1: Distribution Platform",
   "GP_Project_Assembly_Phase_2": "Phase 2: Construction Dock",
   "GP_Project_Assembly_Phase_3": "Phase 3: Main Body",
   "GP_Project_Assembly_Phase_4": "Phase 4: Propulsion Systems",
   "GP_Project_Assembly_Phase_5": "Phase 5: Assembly",
   "GP_Project_Assembly_Phase_6": "Phase 6: Completing",
   "GP_Project_Assembly_Phase_7": "Phase 7: Completed",

   # Vehicles
   "BP_StartingPod_C": "Starting Pod",
   "BP_DroneTransport_C": "Drone",
   "BP_Explorer_C": "Explorer",
   "BP_FreightWagon_C": "Freight Car",
   "BP_Golfcart_C": "Factory Cart (TM)",
   "BP_GolfcartGold_C": "Factory Cart (Gold)",
   "BP_Locomotive_C": "Electric Locomotive",
   "BP_Tractor_C": "Tractor",
   "BP_Train_C": "Train",
   "BP_Truck_C": "Truck",
   "BP_VehicleTargetPoint_C": "Vehicle Target Point",
   "Testa_BP_WB_C": "Cyber Wagon",

   # Equipment
   "BP_EqDescZipLine_C": "Zipline",
   "BP_EquipmentDescriptorBeacon_C": "Beacon",
   "BP_EquipmentDescriptorBuildGun_C": "Build Gun",
   "BP_EquipmentDescriptorCandyCane_C": "Candy Cane Basher",
   "BP_EquipmentDescriptorCupGold_C": "'Employee of the Planet' Cup",
   "BP_EquipmentDescriptorCup_C": "Cup",
   "BP_EquipmentDescriptorGasmask_C": "Gas Mask",
   "BP_EquipmentDescriptorHazmatSuit_C": "Hazmat Suit",
   "BP_EquipmentDescriptorHoverPack_C": "Hover Pack",
   "BP_EquipmentDescriptorJetPack_C": "Jetpack",
   "BP_EquipmentDescriptorJumpingStilts_C": "Blade Runners",
   "BP_EquipmentDescriptorMachinegun_C": "Machine Gun",
   "BP_EquipmentDescriptorNobeliskDetonator_C": "Nobelisk Detonator",
   "BP_EquipmentDescriptorObjectScanner_C": "Object Scanner",
   "BP_EquipmentDescriptorResourceMiner_C": "Portable Miner",
   "BP_EquipmentDescriptorRifleMk2_C": "Rifle Mk.2",
   "BP_EquipmentDescriptorRifle_C": "Rifle",
   "BP_EquipmentDescriptorShockShank_C": "Xeno-Zapper",
   "BP_EquipmentDescriptorSnowballMittens_C": "Snowball Pile",
   "BP_EquipmentDescriptorStunSpear_C": "Xeno-Basher",
   "BP_ItemDescriptorPortableMiner_C": "Portable Miner",

   # Creatures
   "Desc_HogAlpha_C": "Alpha Hog",
   "Desc_HogBasic_C": "Fluffy-tailed Hog",
   "Desc_HogCliff_C": "Cliff Hog",
   "Desc_HogNuclear_C": "Radioactive Cliff Hog",
   "Desc_NonflyingBird_C": "Non-flying Bird",  # Technically "Non-flying Birb"
   "Desc_SpaceGiraffe_C": "Space Giraffe-Tick-Penguin-Whale Thing",
   "Desc_SpaceRabbit_C": "Lizard Doggo",
   "Desc_SpitterAquatic_Alpha_C": "Alpha Aquatic Spitter",
   "Desc_SpitterAquatic_Small_C": "Small Aquatic Spitter",
   "Desc_SpitterDesert_Alpha_C": "Alpha Desert Spitter",
   "Desc_SpitterDesert_Small_C": "Small Desert Spitter",
   "Desc_SpitterForest_Alpha_C": "Alpha Forest Spitter",
   "Desc_SpitterForest_Red_Alpha_C": "Alpha Red Forest Spitter",
   "Desc_SpitterForest_Small_C": "Small Forest Spitter",
   "Desc_SpitterForest_Small_Red_C": "Small Red Forest Spitter",
   "Desc_StingerAlpha_C": "Alpha Stinger",
   "Desc_StingerElite_C": "Gas Stinger",
   "Desc_StingerSmall_C": "Small Stinger",
   "Char_AlphaHog_C": "Alpha Hog",
   "Char_CliffHog_C": "Cliff Hog",
   "Char_EliteStinger_C": "Gas Stinger",
   "Char_Hog_C": "Fluffy-tailed Hog",
   "Char_NonFlyingBird_C": "Non-flying Bird",  # Technically "Non-flying Birb"
   "Char_NuclearHog_C": "Radioactive Cliff Hog",
   "Char_SpaceGiraffe_C": "Space Giraffe-Tick-Penguin-Whale Thing",
   "Char_SpaceRabbit_C": "Lizard Doggo",
   "Char_SpitterAquaticAlpha_C": "Alpha Aquatic Spitter",
   "Char_SpitterAquaticSmall_C": "Small Aquatic Spitter",
   "Char_SpitterDesertAlpha_C": "Alpha Desert Spitter",
   "Char_SpitterDesertSmall_C": "Small Desert Spitter",
   "Char_SpitterForestAlpha_C": "Alpha Forest Spitter",
   "Char_SpitterForestRedAlpha_C": "Alpha Red Forest Spitter",
   "Char_SpitterForestRedSmall_C": "Small Red Forest Spitter",
   "Char_SpitterForestSmall_C": "Small Forest Spitter",
   "Char_Stinger_C": "Stinger",
   "Char_Stinger_Child_C": "Small Stinger",

   # Buildables
   "BP_ProjectAssembly_C": "Space Elevator Terminal",  # This is a guess
   "Build_AlienPowerBuilding_C": "Alien Power Augmenter",
   "Build_AssemblerMk1_C": "Assembler",
   "Build_Beam_C": "Metal Beam",
   "Build_Beam_Connector_C": "Beam Connector",
   "Build_Beam_Connector_Double_C": "Beam Connector Double",
   "Build_Beam_Painted_C": "Painted Beam",
   "Build_Beam_Support_C": "Beam Support",
   "Build_Blender_C": "Blender",
   "Build_BlueprintDesigner_C": "Blueprint Designer",
   "Build_Blueprint_C": "Factory Blueprint",
   "Build_CandyCaneDecor_C": "Candy Cane",
   "Build_CatwalkCorner_C": "Catwalk Corner",
   "Build_CatwalkCross_C": "Catwalk Crossing",
   "Build_CatwalkRamp_C": "Catwalk Ramp",
   "Build_CatwalkStairs_C": "Catwalk Stairs",
   "Build_CatwalkStraight_C": "Catwalk Straight",
   "Build_CatwalkT_C": "Catwalk T-Crossing",
   "Build_CeilingLight_C": "Ceiling Light",
   "Build_CentralStorage_C": "Dimensional Depot Uploader",
   "Build_Concrete_Barrier_01_C": "Road Barrier",
   "Build_ConstructorMk1_C": "Constructor",
   "Build_Converter_C": "Converter",
   "Build_ConveyorAttachmentMerger_C": "Conveyor Merger",
   "Build_ConveyorAttachmentSplitterProgrammable_C": "Programmable Splitter",
   "Build_ConveyorAttachmentSplitterSmart_C": "Smart Splitter",
   "Build_ConveyorAttachmentSplitter_C": "Conveyor Splitter",
   "Build_ConveyorBeltMk1_C": "Conveyor Belt Mk.1",
   "Build_ConveyorBeltMk2_C": "Conveyor Belt Mk.2",
   "Build_ConveyorBeltMk3_C": "Conveyor Belt Mk.3",
   "Build_ConveyorBeltMk4_C": "Conveyor Belt Mk.4",
   "Build_ConveyorBeltMk5_C": "Conveyor Belt Mk.5",
   "Build_ConveyorBeltMk6_C": "Conveyor Belt Mk.6",
   "Build_ConveyorCeilingAttachment_C": "Conveyor Ceiling Mount",
   "Build_ConveyorLiftMk1_C": "Conveyor Lift Mk.1",
   "Build_ConveyorLiftMk2_C": "Conveyor Lift Mk.2",
   "Build_ConveyorLiftMk3_C": "Conveyor Lift Mk.3",
   "Build_ConveyorLiftMk4_C": "Conveyor Lift Mk.4",
   "Build_ConveyorLiftMk5_C": "Conveyor Lift Mk.5",
   "Build_ConveyorLiftMk6_C": "Conveyor Lift Mk.6",
   "Build_ConveyorPoleStackable_C": "Stackable Conveyor Pole",
   "Build_ConveyorPoleWall_C": "Conveyor Wall Mount",
   "Build_ConveyorPole_C": "Conveyor Pole",
   "Build_DownQuarterPipeInCorner_Asphalt_8x4_C": "Inverted Inner Corner Quarter Pipe (Asphalt)",
   "Build_DownQuarterPipeInCorner_ConcretePolished_8x4_C": "Inverted Inner Corner Quarter Pipe (Polished Concrete)",
   "Build_DownQuarterPipeInCorner_Concrete_8x4_C": "Inverted Inner Corner Quarter Pipe (Concrete)",
   "Build_DownQuarterPipeInCorner_Grip_8x4_C": "Inverted Inner Corner Quarter Pipe (Grip)",
   "Build_DownQuarterPipeOutCorner_Asphalt_8x4_C": "Inverted Outer Corner Quarter Pipe (Asphalt)",
   "Build_DownQuarterPipeOutCorner_ConcretePolished_8x4_C": "Inverted Outer Corner Quarter Pipe (Polished Concrete)",
   "Build_DownQuarterPipeOutCorner_Concrete_8x4_C": "Inverted Outer Corner Quarter Pipe (Concrete)",
   "Build_DownQuarterPipeOutCorner_Grip_8x4_C": "Inverted Outer Corner Quarter Pipe (Grip)",
   "Build_DownQuarterPipe_Asphalt_8x4_C": "Inverted Quarter Pipe (Asphalt)",
   "Build_DownQuarterPipe_ConcretePolished_8x4_C": "Inverted Quarter Pipe (Polished Concrete)",
   "Build_DownQuarterPipe_Concrete_8x4_C": "Inverted Quarter Pipe (Concrete)",
   "Build_DownQuarterPipe_Grip_8x4_C": "Inverted Quarter Pipe (Grip)",
   "Build_DroneStation_C": "Drone Port",
   "Build_Fence_01_C": "Industrial Railing",
   "Build_Flat_Frame_01_C": "Frame Floor",
   "Build_FloodlightPole_C": "Flood Light Tower",
   "Build_FloodlightWall_C": "Wall Mounted Flood Light",
   "Build_FoundationGlass_01_C": "Glass Frame Foundation",
   "Build_FoundationPassthrough_Hypertube_C": "Hypertube Floor Hole",
   "Build_FoundationPassthrough_Lift_C": "Conveyor Lift Floor Hole",
   "Build_FoundationPassthrough_Pipe_C": "Pipeline Floor Hole",
   "Build_Foundation_8x1_01_C": "Foundation 1m",
   "Build_Foundation_8x2_01_C": "Foundation 2m",
   "Build_Foundation_8x4_01_C": "Foundation 4m",
   "Build_Foundation_Asphalt_8x1_C": "Foundation 1m (Asphalt)",
   "Build_Foundation_Asphalt_8x2_C": "Foundation 2m (Asphalt)",
   "Build_Foundation_Asphalt_8x4_C": "Foundation 4m (Asphalt)",
   "Build_Foundation_ConcretePolished_8x1_C": "Foundation 1m (Polished Concrete)",
   "Build_Foundation_ConcretePolished_8x2_2_C": "Foundation 2m (Polished Concrete)",
   "Build_Foundation_ConcretePolished_8x4_C": "Foundation 4m (Polished Concrete)",
   "Build_Foundation_Concrete_8x1_C": "Foundation 1m (Concrete)",
   "Build_Foundation_Concrete_8x2_C": "Foundation 2m (Concrete)",
   "Build_Foundation_Concrete_8x4_C": "Foundation 4m (Concrete)",
   "Build_Foundation_Frame_01_C": "Frame Foundation",
   "Build_Foundation_Metal_8x1_C": "Foundation 1m (Metal)",
   "Build_Foundation_Metal_8x2_C": "Foundation 2m (Metal)",
   "Build_Foundation_Metal_8x4_C": "Foundation 4m (Metal)",
   "Build_FoundryMk1_C": "Foundry",
   "Build_FrackingExtractor_C": "Resource Well Extractor",
   "Build_FrackingSmasher_C": "Resource Well Pressurizer",
   "Build_Gate_Automated_8x4_C": "Automated Gate",
   "Build_GeneratorBiomass_Automated_C": "Biomass Burner",
   "Build_GeneratorBiomass_C": "Biomass Burner (without input)",
   "Build_GeneratorCoal_C": "Coal Generator",
   "Build_GeneratorFuel_C": "Fuel Generator",
   "Build_GeneratorGeoThermal_C": "Geothermal Generator",
   "Build_GeneratorIntegratedBiomass_C": "Biomass Burner",
   "Build_GeneratorNuclear_C": "Nuclear Power Plant",
   "Build_HadronCollider_C": "Particle Accelerator",
   "Build_HubTerminal_C": "HUB Terminal",
   "Build_HyperPoleStackable_C": "Stackable Hypertube Support",
   "Build_HyperTubeWallHole_C": "Hypertube Wall Hole",
   "Build_HyperTubeWallSupport_C": "Hypertube Wall Support",
   "Build_IndustrialTank_C": "Industrial Fluid Buffer",
   "Build_InvertedRamp_Asphalt_8x1_C": "Inv. Ramp 1m (Asphalt)",
   "Build_InvertedRamp_Asphalt_8x2_C": "Inv. Ramp 2m (Asphalt)",
   "Build_InvertedRamp_Asphalt_8x4_C": "Inv. Ramp 4m (Asphalt)",
   "Build_InvertedRamp_Concrete_8x1_C": "Inv. Ramp 1m (Concrete)",
   "Build_InvertedRamp_Concrete_8x2_C": "Inv. Ramp 2m (Concrete)",
   "Build_InvertedRamp_Concrete_8x4_C": "Inv. Ramp 4m (Concrete)",
   "Build_InvertedRamp_DCorner_Asphalt_8x1_C": "Inv. Down Corner 1m (Asphalt)",
   "Build_InvertedRamp_DCorner_Asphalt_8x2_C": "Inv. Down Corner 2m (Asphalt)",
   "Build_InvertedRamp_DCorner_Asphalt_8x4_C": "Inv. Down Corner 4m (Asphalt)",
   "Build_InvertedRamp_DCorner_Concrete_8x1_C": "Inv. Down Corner 1m (Concrete)",
   "Build_InvertedRamp_DCorner_Concrete_8x2_C": "Inv. Down Corner 2m (Concrete)",
   "Build_InvertedRamp_DCorner_Concrete_8x4_C": "Inv. Down Corner 4m (Concrete)",
   "Build_InvertedRamp_DCorner_Metal_8x1_C": "Inv. Down Corner 1m (Metal)",
   "Build_InvertedRamp_DCorner_Metal_8x2_C": "Inv. Down Corner 2m (Metal)",
   "Build_InvertedRamp_DCorner_Metal_8x4_C": "Inv. Down Corner 4m (Metal)",
   "Build_InvertedRamp_DCorner_Polished_8x1_C": "Inv. Down Corner 1m (Polished)",
   "Build_InvertedRamp_DCorner_Polished_8x2_C": "Inv. Down Corner 2m (Polished)",
   "Build_InvertedRamp_DCorner_Polished_8x4_C": "Inv. Down Corner 4m (Polished)",
   "Build_InvertedRamp_Metal_8x1_C": "Inv. Ramp 1m (Metal)",
   "Build_InvertedRamp_Metal_8x2_C": "Inv. Ramp 2m (Metal)",
   "Build_InvertedRamp_Metal_8x4_C": "Inv. Ramp 4m (Metal)",
   "Build_InvertedRamp_Polished_8x1_C": "Inv. Ramp 1m (Polished)",
   "Build_InvertedRamp_Polished_8x2_C": "Inv. Ramp 2m (Polished)",
   "Build_InvertedRamp_Polished_8x4_C": "Inv. Ramp 4m (Polished)",
   "Build_InvertedRamp_UCorner_Asphalt_8x1_C": "Inv. Up Corner 1m (Asphalt)",
   "Build_InvertedRamp_UCorner_Asphalt_8x2_C": "Inv. Up Corner 2m (Asphalt)",
   "Build_InvertedRamp_UCorner_Asphalt_8x4_C": "Inv. Up Corner 4m (Asphalt)",
   "Build_InvertedRamp_UCorner_Concrete_8x1_C": "Inv. Up Corner 1m (Concrete)",
   "Build_InvertedRamp_UCorner_Concrete_8x2_C": "Inv. Up Corner 2m (Concrete)",
   "Build_InvertedRamp_UCorner_Concrete_8x4_C": "Inv. Up Corner 4m (Concrete)",
   "Build_InvertedRamp_UCorner_Metal_8x1_C": "Inv. Up Corner 1m (Metal)",
   "Build_InvertedRamp_UCorner_Metal_8x2_C": "Inv. Up Corner 2m (Metal)",
   "Build_InvertedRamp_UCorner_Metal_8x4_C": "Inv. Up Corner 4m (Metal)",
   "Build_InvertedRamp_UCorner_Polished_8x1_C": "Inv. Up Corner 1m (Polished)",
   "Build_InvertedRamp_UCorner_Polished_8x2_C": "Inv. Up Corner 2m (Polished)",
   "Build_InvertedRamp_UCorner_Polished_8x4_C": "Inv. Up Corner 4m (Polished)",
   "Build_JumpPadAdjustable_C": "Jump Pad",
   "Build_Ladder_C": "Ladder",
   "Build_LandingPad_C": "U-Jelly Landing Pad",
   "Build_LightsControlPanel_C": "Lights Control Panel",
   "Build_LookoutTower_C": "Lookout Tower",
   "Build_Mam_C": "MAM",
   "Build_ManufacturerMk1_C": "Manufacturer",
   "Build_MinerMk1_C": "Miner Mk.1",
   "Build_MinerMk2_C": "Miner Mk.2",
   "Build_MinerMk3_C": "Miner Mk.3",
   "Build_OilPump_C": "Oil Extractor",
   "Build_OilRefinery_C": "Refinery",
   "Build_Packager_C": "Packager",
   "Build_PillarBase_C": "Big Pillar Support",
   "Build_PillarBase_Small_C": "Small Pillar Support",
   "Build_PillarMiddle_C": "Big Metal Pillar",
   "Build_PillarMiddle_Concrete_C": "Big Concrete Pillar",
   "Build_PillarMiddle_Frame_C": "Big Frame Pillar",
   "Build_PillarTop_C": "Pillar Top",
   "Build_Pillar_Small_Concrete_C": "Small Concrete Pillar",
   "Build_Pillar_Small_Frame_C": "Small Frame Pillar",
   "Build_Pillar_Small_Metal_C": "Small Metal Pillar",
   "Build_PipeHyperStart_C": "Hypertube Entrance",
   "Build_PipeHyperSupport_C": "Hypertube Support",
   "Build_PipeHyper_C": "Hypertube",
   "Build_PipeStorageTank_C": "Fluid Buffer",
   "Build_PipeSupportStackable_C": "Stackable Pipeline Support",
   "Build_PipelineFlowIndicator_C": "Pipeline Flow Indicator",  # Part of a Pipeline
   "Build_PipelineJunction_Cross_C": "Pipeline Junction Cross",
   "Build_PipelineMK2_C": "Pipeline Mk.2",
   "Build_PipelineMK2_NoIndicator_C": "Pipeline Mk.2 (No Indicator)",
   "Build_PipelinePumpMK2_C": "Pipeline Pump Mk.2",
   "Build_PipelinePump_C": "Pipeline Pump Mk.1",
   "Build_PipelineSupportWallHole_C": "Pipeline Wall Hole",
   "Build_PipelineSupportWall_C": "Pipeline Wall Support",
   "Build_PipelineSupport_C": "Pipeline Support",
   "Build_Pipeline_C": "Pipeline Mk.1",
   "Build_Pipeline_NoIndicator_C": "Pipeline Mk.1 (No Indicator)",
   "Build_Portal_C": "Main Portal",
   "Build_PortalSatellite_C": "Satellite Portal",
   "BUILD_Potty_mk1_C": "The HUB Toilet",
   "Build_PowerLine_C": "Power Line",
   "Build_PowerPoleMk1_C": "Power Pole Mk.1",
   "Build_PowerPoleMk2_C": "Power Pole Mk.2",
   "Build_PowerPoleMk3_C": "Power Pole Mk.3",
   "Build_PowerPoleWallDouble_C": "Double Wall Outlet Mk.1",
   "Build_PowerPoleWallDouble_Mk2_C": "Double Wall Outlet Mk.2",
   "Build_PowerPoleWallDouble_Mk3_C": "Double Wall Outlet Mk.3",
   "Build_PowerPoleWall_C": "Wall Outlet Mk.1",
   "Build_PowerPoleWall_Mk2_C": "Wall Outlet Mk.2",
   "Build_PowerPoleWall_Mk3_C": "Wall Outlet Mk.3",
   "Build_PowerStorageMk1_C": "Power Storage",
   "Build_PowerSwitch_C": "Power Switch",
   "Build_PowerTowerPlatform_C": "Power Tower Platform",
   "Build_PowerTower_C": "Power Tower",
   "Build_PriorityPowerSwitch_C": "Priority Power Switch",
   "Build_QuantumEncoder_C": "Quantum Encoder",
   "Build_QuarterPipeCorner_01_C": "Inner Corner Quarter Pipe",
   "Build_QuarterPipeCorner_02_C": "Inverted Inner Corner Quarter Pipe",
   "Build_QuarterPipeCorner_03_C": "Outer Corner Quarter Pipe",
   "Build_QuarterPipeCorner_04_C": "Inverted Outer Corner Quarter Pipe",
   "Build_QuarterPipeInCorner_Asphalt_8x4_C": "Inner Corner Quarter Pipe (Asphalt)",
   "Build_QuarterPipeInCorner_ConcretePolished_8x4_C": "Inner Corner Quarter Pipe (Polished Concrete)",
   "Build_QuarterPipeInCorner_Concrete_8x4_C": "Inner Corner Quarter Pipe (Concrete)",
   "Build_QuarterPipeInCorner_Grip_8x4_C": "Inner Corner Quarter Pipe (Grip)",
   "Build_QuarterPipeMiddleInCorner_Asphalt_8x1_C": "Inner Corner Extension 1m (Asphalt)",
   "Build_QuarterPipeMiddleInCorner_Asphalt_8x2_C": "Inner Corner Extension 2m (Asphalt)",
   "Build_QuarterPipeMiddleInCorner_Asphalt_8x4_C": "Inner Corner Extension 4m (Asphalt)",
   "Build_QuarterPipeMiddleInCorner_Concrete_8x1_C": "Inner Corner Extension 1m (Concrete)",
   "Build_QuarterPipeMiddleInCorner_Concrete_8x2_C": "Inner Corner Extension 2m (Concrete)",
   "Build_QuarterPipeMiddleInCorner_Concrete_8x4_C": "Inner Corner Extension 4m (Concrete)",
   "Build_QuarterPipeMiddleInCorner_Ficsit_8x1_C": "Inner Corner Extension 1m (FICSIT)",
   "Build_QuarterPipeMiddleInCorner_Ficsit_8x2_C": "Inner Corner Extension 2m (FICSIT)",
   "Build_QuarterPipeMiddleInCorner_Ficsit_8x4_C": "Inner Corner Extension 4m (FICSIT)",
   "Build_QuarterPipeMiddleInCorner_Grip_8x1_C": "Inner Corner Extension 1m (Grip)",
   "Build_QuarterPipeMiddleInCorner_Grip_8x2_C": "Inner Corner Extension 2m (Grip)",
   "Build_QuarterPipeMiddleInCorner_Grip_8x4_C": "Inner Corner Extension 4m (Grip)",
   "Build_QuarterPipeMiddleInCorner_PolishedConcrete_8x1_C": "Inner Corner Extension 1m (Polished Concrete)",
   "Build_QuarterPipeMiddleInCorner_PolishedConcrete_8x2_C": "Inner Corner Extension 2m (Polished Concrete)",
   "Build_QuarterPipeMiddleInCorner_PolishedConcrete_8x4_C": "Inner Corner Extension 4m (Polished Concrete)",
   "Build_QuarterPipeMiddleOutCorner_Asphalt_4x1_C": "Outer Corner Extension 1m (Asphalt)",
   "Build_QuarterPipeMiddleOutCorner_Asphalt_4x2_C": "Outer Corner Extension 2m (Asphalt)",
   "Build_QuarterPipeMiddleOutCorner_Asphalt_4x4_C": "Outer Corner Extension 4m (Asphalt)",
   "Build_QuarterPipeMiddleOutCorner_Concrete_4x1_C": "Outer Corner Extension 1m (Concrete)",
   "Build_QuarterPipeMiddleOutCorner_Concrete_4x2_C": "Outer Corner Extension 2m (Concrete)",
   "Build_QuarterPipeMiddleOutCorner_Concrete_4x4_C": "Outer Corner Extension 4m (Concrete)",
   "Build_QuarterPipeMiddleOutCorner_Ficsit_4x1_C": "Outer Corner Extension 1m (FICSIT)",
   "Build_QuarterPipeMiddleOutCorner_Ficsit_4x2_C": "Outer Corner Extension 2m (FICSIT)",
   "Build_QuarterPipeMiddleOutCorner_Ficsit_4x4_C": "Outer Corner Extension 4m (FICSIT)",
   "Build_QuarterPipeMiddleOutCorner_Grip_4x1_C": "Outer Corner Extension 1m (Grip)",
   "Build_QuarterPipeMiddleOutCorner_Grip_4x2_C": "Outer Corner Extension 2m (Grip)",
   "Build_QuarterPipeMiddleOutCorner_Grip_4x4_C": "Outer Corner Extension 4m (Grip)",
   "Build_QuarterPipeMiddleOutCorner_PolishedConcrete_4x1_C": "Outer Corner Extension 1m (Polished Concrete)",
   "Build_QuarterPipeMiddleOutCorner_PolishedConcrete_4x2_C": "Outer Corner Extension 2m (Polished Concrete)",
   "Build_QuarterPipeMiddleOutCorner_PolishedConcrete_4x4_C": "Outer Corner Extension 4m (Polished Concrete)",
   "Build_QuarterPipeMiddle_Asphalt_8x1_C": "Half 1m Foundation (Asphalt)",
   "Build_QuarterPipeMiddle_Asphalt_8x2_C": "Half 2m Foundation (Asphalt)",
   "Build_QuarterPipeMiddle_Asphalt_8x4_C": "Half 4m Foundation (Asphalt)",
   "Build_QuarterPipeMiddle_Concrete_8x1_C": "Half 1m Foundation (Concrete)",
   "Build_QuarterPipeMiddle_Concrete_8x2_C": "Half 2m Foundation (Concrete)",
   "Build_QuarterPipeMiddle_Concrete_8x4_C": "Half 4m Foundation (Concrete)",
   "Build_QuarterPipeMiddle_Ficsit_8x1_C": "Half 1m Foundation (FICSIT)",
   "Build_QuarterPipeMiddle_Ficsit_8x2_C": "Half 2m Foundation (FICSIT)",
   "Build_QuarterPipeMiddle_Ficsit_8x4_C": "Half 4m Foundation (FICSIT)",
   "Build_QuarterPipeMiddle_Grip_8x1_C": "Half 1m Foundation (Grip)",
   "Build_QuarterPipeMiddle_Grip_8x2_C": "Half 2m Foundation (Grip)",
   "Build_QuarterPipeMiddle_Grip_8x4_C": "Half 4m Foundation (Grip)",
   "Build_QuarterPipeMiddle_PolishedConcrete_8x1_C": "Half 1m Foundation (Polished Concrete)",
   "Build_QuarterPipeMiddle_PolishedConcrete_8x2_C": "Half 2m Foundation (Polished Concrete)",
   "Build_QuarterPipeMiddle_PolishedConcrete_8x4_C": "Half 4m Foundation (Polished Concrete)",
   "Build_QuarterPipeOutCorner_Asphalt_8x4_C": "Outer Corner Quarter Pipe (Asphalt)",
   "Build_QuarterPipeOutCorner_ConcretePolished_8x4_C": "Outer Corner Quarter Pipe (Polished Concrete)",
   "Build_QuarterPipeOutCorner_Concrete_8x4_C": "Outer Corner Quarter Pipe (Concrete)",
   "Build_QuarterPipeOutCorner_Grip_8x4_C": "Outer Corner Quarter Pipe (Grip)",
   "Build_QuarterPipe_02_C": "Inverted Quarter Pipe",
   "Build_QuarterPipe_Asphalt_8x4_C": "Quarter Pipe (Asphalt)",
   "Build_QuarterPipe_C": "Quarter Pipe",
   "Build_QuarterPipe_ConcretePolished_8x4_C": "Quarter Pipe (Polished Concrete)",
   "Build_QuarterPipe_Concrete_8x4_C": "Quarter Pipe (Concrete)",
   "Build_QuarterPipe_Grip_8x4_C": "Quarter Pipe (Grip)",
   "Build_RadarTower_C": "Radar Tower",
   "Build_Railing_01_C": "Modern Railing",
   "Build_RailroadBlockSignal_C": "Block Signal",
   "Build_RailroadPathSignal_C": "Path Signal",
   "Build_RailroadSwitchControl_C": "Railroad Switch Control",
   "Build_RailroadTrackIntegrated_C": "Integrated Platform Track",
   "Build_RailroadTrack_C": "Railway",
   "Build_RampDouble_8x1_C": "Double Ramp 2m",
   "Build_RampDouble_Asphalt_8x1_C": "Double Ramp 2m (Asphalt)",
   "Build_RampDouble_Asphalt_8x2_C": "Double Ramp 4m (Asphalt)",
   "Build_RampDouble_Asphalt_8x4_C": "Double Ramp 8m (Asphalt)",
   "Build_RampDouble_C": "Double Ramp 4m",
   "Build_RampDouble_Concrete_8x1_C": "Double Ramp 2m (Concrete)",
   "Build_RampDouble_Concrete_8x2_C": "Double Ramp 4m (Concrete)",
   "Build_RampDouble_Concrete_8x4_C": "Double Ramp 8m (Concrete)",
   "Build_RampDouble_Metal_8x1_C": "Double Ramp 2m (Metal)",
   "Build_RampDouble_Metal_8x2_C": "Double Ramp 4m (Metal)",
   "Build_RampDouble_Metal_8x4_C": "Double Ramp 8m (Metal)",
   "Build_RampDouble_Polished_8x1_C": "Double Ramp 2m (Polished)",
   "Build_RampDouble_Polished_8x2_C": "Double Ramp 4m (Polished)",
   "Build_RampDouble_Polished_8x4_C": "Double Ramp 8m (Polished)",
   "Build_RampInverted_8x1_C": "Inv. Ramp 1m",
   "Build_RampInverted_8x1_Corner_01_C": "Inv. Up Corner 1m",
   "Build_RampInverted_8x1_Corner_02_C": "Inv. Down Corner 1m",
   "Build_RampInverted_8x2_01_C": "Inv. Ramp 2m",
   "Build_RampInverted_8x2_Corner_01_C": "Inv. Up Corner 2m",
   "Build_RampInverted_8x2_Corner_02_C": "Inv. Down Corner 2m",
   "Build_RampInverted_8x4_Corner_01_C": "Inv. Up Corner 4m",
   "Build_RampInverted_8x4_Corner_02_C": "Inv. Down Corner 4m",
   "Build_Ramp_8x1_01_C": "Ramp 1m",
   "Build_Ramp_8x2_01_C": "Ramp 2m",
   "Build_Ramp_8x4_01_C": "Ramp 4m",
   "Build_Ramp_8x4_Inverted_01_C": "Inv. Ramp 4m",
   "Build_Ramp_8x8x8_C": "Double Ramp 8m",
   "Build_Ramp_Asphalt_8x1_C": "Ramp 1m (Asphalt)",
   "Build_Ramp_Asphalt_8x2_C": "Ramp 2m (Asphalt)",
   "Build_Ramp_Asphalt_8x4_C": "Ramp 4m (Asphalt)",
   "Build_Ramp_Concrete_8x1_C": "Ramp 1m (Concrete)",
   "Build_Ramp_Concrete_8x2_C": "Ramp 2m (Concrete)",
   "Build_Ramp_Concrete_8x4_C": "Ramp 4m (Concrete)",
   "Build_Ramp_Diagonal_8x1_01_C": "Down Corner Ramp 1m",
   "Build_Ramp_Diagonal_8x1_02_C": "Up Corner Ramp 1m",
   "Build_Ramp_Diagonal_8x2_01_C": "Down Corner Ramp 2m",
   "Build_Ramp_Diagonal_8x2_02_C": "Up Corner Ramp 2m",
   "Build_Ramp_Diagonal_8x4_01_C": "Down Corner Ramp 4m",
   "Build_Ramp_Diagonal_8x4_02_C": "Up Corner Ramp 4m",
   "Build_Ramp_DownCorner_Asphalt_8x1_C": "Down Corner Ramp 1m (Asphalt)",
   "Build_Ramp_DownCorner_Asphalt_8x2_C": "Down Corner Ramp 2m (Asphalt)",
   "Build_Ramp_DownCorner_Asphalt_8x4_C": "Down Corner Ramp 4m (Asphalt)",
   "Build_Ramp_DownCorner_Concrete_8x1_C": "Down Corner Ramp 1m (Concrete)",
   "Build_Ramp_DownCorner_Concrete_8x2_C": "Down Corner Ramp 2m (Concrete)",
   "Build_Ramp_DownCorner_Concrete_8x4_C": "Down Corner Ramp 4m (Concrete)",
   "Build_Ramp_DownCorner_Metal_8x1_C": "Down Corner Ramp 1m (Metal)",
   "Build_Ramp_DownCorner_Metal_8x2_C": "Down Corner Ramp 2m (Metal)",
   "Build_Ramp_DownCorner_Metal_8x4_C": "Down Corner Ramp 4m (Metal)",
   "Build_Ramp_DownCorner_Polished_8x1_C": "Down Corner Ramp 1m (Polished)",
   "Build_Ramp_DownCorner_Polished_8x2_C": "Down Corner Ramp 2m (Polished)",
   "Build_Ramp_DownCorner_Polished_8x4_C": "Down Corner Ramp 4m (Polished)",
   "Build_Ramp_Frame_01_C": "Frame Ramp",
   "Build_Ramp_Frame_Inverted_01_C": "Inverted Frame Ramp",
   "Build_Ramp_Metal_8x1_C": "Ramp 1m (Metal)",
   "Build_Ramp_Metal_8x2_C": "Ramp 2m (Metal)",
   "Build_Ramp_Metal_8x4_C": "Ramp 4m (Metal)",
   "Build_Ramp_Polished_8x1_C": "Ramp 1m (Polished)",
   "Build_Ramp_Polished_8x2_C": "Ramp 2m (Polished)",
   "Build_Ramp_Polished_8x4_C": "Ramp 4m (Polished)",
   "Build_Ramp_UpCorner_Asphalt_8x1_C": "Up Corner Ramp 1m (Asphalt)",
   "Build_Ramp_UpCorner_Asphalt_8x2_C": "Up Corner Ramp 2m (Asphalt)",
   "Build_Ramp_UpCorner_Asphalt_8x4_C": "Up Corner Ramp 4m (Asphalt)",
   "Build_Ramp_UpCorner_Concrete_8x1_C": "Up Corner Ramp 1m (Concrete)",
   "Build_Ramp_UpCorner_Concrete_8x2_C": "Up Corner Ramp 2m (Concrete)",
   "Build_Ramp_UpCorner_Concrete_8x4_C": "Up Corner Ramp 4m (Concrete)",
   "Build_Ramp_UpCorner_Metal_8x1_C": "Up Corner Ramp 1m (Metal)",
   "Build_Ramp_UpCorner_Metal_8x2_C": "Up Corner Ramp 2m (Metal)",
   "Build_Ramp_UpCorner_Metal_8x4_C": "Up Corner Ramp 4m (Metal)",
   "Build_Ramp_UpCorner_Polished_8x1_C": "Up Corner Ramp 1m (Polished)",
   "Build_Ramp_UpCorner_Polished_8x2_C": "Up Corner Ramp 2m (Polished)",
   "Build_Ramp_UpCorner_Polished_8x4_C": "Up Corner Ramp 4m (Polished)",
   "Build_ResourceSinkShop_C": "AWESOME Shop",
   "Build_ResourceSink_C": "AWESOME Sink",
   "Build_Roof_A_01_C": "Roof Flat (Asphalt)",
   "Build_Roof_A_02_C": "Roof 1m (Asphalt)",
   "Build_Roof_A_03_C": "Roof 2m (Asphalt)",
   "Build_Roof_A_04_C": "Roof 4m (Asphalt)",
   "Build_Roof_Metal_InCorner_01_C": "Inner Corner Roof 1m (Metal)",
   "Build_Roof_Metal_InCorner_02_C": "Inner Corner Roof 2m (Metal)",
   "Build_Roof_Metal_InCorner_03_C": "Inner Corner Roof 4m (Metal)",
   "Build_Roof_Metal_OutCorner_01_C": "Outer Corner Roof 1m (Metal)",
   "Build_Roof_Metal_OutCorner_02_C": "Outer Corner Roof 2m (Metal)",
   "Build_Roof_Metal_OutCorner_03_C": "Outer Corner Roof 4m (Metal)",
   "Build_Roof_Orange_01_C": "Roof Flat (Orange)",
   "Build_Roof_Orange_02_C": "Roof 1m (Orange)",
   "Build_Roof_Orange_03_C": "Roof 2m (Orange)",
   "Build_Roof_Orange_04_C": "Roof 4m (Orange)",
   "Build_Roof_Orange_InCorner_01_C": "Inner Corner Roof 1m (Orange)",
   "Build_Roof_Orange_InCorner_02_C": "Inner Corner Roof 2m (Orange)",
   "Build_Roof_Orange_InCorner_03_C": "Inner Corner Roof 4m (Orange)",
   "Build_Roof_Orange_OutCorner_01_C": "Outer Corner Roof 1m (Orange)",
   "Build_Roof_Orange_OutCorner_02_C": "Outer Corner Roof 2m (Orange)",
   "Build_Roof_Orange_OutCorner_03_C": "Outer Corner Roof 4m (Orange)",
   "Build_Roof_Tar_01_C": "Roof Flat (Tar)",
   "Build_Roof_Tar_02_C": "Roof 1m (Tar)",
   "Build_Roof_Tar_03_C": "Roof 2m (Tar)",
   "Build_Roof_Tar_04_C": "Roof 4m (Tar)",
   "Build_Roof_Tar_InCorner_01_C": "Inner Corner Roof 1m (Tar)",
   "Build_Roof_Tar_InCorner_02_C": "Inner Corner Roof 2m (Tar)",
   "Build_Roof_Tar_InCorner_03_C": "Inner Corner Roof 4m (Tar)",
   "Build_Roof_Tar_OutCorner_01_C": "Outer Corner Roof 1m (Tar)",
   "Build_Roof_Tar_OutCorner_02_C": "Outer Corner Roof 2m (Tar)",
   "Build_Roof_Tar_OutCorner_03_C": "Outer Corner Roof 4m (Tar)",
   "Build_Roof_Window_01_C": "Roof Flat (Window)",
   "Build_Roof_Window_02_C": "Roof 1m (Window)",
   "Build_Roof_Window_03_C": "Roof 2m (Window)",
   "Build_Roof_Window_04_C": "Roof 4m (Window)",
   "Build_Roof_Window_InCorner_01_C": "Inner Corner Roof 1m (Window)",
   "Build_Roof_Window_InCorner_02_C": "Inner Corner Roof 2m (Window)",
   "Build_Roof_Window_InCorner_03_C": "Inner Corner Roof 4m (Window)",
   "Build_Roof_Window_OutCorner_01_C": "Outer Corner Roof 1m (Window)",
   "Build_Roof_Window_OutCorner_02_C": "Outer Corner Roof 2m (Window)",
   "Build_Roof_Window_OutCorner_03_C": "Outer Corner Roof 4m (Window)",
   "Build_SignPole_C": "Sign Pole", # Not a separate item
   "Build_SM_RailingRamp_8x1_01_C": "SM_RailingRamp_8x1_01",
   "Build_SM_RailingRamp_8x2_01_C": "SM_RailingRamp_8x2_01",
   "Build_SM_RailingRamp_8x4_01_C": "SM_RailingRamp_8x4_01",
   "Build_SmelterMk1_C": "Smelter",
   "Build_SnowDispenser_C": "FICSMAS Snow Dispenser",
   "Build_Snowman_C": "Snowman",
   "Build_SpaceElevator_C": "Space Elevator",
   "Build_Stairs_Left_01_C": "Stairs Left",
   "Build_Stairs_Right_01_C": "Stairs Right",
   "Build_StandaloneWidgetSign_Huge_C": "Large Billboard",
   "Build_StandaloneWidgetSign_Large_C": "Small Billboard",
   "Build_StandaloneWidgetSign_Medium_C": "Display Sign",
   "Build_StandaloneWidgetSign_Portrait_C": "Portrait Sign",
   "Build_StandaloneWidgetSign_SmallVeryWide_C": "Label Sign 4m",
   "Build_StandaloneWidgetSign_SmallWide_C": "Label Sign 3m",
   "Build_StandaloneWidgetSign_Small_C": "Label Sign 2m",
   "Build_StandaloneWidgetSign_Square_C": "Square Sign 2m",
   "Build_StandaloneWidgetSign_Square_Small_C": "Square Sign 1m",
   "Build_StandaloneWidgetSign_Square_Tiny_C": "Square Sign 0.5m",
   "Build_SteelWall_8x1_C": "Basic Wall 1m",
   "Build_SteelWall_8x4_C": "Tilted Wall 4m",
   "Build_SteelWall_8x4_Gate_01_C": "Gate Hole Wall",
   "Build_SteelWall_8x4_Window_01_C": "Single Window",
   "Build_SteelWall_8x4_Window_02_C": "Reinforced Window",
   "Build_SteelWall_8x4_Window_03_C": "Frame Window",
   "Build_SteelWall_8x4_Window_04_C": "Panel Window",
   "Build_SteelWall_FlipTris_8x1_C": "Inv. Ramp Wall 1m",
   "Build_SteelWall_FlipTris_8x2_C": "Inv. Ramp Wall 2m",
   "Build_SteelWall_FlipTris_8x4_C": "Inv. Ramp Wall 4m",
   "Build_SteelWall_FlipTris_8x8_C": "Inv. Ramp Wall 8m",
   "Build_SteelWall_Tris_8x1_C": "Ramp Wall 1m",
   "Build_SteelWall_Tris_8x2_C": "Ramp Wall 2m",
   "Build_SteelWall_Tris_8x4_C": "Ramp Wall 4m",
   "Build_SteelWall_Tris_8x8_C": "Ramp Wall 8m",
   "Build_StorageBlueprint_C": "Blueprint Storage Box",
   "Build_StorageContainerMk1_C": "Storage Container",
   "Build_StorageContainerMk2_C": "Industrial Storage Container",
   "Build_StorageHazard_C": "Hazard Storage Box",
   "Build_StorageIntegrated_C": "Personal Storage Box",
   "Build_StorageMedkit_C": "Medical Storage Box",
   "Build_StoragePlayer_C": "Personal Storage Box",
   "Build_StreetLight_C": "Street Light",
   "Build_TetrominoGame_Computer_C": "Productive Packer Deluxe",
   "Build_TradingPost_C": "The HUB",
   "Build_TrainDockingStationLiquid_C": "Fluid Freight Platform",
   "Build_TrainDockingStation_C": "Freight Platform",
   "Build_TrainPlatformEmpty_02_C": "Empty Platform With Catwalk",
   "Build_TrainPlatformEmpty_C": "Empty Platform",
   "Build_TrainStation_C": "Train Station",
   "Build_TreeGiftProducer_C": "FICSMAS Gift Tree",
   "Build_TruckStation_C": "Truck Station",
   "Build_Valve_C": "Valve",
   "Build_WalkwayCross_C": "Walkway Crossing",
   "Build_WalkwayRamp_C": "Walkway Ramp",
   "Build_WalkwayStraight_C": "Walkway Straight",
   "Build_WalkwayT_C": "Walkway T-Crossing",
   "Build_WalkwayTrun_C": "Walkway Turn",
   "Build_WallSet_Steel_Angular_8x4_C": "Tilted Wall 4m",
   "Build_WallSet_Steel_Angular_8x8_C": "Tilted Wall 8m",
   "Build_Wall_8x4_01_C": "Basic Wall 4m",
   "Build_Wall_8x4_02_C": "Basic Wall 4m",
   "Build_Wall_Concrete_8x1_C": "Basic Wall 1m",
   "Build_Wall_Concrete_8x4_C": "Basic Wall 4m",
   "Build_Wall_Concrete_8x4_ConveyorHole_01_C": "Conveyor Wall x1",
   "Build_Wall_Concrete_8x4_ConveyorHole_02_C": "Conveyor Wall x2",
   "Build_Wall_Concrete_8x4_ConveyorHole_03_C": "Conveyor Wall x3",
   "Build_Wall_Concrete_8x4_Corner_01_C": "Tilted Corner Wall 4m",
   "Build_Wall_Concrete_8x4_Corner_2_C": "Tilted Concave Wall 4m",
   "Build_Wall_Concrete_8x4_Window_01_C": "Single Window",
   "Build_Wall_Concrete_8x4_Window_02_C": "Frame Window",
   "Build_Wall_Concrete_8x4_Window_03_C": "Panel Window",
   "Build_Wall_Concrete_8x4_Window_04_C": "Reinforced Window",
   "Build_Wall_Concrete_8x8_Corner_01_C": "Tilted Corner Wall 8m",
   "Build_Wall_Concrete_8x8_Corner_2_C": "Tilted Concave Wall 8m",
   "Build_Wall_Concrete_Angular_8x4_C": "Tilted Wall 4m",
   "Build_Wall_Concrete_Angular_8x8_C": "Tilted Wall 8m",
   "Build_Wall_Concrete_CDoor_8x4_C": "Center Door Wall",
   "Build_Wall_Concrete_FlipTris_8x1_C": "Inv. Ramp Wall 1m",
   "Build_Wall_Concrete_FlipTris_8x2_C": "Inv. Ramp Wall 2m",
   "Build_Wall_Concrete_FlipTris_8x4_C": "Inv. Ramp Wall 4m",
   "Build_Wall_Concrete_FlipTris_8x8_C": "Inv. Ramp Wall 8m",
   "Build_Wall_Concrete_Gate_8x4_C": "Gate Hole Wall",
   "Build_Wall_Concrete_SDoor_8x4_C": "Side Door Wall",
   "Build_Wall_Concrete_Tris_8x1_C": "Ramp Wall 1m (Concrete)",
   "Build_Wall_Concrete_Tris_8x2_C": "Ramp Wall 2m (Concrete)",
   "Build_Wall_Concrete_Tris_8x4_C": "Ramp Wall 4m (Concrete)",
   "Build_Wall_Concrete_Tris_8x8_C": "Ramp Wall 8m (Concrete)",
   "Build_Wall_Conveyor_8x4_01_C": "Conveyor Wall x3",
   "Build_Wall_Conveyor_8x4_01_Steel_C": "Conveyor Wall x3",
   "Build_Wall_Conveyor_8x4_02_C": "Conveyor Wall x2",
   "Build_Wall_Conveyor_8x4_02_Steel_C": "Conveyor Wall x2",
   "Build_Wall_Conveyor_8x4_03_C": "Conveyor Wall x1",
   "Build_Wall_Conveyor_8x4_03_Steel_C": "Conveyor Wall x1",
   "Build_Wall_Conveyor_8x4_04_C": "Wall Conveyor Perpendicular",
   "Build_Wall_Conveyor_8x4_04_Steel_C": "Wall Conveyor Perpendicular",
   "Build_Wall_Door_8x4_01_C": "Center Door Wall",
   "Build_Wall_Door_8x4_01_Steel_C": "Center Door Wall",
   "Build_Wall_Door_8x4_03_C": "Side Door Wall",
   "Build_Wall_Door_8x4_03_Steel_C": "Side Door Wall",
   "Build_Wall_Frame_01_C": "Frame Wall",
   "Build_Wall_Gate_8x4_01_C": "Gate Hole Wall",
   "Build_Wall_Orange_8x1_C": "Basic Wall 1m",
   "Build_Wall_Orange_8x4_Corner_01_C": "Tilted Corner Wall 4m",
   "Build_Wall_Orange_8x4_Corner_02_C": "Tilted Concave Wall 4m",
   "Build_Wall_Orange_8x8_Corner_01_C": "Tilted Corner Wall 8m",
   "Build_Wall_Orange_8x8_Corner_02_C": "Tilted Concave Wall 8m",
   "Build_Wall_Orange_Angular_8x4_C": "Tilted Wall 4m",
   "Build_Wall_Orange_Angular_8x8_C": "Tilted Wall 8m",
   "Build_Wall_Orange_FlipTris_8x1_C": "Inv. Ramp Wall 1m",
   "Build_Wall_Orange_FlipTris_8x2_C": "Inv. Ramp Wall 2m",
   "Build_Wall_Orange_FlipTris_8x4_C": "Inv. Ramp Wall 4m",
   "Build_Wall_Orange_FlipTris_8x8_C": "Inv. Ramp Wall 8m",
   "Build_Wall_Orange_Tris_8x1_C": "Ramp Wall 1m (Orange)",
   "Build_Wall_Orange_Tris_8x2_C": "Ramp Wall 2m (Orange)",
   "Build_Wall_Orange_Tris_8x4_C": "Ramp Wall 4m (Orange)",
   "Build_Wall_Orange_Tris_8x8_C": "Ramp Wall 8m (Orange)",
   "Build_Wall_Steel_8x4_Corner_01_C": "Tilted Corner Wall 4m",
   "Build_Wall_Steel_8x4_Corner_2_C": "Tilted Concave Wall 4m",
   "Build_Wall_Steel_8x8_Corner_01_C": "Tilted Corner Wall 8m",
   "Build_Wall_Steel_8x8_Corner_2_C": "Tilted Concave Wall 8m",
   "Build_Wall_Window_8x4_01_C": "Single Window",
   "Build_Wall_Window_8x4_02_C": "Frame Window",
   "Build_Wall_Window_8x4_03_C": "Panel Window",
   "Build_Wall_Window_8x4_04_C": "Reinforced Window",
   "Build_Wall_Window_Thin_8x4_01_C": "Full Frame Window",
   "Build_Wall_Window_Thin_8x4_02_C": "Hex Frame Window",
   "Build_WaterPump_C": "Water Extractor",
   "Build_WorkBenchIntegrated_C": "Craft Bench",
   "Build_WorkBench_C": "Craft Bench",
   "Build_Workshop_C": "Equipment Workshop",
   "Build_WreathDecor_C": "FICSMAS Wreath",
   "Build_XmassLightsLine_C": "FICSMAS Power Light",
   "Build_XmassTree_C": "Giant FICSMAS Tree",

   # Items
   "Desc_AlienDNACapsule_C": "Alien DNA Capsule",
   "Desc_AlienProtein_C": "Alien Protein",
   "Desc_AluminaSolution_C": "Alumina Solution",
   "Desc_AluminumCasing_C": "Aluminum Casing",
   "Desc_AluminumIngot_C": "Aluminum Ingot",
   "Desc_AluminumPlateReinforced_C": "Heat Sink",
   "Desc_AluminumPlate_C": "Alclad Aluminum Sheet",
   "Desc_AluminumScrap_C": "Aluminum Scrap",
   "Desc_Battery_C": "Battery",
   "Desc_BerryBush_C": "Berry Bush Plant",
   "Desc_Berry_C": "Paleberry",
   "Desc_Biofuel_C": "Solid Biofuel",
   "Desc_BoomBox_C": "Boombox",
   "Desc_Cable_C": "Cable",
   "Desc_Camera_C": "AWESOME Camera",
   "Desc_CandyCane_C": "Candy Cane",
   "Desc_CartridgeChaos_C": "Turbo Rifle Ammo",
   "Desc_CartridgePlasma_C": "Rifle Plasmidge",
   "Desc_CartridgeSmartProjectile_C": "Homing Rifle Ammo",
   "Desc_CartridgeSmart_C": "Rifle Smartridge",
   "Desc_CartridgeStandard_C": "Rifle Ammo",
   "Desc_Cement_C": "Concrete",
   "Desc_Chainsaw_C": "Chainsaw",
   "Desc_CharacterClap_Statue_C": "Pretty Good Pioneering Statue",
   "Desc_CharacterRunStatue_C": "Adequate Pioneering Statue",
   "Desc_CharacterSpin_Statue_C": "Satisfactory Pioneering Statue",
   "Desc_CircuitBoardHighSpeed_C": "AI Limiter",
   "Desc_CircuitBoard_C": "Circuit Board",
   "Desc_Coal_C": "Coal",
   "Desc_ColorCartridge_C": "Color Cartridge",
   "Desc_CompactedCoal_C": "Compacted Coal",
   "Desc_ComputerSuper_C": "Supercomputer",
   "Desc_Computer_C": "Computer",
   "Desc_CoolingSystem_C": "Cooling System",
   "Desc_CopperDust_C": "Copper Powder",
   "Desc_CopperIngot_C": "Copper Ingot",
   "Desc_CopperSheet_C": "Copper Sheet",
   "Desc_CrystalOscillator_C": "Crystal Oscillator",
   "Desc_CrystalShard_C": "Power Shard",
   "Desc_Crystal_C": "Blue Power Slug",
   "Desc_Crystal_mk2_C": "Yellow Power Slug",
   "Desc_Crystal_mk3_C": "Purple Power Slug",
   "Desc_DarkMatter_C": "Dark Matter Crystal",
   "Desc_Diamond_C": "Diamonds",
   "Desc_DoggoStatue_C": "Lizard Doggo Statue",
   "Desc_DowsingStick_C": "Dowsing stick",
   "Desc_ElectromagneticControlRod_C": "Electromagnetic Control Rod",
   "Desc_Fabric_C": "Fabric",
   "Desc_FicsiteIngot_C": "Ficsite Ingot",
   "Desc_FicsiteMesh_C": "Ficsite Trigon",
   "Desc_Filter_C": "Gas Filter",
   "Desc_Fireworks_Projectile_01_C": "Sweet Fireworks",
   "Desc_Fireworks_Projectile_02_C": "Fancy Fireworks",
   "Desc_Fireworks_Projectile_03_C": "Sparkly Fireworks",
   "Desc_FlowerPetals_C": "Flower Petals",
   "Desc_FluidCanister_C": "Empty Canister",
   "Desc_Fuel_C": "Packaged Fuel",
   "Desc_GasTank_C": "Empty Fluid Tank",
   "Desc_GenericBiomass_C": "Biomass",
   "Desc_Geyser_C": "Geyser",
   "Desc_Gift_C": "FICSMAS Gift",
   "Desc_GoldIngot_C": "Caterium Ingot",
   "Desc_GoldenNut_Statue_C": "Golden Nut Statue",
   "Desc_GunpowderMK2_C": "Smokeless Powder",
   "Desc_Gunpowder_C": "Black Powder",
   "Desc_HUBParts_C": "HUB Parts",
   "Desc_HardDrive_C": "Hard Drive",
   "Desc_HatcherBasic_C": "Tropical Crab Hatcher",
   "Desc_HatcherParts_C": "Hatcher Remains",
   "Desc_HazmatFilter_C": "Iodine Infused Filter",
   "Desc_HeavyOilResidue_C": "Heavy Oil Residue",
   "Desc_HighSpeedConnector_C": "High-Speed Connector",
   "Desc_HighSpeedWire_C": "Quickwire",
   "Desc_HogParts_C": "Hog Remains",
   "Desc_Hog_Statue_C": "Silver Hog Statue",
   "Desc_HostileCreature_C": "Enemies",
   "Desc_HydrogenGas_C": "Hydrogen Gas",
   "Desc_IronIngot_C": "Iron Ingot",
   "Desc_IronPlateReinforced_C": "Reinforced Iron Plate",
   "Desc_IronPlate_C": "Iron Plate",
   "Desc_IronRod_C": "Iron Rod",
   "Desc_IronScrew_C": "Screw",
   "Desc_Leaves_C": "Leaves",
   "Desc_LiquidBiofuel_C": "Liquid Biofuel",
   "Desc_LiquidFuel_C": "Fuel",
   "Desc_LiquidOil_C": "Crude Oil",
   "Desc_LiquidTurboFuel_C": "Turbofuel",
   "Desc_Medkit_C": "Medicinal Inhaler",
   "Desc_ModularFrameFused_C": "Fused Modular Frame",
   "Desc_ModularFrameHeavy_C": "Heavy Modular Frame",
   "Desc_ModularFrameLightweight_C": "Radio Control Unit",
   "Desc_ModularFrame_C": "Modular Frame",
   "Desc_MotorLightweight_C": "Turbo Motor",
   "Desc_Motor_C": "Motor",
   "Desc_Mycelia_C": "Mycelia",
   "Desc_NaturalGas_C": "Natural Gas",
   "Desc_NitricAcid_C": "Nitric Acid",
   "Desc_NitrogenGas_C": "Nitrogen Gas",
   "Desc_NobeliskCluster_C": "Cluster Nobelisk",
   "Desc_NobeliskExplosive_C": "Nobelisk",
   "Desc_NobeliskGas_C": "Gas Nobelisk",
   "Desc_NobeliskNuke_C": "Nuke Nobelisk",
   "Desc_NobeliskShockwave_C": "Pulse Nobelisk",
   "Desc_NonFissibleUranium_C": "Non-fissile Uranium",
   "Desc_NuclearFuelRod_C": "Uranium Fuel Rod",
   "Desc_NuclearWaste_C": "Uranium Waste",
   "Desc_NutBush_C": "Nut Bush Plant",
   "Desc_Nut_C": "Beryl Nut",
   "Desc_OreBauxite_C": "Bauxite",
   "Desc_OreCopper_C": "Copper Ore",
   "Desc_OreGold_C": "Caterium Ore",
   "Desc_OreIron_C": "Iron Ore",
   "Desc_OreUranium_C": "Uranium",
   "Desc_PackagedAlumina_C": "Packaged Alumina Solution",
   "Desc_PackagedBiofuel_C": "Packaged Liquid Biofuel",
   "Desc_PackagedNitricAcid_C": "Packaged Nitric Acid",
   "Desc_PackagedNitrogenGas_C": "Packaged Nitrogen Gas",
   "Desc_PackagedOilResidue_C": "Packaged Heavy Oil Residue",
   "Desc_PackagedOil_C": "Packaged Oil",
   "Desc_PackagedRocketFuel_C": "Packaged Rocket Fuel",
   "Desc_PackagedSulfuricAcid_C": "Packaged Sulfuric Acid",
   "Desc_PackagedWater_C": "Packaged Water",
   "Desc_Parachute_C": "Parachute",
   "Desc_PetroleumCoke_C": "Petroleum Coke",
   "Desc_Pigment_C": "Pigment",
   "Desc_Plastic_C": "Plastic",
   "Desc_PlutoniumCell_C": "Encased Plutonium Cell",
   "Desc_PlutoniumFuelRod_C": "Plutonium Fuel Rod",
   "Desc_PlutoniumPellet_C": "Plutonium Pellet",
   "Desc_PlutoniumWaste_C": "Plutonium Waste",
   "Desc_PolymerResin_C": "Polymer Resin",
   "Desc_PressureConversionCube_C": "Pressure Conversion Cube",
   "Desc_PropaneGas_C": "Propane Gas",
   "Desc_QuantumCrystal_C": "Quantum Crystal",
   "Desc_QuantumOscillator_C": "Superposition Oscillator",
   "Desc_QuartzCrystal_C": "Quartz Crystal",
   "Desc_RawQuartz_C": "Raw Quartz",
   "Desc_RebarGunProjectile_C": "Rebar Gun",
   "Desc_RebarGun_C": "Rebar Gun (OLD)",
   "Desc_Rebar_Aluminum_C": "Aluminum Rebar",
   "Desc_Rebar_ChemicalShot_C": "Rebar Syringe",
   "Desc_Rebar_Explosive_C": "Explosive Rebar",
   "Desc_Rebar_Hookshot_C": "Rebar Hookshot",
   "Desc_Rebar_Rocket_C": "Rocket Rebar",
   "Desc_Rebar_Spreadshot_C": "Shatter Rebar",
   "Desc_Rebar_Steel_C": "Steel Rebar",
   "Desc_Rebar_Stunshot_C": "Stun Rebar",
   "Desc_ResourceSinkCoupon_C": "FICSIT Coupon",
   "Desc_RocketFuel_C": "Rocket Fuel",
   "Desc_Rotor_C": "Rotor",
   "Desc_Rubber_C": "Rubber",
   "Desc_SAMFluctuator_C": "SAM Fluctuator",
   "Desc_SAMIngot_C": "SAM Ingot",
   "Desc_SAM_C": "SAM Ore",
   "Desc_Shroom_C": "Bacon Agaric",
   "Desc_Silica_C": "Silica",
   "Desc_SingularityCell_C": "Singularity Cell",
   "Desc_Snow_C": "Actual Snow",
   "Desc_SnowballProjectile_C": "Snowball",
   "Desc_SpaceElevatorPart_1_C": "Smart Plating",
   "Desc_SpaceElevatorPart_2_C": "Versatile Framework",
   "Desc_SpaceElevatorPart_3_C": "Automated Wiring",
   "Desc_SpaceElevatorPart_4_C": "Modular Engine",
   "Desc_SpaceElevatorPart_5_C": "Adaptive Control Unit",
   "Desc_SpaceElevatorPart_6_C": "Magnetic Field Generator",
   "Desc_SpaceElevatorPart_7_C": "Assembly Director System",
   "Desc_SpaceElevatorPart_8_C": "Thermal Propulsion Rocket",
   "Desc_SpaceElevatorPart_9_C": "Nuclear Pasta",
   "Desc_SpaceElevatorPart_10_C": "Biochemical Sculptor",
   "Desc_SpaceElevatorPart_11_C": "Ballistic Warp Drive",
   "Desc_SpaceElevatorPart_12_C": "AI Expansion Server",
   "Desc_SpaceGiraffeStatue_C": "Confusing Creature Statue",
   "Desc_SpikedRebar_C": "Iron Rebar",
   "Desc_SpitterParts_C": "Plasma Spitter Remains",
   "Desc_SpitterWave_C": "Spitter Wave",
   "Desc_Stator_C": "Stator",
   "Desc_SteelIngot_C": "Steel Ingot",
   "Desc_SteelPipe_C": "Steel Pipe",
   "Desc_SteelPlateReinforced_C": "Encased Industrial Beam",
   "Desc_SteelPlate_C": "Steel Beam",
   "Desc_StingerParts_C": "Stinger Remains",
   "Desc_Stone_C": "Limestone",
   "Desc_Sulfur_C": "Sulfur",
   "Desc_SulfuricAcid_C": "Sulfuric Acid",
   "Desc_TemporalProcessor_C": "Neural-Quantum Processor",
   "Desc_TimeCrystal_C": "Time Crystal",
   "Desc_ToolBelt_C": "Tool Belt",
   "Desc_TurboFuel_C": "Packaged Turbofuel",
   "Desc_UraniumCell_C": "Encased Uranium Cell",
   "Desc_UraniumPellet_C": "Uranium Pellet",
   "Desc_VolcanicGas_C": "Volcanic Gas",
   "Desc_WAT1_C": "Somersloop",
   "Desc_WAT2_C": "Mercer Sphere",
   "Desc_Water_C": "Water",
   "Desc_Wildcard_C": "Any",
   "Desc_Wire_C": "Wire",
   "Desc_Wood_C": "Wood",
   "Desc_XmasBall1_C": "Red FICSMAS Ornament",
   "Desc_XmasBall2_C": "Blue FICSMAS Ornament",
   "Desc_XmasBall3_C": "Copper FICSMAS Ornament",
   "Desc_XmasBall4_C": "Iron FICSMAS Ornament",
   "Desc_XmasBallCluster_C": "FICSMAS Ornament Bundle",
   "Desc_XmasBow_C": "FICSMAS Bow",
   "Desc_XmasBranch_C": "FICSMAS Tree Branch",
   "Desc_XmasLights_C": "FICSMAS Lights",
   "Desc_XmasStar_C": "FICSMAS Wonder Star",
   "Desc_XmasWreath_C": "FICSMAS Decoration",
   "Desc_Zipline_C": "Zipline",

   # Milestones
   "Schematic_Tutorial1_C": "HUB Upgrade 1",
   "Schematic_Tutorial1_5_C": "HUB Upgrade 2",
   "Schematic_Tutorial2_C": "HUB Upgrade 3",
   "Schematic_Tutorial3_C": "HUB Upgrade 4",
   "Schematic_Tutorial4_C": "HUB Upgrade 5",
   "Schematic_Tutorial5_C": "HUB Upgrade 6",
   "Schematic_1-1_C": "Base Building",
   "Schematic_1-2_C": "Logistics",
   "Schematic_1-3_C": "Field Research",
   "Schematic_2-1_C": "Part Assembly",
   "Schematic_2-2_C": "Obstacle Clearing",
   "Schematic_2-3_C": "Jump Pads",
   "Schematic_2-5_C": "Resource Sink Bonus Program",
   "Schematic_3-2_C": "Logistics Mk.2",
   "Schematic_3-1_C": "Coal Power",
   "Schematic_3-3_C": "Vehicular Transport",
   "Schematic_3-4_C": "Basic Steel Production",
   "Schematic_4-2_C": "Enhanced Asset Security",
   "Schematic_4-1_C": "Advanced Steel Production",
   "Schematic_4-3_C": "Expanded Power Infrastructure",
   "Schematic_4-4_C": "Hypertubes",
   "Schematic_5-3_C": "Logistics Mk.3",
   "Schematic_4-5_C": "FICSIT Blueprints",
   "Schematic_5-1_C": "Oil Processing",
   "Schematic_5-1-1_C": "Oil Processing 2",
   "Schematic_5-2_C": "Industrial Manufacturing",
   "Schematic_5-4_C": "Fluid Packaging",
   "Schematic_5-4-1_C": "Alternative Fluid Transport 2",
   "Schematic_5-5_C": "Petroleum Power",
   "Schematic_6-1_C": "Logistics Mk.4",
   "Schematic_6-2_C": "Jetpack",
   "Schematic_6-3_C": "Monorail Train Technology",
   "Schematic_6-5_C": "Pipeline Engineering Mk.2",
   "Schematic_6-6_C": "FICSIT Blueprints Mk.2",
   "Schematic_7-1_C": "Bauxite Refinement",
   "Schematic_7-1-1_C": "Bauxite Refinement 2",
   "Schematic_7-2_C": "Logistics Mk.5",
   "Schematic_7-4_C": "Aeronautical Engineering",
   "Schematic_7-4-1_C": "Aeronautical Engineering 2",
   "Schematic_7-3_C": "Hazmat Suit",
   "Schematic_8-3_C": "Hover Pack",
   "Schematic_8-1_C": "Nuclear Power",
   "Schematic_8-2_C": "Advanced Aluminum Production",
   "Schematic_8-2-1_C": "Advanced Aluminum Production 2",
   "Schematic_8-4_C": "Leading-edge Production",
   "Schematic_8-5_C": "Particle Enrichment",
   "Schematic_8-5-1_C": "Particle Enrichment 2",
}

ITEMS_FOR_PLAYER_INVENTORY = ( # @@@ TODO: THIS LIST IS KNOWN TO BE INCOMPLETE
   "/Game/FactoryGame/Equipment/Chainsaw/Desc_Chainsaw.Desc_Chainsaw_C",
   "/Game/FactoryGame/Equipment/RebarGun/Ammo/Desc_Rebar_Stunshot.Desc_Rebar_Stunshot_C",
   "/Game/FactoryGame/Events/Christmas/Parts/Desc_CandyCane.Desc_CandyCane_C",
   "/Game/FactoryGame/Events/Christmas/Parts/Desc_Gift.Desc_Gift_C",
   "/Game/FactoryGame/Events/Christmas/Parts/Desc_Snow.Desc_Snow_C",
   "/Game/FactoryGame/Events/Christmas/Parts/Desc_XmasBall1.Desc_XmasBall1_C",
   "/Game/FactoryGame/Events/Christmas/Parts/Desc_XmasBall2.Desc_XmasBall2_C",
   "/Game/FactoryGame/Events/Christmas/Parts/Desc_XmasBall3.Desc_XmasBall3_C",
   "/Game/FactoryGame/Events/Christmas/Parts/Desc_XmasBall4.Desc_XmasBall4_C",
   "/Game/FactoryGame/Events/Christmas/Parts/Desc_XmasBallCluster.Desc_XmasBallCluster_C",
   "/Game/FactoryGame/Events/Christmas/Parts/Desc_XmasBow.Desc_XmasBow_C",
   "/Game/FactoryGame/Events/Christmas/Parts/Desc_XmasBranch.Desc_XmasBranch_C",
   "/Game/FactoryGame/Events/Christmas/Parts/Desc_XmasStar.Desc_XmasStar_C",
   "/Game/FactoryGame/Events/Christmas/Parts/Desc_XmasWreath.Desc_XmasWreath_C",
   "/Game/FactoryGame/Prototype/WAT/Desc_WAT1.Desc_WAT1_C",
   "/Game/FactoryGame/Prototype/WAT/Desc_WAT2.Desc_WAT2_C",
   "/Game/FactoryGame/Resource/Environment/Berry/Desc_Berry.Desc_Berry_C",
   "/Game/FactoryGame/Resource/Environment/CrashSites/Desc_HardDrive.Desc_HardDrive_C",
   "/Game/FactoryGame/Resource/Environment/Crystal/Desc_Crystal.Desc_Crystal_C",
   "/Game/FactoryGame/Resource/Environment/Crystal/Desc_CrystalShard.Desc_CrystalShard_C",
   "/Game/FactoryGame/Resource/Environment/Crystal/Desc_Crystal_mk2.Desc_Crystal_mk2_C",
   "/Game/FactoryGame/Resource/Environment/Crystal/Desc_Crystal_mk3.Desc_Crystal_mk3_C",
   "/Game/FactoryGame/Resource/Environment/DesertShroom/Desc_Shroom.Desc_Shroom_C",
   "/Game/FactoryGame/Resource/Environment/Nut/Desc_Nut.Desc_Nut_C",
   "/Game/FactoryGame/Resource/Equipment/Beacon/Desc_Parachute.Desc_Parachute_C",
   "/Game/FactoryGame/Resource/Equipment/GemstoneScanner/BP_EquipmentDescriptorObjectScanner.BP_EquipmentDescriptorObjectScanner_C",
   "/Game/FactoryGame/Resource/Equipment/HoverPack/BP_EquipmentDescriptorHoverPack.BP_EquipmentDescriptorHoverPack_C",
   "/Game/FactoryGame/Resource/Equipment/JetPack/BP_EquipmentDescriptorJetPack.BP_EquipmentDescriptorJetPack_C",
   "/Game/FactoryGame/Resource/Equipment/JumpingStilts/BP_EquipmentDescriptorJumpingStilts.BP_EquipmentDescriptorJumpingStilts_C",
   "/Game/FactoryGame/Resource/Equipment/NailGun/Desc_RebarGunProjectile.Desc_RebarGunProjectile_C",
   "/Game/FactoryGame/Resource/Equipment/NobeliskDetonator/BP_EquipmentDescriptorNobeliskDetonator.BP_EquipmentDescriptorNobeliskDetonator_C",
   "/Game/FactoryGame/Resource/Equipment/PortableMiner/BP_ItemDescriptorPortableMiner.BP_ItemDescriptorPortableMiner_C",
   "/Game/FactoryGame/Resource/Equipment/ShockShank/BP_EquipmentDescriptorShockShank.BP_EquipmentDescriptorShockShank_C",
   "/Game/FactoryGame/Resource/Equipment/StunSpear/BP_EquipmentDescriptorStunSpear.BP_EquipmentDescriptorStunSpear_C",
   "/Game/FactoryGame/Resource/Equipment/Zipline/BP_EqDescZipLine.BP_EqDescZipLine_C",
   "/Game/FactoryGame/Resource/Parts/AlienDNACapsule/Desc_AlienDNACapsule.Desc_AlienDNACapsule_C",
   "/Game/FactoryGame/Resource/Parts/AlienProtein/Desc_AlienProtein.Desc_AlienProtein_C",
   "/Game/FactoryGame/Resource/Parts/AluminumCasing/Desc_AluminumCasing.Desc_AluminumCasing_C",
   "/Game/FactoryGame/Resource/Parts/AluminumIngot/Desc_AluminumIngot.Desc_AluminumIngot_C",
   "/Game/FactoryGame/Resource/Parts/AluminumPlate/Desc_AluminumPlate.Desc_AluminumPlate_C",
   "/Game/FactoryGame/Resource/Parts/AluminumPlateReinforced/Desc_AluminumPlateReinforced.Desc_AluminumPlateReinforced_C",
   "/Game/FactoryGame/Resource/Parts/AluminumScrap/Desc_AluminumScrap.Desc_AluminumScrap_C",
   "/Game/FactoryGame/Resource/Parts/AnimalParts/Desc_HatcherParts.Desc_HatcherParts_C",
   "/Game/FactoryGame/Resource/Parts/AnimalParts/Desc_HogParts.Desc_HogParts_C",
   "/Game/FactoryGame/Resource/Parts/AnimalParts/Desc_SpitterParts.Desc_SpitterParts_C",
   "/Game/FactoryGame/Resource/Parts/AnimalParts/Desc_StingerParts.Desc_StingerParts_C",
   "/Game/FactoryGame/Resource/Parts/Battery/Desc_Battery.Desc_Battery_C",
   "/Game/FactoryGame/Resource/Parts/BioFuel/Desc_Biofuel.Desc_Biofuel_C",
   "/Game/FactoryGame/Resource/Parts/Cable/Desc_Cable.Desc_Cable_C",
   "/Game/FactoryGame/Resource/Parts/CartridgeStandard/Desc_CartridgeStandard.Desc_CartridgeStandard_C",
   "/Game/FactoryGame/Resource/Parts/Cement/Desc_Cement.Desc_Cement_C",
   "/Game/FactoryGame/Resource/Parts/CircuitBoard/Desc_CircuitBoard.Desc_CircuitBoard_C",
   "/Game/FactoryGame/Resource/Parts/CircuitBoardHighSpeed/Desc_CircuitBoardHighSpeed.Desc_CircuitBoardHighSpeed_C",
   "/Game/FactoryGame/Resource/Parts/ColorCartridge/Desc_ColorCartridge.Desc_ColorCartridge_C",
   "/Game/FactoryGame/Resource/Parts/CompactedCoal/Desc_CompactedCoal.Desc_CompactedCoal_C",
   "/Game/FactoryGame/Resource/Parts/Computer/Desc_Computer.Desc_Computer_C",
   "/Game/FactoryGame/Resource/Parts/ComputerQuantum/Desc_ComputerQuantum.Desc_ComputerQuantum_C",
   "/Game/FactoryGame/Resource/Parts/ComputerSuper/Desc_ComputerSuper.Desc_ComputerSuper_C",
   "/Game/FactoryGame/Resource/Parts/CoolingSystem/Desc_CoolingSystem.Desc_CoolingSystem_C",
   "/Game/FactoryGame/Resource/Parts/CopperDust/Desc_CopperDust.Desc_CopperDust_C",
   "/Game/FactoryGame/Resource/Parts/CopperIngot/Desc_CopperIngot.Desc_CopperIngot_C",
   "/Game/FactoryGame/Resource/Parts/CopperSheet/Desc_CopperSheet.Desc_CopperSheet_C",
   "/Game/FactoryGame/Resource/Parts/CrystalOscillator/Desc_CrystalOscillator.Desc_CrystalOscillator_C",
   "/Game/FactoryGame/Resource/Parts/ElectromagneticControlRod/Desc_ElectromagneticControlRod.Desc_ElectromagneticControlRod_C",
   "/Game/FactoryGame/Resource/Parts/Filter/Desc_Filter.Desc_Filter_C",
   "/Game/FactoryGame/Resource/Parts/FluidCanister/Desc_FluidCanister.Desc_FluidCanister_C",
   "/Game/FactoryGame/Resource/Parts/Fuel/Desc_Fuel.Desc_Fuel_C",
   "/Game/FactoryGame/Resource/Parts/GenericBiomass/Desc_Fabric.Desc_Fabric_C",
   "/Game/FactoryGame/Resource/Parts/GenericBiomass/Desc_FlowerPetals.Desc_FlowerPetals_C",
   "/Game/FactoryGame/Resource/Parts/GenericBiomass/Desc_GenericBiomass.Desc_GenericBiomass_C",
   "/Game/FactoryGame/Resource/Parts/GenericBiomass/Desc_Leaves.Desc_Leaves_C",
   "/Game/FactoryGame/Resource/Parts/GenericBiomass/Desc_Mycelia.Desc_Mycelia_C",
   "/Game/FactoryGame/Resource/Parts/GenericBiomass/Desc_Wood.Desc_Wood_C",
   "/Game/FactoryGame/Resource/Parts/GoldIngot/Desc_GoldIngot.Desc_GoldIngot_C",
   "/Game/FactoryGame/Resource/Parts/GunPowder/Desc_Gunpowder.Desc_Gunpowder_C",
   "/Game/FactoryGame/Resource/Parts/GunPowder/Desc_GunpowderMK2.Desc_GunpowderMK2_C",
   "/Game/FactoryGame/Resource/Parts/HUBParts/Desc_HUBParts.Desc_HUBParts_C",
   "/Game/FactoryGame/Resource/Parts/HighSpeedConnector/Desc_HighSpeedConnector.Desc_HighSpeedConnector_C",
   "/Game/FactoryGame/Resource/Parts/HighSpeedWire/Desc_HighSpeedWire.Desc_HighSpeedWire_C",
   "/Game/FactoryGame/Resource/Parts/IodineInfusedFilter/Desc_HazmatFilter.Desc_HazmatFilter_C",
   "/Game/FactoryGame/Resource/Parts/IronIngot/Desc_IronIngot.Desc_IronIngot_C",
   "/Game/FactoryGame/Resource/Parts/IronPlate/Desc_IronPlate.Desc_IronPlate_C",
   "/Game/FactoryGame/Resource/Parts/IronPlateReinforced/Desc_IronPlateReinforced.Desc_IronPlateReinforced_C",
   "/Game/FactoryGame/Resource/Parts/IronRod/Desc_IronRod.Desc_IronRod_C",
   "/Game/FactoryGame/Resource/Parts/IronScrew/Desc_IronScrew.Desc_IronScrew_C",
   "/Game/FactoryGame/Resource/Parts/ModularFrame/Desc_ModularFrame.Desc_ModularFrame_C",
   "/Game/FactoryGame/Resource/Parts/ModularFrameFused/Desc_ModularFrameFused.Desc_ModularFrameFused_C",
   "/Game/FactoryGame/Resource/Parts/ModularFrameHeavy/Desc_ModularFrameHeavy.Desc_ModularFrameHeavy_C",
   "/Game/FactoryGame/Resource/Parts/ModularFrameLightweight/Desc_ModularFrameLightweight.Desc_ModularFrameLightweight_C",
   "/Game/FactoryGame/Resource/Parts/Motor/Desc_Motor.Desc_Motor_C",
   "/Game/FactoryGame/Resource/Parts/MotorLightweight/Desc_MotorLightweight.Desc_MotorLightweight_C",
   "/Game/FactoryGame/Resource/Parts/NobeliskExplosive/Desc_NobeliskExplosive.Desc_NobeliskExplosive_C",
   "/Game/FactoryGame/Resource/Parts/Plastic/Desc_Plastic.Desc_Plastic_C",
   "/Game/FactoryGame/Resource/Parts/PolymerResin/Desc_PolymerResin.Desc_PolymerResin_C",
   "/Game/FactoryGame/Resource/Parts/PressureConversionCube/Desc_PressureConversionCube.Desc_PressureConversionCube_C",
   "/Game/FactoryGame/Resource/Parts/QuantumOscillator/Desc_QuantumOscillator.Desc_QuantumOscillator_C",
   "/Game/FactoryGame/Resource/Parts/QuartzCrystal/Desc_QuartzCrystal.Desc_QuartzCrystal_C",
   "/Game/FactoryGame/Resource/Parts/ResourceSinkCoupon/Desc_ResourceSinkCoupon.Desc_ResourceSinkCoupon_C",
   "/Game/FactoryGame/Resource/Parts/Rotor/Desc_Rotor.Desc_Rotor_C",
   "/Game/FactoryGame/Resource/Parts/Rubber/Desc_Rubber.Desc_Rubber_C",
   "/Game/FactoryGame/Resource/Parts/Silica/Desc_Silica.Desc_Silica_C",
   "/Game/FactoryGame/Resource/Parts/SnowballProjectile/Desc_SnowballProjectile.Desc_SnowballProjectile_C",
   "/Game/FactoryGame/Resource/Parts/SpaceElevatorParts/Desc_SpaceElevatorPart_1.Desc_SpaceElevatorPart_1_C",
   "/Game/FactoryGame/Resource/Parts/SpaceElevatorParts/Desc_SpaceElevatorPart_2.Desc_SpaceElevatorPart_2_C",
   "/Game/FactoryGame/Resource/Parts/SpaceElevatorParts/Desc_SpaceElevatorPart_3.Desc_SpaceElevatorPart_3_C",
   "/Game/FactoryGame/Resource/Parts/SpaceElevatorParts/Desc_SpaceElevatorPart_4.Desc_SpaceElevatorPart_4_C",
   "/Game/FactoryGame/Resource/Parts/SpaceElevatorParts/Desc_SpaceElevatorPart_5.Desc_SpaceElevatorPart_5_C",
   "/Game/FactoryGame/Resource/Parts/SpaceElevatorParts/Desc_SpaceElevatorPart_9.Desc_SpaceElevatorPart_9_C",
   "/Game/FactoryGame/Resource/Parts/SpikedRebar/Desc_SpikedRebar.Desc_SpikedRebar_C",
   "/Game/FactoryGame/Resource/Parts/Stator/Desc_Stator.Desc_Stator_C",
   "/Game/FactoryGame/Resource/Parts/SteelIngot/Desc_SteelIngot.Desc_SteelIngot_C",
   "/Game/FactoryGame/Resource/Parts/SteelPipe/Desc_SteelPipe.Desc_SteelPipe_C",
   "/Game/FactoryGame/Resource/Parts/SteelPlate/Desc_SteelPlate.Desc_SteelPlate_C",
   "/Game/FactoryGame/Resource/Parts/SteelPlateReinforced/Desc_SteelPlateReinforced.Desc_SteelPlateReinforced_C",
   "/Game/FactoryGame/Resource/Parts/Turbofuel/Desc_TurboFuel.Desc_TurboFuel_C",
   "/Game/FactoryGame/Resource/Parts/Wire/Desc_Wire.Desc_Wire_C",
   "/Game/FactoryGame/Resource/RawResources/Coal/Desc_Coal.Desc_Coal_C",
   "/Game/FactoryGame/Resource/RawResources/OreBauxite/Desc_OreBauxite.Desc_OreBauxite_C",
   "/Game/FactoryGame/Resource/RawResources/OreCopper/Desc_OreCopper.Desc_OreCopper_C",
   "/Game/FactoryGame/Resource/RawResources/OreGold/Desc_OreGold.Desc_OreGold_C",
   "/Game/FactoryGame/Resource/RawResources/OreIron/Desc_OreIron.Desc_OreIron_C",
   "/Game/FactoryGame/Resource/RawResources/RawQuartz/Desc_RawQuartz.Desc_RawQuartz_C",
   "/Game/FactoryGame/Resource/RawResources/SAM/Desc_SAM.Desc_SAM_C",
   "/Game/FactoryGame/Resource/RawResources/Stone/Desc_Stone.Desc_Stone_C",
   "/Game/FactoryGame/Resource/RawResources/Sulfur/Desc_Sulfur.Desc_Sulfur_C",
   "/Game/FactoryGame/Resource/RawResources/Water/Desc_PackagedWater.Desc_PackagedWater_C"
)

CONVEYOR_BELTS = (
   "/Game/FactoryGame/Buildable/Factory/ConveyorBeltMk1/Build_ConveyorBeltMk1.Build_ConveyorBeltMk1_C",
   "/Game/FactoryGame/Buildable/Factory/ConveyorBeltMk2/Build_ConveyorBeltMk2.Build_ConveyorBeltMk2_C",
   "/Game/FactoryGame/Buildable/Factory/ConveyorBeltMk3/Build_ConveyorBeltMk3.Build_ConveyorBeltMk3_C",
   "/Game/FactoryGame/Buildable/Factory/ConveyorBeltMk4/Build_ConveyorBeltMk4.Build_ConveyorBeltMk4_C",
   "/Game/FactoryGame/Buildable/Factory/ConveyorBeltMk5/Build_ConveyorBeltMk5.Build_ConveyorBeltMk5_C",
   "/Game/FactoryGame/Buildable/Factory/ConveyorBeltMk6/Build_ConveyorBeltMk6.Build_ConveyorBeltMk6_C",
   "/Game/FactoryGame/Buildable/Factory/ConveyorLiftMk1/Build_ConveyorLiftMk1.Build_ConveyorLiftMk1_C",
   "/Game/FactoryGame/Buildable/Factory/ConveyorLiftMk2/Build_ConveyorLiftMk2.Build_ConveyorLiftMk2_C",
   "/Game/FactoryGame/Buildable/Factory/ConveyorLiftMk3/Build_ConveyorLiftMk3.Build_ConveyorLiftMk3_C",
   "/Game/FactoryGame/Buildable/Factory/ConveyorLiftMk4/Build_ConveyorLiftMk4.Build_ConveyorLiftMk4_C",
   "/Game/FactoryGame/Buildable/Factory/ConveyorLiftMk5/Build_ConveyorLiftMk5.Build_ConveyorLiftMk5_C",
   "/Game/FactoryGame/Buildable/Factory/ConveyorLiftMk6/Build_ConveyorLiftMk6.Build_ConveyorLiftMk6_C",
)

# When power slugs are collected, they change from 1 ActorHeader + 1 Object into 1 First-Collectable + 1 Second-Collectable
POWER_SLUG = (
   "/Game/FactoryGame/Resource/Environment/Crystal/BP_Crystal.BP_Crystal_C",
   "/Game/FactoryGame/Resource/Environment/Crystal/BP_Crystal_mk2.BP_Crystal_mk2_C",
   "/Game/FactoryGame/Resource/Environment/Crystal/BP_Crystal_mk3.BP_Crystal_mk3_C",
)

MINERS = (
   "/Game/FactoryGame/Buildable/Factory/MinerMK1/Build_MinerMk1.Build_MinerMk1_C", # From MinerMk1 to MinerMK1 in v1.0
   "/Game/FactoryGame/Buildable/Factory/MinerMk2/Build_MinerMk2.Build_MinerMk2_C",
   "/Game/FactoryGame/Buildable/Factory/MinerMk3/Build_MinerMk3.Build_MinerMk3_C",
   "/Game/FactoryGame/Buildable/Factory/OilPump/Build_OilPump.Build_OilPump_C",
   "/Game/FactoryGame/Buildable/Factory/FrackingSmasher/Build_FrackingSmasher.Build_FrackingSmasher_C",
   "/Game/FactoryGame/Buildable/Factory/FrackingExtractor/Build_FrackingExtractor.Build_FrackingExtractor_C",
   "/Game/FactoryGame/Buildable/Factory/GeneratorGeoThermal/Build_GeneratorGeoThermal.Build_GeneratorGeoThermal_C",
)

MINED_RESOURCES = (
   "/Game/FactoryGame/Resource/BP_ResourceNode.BP_ResourceNode_C",
   "/Game/FactoryGame/Resource/BP_FrackingCore.BP_FrackingCore_C",
   "/Game/FactoryGame/Resource/BP_FrackingSatellite.BP_FrackingSatellite_C",
   "/Game/FactoryGame/Resource/BP_ResourceNodeGeyser.BP_ResourceNodeGeyser_C",
   #"/Game/FactoryGame/Resource/BP_ResourceDeposit.BP_ResourceDeposit_C",  # These are manually harvested resource rocks which have the properties mResourceDepositTableIndex, mMineAmount, mResourcesLeft
)

POWER_LINE = "/Game/FactoryGame/Buildable/Factory/PowerLine/Build_PowerLine.Build_PowerLine_C"
CRASH_SITE = "/Game/FactoryGame/World/Benefit/DropPod/BP_DropPod.BP_DropPod_C"

SOMERSLOOP = "/Game/FactoryGame/Prototype/WAT/BP_WAT1.BP_WAT1_C"
MERCER_SPHERE = "/Game/FactoryGame/Prototype/WAT/BP_WAT2.BP_WAT2_C"
MERCER_SHRINE = "/Game/FactoryGame/Prototype/WAT/BP_MercerShrine.BP_MercerShrine_C"

# 89 hard drives (alternate recipes & inflated pocket dimention)
UNLOCK_PATHS__HARD_DRIVES = (
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_AdheredIronPlate.Schematic_Alternate_AdheredIronPlate_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update4/Schematic_Alternate_AlcladCasing.Schematic_Alternate_AlcladCasing_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update4/Schematic_Alternate_AutomatedMiner.Schematic_Alternate_AutomatedMiner_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_HighSpeedWiring.Schematic_Alternate_HighSpeedWiring_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_Coal2.Schematic_Alternate_Coal2_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_BoltedFrame.Schematic_Alternate_BoltedFrame_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_ReinforcedIronPlate1.Schematic_Alternate_ReinforcedIronPlate1_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_Screw.Schematic_Alternate_Screw_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_CircuitBoard2.Schematic_Alternate_CircuitBoard2_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_Computer1.Schematic_Alternate_Computer1_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_Wire2.Schematic_Alternate_Wire2_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_Coal1.Schematic_Alternate_Coal1_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_Silica.Schematic_Alternate_Silica_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update4/Schematic_Alternate_ClassicBattery.Schematic_Alternate_ClassicBattery_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_CoatedCable.Schematic_Alternate_CoatedCable_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_CoatedIronCanister.Schematic_Alternate_CoatedIronCanister_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_CoatedIronPlate.Schematic_Alternate_CoatedIronPlate_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_CokeSteelIngot.Schematic_Alternate_CokeSteelIngot_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_EnrichedCoal.Schematic_Alternate_EnrichedCoal_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_IngotSteel2.Schematic_Alternate_IngotSteel2_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update4/Schematic_Alternate_CoolingDevice.Schematic_Alternate_CoolingDevice_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_CopperAlloyIngot.Schematic_Alternate_CopperAlloyIngot_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_CopperRotor.Schematic_Alternate_CopperRotor_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_Beacon1.Schematic_Alternate_Beacon1_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_Computer2.Schematic_Alternate_Computer2_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update4/Schematic_Alternate_DilutedFuel.Schematic_Alternate_DilutedFuel_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_DilutedPackagedFuel.Schematic_Alternate_DilutedPackagedFuel_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update4/Schematic_Alternate_ElectricMotor.Schematic_Alternate_ElectricMotor_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_ElectroAluminumScrap.Schematic_Alternate_ElectroAluminumScrap_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_ElectrodeCircuitBoard.Schematic_Alternate_ElectrodeCircuitBoard_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_ElectromagneticControlRod1.Schematic_Alternate_ElectromagneticControlRod1_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_ReinforcedSteelPlate.Schematic_Alternate_ReinforcedSteelPlate_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update4/Schematic_Alternate_FertileUranium.Schematic_Alternate_FertileUranium_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_Gunpowder1.Schematic_Alternate_Gunpowder1_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_Concrete.Schematic_Alternate_Concrete_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_FlexibleFramework.Schematic_Alternate_FlexibleFramework_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_Quickwire.Schematic_Alternate_Quickwire_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_FusedWire.Schematic_Alternate_FusedWire_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_HeatSink1.Schematic_Alternate_HeatSink1_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update4/Schematic_Alternate_HeatFusedFrame.Schematic_Alternate_HeatFusedFrame_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_HeavyModularFrame.Schematic_Alternate_HeavyModularFrame_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_HeavyFlexibleFrame.Schematic_Alternate_HeavyFlexibleFrame_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_HeavyOilResidue.Schematic_Alternate_HeavyOilResidue_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_UraniumCell1.Schematic_Alternate_UraniumCell1_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update4/Schematic_Alternate_InstantPlutoniumCell.Schematic_Alternate_InstantPlutoniumCell_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update4/Schematic_Alternate_InstantScrap.Schematic_Alternate_InstantScrap_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_Cable1.Schematic_Alternate_Cable1_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_CrystalOscillator.Schematic_Alternate_CrystalOscillator_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_IngotIron.Schematic_Alternate_IngotIron_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_Wire1.Schematic_Alternate_Wire1_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update4/Schematic_Alternate_OCSupercomputer.Schematic_Alternate_OCSupercomputer_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_PlasticSmartPlating.Schematic_Alternate_PlasticSmartPlating_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update4/Schematic_Alternate_PlutoniumFuelUnit.Schematic_Alternate_PlutoniumFuelUnit_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_PolymerResin.Schematic_Alternate_PolymerResin_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_PureAluminumIngot.Schematic_Alternate_PureAluminumIngot_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_PureCateriumIngot.Schematic_Alternate_PureCateriumIngot_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_PureCopperIngot.Schematic_Alternate_PureCopperIngot_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_PureIronIngot.Schematic_Alternate_PureIronIngot_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_PureQuartzCrystal.Schematic_Alternate_PureQuartzCrystal_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_Cable2.Schematic_Alternate_Cable2_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_Stator.Schematic_Alternate_Stator_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_RadioControlUnit1.Schematic_Alternate_RadioControlUnit1_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update4/Schematic_Alternate_RadioControlSystem.Schematic_Alternate_RadioControlSystem_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_Plastic1.Schematic_Alternate_Plastic1_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_RecycledRubber.Schematic_Alternate_RecycledRubber_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_Motor1.Schematic_Alternate_Motor1_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_RubberConcrete.Schematic_Alternate_RubberConcrete_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_CircuitBoard1.Schematic_Alternate_CircuitBoard1_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_HighSpeedConnector.Schematic_Alternate_HighSpeedConnector_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update4/Schematic_Alternate_SloppyAlumina.Schematic_Alternate_SloppyAlumina_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_IngotSteel1.Schematic_Alternate_IngotSteel1_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_SteamedCopperSheet.Schematic_Alternate_SteamedCopperSheet_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_SteelCanister.Schematic_Alternate_SteelCanister_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_SteelCoatedPlate.Schematic_Alternate_SteelCoatedPlate_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_SteelRod.Schematic_Alternate_SteelRod_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_Rotor.Schematic_Alternate_Rotor_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_Screw2.Schematic_Alternate_Screw2_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_ModularFrame.Schematic_Alternate_ModularFrame_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_ReinforcedIronPlate2.Schematic_Alternate_ReinforcedIronPlate2_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update4/Schematic_Alternate_SuperStateComputer.Schematic_Alternate_SuperStateComputer_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update4/Schematic_Alternate_TurboBlendFuel.Schematic_Alternate_TurboBlendFuel_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_TurboMotor1.Schematic_Alternate_TurboMotor1_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_TurboHeavyFuel.Schematic_Alternate_TurboHeavyFuel_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update4/Schematic_Alternate_TurboPressureMotor.Schematic_Alternate_TurboPressureMotor_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_TurboFuel.Schematic_Alternate_TurboFuel_C",
   "/Game/FactoryGame/Schematics/Alternate/Parts/Schematic_Alternate_NuclearFuelRod1.Schematic_Alternate_NuclearFuelRod1_C",
   "/Game/FactoryGame/Schematics/Alternate/New_Update3/Schematic_Alternate_WetConcrete.Schematic_Alternate_WetConcrete_C",
   "/Game/FactoryGame/Schematics/Alternate/Upgrades/Schematic_Alternate_InventorySlots2.Schematic_Alternate_InventorySlots2_C",
   "/Game/FactoryGame/Schematics/Alternate/Upgrades/Schematic_Alternate_InventorySlots1.Schematic_Alternate_InventorySlots1_C",
)

# 80 awesome shop unlocks -- Also removed from "mAvailableSchematics" under Persistent_Level:PersistentLevel.BP_GameState_C_2147330588
UNLOCK_PATHS__AWESOME_SHOP = (
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_BeamSet.ResourceSink_BeamSet_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_Catwalks.ResourceSink_Catwalks_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_ConcretePillarSet.ResourceSink_ConcretePillarSet_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_FactoryBarrier.ResourceSink_FactoryBarrier_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_FactoryFence.ResourceSink_FactoryFence_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_FactoryRailing.ResourceSink_FactoryRailing_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_FoudationPillar.ResourceSink_FoudationPillar_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_FramePillarSet.ResourceSink_FramePillarSet_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_FrameworkFoundations.ResourceSink_FrameworkFoundations_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_Ladders.ResourceSink_Ladders_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_Roofs_Basic.ResourceSink_Roofs_Basic_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_Roofs_Corners.ResourceSink_Roofs_Corners_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_Stairs.ResourceSink_Stairs_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_Walkways.ResourceSink_Walkways_C",
   "/Game/FactoryGame/Schematics/ResourceSink/Patterns/ResourceSink_Arrows_FoundationPatterns.ResourceSink_Arrows_FoundationPatterns_C",
   "/Game/FactoryGame/Schematics/ResourceSink/Customizer/ResourceSink_Customizer_Asphalt_FoundationMaterial.ResourceSink_Customizer_Asphalt_FoundationMaterial_C",
   "/Game/FactoryGame/Schematics/ResourceSink/Customizer/ResourceSink_Customizer_Concrete_FoundationMaterial.ResourceSink_Customizer_Concrete_FoundationMaterial_C",
   "/Game/FactoryGame/Schematics/ResourceSink/Customizer/ResourceSink_Customizer_ConcreteWallMaterial.ResourceSink_Customizer_ConcreteWallMaterial_C",
   "/Game/FactoryGame/Schematics/ResourceSink/Customizer/ResourceSink_Customizer_GlassRoofMaterial.ResourceSink_Customizer_GlassRoofMaterial_C",
   "/Game/FactoryGame/Schematics/ResourceSink/Customizer/ResourceSink_Customizer_GripMetal_FoundationMaterial.ResourceSink_Customizer_GripMetal_FoundationMaterial_C",
   "/Game/FactoryGame/Schematics/ResourceSink/Customizer/ResourceSink_Customizer_PolishedConcrete_FoundationMaterial.ResourceSink_Customizer_PolishedConcrete_FoundationMaterial_C",
   "/Game/FactoryGame/Schematics/ResourceSink/Customizer/ResourceSink_Customizer_SteelRoofMaterial.ResourceSink_Customizer_SteelRoofMaterial_C",
   "/Game/FactoryGame/Schematics/ResourceSink/Customizer/ResourceSink_Customizer_SteelWallMaterial.ResourceSink_Customizer_SteelWallMaterial_C",
   "/Game/FactoryGame/Schematics/ResourceSink/Customizer/ResourceSink_Customizer_TarRoofMaterial.ResourceSink_Customizer_TarRoofMaterial_C",
   "/Game/FactoryGame/Schematics/ResourceSink/Patterns/ResourceSink_DotLines_FoundationPatterns.ResourceSink_DotLines_FoundationPatterns_C",
   "/Game/FactoryGame/Schematics/ResourceSink/Patterns/ResourceSink_FullLines_FoundationPatterns.ResourceSink_FullLines_FoundationPatterns_C",
   "/Game/FactoryGame/Schematics/ResourceSink/Patterns/ResourceSink_IconsFactory_FoundationPatterns.ResourceSink_IconsFactory_FoundationPatterns_C",
   "/Game/FactoryGame/Schematics/ResourceSink/Patterns/ResourceSink_IconsTransport_FoundationPatterns.ResourceSink_IconsTransport_FoundationPatterns_C",
   "/Game/FactoryGame/Schematics/ResourceSink/Patterns/ResourceSink_Number_FoundationPatterns.ResourceSink_Number_FoundationPatterns_C",
   "/Game/FactoryGame/Schematics/ResourceSink/Patterns/ResourceSink_Pathways_FoundationPatterns.ResourceSink_Pathways_FoundationPatterns_C",
   "/Game/FactoryGame/Schematics/ResourceSink/Patterns/ResourceSink_Zones_FoundationPatterns.ResourceSink_Zones_FoundationPatterns_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_CurvedFoundationPack.ResourceSink_CurvedFoundationPack_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_DiagonalRamps.ResourceSink_DiagonalRamps_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_FoundationExpansionPack.ResourceSink_FoundationExpansionPack_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_HalfFoundations.ResourceSink_HalfFoundations_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_InvertedCornerRamps.ResourceSink_InvertedCornerRamps_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_InvertedRampPack.ResourceSink_InvertedRampPack_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_QuarterPipeExtensions.ResourceSink_QuarterPipeExtensions_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_Checkmark.ResourceSink_Checkmark_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_CyberWagon.ResourceSink_CyberWagon_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_CyberWagon_Unlock.ResourceSink_CyberWagon_Unlock_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_FactoryCart.ResourceSink_FactoryCart_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_GoldenCart.ResourceSink_GoldenCart_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_GoldenCart_Unlock.ResourceSink_GoldenCart_Unlock_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_GoldenCup.ResourceSink_GoldenCup_C",
   "/Game/FactoryGame/Schematics/Tapes/Schematic_AbsoluteFicsit.Schematic_AbsoluteFicsit_C",
   "/Game/FactoryGame/Schematics/Tapes/Schematic_Goat.Schematic_Goat_C",
   "/Game/FactoryGame/Schematics/Tapes/Schematic_JoelSyntholm.Schematic_JoelSyntholm_C",
   "/Game/FactoryGame/Schematics/Tapes/Schematic_LeMichael.Schematic_LeMichael_C",
   "/Game/FactoryGame/Schematics/Tapes/Schematic_Sanctum.Schematic_Sanctum_C",
   "/Game/FactoryGame/Schematics/Tapes/Schematic_Sanctum2.Schematic_Sanctum2_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_ConveyorCeilingMount.ResourceSink_ConveyorCeilingMount_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_ConveyorLiftHole.ResourceSink_ConveyorLiftHole_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_ConveyorWallMount.ResourceSink_ConveyorWallMount_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_HyperTubeFloorHole.ResourceSink_HyperTubeFloorHole_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_HyperTubeWallAttachements.ResourceSink_HyperTubeWallAttachements_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_NoIndicator_PipelineMK1.ResourceSink_NoIndicator_PipelineMK1_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_NoIndicator_PipelineMK2.ResourceSink_NoIndicator_PipelineMK2_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_PipelineFloorHole.ResourceSink_PipelineFloorHole_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_PipelineWallAttachments.ResourceSink_PipelineWallAttachments_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_WallPowerPoles.ResourceSink_WallPowerPoles_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_WallPowerPolesMK2.ResourceSink_WallPowerPolesMK2_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_WallPowerPolesMK3.ResourceSink_WallPowerPolesMK3_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_BillboardSigns.ResourceSink_BillboardSigns_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_CeilingLight.ResourceSink_CeilingLight_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_DisplaySigns.ResourceSink_DisplaySigns_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_HazardBoxSkin.ResourceSink_HazardBoxSkin_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_LabelSigns.ResourceSink_LabelSigns_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_LightControlPanel.ResourceSink_LightControlPanel_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_LightTower.ResourceSink_LightTower_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_MedicalBoxSkin.ResourceSink_MedicalBoxSkin_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_StreetLight.ResourceSink_StreetLight_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_ConveryWalls_Normal.ResourceSink_ConveryWalls_Normal_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_Diagonal_Down_Wallset.ResourceSink_Diagonal_Down_Wallset_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_Diagonal_Up_WallSet.ResourceSink_Diagonal_Up_WallSet_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_DoorWalls_Normal.ResourceSink_DoorWalls_Normal_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_FrameWindows.ResourceSink_FrameWindows_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_GateWalls.ResourceSink_GateWalls_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_Tilted_Walls.ResourceSink_Tilted_Walls_C",
   "/Game/FactoryGame/Schematics/ResourceSink/ResourceSink_WindowedWalls.ResourceSink_WindowedWalls_C",
)

# 85 MAM unlocks -- This also includes "mUnlockedResearchTrees" under Persistent_Level:PersistentLevel.BP_GameState_C_2147330588
UNLOCK_PATHS__MAM = (
   "/Game/FactoryGame/Schematics/Research/AlienOrganisms_RS/Research_ACarapace_2.Research_ACarapace_2_C",
   "/Game/FactoryGame/Schematics/Research/AlienOrganisms_RS/Research_ACarapace_3.Research_ACarapace_3_C",
   "/Game/FactoryGame/Schematics/Research/AlienOrganisms_RS/Research_AO_DNACapsule.Research_AO_DNACapsule_C",
   "/Game/FactoryGame/Schematics/Research/AlienOrganisms_RS/Research_AO_Hatcher.Research_AO_Hatcher_C",
   "/Game/FactoryGame/Schematics/Research/AlienOrganisms_RS/Research_AO_Hog.Research_AO_Hog_C",
   "/Game/FactoryGame/Schematics/Research/AlienOrganisms_RS/Research_AO_Pre_Rebar.Research_AO_Pre_Rebar_C",
   "/Game/FactoryGame/Schematics/Research/AlienOrganisms_RS/Research_AO_Spitter.Research_AO_Spitter_C",
   "/Game/FactoryGame/Schematics/Research/AlienOrganisms_RS/Research_AO_Stinger.Research_AO_Stinger_C",
   "/Game/FactoryGame/Schematics/Research/AlienOrganisms_RS/Research_AOrganisms_2.Research_AOrganisms_2_C",
   "/Game/FactoryGame/Schematics/Research/AlienOrganisms_RS/Research_AOrgans_2.Research_AOrgans_2_C",
   "/Game/FactoryGame/Schematics/Research/AlienOrganisms_RS/Research_AOrgans_3.Research_AOrgans_3_C",
   "/Game/FactoryGame/Schematics/Research/Caterium_RS/Research_Caterium_0.Research_Caterium_0_C",
   "/Game/FactoryGame/Schematics/Research/Caterium_RS/Research_Caterium_1.Research_Caterium_1_C",
   "/Game/FactoryGame/Schematics/Research/Caterium_RS/Research_Caterium_2_1.Research_Caterium_2_1_C",
   "/Game/FactoryGame/Schematics/Research/Caterium_RS/Research_Caterium_2.Research_Caterium_2_C",
   "/Game/FactoryGame/Schematics/Research/Caterium_RS/Research_Caterium_3_2.Research_Caterium_3_2_C",
   "/Game/FactoryGame/Schematics/Research/Caterium_RS/Research_Caterium_3.Research_Caterium_3_C",
   "/Game/FactoryGame/Schematics/Research/Caterium_RS/Research_Caterium_4_1_1.Research_Caterium_4_1_1_C",
   "/Game/FactoryGame/Schematics/Research/Caterium_RS/Research_Caterium_4_1_2.Research_Caterium_4_1_2_C",
   "/Game/FactoryGame/Schematics/Research/Caterium_RS/Research_Caterium_4_1.Research_Caterium_4_1_C",
   "/Game/FactoryGame/Schematics/Research/Caterium_RS/Research_Caterium_4_2.Research_Caterium_4_2_C",
   "/Game/FactoryGame/Schematics/Research/Caterium_RS/Research_Caterium_5_1.Research_Caterium_5_1_C",
   "/Game/FactoryGame/Schematics/Research/Caterium_RS/Research_Caterium_5.Research_Caterium_5_C",
   "/Game/FactoryGame/Schematics/Research/Caterium_RS/Research_Caterium_6_1.Research_Caterium_6_1_C",
   "/Game/FactoryGame/Schematics/Research/Caterium_RS/Research_Caterium_6_2.Research_Caterium_6_2_C",
   "/Game/FactoryGame/Schematics/Research/Caterium_RS/Research_Caterium_6_3.Research_Caterium_6_3_C",
   "/Game/FactoryGame/Schematics/Research/Caterium_RS/Research_Caterium_7_1.Research_Caterium_7_1_C",
   "/Game/FactoryGame/Schematics/Research/Caterium_RS/Research_Caterium_7_2.Research_Caterium_7_2_C",
   "/Game/FactoryGame/Schematics/Research/XMas_RS/Research_XMas_1.Research_XMas_1_C",
   "/Game/FactoryGame/Schematics/Research/XMas_RS/Research_XMas_1-1.Research_XMas_1-1_C",
   "/Game/FactoryGame/Schematics/Research/XMas_RS/Research_XMas_1-2.Research_XMas_1-2_C",
   "/Game/FactoryGame/Schematics/Research/XMas_RS/Research_XMas_2.Research_XMas_2_C",
   "/Game/FactoryGame/Schematics/Research/XMas_RS/Research_XMas_2-1.Research_XMas_2-1_C",
   "/Game/FactoryGame/Schematics/Research/XMas_RS/Research_XMas_2-2.Research_XMas_2-2_C",
   "/Game/FactoryGame/Schematics/Research/XMas_RS/Research_XMas_3.Research_XMas_3_C",
   "/Game/FactoryGame/Schematics/Research/XMas_RS/Research_XMas_3-1.Research_XMas_3-1_C",
   "/Game/FactoryGame/Schematics/Research/XMas_RS/Research_XMas_3-2.Research_XMas_3-2_C",
   "/Game/FactoryGame/Schematics/Research/XMas_RS/Research_XMas_4.Research_XMas_4_C",
   "/Game/FactoryGame/Schematics/Research/XMas_RS/Research_XMas_4-1.Research_XMas_4-1_C",
   "/Game/FactoryGame/Schematics/Research/XMas_RS/Research_XMas_4-2.Research_XMas_4-2_C",
   "/Game/FactoryGame/Schematics/Research/XMas_RS/Research_XMas_5.Research_XMas_5_C",
   "/Game/FactoryGame/Schematics/Research/Mycelia_RS/Research_Mycelia_1.Research_Mycelia_1_C",
   "/Game/FactoryGame/Schematics/Research/Mycelia_RS/Research_Mycelia_2_1.Research_Mycelia_2_1_C",
   "/Game/FactoryGame/Schematics/Research/Mycelia_RS/Research_Mycelia_2.Research_Mycelia_2_C",
   "/Game/FactoryGame/Schematics/Research/Mycelia_RS/Research_Mycelia_3.Research_Mycelia_3_C",
   "/Game/FactoryGame/Schematics/Research/Mycelia_RS/Research_Mycelia_4.Research_Mycelia_4_C",
   "/Game/FactoryGame/Schematics/Research/Mycelia_RS/Research_Mycelia_5.Research_Mycelia_5_C",
   "/Game/FactoryGame/Schematics/Research/Mycelia_RS/Research_Mycelia_6.Research_Mycelia_6_C",
   "/Game/FactoryGame/Schematics/Research/Mycelia_RS/Research_Mycelia_7.Research_Mycelia_7_C",
   "/Game/FactoryGame/Schematics/Research/Mycelia_RS/Research_Mycelia_8.Research_Mycelia_8_C",
   "/Game/FactoryGame/Schematics/Research/Nutrients_RS/Research_Nutrients_0.Research_Nutrients_0_C",
   "/Game/FactoryGame/Schematics/Research/Nutrients_RS/Research_Nutrients_1.Research_Nutrients_1_C",
   "/Game/FactoryGame/Schematics/Research/Nutrients_RS/Research_Nutrients_2.Research_Nutrients_2_C",
   "/Game/FactoryGame/Schematics/Research/Nutrients_RS/Research_Nutrients_3.Research_Nutrients_3_C",
   "/Game/FactoryGame/Schematics/Research/Nutrients_RS/Research_Nutrients_4.Research_Nutrients_4_C",
   "/Game/FactoryGame/Schematics/Research/PowerSlugs_RS/Research_PowerSlugs_1.Research_PowerSlugs_1_C",
   "/Game/FactoryGame/Schematics/Research/PowerSlugs_RS/Research_PowerSlugs_2.Research_PowerSlugs_2_C",
   "/Game/FactoryGame/Schematics/Research/PowerSlugs_RS/Research_PowerSlugs_3.Research_PowerSlugs_3_C",
   "/Game/FactoryGame/Schematics/Research/PowerSlugs_RS/Research_PowerSlugs_4.Research_PowerSlugs_4_C",
   "/Game/FactoryGame/Schematics/Research/PowerSlugs_RS/Research_PowerSlugs_5.Research_PowerSlugs_5_C",
   "/Game/FactoryGame/Schematics/Research/Caterium_RS/Research_Caterium_3_1.Research_Caterium_3_1_C",
   "/Game/FactoryGame/Schematics/Research/Caterium_RS/Research_Caterium_4_3.Research_Caterium_4_3_C",
   "/Game/FactoryGame/Schematics/Research/Quartz_RS/Research_Quartz_0.Research_Quartz_0_C",
   "/Game/FactoryGame/Schematics/Research/Quartz_RS/Research_Quartz_1_1.Research_Quartz_1_1_C",
   "/Game/FactoryGame/Schematics/Research/Quartz_RS/Research_Quartz_1_2.Research_Quartz_1_2_C",
   "/Game/FactoryGame/Schematics/Research/Quartz_RS/Research_Quartz_2_1.Research_Quartz_2_1_C",
   "/Game/FactoryGame/Schematics/Research/Quartz_RS/Research_Quartz_2.Research_Quartz_2_C",
   "/Game/FactoryGame/Schematics/Research/Quartz_RS/Research_Quartz_3_1.Research_Quartz_3_1_C",
   "/Game/FactoryGame/Schematics/Research/Quartz_RS/Research_Quartz_3_4.Research_Quartz_3_4_C",
   "/Game/FactoryGame/Schematics/Research/Quartz_RS/Research_Quartz_4_1.Research_Quartz_4_1_C",
   "/Game/FactoryGame/Schematics/Research/Quartz_RS/Research_Quartz_4.Research_Quartz_4_C",
   "/Game/FactoryGame/Schematics/Research/Sulfur_RS/Research_Sulfur_0.Research_Sulfur_0_C",
   "/Game/FactoryGame/Schematics/Research/Sulfur_RS/Research_Sulfur_1.Research_Sulfur_1_C",
   "/Game/FactoryGame/Schematics/Research/Sulfur_RS/Research_Sulfur_3_1.Research_Sulfur_3_1_C",
   "/Game/FactoryGame/Schematics/Research/Sulfur_RS/Research_Sulfur_3.Research_Sulfur_3_C",
   "/Game/FactoryGame/Schematics/Research/Sulfur_RS/Research_Sulfur_4_1.Research_Sulfur_4_1_C",
   "/Game/FactoryGame/Schematics/Research/Sulfur_RS/Research_Sulfur_4_2.Research_Sulfur_4_2_C",
   "/Game/FactoryGame/Schematics/Research/Sulfur_RS/Research_Sulfur_4.Research_Sulfur_4_C",
   "/Game/FactoryGame/Schematics/Research/Sulfur_RS/Research_Sulfur_5_1.Research_Sulfur_5_1_C",
   "/Game/FactoryGame/Schematics/Research/Sulfur_RS/Research_Sulfur_5_2.Research_Sulfur_5_2_C",
   "/Game/FactoryGame/Schematics/Research/Sulfur_RS/Research_Sulfur_5.Research_Sulfur_5_C",
   "/Game/FactoryGame/Schematics/Research/Sulfur_RS/Research_Sulfur_6.Research_Sulfur_6_C",
   "/Game/FactoryGame/Schematics/Research/Sulfur_RS/Research_Sulfur_compactedCoal.Research_Sulfur_CompactedCoal_C",
   "/Game/FactoryGame/Schematics/Research/Sulfur_RS/Research_Sulfur_ExperimentalPower.Research_Sulfur_ExperimentalPower_C",
   "/Game/FactoryGame/Schematics/Research/Sulfur_RS/Research_Sulfur_TurboFuel.Research_Sulfur_TurboFuel_C",
)

# 47 Tiers -- This also get removed from "mAvailableSchematics" under Persistent_Level:PersistentLevel.BP_GameState_C_2147330588
UNLOCK_PATHS__HUB_TIERS = (
   "/Game/FactoryGame/Schematics/Schematic_StartingRecipes.Schematic_StartingRecipes_C",
   "/Game/FactoryGame/Schematics/Tutorial/Schematic_Tutorial1_5.Schematic_Tutorial1_5_C",
   "/Game/FactoryGame/Schematics/Tutorial/Schematic_Tutorial1.Schematic_Tutorial1_C",
   "/Game/FactoryGame/Schematics/Tutorial/Schematic_Tutorial2.Schematic_Tutorial2_C",
   "/Game/FactoryGame/Schematics/Tutorial/Schematic_Tutorial3.Schematic_Tutorial3_C",
   "/Game/FactoryGame/Schematics/Tutorial/Schematic_Tutorial4.Schematic_Tutorial4_C",
   "/Game/FactoryGame/Schematics/Tutorial/Schematic_Tutorial5.Schematic_Tutorial5_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_1-1.Schematic_1-1_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_1-2.Schematic_1-2_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_1-3.Schematic_1-3_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_2-1.Schematic_2-1_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_2-2.Schematic_2-2_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_2-3.Schematic_2-3_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_2-5.Schematic_2-5_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_3-2.Schematic_3-2_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_3-1.Schematic_3-1_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_3-3.Schematic_3-3_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_3-4.Schematic_3-4_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_4-2.Schematic_4-2_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_4-1.Schematic_4-1_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_4-3.Schematic_4-3_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_4-4.Schematic_4-4_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_4-5.Schematic_4-5_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_5-3.Schematic_5-3_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_5-1.Schematic_5-1_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_5-1-1.Schematic_5-1-1_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_5-2.Schematic_5-2_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_5-4.Schematic_5-4_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_5-4-1.Schematic_5-4-1_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_6-4.Schematic_6-4_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_6-1.Schematic_6-1_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_6-2.Schematic_6-2_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_6-3.Schematic_6-3_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_6-5.Schematic_6-5_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_7-1.Schematic_7-1_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_7-1-1.Schematic_7-1-1_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_7-2.Schematic_7-2_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_7-3.Schematic_7-3_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_7-4.Schematic_7-4_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_7-4-1.Schematic_7-4-1_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_8-3.Schematic_8-3_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_8-1.Schematic_8-1_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_8-2.Schematic_8-2_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_8-2-1.Schematic_8-2-1_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_8-4.Schematic_8-4_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_8-5.Schematic_8-5_C",
   "/Game/FactoryGame/Schematics/Progression/Schematic_8-5-1.Schematic_8-5-1_C",
)

# 11 "special"
UNLOCK_PATHS__SPECIAL = (
   "/Game/FactoryGame/Events/Christmas/Calendar_Schematics/Ficsmas_Schematic_FingerGun_Emote.Ficsmas_Schematic_FingerGun_Emote_C",
   "/Game/FactoryGame/Events/Christmas/Calendar_Schematics/Ficsmas_Schematic_Fireworks.Ficsmas_Schematic_Fireworks_C",
   "/Game/FactoryGame/Events/Christmas/Calendar_Schematics/Ficsmas_Schematic_SkinBundle_1.Ficsmas_Schematic_SkinBundle_1_C",
   "/Game/FactoryGame/Events/Christmas/Calendar_Schematics/Ficsmas_Schematic_SkinBundle_2.Ficsmas_Schematic_SkinBundle_2_C",
   "/Game/FactoryGame/Schematics/Tapes/Schematic_DeepRockGalactic.Schematic_DeepRockGalactic_C",
   "/Game/FactoryGame/Schematics/Tapes/Schematic_Huntdown.Schematic_Huntdown_C",
   "/Game/FactoryGame/Schematics/Tapes/Schematic_SongsOfConquest.Schematic_SongsOfConquest_C",
   "/Game/FactoryGame/Events/Christmas/Buildings/TreeDecor/Schematic_XMassTree_T1.Schematic_XMassTree_T1_C",
   "/Game/FactoryGame/Events/Christmas/Buildings/TreeDecor/Schematic_XMassTree_T2.Schematic_XMassTree_T2_C",
   "/Game/FactoryGame/Events/Christmas/Buildings/TreeDecor/Schematic_XMassTree_T3.Schematic_XMassTree_T3_C",
   "/Game/FactoryGame/Events/Christmas/Buildings/TreeDecor/Schematic_XMassTree_T4.Schematic_XMassTree_T4_C",
)

PROJECT_ASSEMBLY_COSTS = {
   "/Game/FactoryGame/GamePhases/GP_Project_Assembly_Phase_1.GP_Project_Assembly_Phase_1": {
      "Smart Plating": 50,
   },
   "/Game/FactoryGame/GamePhases/GP_Project_Assembly_Phase_2.GP_Project_Assembly_Phase_2": {
      "Smart Plating": 500,
      "Versatile Framework": 500,
      "Automated Wiring": 100,
   },
   "/Game/FactoryGame/GamePhases/GP_Project_Assembly_Phase_3.GP_Project_Assembly_Phase_3": {
      "Versatile Framework": 2500,
      "Modular Engine": 500,
      "Adaptive Control Unit": 100,
   },
   "/Game/FactoryGame/GamePhases/GP_Project_Assembly_Phase_4.GP_Project_Assembly_Phase_4": {
      "Assembly Director System": 500,
      "Magnetic Field Generator": 500,
      "Nuclear Pasta": 100,
      "Thermal Propulsion Rocket": 250,
   },
   "/Game/FactoryGame/GamePhases/GP_Project_Assembly_Phase_5.GP_Project_Assembly_Phase_5": {
      "Nuclear Pasta": 1000,
      "Biochemical Sculptor": 1000,
      "AI Expansion Server": 256,
      "Ballistic Warp Drive": 200,
   },
}
FINAL_PROJECT_ASSEMBLY_PHASE_6 = "/Game/FactoryGame/GamePhases/GP_Project_Assembly_Phase_6.GP_Project_Assembly_Phase_6"
FINAL_PROJECT_ASSEMBLY_PHASE_7 = "/Game/FactoryGame/GamePhases/GP_Project_Assembly_Phase_7.GP_Project_Assembly_Phase_7"

# https://satisfactory.wiki.gg/wiki/Milestones
MILESTONE_COSTS = {
   # Tier 0: Onboarding
   "HUB Upgrade 1": {
      "Iron Rod": 10,
   },
   "HUB Upgrade 2": {
      "Iron Rod": 20,
      "Iron Plate": 10,
   },
   "HUB Upgrade 3": {
      "Iron Plate": 20,
      "Iron Rod": 20,
      "Wire": 20,
   },
   "HUB Upgrade 4": {
      "Iron Plate": 75,
      "Cable": 20,
      "Concrete": 10,
   },
   "HUB Upgrade 5": {
      "Iron Rod": 75,
      "Cable": 50,
      "Concrete": 20,
   },
   "HUB Upgrade 6": {
      "Iron Rod": 100,
      "Iron Plate": 100,
      "Wire": 100,
      "Concrete": 50,
   },
   # Tier 1
   "Base Building": {
      "Concrete": 200,
      "Iron Plate": 100,
      "Iron Rod": 100,
   },
   "Logistics": {
      "Iron Plate": 150,
      "Iron Rod": 150,
      "Wire": 300,
   },
   "Field Research": {
      "Wire": 300,
      "Screw": 300,
      "Iron Plate": 100,
   },
   # Tier 2
   "Part Assembly": {
      "Cable": 200,
      "Iron Rod": 200,
      "Screw": 500,
      "Iron Plate": 300,
   },
   "Obstacle Clearing": {
      "Screw": 500,
      "Cable": 100,
      "Concrete": 100,
   },
   "Jump Pads": {
      "Rotor": 50,
      "Iron Plate": 300,
      "Cable": 150,
   },
   "Resource Sink Bonus Program": {
      "Concrete": 400,
      "Wire": 500,
      "Iron Rod": 200,
      "Iron Plate": 200,
   },
   "Logistics Mk.2": {
      "Reinforced Iron Plate": 50,
      "Concrete": 200,
      "Iron Rod": 300,
      "Iron Plate": 300,
   },
   # Tier 3
   "Coal Power": {
      "Reinforced Iron Plate": 150,
      "Rotor": 50,
      "Cable": 500,
   },
   "Vehicular Transport": {
      "Modular Frame": 25,
      "Rotor": 100,
      "Cable": 200,
      "Iron Rod": 400,
   },
   "Basic Steel Production": {
      "Modular Frame": 50,
      "Rotor": 150,
      "Concrete": 500,
      "Wire": 1000,
   },
   "Enhanced Asset Security": {
      "Reinforced Iron Plate": 100,
      "Iron Rod": 600,
      "Wire": 1500,
   },
   # Tier 4
   "FICSIT Blueprints": {
      "Modular Frame": 100,
      "Steel Beam": 200,
      "Cable": 500,
      "Concrete": 1000,
   },
   "Logistics Mk.3": {
      "Steel Beam": 200,
      "Steel Pipe": 200,
      "Reinforced Iron Plate": 400,
   },
   "Advanced Steel Production": {
      "Steel Pipe": 100,
      "Modular Frame": 100,
      "Rotor": 200,
      "Concrete": 500,
   },
   "Expanded Power Infrastructure": {
      "Encased Industrial Beam": 50,
      "Steel Beam": 100,
      "Modular Frame": 200,
      "Wire": 2000,
   },
   "Hypertubes": {
      "Encased Industrial Beam": 50,
      "Steel Pipe": 300,
      "Copper Sheet": 500,
   },
   # Tier 5
   "Jetpack": {
      "Motor": 50,
      "Cable": 1000,
      "Iron Plate": 1000,
   },
   "Oil Processing": {
      "Motor": 50,
      "Encased Industrial Beam": 100,
      "Steel Pipe": 500,
      "Copper Sheet": 500,
   },
   "Logistics Mk.4": {
      "Rubber": 200,
      "Encased Industrial Beam": 300,
      "Modular Frame": 400,
   },
   "Fluid Packaging": {
      "Plastic": 200,
      "Steel Beam": 400,
      "Copper Sheet": 1000,
   },
   "Petroleum Power": {
      "Motor": 100,
      "Encased Industrial Beam": 100,
      "Rubber": 200,
      "Plastic": 200,
   },
   # Tier 6
   "Industrial Manufacturing": {
      "Motor": 200,
      "Modular Frame": 200,
      "Plastic": 400,
      "Cable": 1000,
   },
   "Monorail Train Technology": {
      "Motor": 250,
      "Encased Industrial Beam": 500,
      "Steel Beam": 100,
      "Steel Pipe": 1000,
   },
   "Railway Signaling": {
      "Computer": 50,
      "Steel Pipe": 400,
      "Copper Sheet": 1000,
   },
   "Pipeline Engineering Mk.2": {
      "Heavy Modular Frame": 50,
      "Plastic": 500,
      "Rubber": 500,
   },
   "FICSIT Blueprints Mk.2": {
      "Heavy Modular Frame": 100,
      "Computer": 200,
      "Rubber": 400,
      "Concrete": 1500,
   },
   # Tier 7
   "Bauxite Refinement": {
      "Computer": 100,
      "Heavy Modular Frame": 100,
      "Motor": 200,
      "Rubber": 500,
   },
   "Hover Pack": {
      "Alclad Aluminum Sheet": 100,
      "Heavy Modular Frame": 100,
      "Computer": 100,
      "Motor": 250,
   },
   "Logistics Mk.5": {
      "Alclad Aluminum Sheet": 200,
      "Encased Industrial Beam": 400,
      "Reinforced Iron Plate": 600,
   },
   "Hazmat Suit": {
      "Gas Filter": 50,
      "Aluminum Casing": 100,
      "Quickwire": 500,
   },
   "Control System Development": {
      "Alclad Aluminum Sheet": 200,
      "Aluminum Casing": 400,
      "Computer": 200,
      "Plastic": 1000,
   },
   # Tier 8
   "Aeronautical Engineering": {
      "Radio Control Unit": 50,
      "Alclad Aluminum Sheet": 100,
      "Aluminum Casing": 200,
      "Motor": 300,
   },
   "Nuclear Power": {
      "Supercomputer": 50,
      "Heavy Modular Frame": 200,
      "Cable": 1000,
      "Concrete": 2000,
   },
   "Advanced Aluminum Production": {
      "Radio Control Unit": 50,
      "Aluminum Casing": 200,
      "Alclad Aluminum Sheet": 400,
      "Wire": 3000,
   },
   "Leading-edge Production": {
      "Fused Modular Frame": 50,
      "Supercomputer": 100,
      "Steel Pipe": 1000,
   },
   "Particle Enrichment": {
      "Turbo Motor": 50,
      "Fused Modular Frame": 100,
      "Cooling System": 200,
      "Quickwire": 2500,
   },
   # Tier 9
   "Matter Conversion": {
      "Fused Modular Frame": 100,
      "Radio Control Unit": 250,
      "Cooling System": 500,
   },
   "Quantum Encoding": {
      "Time Crystal": 50,
      "Ficsite Trigon": 100,
      "Turbo Motor": 200,
      "Supercomputer": 400,
   },
   "Ficsit Blueprints Mk.3": {
      "Neural-Quantum Processor": 100,
      "Time Crystal": 250,
      "Ficsite Trigon": 500,
      "Fused Modular Frame": 500,
   },
   "Spatial Energy Regulation": {
      "Superposition Oscillator": 100,
      "Turbo Motor": 250,
      "Radio Control Unit": 500,
      "SAM Fluctuator": 1000,
   },
   "Peak Efficiency": {
      "Time Crystal": 250,
      "Ficsite Trigon": 250,
      "Alclad Aluminum Sheet": 5000,
      "Iron Plate": 10000,
   },
}

satisfactoryCalculatorInteractiveMapExtras = []

class ParseError(Exception):
    pass

def parseInt8(offset, data):
   nextOffset = offset + 1
   if nextOffset > len(data):
      raise ParseError(f"Offset {offset} too large for int8 in {len(data)}-byte data.")
   return (nextOffset, struct.unpack("<c", data[offset:nextOffset])[0])

def parseUint8(offset, data):
   nextOffset = offset + 1
   if nextOffset > len(data):
      raise ParseError(f"Offset {offset} too large for uint8 in {len(data)}-byte data.")
   return (nextOffset, struct.unpack("<B", data[offset:nextOffset])[0])

def parseInt32(offset, data):
   nextOffset = offset + 4
   if nextOffset > len(data):
      raise ParseError(f"Offset {offset} too large for int32 in {len(data)}-byte data.")
   return (nextOffset, struct.unpack("<i", data[offset:nextOffset])[0])

def parseUint32(offset, data):
   nextOffset = offset + 4
   if nextOffset > len(data):
      raise ParseError(f"Offset {offset} too large for uint32 in {len(data)}-byte data.")
   return (nextOffset, struct.unpack("<I", data[offset:nextOffset])[0])

def parseInt64(offset, data):
   nextOffset = offset + 8
   if nextOffset > len(data):
      raise ParseError(f"Offset {offset} too large for int64 in {len(data)}-byte data.")
   return (nextOffset, struct.unpack("<q", data[offset:nextOffset])[0])

def parseUint64(offset, data):
   nextOffset = offset + 8
   if nextOffset > len(data):
      raise ParseError(f"Offset {offset} too large for int64 in {len(data)}-byte data.")
   return (nextOffset, struct.unpack("<Q", data[offset:nextOffset])[0])

def parseFloat(offset, data):
   nextOffset = offset + 4
   if nextOffset > len(data):
      raise ParseError(f"Offset {offset} too large for float in {len(data)}-byte data.")
   return (nextOffset, struct.unpack("<f", data[offset:nextOffset])[0])

def parseDouble(offset, data):
   nextOffset = offset + 8
   if nextOffset > len(data):
      raise ParseError(f"Offset {offset} too large for double in {len(data)}-byte data.")
   return (nextOffset, struct.unpack("<d", data[offset:nextOffset])[0])

def parseBool(offset, data, parser, contextForException):
   (offset, flag) = parser(offset, data)
   if flag != 0 and flag != 1:
      raise ParseError(f"Oops: Inaccurate assumption of {contextForException} value.  Actual={flag}")
   return (offset, flag != 0)

def parseString(offset, data):
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

def parseData(offset, data, length):
   if offset + length > len(data):
      raise ParseError(f"Offset {offset} too large for data of length {length} in {len(data)}-byte data.")
   return (offset + length, data[offset:offset+length])

def TESTING_ONLY_dumpSection(offset, data, sectionStart, sectionSize, name = ""):
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

def TESTING_ONLY_dumpData(offset, data, length, name = ""):
   return TESTING_ONLY_dumpSection(offset, data, offset, length, name)

def confirmBasicType(originalOffset, data, parser, expectedValue, message = None):
   (newOffset, value) = parser(originalOffset, data)
   if value != expectedValue:
      if message == None:
         raise ParseError(f"Value {value} at offset {originalOffset} does not match the expected value {expectedValue}.")
      else:
         raise ParseError(f"Value {value} at offset {originalOffset} does not match the expected value {expectedValue}: {message}")
   return newOffset

TICKS_IN_SECOND = 10 * 1000 * 1000
EPOCH_1_TO_1970 = 719162 * 24 * 60 * 60
class SaveFileInfo:
   validFlag = False

   def parse(self, data):
      (offset, self.saveHeaderType) = parseUint32(0, data)
      if self.saveHeaderType != 13: # For v0.8.3.3 thru v1.0.0.3
         raise ParseError(f"Unsupported save header version number {self.saveHeaderType}.")
      (offset, self.saveVersion) = parseUint32(offset, data)
      if self.saveVersion != 46:  # 30=v0.6.1.3  42=v0.8.3.3  46=v1.0.0.1 & v1.0.0.3
         raise ParseError(f"Unsupported save version number {self.saveVersion}.")
      (offset, self.buildVersion) = parseUint32(offset, data)
      (offset, self.mapName) = parseString(offset, data)
      (offset, self.mapOptions) = parseString(offset, data)
      (offset, self.sessionName) = parseString(offset, data)
      (offset, self.playDurationInSeconds) = parseUint32(offset, data)
      (offset, self.saveDateTimeInTicks) = parseUint64(offset, data)
      self.saveDatetime = datetime.datetime.fromtimestamp(self.saveDateTimeInTicks / TICKS_IN_SECOND - EPOCH_1_TO_1970)
      (offset, self.sessionVisibility) = parseInt8(offset, data)
      (offset, self.editorObjectVersion) = parseUint32(offset, data)
      (offset, self.modMetadata) = parseString(offset, data)
      (offset, self.isModdedSave) = parseUint32(offset, data)
      (offset, self.persistentSaveIdentifier) = parseString(offset, data)

      offset = confirmBasicType(offset, data, parseUint32, 1)
      offset = confirmBasicType(offset, data, parseUint32, 1)
      (offset, random1) = parseUint64(offset, data)
      (offset, random2) = parseUint64(offset, data)
      self.random = [random1, random2]
      (offset, self.cheatFlag) = parseBool(offset, data, parseUint32, "SaveFileInfo.cheatFlag")

      self.validFlag = True
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

class ActorHeader:
   validFlag = False

   def parse(self, offset, data):
      (offset, self.typePath) = parseString(offset, data)
      (offset, self.rootObject) = parseString(offset, data)
      (offset, self.instanceName) = parseString(offset, data)
      (offset, self.needTransform) = parseUint32(offset, data)

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

      (offset, self.wasPlacedInLevel) = parseUint32(offset, data)
      self.validFlag = True
      return offset

   def __str__(self):
      if self.validFlag:
         return f"<ActorHeader: typePath={self.typePath}, rootObject={self.rootObject}, instanceName={self.instanceName}, needTransform={self.needTransform}, rotation={self.rotation}, position={self.position}, scale={self.scale}, wasPlacedInLevel={self.wasPlacedInLevel}>"
      else:
         raise ParseError("Unable to convert invalid ActorHeader to str")

class ComponentHeader:
   validFlag = False

   def parse(self, offset, data):
      (offset, self.className) = parseString(offset, data)
      (offset, self.rootObject) = parseString(offset, data)
      (offset, self.instanceName) = parseString(offset, data)
      (offset, self.parentActorName) = parseString(offset, data)
      self.validFlag = True
      return offset

   def __str__(self):
      if self.validFlag:
         return f"<ComponentHeader: className={self.className}, rootObject={self.rootObject}, instanceName={self.instanceName}, parentActorName={self.parentActorName}>"
      else:
         raise ParseError("Unable to convert invalid ComponentHeader to str")

def toString(value):
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

def getPropertyValue(properties, needlePropertyName):
   for (haystackPropertyName, propertyValue) in properties:
      if haystackPropertyName == needlePropertyName:
         return propertyValue
   return None

class Object:
   validFlag = False

   def parse(self, offset, data, actorOrComponentObjectHeader):
      self.instanceName = actorOrComponentObjectHeader.instanceName
      (offset, self.objectGameVersion) = parseUint32(offset, data) # 42=v0.8.3.3 46=v1.0.0.1 & v1.0.0.3
      (offset, self.flag) = parseBool(offset, data, parseUint32, "Object.flag")  # No association with actor vs component difference.
      (offset, objectSize) = parseUint32(offset, data)
      offsetStartThis = offset

      self.actorReferenceAssociations = None
      if isinstance(actorOrComponentObjectHeader, ActorHeader):
         (offset, parentObjectReference) = parseObjectReference(offset, data)
         (offset, actorComponentReferenceCount) = parseUint32(offset, data)
         actorComponentReferences = []
         for jdx in range(actorComponentReferenceCount):
            (offset, actorComponentReference) = parseObjectReference(offset, data)
            actorComponentReferences.append(actorComponentReference)
         self.actorReferenceAssociations = [parentObjectReference, actorComponentReferences]

      (offset, self.properties, self.propertyTypes) = parseProperties(offset, data)

      offset = confirmBasicType(offset, data, parseUint32, 0)

      self.actorSpecificInfo = None
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
            trainList = []
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
            (offset, count1) = parseUint32(offset, data)
            self.actorSpecificInfo = []
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
                  offset = confirmBasicType(offset, data, parseUint32, 0)
                  (offset, maybeIndex) = parseUint32(offset, data) # seen 0-4
                  offset = confirmBasicType(offset, data, parseUint8, 0)

                  (offset, recipePathName) = parseString(offset, data)
                  (offset, blueprintProxyLevelPath) = parseObjectReference(offset, data)

                  lightweightBuildableInstances.append([rotationQuaternion, position, swatchPathName, patternDescNumber, [primaryColor, secondaryColor], maybeIndex, recipePathName, blueprintProxyLevelPath])

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
               "/Game/FactoryGame/Buildable/Vehicle/Golfcart/BP_GolfcartGold.BP_GolfcartGold_C"):
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
               "/Script/FactoryGame.FGTrainPlatformConnection"):
            offset = confirmBasicType(offset, data, parseUint32, 0)

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

      self.validFlag = True
      return offset

   def __str__(self):
      if self.validFlag:
         actorReferenceAssociationsStr = "n/a"
         if self.actorReferenceAssociations != None:
            actorReferenceAssociationsStr = ""
            for levelPathName in self.actorReferenceAssociations[1]:
               if len(actorReferenceAssociationsStr) > 0:
                  actorReferenceAssociationsStr += ", "
               actorReferenceAssociationsStr += str(levelPathName)
            actorReferenceAssociationsStr = f"({self.actorReferenceAssociations[0]}, [{actorReferenceAssociationsStr}])"
         return f"<Object: instanceName={self.instanceName}, objectGameVersion={self.objectGameVersion}, flag={self.flag}, actorReferenceAssociations={actorReferenceAssociationsStr}, properties={toString(self.properties)}, actorSpecificInfo={toString(self.actorSpecificInfo)}>"
      else:
         raise ParseError("Unable to convert invalid Object to str")

class ObjectReference:
   validFlag = False

   def parse(self, offset, data):
      (offset, self.levelName) = parseString(offset, data)
      (offset, self.pathName) = parseString(offset, data)
      self.validFlag = True
      return offset

   def __str__(self):
      if self.validFlag:
         if self.levelName == "" and self.pathName == "":
            return "<ObjectReference/>"
         else:
            return f"<ObjectReference: levelName={self.levelName}, pathName={self.pathName}>"
      else:
         raise ParseError("Unable to convert invalid ObjectReference to str")

def parseObjectReference(offset, data):
   objectReference = ObjectReference()
   offset = objectReference.parse(offset, data)
   return (offset, objectReference)

def getLevelSize(offset, data, persistentLevelFlag = False):
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

   # Collectables #2
   if not persistentLevelFlag:
      (offset, collectedCount2) = parseUint32(offset, data)
      for count in range(collectedCount2):
         (offset, objectReference) = parseObjectReference(offset, data)

   return (offset, actorAndComponentCount * 2)

def parseLevel(offset, data, persistentLevelFlag = False, progressBar = None):
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

      if headerType == 1:
         objectHeader = ActorHeader()
      elif headerType == 0:
         objectHeader = ComponentHeader()
      else:
         raise ParseError(f"Invalid headerType {headerType}")
      offset = objectHeader.parse(offset, data)
      actorAndComponentObjectHeaders.append(objectHeader)
      if progressBar != None:
         progressBar.add()

   # Collectables #1
   collectables1 = None
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
      if progressBar != None:
         progressBar.add()
   if offset - objectStartOffset != allObjectsSize:
      raise ParseError(f"Object size mismatch: expect={allObjectsSize} != actual={offset - objectStartOffset}")

   # Collectables #2
   collectables2 = []
   if not persistentLevelFlag:
      (offset, collectedCount2) = parseUint32(offset, data)
      for count in range(collectedCount2):
         (offset, objectReference) = parseObjectReference(offset, data)
         collectables2.append(objectReference)

   return (offset, (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2))

def parseProperties(offset, data):
   properties = []
   propertyTypes = []
   while True:
      (offset, propertyName) = parseString(offset, data)
      if propertyName == "None":
         break

      (offset, propertyType) = parseString(offset, data)
      (offset, propertySize) = parseUint32(offset, data)
      (offset, propertyIndex) = parseUint32(offset, data)  # Doesn't appear to be an actual 'index'
      retainedPropertyType = propertyType

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
         (offset, flags) = parseUint32(offset, data)
         (offset, historyType) = parseUint8(offset, data)
         if historyType == 255:
            (offset, isTextCultureInvariant) = parseUint32(offset, data)
            (offset, s) = parseString(offset, data)
            properties.append([propertyName, [flags, historyType, isTextCultureInvariant, s]])
         elif historyType == 3: # Only observed in modded save (for propertyName="mMapText")
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
               offset = confirmBasicType(offset, data, parseUint32, 18) # flags
               offset = confirmBasicType(offset, data, parseUint8, 255) # historyType
               offset = confirmBasicType(offset, data, parseUint32, 1)  # isTextCultureInvariant
               (offset, argValue) = parseString(offset, data)
               args.append([argName, argValue])
            properties.append([propertyName, [flags, historyType, uuid, format, args]])
         else:
            raise ParseError(f"Unexpected TextProperty historyType {historyType}")
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
            elif structElementType in ("ConnectionData", "BuildingConnection", "STRUCT_ProgElevator_Floor"): # Only observed in modded save
               (offset, allValues) = parseData(offset, data, structSize)
               values.append(allValues)
               while len(values) < arrayCount:
                  values.append(None)
            elif structElementType in (
                  "BlueprintCategoryRecord",
                  "BlueprintSubCategoryRecord",
                  "DroneTripInformation",
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
                  "ManagedSignConnectionSettings", # Only observed in modded save
                  "SignComponentData",             # Only observed in modded save
                  "SignComponentVariableData",     # Only observed in modded save
                  "SignComponentVariableMetaData", # Only observed in modded save
                  "SwatchGroupData",               # Only observed in modded save
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
         offset = confirmBasicType(offset, data, parseUint32, 0)
         offset = confirmBasicType(offset, data, parseUint32, 0)
         offset = confirmBasicType(offset, data, parseUint32, 0)
         offset = confirmBasicType(offset, data, parseUint32, 0)
         offset = confirmBasicType(offset, data, parseUint8, 0)
         propertyStartOffset = offset
         if structPropertyType == "InventoryItem":
            offset = confirmBasicType(offset, data, parseUint32, 0)
            (offset, itemName) = parseString(offset, data)
            (offset, itemHasPropertiesFlag) = parseBool(offset, data, parseUint32, "StructProperty.InventoryItem.itemHasPropertiesFlag")
            itemProperties = 1
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
            (offset, value) = parseFloat(offset, data)
            properties.append([propertyName, value])
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
            offset = confirmBasicType(offset, data, parseUint32, 1)
            (offset, clientType) = parseUint8(offset, data) # Seen 1 or 6 (Maybe 1=Epic 6=Steam)
            (offset, clientSize) = parseUint32(offset, data)
            (offset, clientData) = parseData(offset, data, clientSize)
            properties.append([propertyName, [clientUuid, clientType, clientData]])
         elif structPropertyType in ("Rotator", "SignComponentEditorMetadata"): # Only observed in modded save
            (offset, rawData) = parseData(offset, data, propertySize)
            properties.append([propertyName, rawData])
         elif structPropertyType in (
               "BlueprintRecord",
               "BoomBoxPlayerState",
               "DroneDockingStateInfo",
               "DroneTripInformation",
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
               "TimerHandle",
               "TopLevelAssetPath", # 20240915\SatisFaction_20240915-002433.sav
               "TrainDockingRuleSet",
               "TrainSimulationData",
               "Transform",
               "Vector_NetQuantize",
               "BuildingConnections", # Only observed in modded save
               "ManagedSignData",     # Only observed in modded save
               ):
            (offset, prop, propTypes) = parseProperties(offset, data)
            properties.append([propertyName, [prop, propTypes]])
         else:
            raise ParseError(f"Unsupported structPropertyType '{structPropertyType}'")
         if propertySize != offset - propertyStartOffset:
            raise ParseError(f"Unexpected propery size. diff={offset - propertyStartOffset - propertySize} type={propertyType} structPropertyType={structPropertyType} start={propertyStartOffset}")

      elif propertyType == "MapProperty":
         (offset, keyType) = parseString(offset, data)
         (offset, valueType) = parseString(offset, data)
         retainedPropertyType = [propertyType, keyType, valueType]
         offset = confirmBasicType(offset, data, parseUint8, 0)
         propertyStartOffset = offset
         offset = confirmBasicType(offset, data, parseUint32, 0)
         (offset, numberOfElements) = parseUint32(offset, data)
         values = []
         propTypess = None
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
         raise ParseError(f"Unsupported propertyType '{propertyType}' for property '{propertyName}'")

      propertyTypes.append([propertyName, retainedPropertyType, propertyIndex])

      if len(properties) != len(propertyTypes):
         raise ParseError(f"Logic error: Number of properties {len(properties)} != Number of property types {len(propertyTypes)}")

   return (offset, properties, propertyTypes)

def readCompressedSaveFile(filename):
   with open(filename, "rb") as fin:
      return fin.read()

class ProgressBar():
   prior = None
   current = 0
   fillChar = "#"
   emptyChar = "."
   completedChar = b'\x13\x27'.decode('utf-16')
   fillColor = "\033[1;37;47m"
   emptyColor = "\033[0;30;40m"
   resetColor = "\033[0m"
   def __init__(self, total, prefix="", width=70):
      self.total = total
      self.prefix = prefix
      self.width = width
      self.show()
   def add(self, more=1):
      self.current += more
      self.show()
   def set(self, current=1):
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

def decompressSaveFile(offset, data):
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

def pathNameToReadableName(name):
   if len(name) == 0:
      return name
   originalName = name
   pos = name.rfind(".")
   if pos != -1:
      name = name[pos+1:]
   if name in READABLE_PATH_NAME_CORRECTIONS:
      return READABLE_PATH_NAME_CORRECTIONS[name]
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

def readFullSaveFile(filename, decompressedOutputFilename = None):
   global satisfactoryCalculatorInteractiveMapExtras
   satisfactoryCalculatorInteractiveMapExtras = []

   data = readCompressedSaveFile(filename)
   saveFileInfo = SaveFileInfo()
   offset = saveFileInfo.parse(data)
   data = decompressSaveFile(offset, data)

   # SaveFileHeader
   (offset, uncompressedSize) = parseUint64(0, data) # uncompressedSize <= len(data)
   uncompressedSize += 8 # Length doesn't include the length itself even if the length is called compressed data length and the length is itself compressed.

   if decompressedOutputFilename != None:
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

   offset = confirmBasicType(offset, data, parseUint32, 0)

   if offset == len(data):
      satisfactoryCalculatorInteractiveMapExtras.append("Missing final array count") # This can cause the input save file to lose content
      data += b"\x00\x00\x00\x00"

   (offset, extraMercerShrineCount) = parseUint32(offset, data)
   extraMercerShrineList = []
   for idx in range(extraMercerShrineCount):
      # Persistent_Level:PersistentLevel.BP_MercerShrine_C_*
      (offset, msLevelPathName) = parseObjectReference(offset, data)
      extraMercerShrineList.append(msLevelPathName)

   if offset != len(data):
      raise ParseError(f"Parsed data {offset} does not match decompressed data {len(data)}.")
   if PROGRESS_BAR_ENABLE_PARSE:
      progressBar.complete()

   if len(satisfactoryCalculatorInteractiveMapExtras) > 0:
      print(f"File suspected of having been saved by satisfactory-calculator.com/en/interactive-map for {len(satisfactoryCalculatorInteractiveMapExtras)} reasons.", file=sys.stderr)

   if PRINT_DEBUG:
      countOfNoneCollectables1 = 0
      emptyCollectables1 = 0
      for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
         if collectables1 == None:
            countOfNoneCollectables1 += 1
         elif len(collectables1) == 0:
            emptyCollectables1 += 1
      if countOfNoneCollectables1 > 0:
         print(f"Skipped {countOfNoneCollectables1} level collectables1 with {emptyCollectables1} empty collectables1")
      if extraMercerShrineCount > 0:
         print(f"extraMercerShrineCount={extraMercerShrineCount}")

   return (saveFileInfo, (headhex1, headhex2), grids, levels, extraMercerShrineList)

def readSaveFileInfo(filename):
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
   droppedItemsOutputFilename = outBase + "-dropped.txt"

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
         (saveFileInfo, headhex, grids, levels, extraMercerShrineList) = readFullSaveFile(savFilename, decompressedOutputFilename)
         dumpOut.write("Successfully parsed save file\n\n")

         dumpOut.write(str(saveFileInfo))
         dumpOut.write("\nGrids:\n")
         for grid in grids:
            dumpOut.write(f"  {grid}\n")

         if PROGRESS_BAR_ENABLE_DUMP:
            progressBarTotal = 0
            for level in levels:
               (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) = level
               progressBarTotal += len(actorAndComponentObjectHeaders)
               progressBarTotal += len(objects)
               if collectables1 != None:
                  progressBarTotal += len(collectables1)
               progressBarTotal += len(collectables2)
            progressBar = ProgressBar(progressBarTotal, "      Dumping: ")
         dumpOut.write("\nLevels:\n")
         for level in levels:
            (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) = level
            dumpOut.write(f"  Level: {levelName}\n")
            for actorOrComponentObjectHeader in actorAndComponentObjectHeaders:
               dumpOut.write(f"    {actorOrComponentObjectHeader}\n")
               if PROGRESS_BAR_ENABLE_DUMP:
                  progressBar.add()
            for object in objects:
               dumpOut.write(f"    {object}\n")
               if PROGRESS_BAR_ENABLE_DUMP:
                  progressBar.add()
            if collectables1 != None:
               for collectable in collectables1:
                  dumpOut.write(f"    Collectable1: {collectable}\n")
                  if PROGRESS_BAR_ENABLE_DUMP:
                     progressBar.add()
            for collectable in collectables2:
               dumpOut.write(f"    Collectable2: {collectable}\n")
               if PROGRESS_BAR_ENABLE_DUMP:
                  progressBar.add()
         if PROGRESS_BAR_ENABLE_DUMP:
            progressBar.complete()

         dumpOut.write("\nAdditional object references:\n")
         for msLevelPathName in extraMercerShrineList:
            dumpOut.write(f"  {msLevelPathName}\n")

         with open(somersloopOutputFilename, "w") as somersloopOut:
            somersloopOut.write("# Exported from Satisfactory \n")
            somersloopOut.write("SOMERSLOOPS = {\n")
            for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
               for actorOrComponentObjectHeader in actorAndComponentObjectHeaders:
                  if isinstance(actorOrComponentObjectHeader, ActorHeader):
                     if actorOrComponentObjectHeader.typePath == SOMERSLOOP:
                        # scale=(1.600000023841858, 1.600000023841858, 1.600000023841858)
                        somersloopOut.write(f'   "{actorOrComponentObjectHeader.instanceName}": ("{actorOrComponentObjectHeader.rootObject}", {actorOrComponentObjectHeader.rotation}, {actorOrComponentObjectHeader.position}),\n')
            somersloopOut.write("} # SOMERSLOOPS\n")

         with open(mercerSphereOutputFilename, "w") as mercerSphereOut:
            mercerSphereOut.write("# Exported from Satisfactory \n")
            mercerSphereOut.write("MERCER_SPHERES = {\n")
            for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
               for actorOrComponentObjectHeader in actorAndComponentObjectHeaders:
                  if isinstance(actorOrComponentObjectHeader, ActorHeader):
                     if actorOrComponentObjectHeader.typePath == MERCER_SPHERE:
                        # scale=(2.700000047683716, 2.6999998092651367, 2.6999998092651367)
                        mercerSphereOut.write(f'   "{actorOrComponentObjectHeader.instanceName}": ("{actorOrComponentObjectHeader.rootObject}", {actorOrComponentObjectHeader.rotation}, {actorOrComponentObjectHeader.position}),\n')
            mercerSphereOut.write("} # MERCER_SPHERES\n")
            mercerSphereOut.write("MERCER_SHRINES = {\n")
            for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
               for actorOrComponentObjectHeader in actorAndComponentObjectHeaders:
                  if isinstance(actorOrComponentObjectHeader, ActorHeader):
                     if actorOrComponentObjectHeader.typePath == MERCER_SHRINE:
                        # scale=(1.0, 1.0, 1.0) or (0.8999999761581421, 0.8999999761581421, 0.8999999761581421)
                        mercerSphereOut.write(f'   "{actorOrComponentObjectHeader.instanceName}": ("{actorOrComponentObjectHeader.rootObject}", {actorOrComponentObjectHeader.rotation}, {actorOrComponentObjectHeader.position}, {actorOrComponentObjectHeader.scale[1]}),\n')
            mercerSphereOut.write("} # MERCER_SHRINES\n")

         with open(slugOutputFilename, "w") as slugOut:

            numSlug = [0, 0, 0]
            for slugIdx in range(3):
               slugOut.write(f"POWER_SLUGS_{('BLUE', 'YELLOW', 'PURPLE')[slugIdx]} = " + "{\n")
               for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
                  for actorOrComponentObjectHeader in actorAndComponentObjectHeaders:
                     if isinstance(actorOrComponentObjectHeader, ActorHeader) and actorOrComponentObjectHeader.typePath == POWER_SLUG[slugIdx]:
                        slugOut.write(f'   "{actorOrComponentObjectHeader.instanceName}": {actorOrComponentObjectHeader.position},\n')
                        numSlug[slugIdx] += 1
               slugOut.write("}\n")
            slugOut.write(f"# Num slugs: {numSlug}")

            for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
               if collectables1 != None:
                  for collectable in collectables1:
                     if collectable.pathName.startswith("Persistent_Level:PersistentLevel.BP_Crystal"):
                        slugOut.write(f"COLLECTED: {collectable.pathName}\n")

         with open(droppedItemsOutputFilename, "w") as dropOut:
            items = {}
            for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
               for actorOrComponentObjectHeader in actorAndComponentObjectHeaders:
                  if isinstance(actorOrComponentObjectHeader, ActorHeader) and actorOrComponentObjectHeader.typePath == "/Script/FactoryGame.FGItemPickup_Spawnable":
                     items[actorOrComponentObjectHeader.instanceName] = actorOrComponentObjectHeader.position
            specificItems = {}
            for (levelName, actorAndComponentObjectHeaders, collectables1, objects, collectables2) in levels:
               for object in objects:
                  if object.instanceName in items:
                     pickupItems = getPropertyValue(object.properties, "mPickupItems")
                     if pickupItems != None:
                        pickupItems = pickupItems[0]
                        item = getPropertyValue(pickupItems, "Item")
                        if item != None:
                           item = item[0]
                           numItems = getPropertyValue(pickupItems, "NumItems")
                           if numItems != None:
                              if item not in specificItems:
                                 specificItems[item] = []
                              specificItems[item].append([object.instanceName, numItems, items[object.instanceName]])
            dropOut.write("# Exported from Satisfactory \n")
            dropOut.write("FREE_DROPPED_ITEMS = {\n")
            for item in specificItems:
               dropOut.write(f'   "{item}": [ # {pathNameToReadableName(item)}\n')
               for (instanceName, quantity, location) in specificItems[item]:
                  dropOut.write(f'      ({quantity}, {location}, "{instanceName}"),\n')
               dropOut.write(f'      ],\n')
            dropOut.write("} # FREE_DROPPED_ITEMS\n")

      except Exception as error:
         raise Exception(f"ERROR: While processing '{savFilename}': {error}")

   exit(0)
