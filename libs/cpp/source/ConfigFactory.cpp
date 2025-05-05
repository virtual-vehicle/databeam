#include "ConfigFactory.h"

ConfigFactory::ConfigFactory()
{
    json_writer.begin();
}

ConfigFactory::~ConfigFactory()
{

}

ConfigEntry& ConfigFactory::string(std::string key, std::string value)
{
    return create_config_entry(key, value);
}

ConfigEntry& ConfigFactory::integer(std::string key, int value)
{
    return create_config_entry(key, value);
}

ConfigEntry& ConfigFactory::number(std::string key, float value)
{
    return create_config_entry(key, value);
}

ConfigEntry& ConfigFactory::boolean(std::string key, bool value)
{
    return create_config_entry(key, value);
}

ConfigEntry& ConfigFactory::string_array(std::string key, std::vector<std::string> values)
{
    return create_config_entry(key, values);
}

ConfigEntry& ConfigFactory::integer_array(std::string key, std::vector<int> values)
{
    return create_config_entry(key, values);
}

ConfigEntry& ConfigFactory::number_array(std::string key, std::vector<float> values)
{
    return create_config_entry(key, values);
}

ConfigEntry& ConfigFactory::boolean_array(std::string key, std::vector<bool> values)
{
    return create_config_entry(key, values);
}

ConfigEntry& ConfigFactory::object(std::string key, ConfigFactory& config_factory)
{
    //make sure no one passes this config factory as parameter
    if(&config_factory == this){
        throw std::runtime_error("ConfigFactory::object(...): Can not use own ConfigFactory instance as parameter.");
    } 

    std::shared_ptr<ObjectConfigEntry> config_entry = std::make_shared<ObjectConfigEntry>(key, &config_factory);
    config_entries.push_back(config_entry);
    return *config_entries[config_entries.size() - 1];
}

void ConfigFactory::write_fields(JsonWriter& json_writer)
{
    for(unsigned int i = 0; i < config_entries.size(); i++)
    {
        config_entries[i]->write_field(json_writer);
    }
}

void ConfigFactory::write_properties(JsonWriter& json_writer)
{
    //begin config properties object
    json_writer.beginObject("config_properties");

    //write config properties for all config entries
    for(unsigned int i = 0; i < config_entries.size(); i++)
    {
        config_entries[i]->write_properties(json_writer);
    }

    //end object and json
    json_writer.endObject();
}

std::string ConfigFactory::get_json_str()
{
    //make sure something was written
    if(config_entries.size() == 0) return "{}";

    //write config fields
    write_fields(json_writer);

    //write config properties
    write_properties(json_writer);

    //end json
    json_writer.end();
    
    //get config json string
    std::string json_str = json_writer.getString();

    //reset
    config_entries.clear();
    json_writer.begin();

    //return generated config
    return json_str;
}
