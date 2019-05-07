from sys import stderr
from traceback import print_exc
from datetime import datetime, timezone

def eprint(*args, **kwargs):
    print(*args, file=stderr, **kwargs)

def noop(*args, **kwargs):
    pass

def obtain(source, attribute):
    return getattr(source, attribute, None)

def cast(source, method, *args, **kwargs):
    source_method = getattr(source, method, noop)
    try:
        return source_method(*args, **kwargs)
    except Exception:
        status = print_exc()
        eprint(status)
        return status

def deduce(reference, attributes):
    if type(attributes) is not list:
        attributes = [attributes]
    return list(map(lambda attr: getattr(reference, attr, None), attributes))

def get_digit(number, position):
    return False if number - 10**position < 0 else number // 10*position % 10

def utc_now():
    return datetime.utcnow().replace(tzinfo=timezone.utc)

def utc_now_timestamp():
    return utc_now().timestamp()