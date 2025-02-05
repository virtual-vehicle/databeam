
#pragma once

#include<string>
#include<nlohmann/json.hpp>

using json = nlohmann::json;

class McapSchema
{
public:
    McapSchema();

    void setTopic(std::string topic) { this->topic = topic; }
    void setDtypeName(std::string dtype_name) { this->dtype_name = dtype_name; }

    void addProperty(std::string prop_name, std::string prop_type);
    void addPropertyExtended(std::string prop_name, std::string prop_dict);

    std::string get_dtype_name();
    std::string get_topic();
    std::string get_schema_string();

private:
    std::string topic = "";
    std::string dtype_name = "";
    json schema;
};