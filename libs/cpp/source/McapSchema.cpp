#include "McapSchema.h"

using json = nlohmann::json;

McapSchema::McapSchema()
{
    schema["type"] = "object";
    schema["properties"] = {};
}

void McapSchema::addProperty(std::string prop_name, std::string prop_type)
{
    json new_property = {
        {"type", prop_type}
    };
    schema["properties"][prop_name] = new_property;
}

void McapSchema::addPropertyExtended(std::string prop_name, std::string prop_dict)
{
    json new_property = json::parse(prop_dict);
    schema["properties"][prop_name] = new_property;
}

std::string McapSchema::get_dtype_name()
{
    return dtype_name;
}

std::string McapSchema::get_topic()
{
    return topic;
}

std::string McapSchema::get_schema_string()
{
    return schema.dump();
}