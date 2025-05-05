
#pragma once

#include<string>
#include<vector>
#include "JsonWriter.h"
#include "ConfigEntry.h"
#include <memory>

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
    ConfigEntry& object(std::string key, ConfigFactory& config_factory);

    std::string get_json_str();

private:
    void write_fields(JsonWriter& json_writer);
    void write_properties(JsonWriter& json_writer);

    template <typename T>
    ConfigEntry& create_config_entry(std::string& key, T value)
    {
        std::shared_ptr<GenericConfigEntry<T>> config_entry = std::make_shared<GenericConfigEntry<T>>(key, value);
        config_entries.push_back(config_entry);
        return *config_entries[config_entries.size() - 1];
    }

    JsonWriter json_writer;
    std::vector<std::shared_ptr<ConfigEntry>> config_entries;

    friend class ConfigEntry;
    friend class ObjectConfigEntry;
};