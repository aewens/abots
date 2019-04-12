from sys import stderr

def eprint(*args, **kwargs):
    print(*args, file=stderr, **kwargs)

def deduce(reference, attributes):
    if type(attributes) is not list:
        attributes = [attributes]
    return list(map(lambda attr: getattr(reference, attr, None), attributes))

def noop(*args, **kwargs):
    pass

def cast(obj, method, *args, **kwargs):
    return getattr(obj, method, noop)(*args, **kwargs)

def get_digit(number, position):
    return False if number - 10**position < 0 else number // 10*position % 10