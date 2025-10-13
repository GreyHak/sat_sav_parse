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
import os
import shutil
import sys
import time

import sav_parse
import sav_to_html

if __name__ == '__main__':

   if (len(sys.argv) <= 1 or len(sys.argv[1]) == 0) and os.path.isdir(".config/Epic/FactoryGame/Saved/SaveGames/server"):
      savePath = ".config/Epic/FactoryGame/Saved/SaveGames/server"
   elif (len(sys.argv) <= 1 or len(sys.argv[1]) == 0) and "LOCALAPPDATA" in os.environ and os.path.isdir(f"{os.environ['LOCALAPPDATA']}/FactoryGame/Saved/SaveGames"):
      savePath = f"{os.environ['LOCALAPPDATA']}/FactoryGame/Saved/SaveGames/*"
   elif len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
      savePath = sys.argv[1]
   else:
      print("ERROR: Please supply save file path/name to perform parsing.", file=sys.stderr)
      exit(1)

   htmlOutputDir = "."
   if len(sys.argv) > 2:
      htmlOutputDir = sys.argv[2]
      if not os.path.isdir(htmlOutputDir):
         print(f"ERROR: HTML output folder does not exist: '{htmlOutputDir}'")
         exit(1)

   sleepTimeInSeconds = 1.0 * 60 # 1 minute
   if len(sys.argv) > 3:
      sleepTimeInSeconds = float(sys.argv[3])

   archivePath = None
   if len(sys.argv) > 4:
      archivePath = sys.argv[4]
      if not os.path.isdir(archivePath):
         print(f"ERROR: Archive folder does not exist: '{archivePath}'")
         exit(1)

   if archivePath is None:
      print(f"Monitoring {savePath}")
   else:
      print(f"Monitoring {savePath} and archiving to {archivePath}")

   priorSavFilename = None
   while True:
      allSaveFiles = glob.glob(f"{savePath}/*.sav")
      try:
         savFilename = max(allSaveFiles, key=os.path.getmtime)
      except FileNotFoundError:
         next

      if savFilename != priorSavFilename:
         priorSavFilename = savFilename
         savBasename = os.path.basename(savFilename)
         print(f"Found new file {savBasename}")

         print(f"Generating HTML in {htmlOutputDir}")
         sav_to_html.generateHTML(savFilename, htmlOutputDir)

         if archivePath is not None:
            saveFileInfo = sav_parse.readSaveFileInfo(savFilename)
            archiveFilePath = os.path.join(archivePath, f"{saveFileInfo.sessionName}_{saveFileInfo.saveDatetime.strftime('%Y%m%d-%H%M%S')}.sav")
            if not os.path.exists(archiveFilePath):
               print(f"Archiving save to {archiveFilePath}")
               shutil.copy2(savFilename, archiveFilePath)

         print()
      time.sleep(sleepTimeInSeconds)
