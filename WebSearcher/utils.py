import hashlib
import re
from pathlib import Path

import orjson

# Files ------------------------------------------------------------------------


def read_lines(fp: str | Path):
    fp = Path(fp)
    with open(fp) as infile:
        if fp.suffix == ".json":
            return [orjson.loads(line) for line in infile]
        else:
            return [line.strip() for line in infile]


def write_lines(iter_data, fp: str | Path, overwrite=False):
    fp = Path(fp)
    mode = "w" if overwrite else "a+"

    with open(fp, mode) as outfile:
        for data in iter_data:
            if fp.suffix == ".json":
                line_output = orjson.dumps(data).decode("utf-8")
            else:
                line_output = data
            outfile.write(f"{line_output}\n")


# Strings ----------------------------------------------------------------------


def get_between_parentheses(s, regex=r"\((.*?)\)"):
    return re.search(regex, s).group(1)


# Misc -------------------------------------------------------------------------


def hash_id(s):
    return hashlib.sha224(s.encode("utf-8")).hexdigest()
