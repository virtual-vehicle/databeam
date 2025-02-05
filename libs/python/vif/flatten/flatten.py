from collections.abc import MutableMapping


def flatten(dictionary, parent_key=False, separator='.'):
    """
    Turn a nested dictionary into a flattened dictionary
    :param dictionary: The dictionary to flatten
    :param parent_key: The string to prepend to dictionary's keys
    :param separator: The string used to separate flattened keys
    :return: A flattened dictionary

    https://github.com/ScriptSmith/socialreaper/blob/master/socialreaper/tools.py#L8
    https://stackoverflow.com/questions/6027558/flatten-nested-dictionaries-compressing-keys?answertab=oldest#tab-top
    """

    items = []
    for key, value in dictionary.items():
        new_key = str(parent_key) + separator + key if parent_key else key
        if isinstance(value, MutableMapping):
            items.extend(flatten(value, new_key, separator).items())
        elif isinstance(value, list):
            for k, v in enumerate(value):
                items.extend(flatten({str(k): v}, new_key, separator).items())
        else:
            items.append((new_key, value))
    return dict(items)


if __name__ == '__main__':
    testdata = {
        'a': 1,
        'b': {'Ba': [0, 1, 2], 'Bb': {'BBa': 1, 'BBb': 2}, 'Bc': 'c'},
        'c': ['hi', 'im', 'cow'],
        'd': 'end'
    }
    print(flatten(testdata))
