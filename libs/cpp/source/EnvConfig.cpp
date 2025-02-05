
#include "EnvConfig.h"
#include <cstdlib>
#include <iostream>

EnvConfig::EnvConfig()
{
    
}

EnvConfig::~EnvConfig()
{

}

void EnvConfig::add(std::string key, std::string default_value)
{
    char* env_value = std::getenv(key.c_str());

    if(env_value != nullptr) default_value = std::string(env_value);

    env_map.insert(std::pair<std::string, std::string>(key, default_value));
}

std::string EnvConfig::get(std::string key)
{
    std::map<std::string, std::string>::iterator it;

    it = env_map.find(key);

    if(it == env_map.end())
    {
        std::cout << "EnvConfig: Environment variable " + 
            key + " not found." << std::endl;
    }

    return it->second;
}