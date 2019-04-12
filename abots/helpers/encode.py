from json import dumps, loads
from codecs import encode as c_encode, decode as c_decode
from base64 import b64encode, b64decode
from re import compile as regex

# JSON encoder, converts a python object to a string
def jots(data, readable=False):
    kwargs = dict()

    # If readable is set, it pretty prints the JSON to be more human-readable
    if readable:
        kwargs["sort_keys"] = True
        kwargs["indent"] = 4 
        kwargs["separators"] = (",", ":")
    try:
        return json.dumps(data, **kwargs)
    except ValueError as e:
        return None
        
# JSON decoder, converts a string to a python object
def jsto(data):
    try:
        return json.loads(data)
    except ValueError as e:
        return None

# Encodes data to base64
def b64e(data, altchars=None, url=False, use_bin=False):
    if type(data) is str:
        data = data.encode("utf-8")
    if altchars is None and url:
        altchars = "-_"
    base64_data = b64encode(hex_data, altchars)
    if use_bin:
        return base64_data
    return base64_data.decode("utf-8")

# Decodes data from base64
def b64d(base64_data, altchars=None, url=False, use_bin=False):
    if type(base64_data) is str:
        base64_data = base64_data.encode("utf-8")
    if altchars is None and url:
        altchars = "-_"
    data = b64decode(base64_data, altchars)
    if use_bin:
        return data
    return data.decode("utf-8")

# Converts hex to base64 encoding
def h2b64(hex_data, altchars=None, url=False, use_bin=False):
    if type(hex_data) is str:
        hex_data = c_decode(hex_data, "hex")
    return b64e(hex_data, altchars, url, use_bin)

# Decodes base64 and converts to hex
def b642h(base64_data, altchars=None, url=False, use_bin=False):
    base64_decoded = b64d(base64_data, altchars, url, use_bin)
    hex_data = c_encode(base64_decoded, "hex")
    if use_bin:
        return hex_data
    return hex_data.decode("utf-8")

# str(ClassName) -> "<class '__main__.ClassName'>"
# This function extracts the class name from the str output
def ctos(_class):
    pattern = regex(r"[<'>]")
    cleaned = pattern.sub("", str(_class))
    return cleaned.split("class ", 1)[1].split(".")[-1]