#include "rapidjson/writer.h"
#include "rapidjson/pointer.h"
#include "rapidjson/prettywriter.h"
#include "rapidjson/stringbuffer.h"
#include "Json.h"

Json::Json()
{

}

Json::Json(std::string& json_string)
{
    parse(json_string);
}

Json::~Json()
{

}

void Json::parse(std::string& json_string)
{
    document.Parse(json_string.c_str());
}

std::string Json::stringify()
{
    //create string buffer
    rapidjson::StringBuffer buffer;

    //create writer
    rapidjson::Writer<rapidjson::StringBuffer> writer(buffer);

    //serialize json to string
    document.Accept(writer);
 
    //return json string
    return std::string(buffer.GetString());
}

std::string Json::stringify_pretty()
{
    //create string buffer
    rapidjson::StringBuffer buffer;

    //create writer
    rapidjson::PrettyWriter<rapidjson::StringBuffer> writer(buffer);

    //serialize json to string
    document.Accept(writer);
 
    //return json string
    return std::string(buffer.GetString());
}

bool Json::has(std::string key)
{
    return document.HasMember(key.c_str());
}

std::string Json::getString(std::string key)
{
    return document[key.c_str()].GetString();
}

bool Json::getBool(std::string key, bool default_value)
{
    if (document.HasMember(key.c_str()))
        return document[key.c_str()].GetBool();
    else
        return default_value;
}

bool Json::getNestedBool(std::string key, bool default_value)
{
    rapidjson::Value* v = rapidjson::Pointer(key.c_str()).Get(document);
    if(v == nullptr) return default_value;
    return v->GetBool();
}

float Json::getNestedFloat(std::string key)
{
    rapidjson::Value* v = rapidjson::Pointer(key.c_str()).Get(document);
    if(v == nullptr) return 0.0f;
    return (float)v->GetDouble();
}

std::string Json::getNestedString(std::string key)
{
    rapidjson::Value* v = rapidjson::Pointer(key.c_str()).Get(document);
    if(v == nullptr) return key + " not found in document.";
    return v->GetString();
}

int Json::getInt(std::string key)
{
    return document[key.c_str()].GetInt();
}

unsigned int Json::getUnsignedInt(std::string key)
{
    return document[key.c_str()].GetUint();
}

int64_t Json::getInt64(std::string key)
{
    return document[key.c_str()].GetInt64();
}

uint64_t Json::getUnsignedInt64(std::string key)
{
    return document[key.c_str()].GetUint64();
}

float Json::getFloat(std::string key)
{
    return (float)document[key.c_str()].GetDouble();
}

double Json::getDouble(std::string key)
{
    return document[key.c_str()].GetDouble();
}

std::vector<bool> Json::getBoolArray(std::string key)
{
    std::vector<bool> array;
    const rapidjson::Value& a = document[key.c_str()];

    for (rapidjson::SizeType i = 0; i < a.Size(); i++){
        array.push_back(a[i].GetBool());
    }    

    return array;
}

std::vector<int> Json::getIntArray(std::string key)
{
    std::vector<int> array;
    const rapidjson::Value& a = document[key.c_str()];

    for (rapidjson::SizeType i = 0; i < a.Size(); i++){
        array.push_back(a[i].GetInt());
    }    

    return array;
}

std::vector<float> Json::getFloatArray(std::string key)
{
    std::vector<float> array;
    const rapidjson::Value& a = document[key.c_str()];

    for (rapidjson::SizeType i = 0; i < a.Size(); i++){
        array.push_back(static_cast<float>(a[i].GetDouble()));
    }    

    return array;
}

std::vector<double> Json::getDoubleArray(std::string key)
{
    std::vector<double> array;
    const rapidjson::Value& a = document[key.c_str()];

    for (rapidjson::SizeType i = 0; i < a.Size(); i++){
        array.push_back(a[i].GetDouble());
    }    

    return array;
}

std::vector<std::string> Json::getStringArray(std::string key)
{
    std::vector<std::string> array;
    const rapidjson::Value& a = document[key.c_str()];

    for (rapidjson::SizeType i = 0; i < a.Size(); i++){
        array.push_back(a[i].GetString());
    }    

    return array;
}

void Json::set(std::string key, bool value)
{
    rapidjson::Value& v = document[key.c_str()];
    v.SetBool(value);
}

void Json::set(std::string key, int value)
{
    rapidjson::Value& v = document[key.c_str()];
    v.SetInt(value);
}

void Json::set(std::string key, float value)
{
    rapidjson::Value& v = document[key.c_str()];
    v.SetDouble(static_cast<double>(value));
}

void Json::set(std::string key, double value)
{
    rapidjson::Value& v = document[key.c_str()];
    v.SetDouble(value);
}

void Json::set(std::string key, std::string value)
{
    rapidjson::Value& v = document[key.c_str()];
    v.SetString(value.c_str(), value.size(), document.GetAllocator());
}

void Json::set(std::string key, std::vector<bool>& array)
{
    rapidjson::Value& a = document[key.c_str()];
    rapidjson::Document::AllocatorType& allocator = document.GetAllocator();

    a.Clear();

    for(unsigned int i = 0; i < array.size(); i++){
        a.PushBack(array[i], allocator);
    }
}


void Json::set(std::string key, std::vector<int>& array)
{
    rapidjson::Value& a = document[key.c_str()];
    rapidjson::Document::AllocatorType& allocator = document.GetAllocator();

    a.Clear();

    for(unsigned int i = 0; i < array.size(); i++){
        a.PushBack(array[i], allocator);
    }
}

void Json::set(std::string key, std::vector<std::string>& array)
{
    rapidjson::Value& a = document[key.c_str()];
    rapidjson::Document::AllocatorType& allocator = document.GetAllocator();

    a.Clear();

    for(unsigned int i = 0; i < array.size(); i++){
        rapidjson::Value v;
        v.SetString(array[i].c_str(), array[i].size(), allocator);
        a.PushBack(v, allocator);
    }
}


void Json::set(std::string key, std::vector<float>& array)
{
    rapidjson::Value& a = document[key.c_str()];
    rapidjson::Document::AllocatorType& allocator = document.GetAllocator();

    a.Clear();

    for(unsigned int i = 0; i < array.size(); i++){
        a.PushBack(static_cast<float>(array[i]), allocator);
    }
}

void Json::set(std::string key, std::vector<double>& array)
{
    rapidjson::Value& a = document[key.c_str()];
    rapidjson::Document::AllocatorType& allocator = document.GetAllocator();

    a.Clear();

    for(unsigned int i = 0; i < array.size(); i++){
        a.PushBack(array[i], allocator);
    }
}
