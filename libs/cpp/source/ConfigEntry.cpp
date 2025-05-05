#include "ConfigEntry.h"
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

void ConfigEntry::write_properties(JsonWriter& json_writer)
{
    if(!any_property_flag && config_factory == nullptr) return;

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

    //write object properties
    if(config_factory != nullptr)
    {
        config_factory->write_properties(json_writer);
    }

    //end config properties object for given key
    json_writer.endObject();
}

void ObjectConfigEntry::write_field(JsonWriter& json_writer)
{
    json_writer.beginObject(key);
    this->config_factory->write_fields(json_writer);
    json_writer.endObject();
}