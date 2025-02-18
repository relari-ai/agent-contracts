from string import ascii_lowercase, digits
import random

def nanoid(size: int = 8):
    return ''.join(random.choices(ascii_lowercase + digits, k=size))
    