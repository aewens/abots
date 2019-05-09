from collections import defaultdict

def infinitedict():
    d = lambda: defaultdict(d)
    return defaultdict(d)