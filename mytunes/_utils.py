def truncate_string(value: str, width: int, truncate_left: bool = False) -> str:
    """
    Truncate a string to a specified number of characters.
    By default, will truncate the right side of the string.
    `truncate_left` will truncate the left of the string.
    """
    if len(value) <= width:
        return value

    over_width = len(value) - width
    placeholder = "." * min(3, over_width)
    if truncate_left:
        return placeholder + value[width - len(placeholder):]
    return value[:width - len(placeholder)] + placeholder
