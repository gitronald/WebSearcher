import re
import os
import json
import random
import itertools
import pandas as pd
from hashlib import sha224
from timeit import default_timer
from string import ascii_letters, digits

# Files ------------------------------------------------------------------------

def all_abs_paths(dir):
    file_paths = []
    for folder, subs, files in os.walk(dir):
        for filename in files:
            file_paths.append(os.path.abspath(os.path.join(folder, filename)))
    return file_paths

def read_lines(fp):
    try:
        is_json = '.json' in fp
    except TypeError:
        is_json = '.json' in fp.__fspath__()

    with open(fp, 'r') as infile:
        if is_json:
            return [json.loads(line) for line in infile]
        else:
            return [line.strip() for line in infile]

def write_lines(iter_data, fp, overwrite=False):
    mode = 'w' if overwrite else 'a+'

    try:
        is_json = '.json' in fp
    except TypeError:
        is_json = 'json' in fp.__fspath__()

    with open(fp, mode) as outfile:
        if is_json:
            for data in iter_data:
                outfile.write('%s\n' % json.dumps(data))
        else:
            for data in iter_data:
                outfile.write('%s\n' % data)


def write_sql_row(data, table, conn):
    """Write a dict `data` as a row in `table` via SQL connection `conn`
    
    Arguments:
        data (dict) -- A dictionary to insert as a row.
        table (str) -- The name of the table.
        conn -- A connection to a SQL database.
    """
    row = pd.DataFrame(data, index=[0])
    row.to_sql(table, con=sql_conn, index=False, if_exists='append')

# Descriptive Stats ------------------------------------------------------------

def dnum(dfcol):
    if df_col.dtype in [int, float]:
        return df_col.describe()
    else:
        return 0

def dft(dfcol):
    tab = pd.DataFrame({
        'n': dfcol.value_counts(),
        'p': dfcol.value_counts(True)
    }).sort_index()
    return tab

# Lists ------------------------------------------------------------------------

def unlist(nested_list):
    return list(itertools.chain.from_iterable(nested_list))

# Strings ----------------------------------------------------------------------

def split_by_spaces(s, n=2):
    # Split a string by n or more spaces
    return re.split(r'\s{%d,}' % n, s)

def get_between_brackets(s, regex=r'\[(.*?)\]'):
    return re.search(regex, s).group(1)

def get_between_parentheses(s, regex=r'\((.*?)\)'):
    return re.search(regex, s).group(1)
    
def remove_digits(string):
    return "".join([x for x in string if not x.isdigit()]).strip()

# Misc -------------------------------------------------------------------------

def make_id():
    return hashlib.sha224(random_string().encode('utf-8')).hexdigest()

def alphanumerics():
    """Generate upper and lowercase letters and digits"""
    return ascii_letters + digits

def random_string(length=12):
    """Generate a random string of alphanumerics"""
    return ''.join(random.choice(alphanumerics()) for i in range(length))
