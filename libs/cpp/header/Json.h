#pragma once

#include <iostream>
#include <string>
#include <vector>
#include "rapidjson/document.h"

class Json
{
public:
    Json();
    explicit Json(std::string& json_string);
    ~Json();

    void parse(std::string& json_string);
    std::string stringify();
    std::string stringify_pretty();

    bool has(std::string key);

    std::string getString(std::string key);

    //getters for data types
    bool getBool(std::string key);
    int getInt(std::string key);
    unsigned int getUnsignedInt(std::string key);
    int64_t getInt64(std::string key);
    uint64_t getUnsignedInt64(std::string key);
    float getFloat(std::string key);
    double getDouble(std::string key);

    bool getNestedBool(std::string key);
    float getNestedFloat(std::string key);
    std::string getNestedString(std::string key);

    std::vector<bool> getBoolArray(std::string key);
    std::vector<int> getIntArray(std::string key);
    std::vector<float> getFloatArray(std::string key);
    std::vector<double> getDoubleArray(std::string key);
    std::vector<std::string> getStringArray(std::string key);

    void set(std::string key, bool value);
    void set(std::string key, int value);
    void set(std::string key, float value);
    void set(std::string key, double value);
    void set(std::string key, std::string value);
    
    void set(std::string key, std::vector<bool>& array);
    void set(std::string key, std::vector<int>& array);
    void set(std::string key, std::vector<std::string>& array);
    void set(std::string key, std::vector<float>& array);
    void set(std::string key, std::vector<double>& array);

private:
    rapidjson::Document document;
    rapidjson::Value* val_ptr;
};