import random
from string import ascii_lowercase, digits


def nanoid(size: int = 8):
    return "".join(random.choices(ascii_lowercase + digits, k=size))
