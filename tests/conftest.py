import json
from argparse import Namespace
from pathlib import Path

import pytest
from idleon_saver.ldb import db_key, get_db
from idleon_saver.scripts.export import Exporter, FirebaseExporter, LocalExporter
from idleon_saver.utility import ROOT_DIR


@pytest.fixture(autouse=True, scope="session")
def testargs(tmp_path_factory) -> Namespace:
    args = Namespace()
    args.infile, args.outfile = "", ""  # defaults
    args.workdir = tmp_path_factory.mktemp("work")
    args.ldb = tmp_path_factory.mktemp("ldb")
    # doesn't need to be a real directory
    # because it's only used for the database key
    args.idleon = Path("C:/Program Files (x86)")
    return args


@pytest.fixture(autouse=True, scope="session")
def testdb(testargs):
    with get_db(testargs.ldb, create_if_missing=True) as db:
        db.put(db_key(testargs.idleon), b"_placeholder")


@pytest.fixture(scope="session")
def datafiles() -> dict[str, str]:
    # Tests shouldn't need to know filenames, so provide a layer of abstraction.
    filename2key = {
        "firebase.json": "firebase",
        "local.json": "local",
        "stencylsave.txt": "stencyl",
    }
    data = {}
    for filename, key in filename2key.items():
        with open(ROOT_DIR.joinpath("tests", "data", filename), "r") as file:
            data[key] = file.read()
    return data


@pytest.fixture(
    scope="session",
    params=[(LocalExporter, "local"), (FirebaseExporter, "firebase")],
)
def exporter(datafiles, request) -> Exporter:
    which_exporter, which_data = request.param
    return which_exporter(json.loads(datafiles[which_data]))
