
#pragma once

#include<string>
#include<vector>
#include "JsonWriter.h"

class ConfigFactory;

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

protected:
    virtual void write_field(JsonWriter& json_writer){};
    virtual void write_properties(JsonWriter& json_writer);

    std::string key = "";
    ConfigFactory* config_factory = nullptr;

private:
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

template <typename T>
class GenericConfigEntry: public ConfigEntry
{
public:
    GenericConfigEntry() = delete;

    GenericConfigEntry(std::string key, T value)
        : ConfigEntry(key)
    {
        this->value = value;
    }

protected:
    void write_field(JsonWriter& json_writer) override
    {
        json_writer.write(key, value);
    }

private:
    T value;

    friend class ConfigFactory;
};

class ObjectConfigEntry: public ConfigEntry
{
public:
    ObjectConfigEntry() = delete;

    ObjectConfigEntry(std::string key, ConfigFactory* config_factory)
        : ConfigEntry(key)
    {
        this->config_factory = config_factory;
    }

protected:
    void write_field(JsonWriter& json_writer) override;

private:
    friend class ConfigFactory;
};