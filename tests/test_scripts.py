import pytest
from idleon_saver.scripts.decode import ldb2stencyl, stencyl2json
from idleon_saver.scripts.encode import json2stencyl, stencyl2ldb
from idleon_saver.utility import chunk


@pytest.mark.parametrize(
    "scripts", [(stencyl2json, json2stencyl), (stencyl2ldb, ldb2stencyl)]
)
def test_inversion(testargs, datafiles, scripts):
    with open(testargs.workdir / "encoded.txt", "w") as file:
        file.write(datafiles["stencyl"])

    for f in scripts:
        f(testargs)

    with open(testargs.workdir / "encoded.txt", "r") as file:
        assert chunk(datafiles["stencyl"], 50) == chunk(file.read(), 50)
