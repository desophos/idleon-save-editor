import csv
import json
import logging
from argparse import ArgumentParser, Namespace
from enum import Enum
from itertools import chain, starmap
from math import floor
from pathlib import Path
from string import ascii_lowercase
from typing import Any, Iterator, Optional, Tuple

from data import (
    Bags,
    bag_maps,
    card_bases,
    card_names,
    class_names,
    cog_boosts,
    cog_datas_map,
    cog_type_map,
    constellation_names,
    pouch_names,
    pouch_sizes,
    skill_names,
    stamp_names,
    starsign_ids,
    starsign_names,
    statue_names,
    vial_names,
)
from idleon_saver.ldb import ldb_args
from idleon_saver.utility import from_keys_in, zip_from_iterable

logger = logging.getLogger(__name__)


class Formats(Enum):
    IC = "idleon_companion"
    COG = "cogstruction"

    @staticmethod
    def lookup(key: str):
        for member in Formats.__members__.values():
            if member.value == key:
                return member


def friendly_name(s: str) -> str:
    return s.replace("_", " ").title()


def char_map(data: dict) -> dict[str, str]:
    return dict(zip(data["GetPlayersUsernames"], "_" + ascii_lowercase))


def get_baseclass(which: int) -> int:
    if which in range(1, 5 + 1):
        # special case for beginner because it has only 4 subclasses
        return 1

    for base in [7, 19, 31]:  # warrior, archer, mage
        # each has 6 subclasses (unreleased but still in ClassNames)
        if which in range(base, base + 6 + 1):
            return base

    raise ValueError(f"Class {which} does not exist")


def get_classname(which: int) -> str:
    return friendly_name(class_names[which])


def get_alchemy(data: dict) -> dict[str, dict]:
    return {
        "upgrades": dict(
            zip(("Orange", "Green", "Purple", "Yellow"), data["CauldronInfo"][:4])
        ),
        "vials": {
            friendly_name(name): level
            for name, level in zip(vial_names, data["CauldronInfo"][4])
            if level > 0
        },
    }


def get_starsign_from_index(i: int) -> str:
    return starsign_ids[starsign_names[i]]


def get_starsigns(data: dict) -> dict[str, bool]:
    return {
        starsign_ids[name]: bool(unlocked)
        for name, unlocked in data["StarSignsUnlocked"].items()
    }


def get_cardtier(name: str, level: int) -> int:
    base = card_bases[name] if name in card_bases else 10
    if level == 0:
        return 0
    elif level >= base * 9:
        return 4
    elif level >= base * 4:
        return 3
    elif level >= base:
        return 2
    else:
        return 1


def get_cards(data: dict) -> dict[str, int]:
    return {
        (card_names[name] if name in card_names else name): get_cardtier(name, level)
        for name, level in data["Cards"][0].items()
        if level > 0
    }


def get_stamps(data: dict) -> Iterator[Tuple[str, int]]:
    return zip(stamp_names.values(), chain(*data["StampLevel"]))


def get_statues(data: dict) -> dict:
    return {
        name: {
            "golden": bool(gold),
            "level": max(lvls),
            "progress": floor(max(progs)),
        }
        for name, gold, lvls, progs in zip(
            statue_names,
            data["StatueG"],
            *[
                [
                    [statue[i] for statue in statues]
                    for statues in zip_from_iterable(
                        char["StatueLevels"] for char in data["PlayerDATABASE"].values()
                    )
                ]
                for i in range(2)
            ],
        )
    }


def get_checklist(data: dict) -> dict[str, bool]:
    return (
        from_keys_in(
            bag_maps[Bags.GEM],
            list(data["PlayerDATABASE"].values())[0]["InvBagsUsed"],
            True,
        )
        | from_keys_in(bag_maps[Bags.STORAGE], data["InvStorageUsed"].keys(), True)
        | {name: True for name, level in get_stamps(data) if level > 0}
    )


def get_pouchsize(itemtype: str, stacksize: int) -> str:
    return (
        "Mini"
        if stacksize == 25 and itemtype == "bCraft"
        else "Miniscule"
        if stacksize == 25 and itemtype == "Foods"
        else pouch_sizes[stacksize]
    )


def get_pouches(carrycaps: dict[str, int]) -> dict[str, bool]:
    return {
        " ".join(
            [
                get_pouchsize(itemtype, stacksize),
                pouch_names[itemtype],
                "Pouch",
            ]
        ): True
        for itemtype, stacksize in carrycaps.items()
        if stacksize > 10
    }


