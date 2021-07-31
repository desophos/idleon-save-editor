import json
import random
from argparse import Namespace

from idleon_saver.ldb import ldb_args
from idleon_saver.stencyl.encoder import StencylEncoder
from idleon_saver.utility import normalize_workfile

CHARS = [x for x in map(chr, range(32, 127)) if x.isalnum()]


class StencylMangler(StencylEncoder):
    def _encode_string(self, s: str) -> str:
        """Same as super except outputs random chars."""
        if s in self.strcache:
            return f"R{self.strcache.index(s)}"
        else:
            self.strcache.append(s)
            # Instead of s, output 10-20 random alphanumeric chars.
            # This should be enough chars to ensure unique strings.
            s = "".join(random.choices(CHARS, k=random.randint(10, 20)))
            return f"y{len(s)}:{s}"


def main(args: Namespace):
    infile = normalize_workfile(args.workdir, "decoded_types.json")
    workdir = infile.parent

    with open(infile, encoding="utf-8") as file:
        data = json.load(file)

    encoded = StencylMangler(data).result

    outfile = workdir / "mangled.txt"
    with open(outfile, "w", encoding="ascii") as file:
        file.write(encoded)

    print(f"Wrote file: {outfile}")


if __name__ == "__main__":
    main(ldb_args())
