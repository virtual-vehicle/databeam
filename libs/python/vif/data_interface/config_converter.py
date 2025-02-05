import sys

from io_modules.udp_sink.config import UdpSinkConfig as module_cfg_class
from vif.data_interface.config_factory import ConfigFactory
import json

def test_cfg():
    cfg = ConfigFactory()
    cfg.string('udp_address', '0.0.0.0')
    cfg.integer('udp_port', 2500).label('udp Port (bind)')
    cfg.boolean('use_length_bytes', False)
    cfg.number('number_length_bytes', 4)
    cfg.boolean('big_endian', False)
    cfg.string('data_format', 'struct').select(['struct', 'json'])
    cfg.string_array('struct_entries', ['key#f']).resizeable()

    return cfg.get_config()

def props_code(props_dict):
    code_str = ""

    for k in props_dict.keys():
        if k == 'label':
            code_str += f".label('{props_dict['label']['default']}')"

        if k == 'flags':
            flags_array = props_dict['flags']['default']

            if 'resizeable' in flags_array:
                code_str += ".resizeable()"

            if 'button' in flags_array:
                code_str += ".button()"

            if 'hidden' in flags_array:
                code_str += ".hidden()"

        if k == 'indent':
            code_str += f".indent({props_dict['indent']['default']})"

        if k == 'visible':
            parts = props_dict['visible']['default'].split("=")
            visible_key = parts[0]
            visible_value = bool(parts[1]) if parts[1] == 'True' or parts[1] == 'False' else f"'{parts[1]}'"
            code_str += f".visible('{visible_key}', {visible_value})"

        if k == 'display_type':
            if props_dict['display_type']['default'] == "select":
                    code_str += f".select({props_dict['options']['default']})"

    return code_str

def compare_configs(orig_cfg, new_cfg):
    result = True

    for k, v in orig_cfg['properties'].items():
        if k == 'config_properties':
            continue

        if k in new_cfg['properties'].keys():
            if not (json.dumps(orig_cfg['properties'][k]) == json.dumps(new_cfg['properties'][k])):
                print("key " + k + " no es match")
            result = result and (json.dumps(orig_cfg['properties'][k]) == json.dumps(new_cfg['properties'][k]))
        else:
            result = False

    orig_props = orig_cfg['properties']['config_properties']['properties']
    new_props = new_cfg['properties']['config_properties']['properties']

    for k, v in orig_props.items():
        if k == 'config_properties':
            continue

        if k in new_props.keys():
            if not (json.dumps(orig_props[k]) == json.dumps(orig_props[k])):
                print("key " + k + " no es match")
            result = result and (json.dumps(orig_props[k]) == json.dumps(orig_props[k]))
        else:
            result = False

    return result

if __name__ == '__main__':
    config = module_cfg_class()
    cfg = config._schema()

    #print(json.dumps(cfg, indent=2))
    #sys.exit(0)

    #try:
    props = cfg['properties']['config_properties']['properties']
    #except KeyError:
    #    props = {}

    code_str = "cfg = ConfigFactory()\n"

    keys = [k for k in cfg['properties'].keys() if k != "config_properties"]

    for k in keys:
        field = cfg['properties'][k]
        field_type = field['type']

        if field_type == "integer":
            code_str += f"cfg.integer('{k}', {field['default']})"

        elif field_type == "number":
            code_str += f"cfg.number('{k}', {field['default']})"

        elif field_type == "boolean":
            code_str += f"cfg.boolean('{k}', {field['default']})"

        elif field_type == "string":
            code_str += f"cfg.string('{k}', '{field['default']}')"

        elif field_type == "array":
            items = field['items']['type']

            if items == "string":
                code_str += f"cfg.string_array('{k}', {str(field['default'])})"
            elif items == "integer":
                code_str += f"cfg.integer_array('{k}', {str(field['default'])})"
            elif items == "number":
                code_str += f"cfg.number_array('{k}', {str(field['default'])})"
            else:
                print("MISSING array type: " + str(items))
                sys.exit(0)
        else:
            print("MISSING field type: " + field_type)
            sys.exit(0)

        code_str += props_code(props[k]['properties']) + "\n" if k in props else "\n"

    code_str += "\nreturn cfg.get_config()"
    print("\n" + code_str)
    print("\n")

    #print("Orig:\n" + json.dumps(cfg, indent=2))
    #print("New:\n" + json.dumps(test_cfg(), indent=2))

    print("Json Match: " + str(json.dumps(cfg) == json.dumps(test_cfg())))
    print("Key/Value Json Match: " + str(compare_configs(cfg, test_cfg())))