from random import random, randint

def clamp(number, low, high):
    return max(low, min(number, high))

def randfloat(start, end=None):
    if end is None:
        end = start
        start = 0
    return (end - start) * random() + start