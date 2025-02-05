import abc
from pathlib import Path
import json
from typing import Mapping, Dict, Any

import jsonschema

from vif.logger.logger import LoggerMixin


def build_schema(fields: Mapping) -> Mapping:
    """
    helper function to patch json schemas for Frontend Module configs
     - marks all fields as required, disallows additional fields
     - adds fixed length based on default for arrays of type 'fixed_array'
    :param fields: the json schema to patch
    :return: the patched schema
    """
    if fields['type'] == 'object':
        # patch in required properties list
        properties = {k: build_schema(v) for k, v in fields['properties'].items()}

        data = {'type': 'object',
                'properties': properties,
                #'required': fields['required'] if 'required' in fields else list((properties.keys())),
                'additionalProperties': fields['additionalProperties'] if 'additionalProperties' in fields else False}

        if 'required' in fields:
            data['required'] = fields['required']

        return data

    elif fields['type'] == 'fixed_array':
        # patch in required length
        x: Dict[str, Any] = {'minItems': len(fields['default']),
                             'maxItems': len(fields['default'])}
        x.update(fields)
        # change type back to array (conform to JSONSchema types)
        x['type'] = 'array'
        # descend into build schema again to process array related stuff
        return build_schema(x)

    elif fields['type'] == 'array':
        # descend into array items
        x = dict(fields)
        x['items'] = build_schema(fields['items'])
        return x

    else:
        return fields


def schema_default(x: Mapping) -> Dict:
    """
    Create a default config for the given frontend module
    :param x: schema for which to generate config
    :return: default config for given mapping
    """
    cfg = {}
    for k, v in x.items():
        if k == 'type' and v == 'object':
            # recurse into 'properties'-object
            cfg.update(schema_default(x['properties']))
        elif isinstance(v, Mapping) and 'default' in v:
            # save the actual config default values
            cfg[k] = v['default']
        elif k != 'properties' and k != 'required' and k != 'additionalProperties':
            # recurse into custom nested structure
            if isinstance(x[k], Mapping):
                cfg.update({k: schema_default(x[k])})
    return cfg


class BaseConfig(abc.ABC, LoggerMixin):
    """
    Abstract base Class for all Configs
    Classes are not intended to be instantiated, all methods are class / static methods
    """

    Name: str  # unique name for the config type

    @classmethod
    @abc.abstractmethod
    def _schema(cls) -> Mapping:
        ...

    @classmethod
    def get_schema(cls) -> Mapping:
        return build_schema(cls._schema())

    @classmethod
    def validate_config(cls, config: Mapping) -> bool:
        try:
            jsonschema.validate(config, schema=cls.get_schema())
        except jsonschema.ValidationError as e:
            cls.static_logger().error(f'Module {cls.Name}: JSON validation failed:\n{e}')
            return False
        return True

    @classmethod
    def get_default_config(cls) -> Dict:
        return schema_default(cls._schema())

    @classmethod
    def json_to_disk(cls, path: Path, file_name: str, meta_data: Dict) -> None:
        file_path = path / file_name

        with file_path.open('w') as f:
            cls.static_logger().debug(f'Write JSON to {f.name}')
            json.dump(meta_data, f, indent=2, ensure_ascii=False)

    @classmethod
    def json_from_disk(cls, path: Path, file_name: str, default_config=None) -> Dict:
        if default_config is None:
            default_config_message = "empty"
            default_config = {}
        else:
            default_config_message = "default config"

        file_path = path / file_name

        try:
            with file_path.open('r') as f:
                cls.static_logger().debug(f'Read JSON {file_path} from disk.')
                return json.load(f)
        except FileNotFoundError:
            cls.static_logger().info(f'JSON file {file_path} not found, returning {default_config_message}')
            return default_config
