
#pragma once

#include<string>
#include<vector>
#include "JsonWriter.h"

class ConfigEntry
{
public:
    ConfigEntry() = delete;
    ConfigEntry(std::string key);
    ~ConfigEntry();

    ConfigEntry& label(std::string label);
    ConfigEntry& select(std::vector<std::string> options);
    ConfigEntry& indent(int indent);
    ConfigEntry& visible_if(std::string key, bool key_value);
    ConfigEntry& visible_if(std::string key, std::string key_value);
    ConfigEntry& resizeable();
    ConfigEntry& button();
    ConfigEntry& hidden();

    

private:
    void write(JsonWriter& json_writer);

    std::string key = "";
    std::string label_str = "";
    std::vector<std::string> select_list;
    int indent_value = -1;
    std::string visible_str = "";
    bool flag_resizeable = false;
    bool flag_hidden = false;
    bool flag_button = false;

    bool any_property_flag = false;

    friend class ConfigFactory;
};

class ConfigFactory
{
public:
    ConfigFactory();
    ~ConfigFactory();

    ConfigEntry& string(std::string key, std::string value);
    ConfigEntry& integer(std::string key, int value);
    ConfigEntry& number(std::string key, float value);
    ConfigEntry& boolean(std::string key, bool value);
    ConfigEntry& string_array(std::string key, std::vector<std::string> values);
    ConfigEntry& integer_array(std::string key, std::vector<int> values);
    ConfigEntry& number_array(std::string key, std::vector<float> values);
    ConfigEntry& boolean_array(std::string key, std::vector<bool> values);

    std::string get_json_str();

private:
    ConfigEntry& create_config_entry(std::string& key);

    JsonWriter json_writer;
    std::vector<ConfigEntry> config_entries;
};