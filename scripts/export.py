import csv
import json
from argparse import ArgumentParser, Namespace
from enum import Enum
from itertools import chain
from math import floor
from pathlib import Path
from string import ascii_lowercase
from typing import Iterator, Tuple

from data import (
    bag_names,
    card_names,
    cog_boosts,
    cog_datas_map,
    cog_type_map,
    constellation_names,
    gem_bag_names,
    pouch_names,
    pouch_sizes,
    skill_names,
    stamp_names,
    statue_names,
    storage_names,
)
from idleon_saver.ldb import ldb_args
from idleon_saver.utility import from_keys_in, normalize_workfile, zip_from_iterable


class Formats(Enum):
    IC = "idleon_companion"
    COG = "cogstruction"

    @staticmethod
    def lookup(key: str):
        for member in Formats.__members__.values():
            if member.value == key:
                return member


def map_bags(names: dict[str, str], capacities: list[list[str]]) -> dict[str, str]:
    return {key: names[name] for key, _, name in capacities if name in names}


def bag_map(data: dict) -> dict[str, str]:
    return map_bags(bag_names, data["CustomLists"]["PlayerCapacities"][0])


def gem_bag_map(data: dict) -> dict[str, str]:
    return map_bags(gem_bag_names, data["CustomLists"]["PlayerCapacities"][0])


def storage_map(data: dict) -> dict[str, str]:
    return map_bags(storage_names, data["CustomLists"]["PlayerCapacities"][1])


def char_map(data: dict) -> dict[str, str]:
    return dict(zip(data["GetPlayersUsernames"], "_" + ascii_lowercase))


def get_baseclass(which: int) -> int:
    if 1 <= which and which <= 5:
        # special case for beginner because it has only 4 subclasses
        return 1
    else:
        for base in [7, 19, 31]:  # warrior, archer, mage
            # each has 6 subclasses (unreleased but still in ClassNames)
            if base <= which and which <= base + 6:
                return base
    raise ValueError(f"Class {which} does not exist")


def get_classname(data: dict, which: int) -> str:
    return data["CustomLists"]["ClassNames"][which].replace("_", " ").title()


def get_alchemy(data: dict) -> dict[str, dict]:
    return {
        "upgrades": dict(
            zip(("Orange", "Green", "Purple", "Yellow"), data["CauldronInfo"][:4])
        ),
        "vials": {
            str(k): v for k, v in enumerate(data["CauldronInfo"][4], start=1) if v > 0
        },
    }


def get_starsigns(data: dict) -> dict[str, bool]:
    return {
        name.replace("_", " "): bool(unlocked)
        for name, unlocked in data["StarSignsUnlocked"].items()
    }


def get_card_bases(data: dict) -> dict[str, float]:
    return {
        name: float(base)
        for name, _, base, _, _ in chain(*data["CustomLists"]["CardStuff"])
    }


def get_cardtier(data: dict, name: str, level: int) -> int:
    base = get_card_bases(data)[name]
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
        card_names[name]: get_cardtier(data, name, level)
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
            gem_bag_map(data),
            list(data["PlayerDATABASE"].values())[0]["InvBagsUsed"],
            True,
        )
        | from_keys_in(storage_map(data), data["InvStorageUsed"].keys(), True)
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
            "class": get_classname(data, chardata["CharacterClass"]),
            "level": chardata["PersonalValuesMap"]["StatList"][4],
            "constellations": {
                constellation_names[i]: True
                for i, (chars, completed) in enumerate(data["StarSignProg"])
                if char_map(data)[charname] in chars
            },
            "starSigns": {
                k: True
                for k in chardata["PersonalValuesMap"]["StarSign"]
                .strip(",_")
                .split(",")
            },
            "skills": dict(list(zip(skill_names, chardata["Lv0"]))[1:]),
            "items": from_keys_in(bag_map(data), chardata["InvBagsUsed"].keys(), True)
            | get_pouches(chardata["MaxCarryCap"]),
        }
        for charname, chardata in data["PlayerDATABASE"].items()
    ]


def to_idleon_companion(raw: dict) -> dict:
    return {
        "version": raw["CustomLists"]["PatchNotesInfo"][-1][0].lstrip("V"),
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

    print(f"Wrote file: {outfile}")


def to_cogstruction(raw: dict) -> dict:
    cog_datas, empties = [], []

    for y in range(8):
        for x in range(12):
            i = y * 12 + x
            if i >= 96:
                break
            elif raw["CogOrder"][i] == "Blank":
                empties.append({"empties_x": x, "empties_y": y})

    for cog, name in zip(raw["CogMap"], raw["CogOrder"]):
        data = {"cog type": "Cog", "name": ""}

        if name == "Blank":
            continue
        elif name.startswith("Player_"):
            data["cog type"] = "Character"
            data["name"] = name.removeprefix("Player_")
        elif name == "CogY":
            data["cog type"] = "Yang_Cog"
        elif name.startswith("CogZ"):
            data["cog type"] = "Omni_Cog"
        else:
            for abbr, cog_type in cog_type_map.items():
                if name.endswith(abbr):
                    data["cog type"] = f"{cog_type}_Cog"
                    break

        for abbr, field in cog_datas_map.items():
            try:
                data[field] = cog[abbr] / 100 if abbr in cog_boosts else cog[abbr]
            except KeyError:
                data[field] = ""

        cog_datas.append(data)

    return {"cog_datas": cog_datas, "empties_datas": empties}


def save_cogstruction(workdir: Path, data: dict):
    for which in ["cog_datas", "empties_datas"]:
        outfile = workdir / f"{which}.csv"

        with open(outfile, "w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=data[which][0].keys())

            writer.writeheader()
            for row in data[which]:
                writer.writerow(row)

        print(f"Wrote file: {outfile}")


def main(args: Namespace):
    export_parsers = {Formats.IC: to_idleon_companion, Formats.COG: to_cogstruction}
    export_savers = {Formats.IC: save_idleon_companion, Formats.COG: save_cogstruction}

    infile = normalize_workfile(args.workdir, "decoded_plain.json")
    workdir = infile.parent

    with open(infile, encoding="utf-8") as file:
        data = json.load(file)

    parsed = export_parsers[args.to](data)
    export_savers[args.to](workdir, parsed)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--to",
        choices=[f for f in Formats],
        type=Formats.lookup,
        default=Formats.IC,
        help="format to parse save data into",
    )
    main(ldb_args(parser))