def get_chars(data: dict) -> list[dict]:
    return [
        {
            "name": charname,
            "class": get_classname(chardata["CharacterClass"]),
            "level": chardata["PersonalValuesMap"]["StatList"][4],
            "constellations": {
                constellation_names[i]: True
                for i, (chars, completed) in enumerate(data["StarSignProg"])
                if char_map(data)[charname] in chars
            },
            "starSigns": {
                get_starsign_from_index(int(k)): True
                for k in chardata["PersonalValuesMap"]["StarSign"]
                .strip(",_")
                .split(",")
            },
            "skills": dict(list(zip(skill_names, chardata["Lv0"]))[1:]),
            "items": from_keys_in(
                bag_maps[Bags.INV], chardata["InvBagsUsed"].keys(), True
            )
            | get_pouches(chardata["MaxCarryCap"]),
        }
        for charname, chardata in data["PlayerDATABASE"].items()
    ]


def to_idleon_companion(raw: dict) -> dict:
    return {
        "alchemy": get_alchemy(raw),
        "starSigns": get_starsigns(raw),
        "cards": get_cards(raw),
        "stamps": {name: level for name, level in get_stamps(raw) if level > 0},
        "statues": get_statues(raw),
        "checklist": get_checklist(raw),
        "chars": get_chars(raw),
    }


def save_idleon_companion(workdir: Path, data: dict):
    outfile = workdir / "idleon_companion.json"

    with open(outfile, "w", encoding="utf-8") as file:
        json.dump(data, file)

    logger.info(f"Wrote file: {outfile}")


def get_empties(cogs: list[str]) -> list[dict[str, int]]:
    if len(cogs) < 96:
        raise AssertionError(
            "cog list must contain at least 96 entries to cover the whole cog board; "
            f"{len(cogs)} isn't enough"
        )

    empties: list[dict[str, int]] = []
    # The cog board is 8 rows by 12 columns = 96 spaces.
    for y in range(8):
        for x in range(12):
            i = y * 12 + x
            # Ignore occupied spaces.
            if cogs[i] == "Blank":
                empties.append({"empties_x": x, "empties_y": y})

    return empties


def get_cog_type(name: str) -> Optional[str]:
    # Check simple special cases.
    if name == "Blank":
        return None
    elif name.startswith("Player_"):
        return "Character"
    elif name == "CogY":
        return "Yang_Cog"
    elif name.startswith("CogZ"):
        return "Omni_Cog"

    # Check each type of directional cog.
    for direction, cog_type in cog_type_map.items():
        if name.endswith(direction):
            return f"{cog_type}_Cog"

    # If the name didn't match any special cases, it's just a regular cog.
    return "Cog"


def get_cog_data(cog: dict[str, Any], name: str) -> Optional[dict[str, Any]]:
    data = {}

    cog_type = get_cog_type(name)
    if cog_type is None:
        return None

    data["cog type"] = cog_type
    data["name"] = name.removeprefix("Player_") if cog_type == "Character" else ""

    for key, field in cog_datas_map.items():
        try:
            # Boosts are stored as percentages, so convert them to multipliers.
            data[field] = cog[key] / 100 if key in cog_boosts else cog[key]
        except KeyError:
            # Cogs only have keys for whatever bonuses they have,
            # but we need to fill in the missing fields for DictWriter.
            data[field] = ""

    return data


def to_cogstruction(raw: dict) -> dict[str, Any]:
    return {
        "cog_datas": list(
            filter(None, starmap(get_cog_data, zip(raw["CogMap"], raw["CogOrder"])))
        ),  # Filter to ignore blank cogs.
        "empties_datas": get_empties(raw["CogOrder"]),
    }


def save_cogstruction(workdir: Path, data: dict):
    for which in ["cog_datas", "empties_datas"]:
        outfile = workdir / f"{which}.csv"

        with open(outfile, "w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=data[which][0].keys())

            writer.writeheader()
            for row in data[which]:
                writer.writerow(row)

        logger.info(f"Wrote file: {outfile}")


parsers = {Formats.IC: to_idleon_companion, Formats.COG: to_cogstruction}
savers = {Formats.IC: save_idleon_companion, Formats.COG: save_cogstruction}


def main(args: Namespace):
    infile = args.workdir / (args.infile or "decoded.json")
    with open(infile, encoding="utf-8") as file:
        data = json.load(file)

    parsed = parsers[args.to](data)
    savers[args.to](args.workdir, parsed)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--to",
        choices=list(Formats),
        type=Formats.lookup,
        default=Formats.IC,
        help="format to parse save data into",
    )
    main(ldb_args(parser))
