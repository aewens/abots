from json import dumps, loads

# JSON encoder, converts a python object to a string
def jots(self, data, readable=False):
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
def jsto(self, data):
    try:
        return json.loads(data)
    except ValueError as e:
        return None