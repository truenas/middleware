def make_sentence(s):
    if not s:
        return s

    if any(s.endswith(c) for c in (".", "!", "?")):
        return s

    return f"{s}."
