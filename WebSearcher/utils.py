import re
import orjson
import hashlib

# Files ------------------------------------------------------------------------

def read_lines(fp):
    try:
        is_json = '.json' in fp
    except TypeError:
        is_json = '.json' in fp.__fspath__()

    with open(fp, 'r') as infile:
        if is_json:
            return [orjson.loads(line) for line in infile]
        else:
            return [line.strip() for line in infile]

def write_lines(iter_data, fp, overwrite=False):
    mode = 'w' if overwrite else 'a+'

    try:
        is_json = '.json' in fp
    except TypeError:
        is_json = 'json' in fp.__fspath__()

    with open(fp, mode) as outfile:
        for data in iter_data:
            if is_json:
                line_output = orjson.dumps(data).decode('utf-8')
            else:
                line_output = data
            outfile.write(f"{line_output}\n")

# Strings ----------------------------------------------------------------------

def get_between_parentheses(s, regex=r'\((.*?)\)'):
    return re.search(regex, s).group(1)

# Misc -------------------------------------------------------------------------

def hash_id(s):
    return hashlib.sha224(s.encode('utf-8')).hexdigest()
