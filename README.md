# Idleon Save Editor

Converts Legends of Idleon Steam save files to and from JSON.

## Warning

Re-encoding the JSON data is not yet working correctly. **Use at your own risk.**

**MAKE BACKUPS** before using and ***DO NOT USE THE ENCODER ON YOUR REAL SAVE DATABASE!***

## Disclaimer

I do not endorse using this tool to edit your live save files. 
This tool is for educational and investigative purposes only.

## Instructions

### Setup

Use either `poetry install` (recommended) or `pip install .` to install dependencies.

Copy your database to a test location (default is `~/dev/leveldb`). For example:

```
cp -r ~/AppData/Roaming/legends-of-idleon/"Local Storage"/leveldb ~/dev/leveldb
```

### Run

You can pass `--help` to any script to see the arguments it takes.
If your paths don't match the defaults, you'll need to pass your paths to the scripts.

Script argument defaults:

* `--idleon`: `C:/Program Files (x86)/Steam/steamapps/common/Legends of Idleon`
* `--ldb`: `~/dev/leveldb`

Currently, scripts must be run individually in sequence. This process will be improved.

1. `ldb2stencyl`
2. `stencyl2json`
3. View/edit `decoded.json` file if desired
4. `json2stencyl`
5. `stencyl2ldb`
