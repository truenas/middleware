def infinite_multiplier_generator(multiplier, max_value, initial_value):
    cur = initial_value
    while True:
        yield cur
        next_val = cur * multiplier
        if next_val <= max_value:
            cur = next_val
