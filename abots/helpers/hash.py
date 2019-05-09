from abots.helpers.general import eprint

from os import urandom
from binascii import hexlify
from hashlib import algorithms_available, pbkdf2_hmac, new as new_hash

def create_hash(algorithm, seed=None, random_bytes=32, use_bin=False):
    if algorithm not in algorithms_available:
        return None
    h = new_hash(algorithm)
    if seed is None:
        h.update(urandom(random_bytes))
    else:
        h.update(seed.encode("utf-8"))
    if use_bin:
        return h.digest()
    return h.hexdigest()

def md5(*args, **kwargs):
    return create_hash("md5", *args, **kwargs)

def sha1(*args, **kwargs):
    return create_hash("sha1", *args, **kwargs)

def sha256(*args, **kwargs):
    return create_hash("sha256", *args, **kwargs)

def sha512(*args, **kwargs):
    return create_hash("sha512", *args, **kwargs)

def pbkdf2(algo, pswd, salt=None, cycles=100000, key_len=None, use_bin=False):
    if algorithm not in algorithms_available:
        return None
    if type(pswd) is str:
        pswd = pswd.encode("utf-8")
    if salt is None:
        salt = urandom(16)
    elif type(salt) is str:
        salt = salt.encode("utf-8")
    derived_key = pbkdf2_hmac(algo, pswd, salt, cycles, key_len)
    if use_bin:
        return derived_key, salt
    return hexlify(derived_key).decode("utf-8"), salt.decode("utf-8")

# n = increase as general computing performance increases, min=14
# r = increase in case of breakthroughs in memory technology, min=8
# p = increase in case of breakthroughs in CPU technology, min=1
def scrypt(password, salt=None, n=14, r=8, p=1, use_bin=False):
    try:
        from hashlib import scrypt as _scrypt
    except ImportError:
        eprint("Error: Missing OpenSSL 1.1+ for hashlib.scrypt")
        return None
    if type(password) is str:
        password = password.encode("utf-8")
    if salt is None:
        salt = urandom(16)
    elif type(salt) is str:
        salt = salt.encode("utf-8")
    # N = 2**n, allows simple increments to the value to get desired effect
    derived_key = _scrypt(password, salt, 2**n, r, p)
    if use_bin:
        return derived_key, salt
    return hexlify(derived_key).decode("utf-8"), salt.decode("utf-8")