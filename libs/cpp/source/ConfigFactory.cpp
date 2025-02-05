#include "ConfigFactory.h"

ConfigEntry::ConfigEntry(std::string key)
{
    this->key = key;
}

ConfigEntry::~ConfigEntry()
{

}

ConfigEntry& ConfigEntry::label(std::string label)
{
    this->label_str = label;
    any_property_flag = true;
    return *this;
}

ConfigEntry& ConfigEntry::select(std::vector<std::string> options)
{
    this->select_list = options;
    any_property_flag = true;
    return *this;
}

ConfigEntry& ConfigEntry::indent(int indent)
{
    if(indent <= 0) return *this;
    if(indent > 50) indent = 50;
    this->indent_value = indent;
    any_property_flag = true;
    return *this;
}

ConfigEntry& ConfigEntry::visible_if(std::string key, bool key_value)
{
    this->visible_str = key + std::string("=") + (key_value ? std::string("True") : std::string("False"));
    any_property_flag = true;
    return *this;
}

ConfigEntry& ConfigEntry::visible_if(std::string key, std::string key_value)
{
    this->visible_str = key + std::string("=") + key_value;
    any_property_flag = true;
    return *this;
}

ConfigEntry& ConfigEntry::resizeable()
{
    this->flag_resizeable = true;
    any_property_flag = true;
    return *this;
}

ConfigEntry& ConfigEntry::button()
{
    this->flag_resizeable = true;
    any_property_flag = true;
    return *this;
}

ConfigEntry& ConfigEntry::hidden()
{
    this->flag_button = true;
    any_property_flag = true;
    return *this;
}

void ConfigEntry::write(JsonWriter& json_writer)
{
    if(!any_property_flag) return;

    //begin new config properties for given key
    json_writer.beginObject(key);

    //write custom label
    if(label_str != "") json_writer.write("label", label_str);

    //write display type select and options list
    if(select_list.size() > 0)
    {
        json_writer.write("display_type", "select");
        json_writer.write("options", select_list);
    }

    //write indent
    if(indent_value != -1) json_writer.write("indent", indent_value);

    //write visible condition
    if(visible_str != "") json_writer.write("visible", visible_str);

    //write resizeable, button and hidden flags
    std::vector<std::string> flags_list;
    if(flag_resizeable) flags_list.push_back("resizeable");
    if(flag_button) flags_list.push_back("button");
    if(flag_hidden) flags_list.push_back("hidden");
    if(flags_list.size() > 0) json_writer.write("flags", flags_list);

    //end config properties object for given key
    json_writer.endObject();
}


ConfigFactory::ConfigFactory()
{
    json_writer.begin();
}

ConfigFactory::~ConfigFactory()
{

}

ConfigEntry& ConfigFactory::create_config_entry(std::string& key)
{
    ConfigEntry config_entry(key);
    config_entries.push_back(config_entry);
    return config_entries[config_entries.size() - 1];
}

ConfigEntry& ConfigFactory::string(std::string key, std::string value)
{
    json_writer.write(key, value);
    return create_config_entry(key);
}

ConfigEntry& ConfigFactory::integer(std::string key, int value)
{
    json_writer.write(key, value);
    return create_config_entry(key);
}

ConfigEntry& ConfigFactory::number(std::string key, float value)
{
    json_writer.write(key, value);
    return create_config_entry(key);
}

ConfigEntry& ConfigFactory::boolean(std::string key, bool value)
{
    json_writer.write(key, value);
    return create_config_entry(key);
}

ConfigEntry& ConfigFactory::string_array(std::string key, std::vector<std::string> values)
{
    json_writer.write(key, values);
    return create_config_entry(key);
}

ConfigEntry& ConfigFactory::integer_array(std::string key, std::vector<int> values)
{
    json_writer.write(key, values);
    return create_config_entry(key);
}

ConfigEntry& ConfigFactory::number_array(std::string key, std::vector<float> values)
{
    json_writer.write(key, values);
    return create_config_entry(key);
}

ConfigEntry& ConfigFactory::boolean_array(std::string key, std::vector<bool> values)
{
    json_writer.write(key, values);
    return create_config_entry(key);
}

std::string ConfigFactory::get_json_str()
{
    //make sure something was written
    if(config_entries.size() == 0) return "{}";

    //begin config properties object
    json_writer.beginObject("config_properties");

    //write config properties for all config entries
    for(unsigned int i = 0; i < config_entries.size(); i++)
    {
        config_entries[i].write(json_writer);
    }

    //end object and json
    json_writer.endObject();
    json_writer.end();
    
    //get config json string
    std::string json_str = json_writer.getString();

    //reset
    config_entries.clear();
    json_writer.begin();

    //return generated config
    return json_str;
}
