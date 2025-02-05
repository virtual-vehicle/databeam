import re


def get_valid_filename(name, allow_unicode=True) -> str:
    """
    Return the given string converted to a string that can be used for a clean
    filename. Remove leading and trailing spaces; convert other spaces to
    underscores; and remove anything that is not an alphanumeric, dash,
    underscore, or dot.
    >>> get_valid_filename("john's portrait in 2004.jpg")
    'johns_portrait_in_2004.jpg'
    """
    s = str(name)
    if not allow_unicode:
        s = s.encode('ascii', 'ignore').decode('ascii')
    s = s.strip().replace(" ", "_")
    s = re.sub(r"(?u)[^-\w.]", "", s)
    if s in {"", ".", ".."}:
        raise ValueError("Could not derive file name from '%s'" % name)
    return s


if __name__ == "__main__":
    print(get_valid_filename(' la la äö/üß- !/.+', allow_unicode=False))
