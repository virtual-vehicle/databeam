
#pragma once

#include <map>
#include <string>

class EnvConfig
{
public:
    EnvConfig();
    ~EnvConfig();

    void add(std::string key, std::string default_value);
    std::string get(std::string key);

    std::map<std::string, std::string> env_map;
};