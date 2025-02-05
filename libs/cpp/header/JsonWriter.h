#pragma once

#include <iostream>
#include <string>
#include <vector>

class JsonWriter
{
public:
    JsonWriter();
    ~JsonWriter();

    void init(JsonWriter& json_writer);
    void begin();
    void end();

    void beginObject(std::string key);
    void endObject();

    //set precision for float and double
    void setFloatPrecision(unsigned int precision);
    void setDoublePrecision(unsigned int precision);

    //primitive data types
    void write(std::string key, bool b);
    void write(std::string key, unsigned int n);
    void write(std::string key, int n);
    void write(std::string key, long long n);
    void write(std::string key, float n);
    void write(std::string key, double n);
    void write(std::string key, const char* s);
    void write(std::string key, std::string s);

    //std::vectors by reference
    void write(std::string key, std::vector<bool>& v);
    void write(std::string key, std::vector<unsigned int>& v);
    void write(std::string key, std::vector<int>& v);
    void write(std::string key, std::vector<float>& v);
    void write(std::string key, std::vector<double>& v);
    void write(std::string key, std::vector<std::string>& v);

    //special writes
    void writeJsonObjectString(std::string key, std::string json_object_string);

    std::string getString() { return json_string; }
    std::string* getStringPtr() { return &json_string; }

private:
    std::string json_string = "";
    std::string spaces = "  ";

    unsigned int float_precision = 6;
    unsigned int double_precision = 6;
};