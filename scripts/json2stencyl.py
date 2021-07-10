import argparse
import json
from pathlib import Path

from idleon_save_editor.stencyl import StencylEncoder

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--file",
        type=Path,
        default="tmp/decoded.json",
        help="location of decoded JSON save file",
    )
    args = parser.parse_args()

    with open(args.file, encoding="utf-8") as file:
        data = json.load(file)

    encoded = StencylEncoder(data).result

    outfile = args.file.parent / "encoded.txt"
    with open(outfile, "w", encoding="ascii") as file:
        file.write(encoded)

    print(f"Wrote file: {outfile}")