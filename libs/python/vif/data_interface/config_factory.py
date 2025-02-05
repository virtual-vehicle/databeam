from typing import List, Self, Dict, Union, Any

class ConfigEntry:
    def __init__(self, key: str, entry_dict: Dict):
        self._key = key
        self._entry_dict = entry_dict
        self._properties: Dict[str, Dict[str, Any]] = {}

    def get_key(self) -> str:
        return self._key

    def get_entry_dict(self) -> Dict:
        return self._entry_dict

    def label(self, label: str) -> Self:
        """
        Adds a custom label for the config entry
        :param label: The label to display
        :return: ConfigPropertiesFactory for further method chaining
        """
        self._properties['label'] = {'type': 'string', 'default': label}
        return self

    def select(self, options: List[str]) -> Self:
        """
        Displays the config entry as a string select form. Works only if the entry is of type string.
        :param options: list of options for the select form
        :return: ConfigPropertiesFactory for further method chaining
        """
        self._properties['display_type'] = {'type': 'string', 'default': 'select'}
        self._properties['options'] = {
            'type': 'array',
            'default': options,
            'items': {'type': 'string'}
        }
        return self

    def indent(self, indent: int = 20) -> Self:
        """
        Creates an indent for the config entry in the webinterface
        :param indent: Indentation for the config entry
        :return: ConfigPropertiesFactory for further method chaining
        """
        self._properties['indent'] = {'type': 'number', 'default': indent}
        return self

    def visible(self, key: str, value: Union[str, bool]) -> Self:
        """
        Adds a condition for the config entry to be visible in
        the webinterface based on the value of another config entry.
        Works only when key refers to a string and boolean config entry.
        :param key: The config entry key on which the visible state of this entry depends on.
        :param value: The value the other config entry must have such that this property is visible
        :return: ConfigPropertiesFactory for further method chaining
        """
        if isinstance(value, bool):
            self._properties['visible'] = {'type': 'string', 'default': f'{key}={"True" if value else "False"}'}
        else:
            self._properties['visible'] = {'type': 'string', 'default': f'{key}={value}'}
        return self

    def resizeable(self) -> Self:
        """
        Makes the config entry array resizeable
        :return: ConfigPropertiesFactory for further method chaining
        """
        if 'flags' not in self._properties:
            self._properties['flags'] = {'type': 'array', 'default': [], 'items': {'type': 'string'}}

        if 'resizeable' not in self._properties['flags']['default']:
            self._properties['flags']['default'].append('resizeable')

        return self

    def button(self) -> Self:
        """
        Makes the config entry as button
        :return: ConfigPropertiesFactory for further method chaining
        """
        if 'flags' not in self._properties:
            self._properties['flags'] = {'type': 'array', 'default': [], 'items': {'type': 'string'}}

        if 'button' not in self._properties['flags']['default']:
            self._properties['flags']['default'].append('button')

        return self

    def hidden(self) -> Self:
        """
        Makes the config entry hidden, does not show in webinterface
        :return: ConfigPropertiesFactory for further method chaining
        """
        if 'flags' not in self._properties:
            self._properties['flags'] = {'type': 'array', 'default': [], 'items': {'type': 'string'}}

        if 'hidden' not in self._properties['flags']['default']:
            self._properties['flags']['default'].append('hidden')

        return self

    def get(self) -> Dict:
        """
        Creates a dictionary from the config properties
        :return: The config properties dict
        """
        return {
            'type': 'object',
            'properties': self._properties
        }

class ConfigFactory:
    def __init__(self):
        self._config_entries: List[ConfigEntry] = []

    def _add_entry(self, key: str, entry_dict: Dict) -> ConfigEntry:
        config_entry = ConfigEntry(key, entry_dict)
        self._config_entries.append(config_entry)
        return config_entry

    def string(self, key: str, value: str) -> ConfigEntry:
        return self._add_entry(key, {'type': 'string', 'default': value})

    def integer(self, key: str, value: int) -> ConfigEntry:
        return self._add_entry(key, {'type': 'integer', 'default': value})

    def number(self, key: str, value: float) -> ConfigEntry:
        return self._add_entry(key, {'type': 'number', 'default': value})

    def boolean(self, key: str, value: bool) -> ConfigEntry:
        return self._add_entry(key, {'type': 'boolean', 'default': value})

    def string_array(self, key: str, value: List[str]) -> ConfigEntry:
        return self._add_entry(key, {'type': 'array', 'default': value, 'items': {'type': 'string'}})

    def integer_array(self, key: str, value: List[int]) -> ConfigEntry:
        return self._add_entry(key, {'type': 'array', 'default': value, 'items': {'type': 'integer'}})

    def number_array(self, key: str, value: List[float]) -> ConfigEntry:
        return self._add_entry(key, {'type': 'array', 'default': value, 'items': {'type': 'number'}})

    def boolean_array(self, key: str, value: List[bool]) -> ConfigEntry:
        return self._add_entry(key, {'type': 'array', 'default': value, 'items': {'type': 'boolean'}})

    def get_config(self):
        # create module config dict
        cfg = {'type': 'object', 'properties': {}}

        # add key entries before config_properties to keep original order
        for entry in self._config_entries:
            cfg['properties'][entry.get_key()] = entry.get_entry_dict()

        # add config properties dict
        cfg['properties']['config_properties'] = {'type': 'object', 'properties': {}}

        # add config properties entries
        for entry in self._config_entries:
            props = entry.get()
            if props['properties']:
                cfg['properties']['config_properties']['properties'][entry.get_key()] = props

        # return module config dict
        return cfg

