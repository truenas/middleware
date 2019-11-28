import math


def gcd_multiple(l):
    if len(l) == 1:
        return l[0]

    return math.gcd(l[0], gcd_multiple(l[1:]))
