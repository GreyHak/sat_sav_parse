# Satisfactory Save Parser

Copyright (c) 2024 [GreyHak](https://github.com/GreyHak)

A set of Python tools for parsing Satisfactory save files, and then displaying
and manipulating the contents.

[Satisfactory](https://www.satisfactorygame.com/) is a non-competitive,
first-person, open-world, factory-building and exploration game produced by
[Coffee Stain Studios](https://www.coffeestain.com/).

## sav_parse.py

`sav_parse.py` will decode the save file.  It can be used as either a library
or a program.

When used as a library, call `sav_parse.readFullSaveFile(<filename>)` to
parse the entire save file, or `sav_parse.readSaveFileInfo(<filename>)` to
parse just the header information.

When used as a program, from the command line call `py sav_parse.py <filename>`
to generate a text file representation of the save file.

## sav_to_resave.py

`sav_to_resave.py` will create a save file based on the data producted by
`sav_parse.py` or a manipulated varient of that data.

## sav_cli.py

`sav_cli.py` makes use of `sav_parse.py` and `sav_to_resave.py` to either
provide specific information from the save file or change data in a save file.

Usage:
  - `py sav_cli.py --help`
  - `py sav_cli.py --list-players <save-filename>`
  - `py sav_cli.py --list-player-inventory <player-state-num> <save-filename>`
  - `py sav_cli.py --export-player-inventory <player-state-num> <save-filename> <output-json-filename>`
  - `py sav_cli.py --import-player-inventory <player-state-num> <original-save-filename> <input-json-filename> <new-save-filename> [--same-time]`
  - `py sav_cli.py --tweak-player-inventory <player-state-num> <slot-index> <item> <quantity> <original-save-filename> <new-save-filename> [--same-time]`
  - `py sav_cli.py --rotate-foundations <primary-color-hex-or-preset> <secondary-color-hex-or-preset> <original-save-filename> <new-save-filename> [--same-time]`
  - `py sav_cli.py --clear-fog <original-save-filename> <new-save-filename> [--same-time]`
  - `py sav_cli.py --export-hotbar <player-state-num> <save-filename> <output-json-filename>`
  - `py sav_cli.py --import-hotbar <player-state-num> <original-save-filename> <input-json-filename> <new-save-filename> [--same-time]`
  - `py sav_cli.py --change-num-inventory-slots <num-inventory-slots> <original-save-filename> <new-save-filename> [--same-time]`
  - `py sav_cli.py --restore-somersloops <original-save-filename> <new-save-filename> [--same-time]`

## sav_to_html.py

Usage: `py sav_to_html.py <save-filename> [output-html-file]`

`sav_to_html.py` makes use of `sav_parse.py` to decode a save file and creates
a save.html.  The HTML page contains:
  - Session Name
  - Save Date
  - Play Time
  - Game Phase
  - Active Milestone
  - Mined Resource Count
  - Collected Power Slugs, Somersloops, and Mercer Sphere Counts
  - Unopened, Looted, and Opened/Unlooted Hard Drive Counts
  - Unlock Progress Counts
  - Sink Point Progress
  - Dimensional Depot Contains: List by item with quantity and percent full
  - Currently Built Items: List of items by quantity

When a blank map, included in the release as `blank_map20.png`,
is provided, this script also creates maps of:
  - The location of all the remaining power slugs.
  - The location of all the remaining somersloops.
  - The location of all the remaining mercer spheres.
  - The location of all the hard drives including which are opened, looted and
    opened/unlooted.
  - The power grid.
  - The resource nodes including their type, locations, purity, and usage.

## Credits

The source code in this repo was developed by [GreyHak](https://github.com/GreyHak).

Source code credit for the the quaternion/euler rotation conversions used by
`sav_cli.py` goes to [**Addison Sears-Collins**](https://automaticaddison.com).

Thanks go to **[AnthorNet](https://github.com/AnthorNet)** of [Satisfactory
Calculator Interactive Map](https://satisfactory-calculator.com/en/interactive-map)
fame.
* The map used by `sav_to_html.py` is a modified version of the map extracted
  from Anthor's Interactive Map.
* Resource purities, available in the `sav_parse.py` RESOURCE_PURITY variable,
  used by `sav_to_html.py`, were extracted from Anthor's Interactive Map.
* Anthor's [pre-Update-8 JavaScript code](https://github.com/AnthorNet/SC-InteractiveMap/blob/dev/src/SaveParser/Read.js)
  was used as a reference.
* Anthor's Interactive Map was also a great test tool to verify the save files
  produced by `sav_to_resave.py` and `sav_cli.py`.

Thanks go to the Wiki authors who documented the old, but still very helpful,
v0.6.1.3 version of the save file format at
[Satisfactory GG Wiki Save Files](https://satisfactory.wiki.gg/wiki/Save_files#Save_file_format).
I updated the Satisfactory GG Wiki for v1.0.0.3 based on the information I
gained during creation of this tools.

## License

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, version 3.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
