def truncate_string(string: str, length: int = 32):
    if len(string) > length:
        return string[: length - 3] + "..."
    else:
        return string
