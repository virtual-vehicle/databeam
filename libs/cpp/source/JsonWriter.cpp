#include "JsonWriter.h"
#include "Utils.h"

JsonWriter::JsonWriter()
{

}

JsonWriter::~JsonWriter()
{

}

void JsonWriter::init(JsonWriter &json_writer)
{
    this->json_string = json_writer.json_string;
    this->spaces = json_writer.spaces;
    this->float_precision = json_writer.float_precision;
    this->double_precision = json_writer.double_precision;
}

void JsonWriter::begin()
{
    json_string = "{\n";
}

void JsonWriter::end()
{
    if(json_string[json_string.length() - 1] == '\n') json_string.pop_back();
    if(json_string[json_string.length() - 1] == ',') json_string.pop_back();
    json_string += "\n}\n";
}

void JsonWriter::beginObject(std::string key)
{
    json_string += spaces + "\"" + key + "\": {\n";
    spaces += "  ";
}

void JsonWriter::endObject()
{
    if(json_string[json_string.length() - 1] == '\n') json_string.pop_back();
    if(json_string[json_string.length() - 1] == ',') json_string.pop_back();
    json_string += "\n";
    spaces.pop_back();
    spaces.pop_back();
    json_string += spaces + "},\n";
}

void JsonWriter::setFloatPrecision(unsigned int precision)
{
    if(precision > 9) precision = 9;
    if(precision < 1) precision = 1;
    float_precision = precision;
}

void JsonWriter::setDoublePrecision(unsigned int precision)
{
    if(precision > 15) precision = 18;
    if(precision < 1) precision = 1;
    double_precision = precision;
}

void JsonWriter::write(std::string key, bool b)
{
    json_string += spaces + "\"" + key + (b ? "\": true,\n" : "\": false,\n");
}

void JsonWriter::write(std::string key, unsigned int n)
{
    json_string += spaces + "\"" + key + "\": " + std::to_string(n) + ",\n";
}

void JsonWriter::write(std::string key, int n)
{
    json_string += spaces + "\"" + key + "\": " + std::to_string(n) + ",\n";
}

void JsonWriter::write(std::string key, long long n)
{
    json_string += spaces + "\"" + key + "\": " + std::to_string(n) + ",\n";
}

void JsonWriter::write(std::string key, float n)
{
    json_string += spaces + "\"" + key + "\": " + Utils::toStringPrecision(n, float_precision) + ",\n";
}

void JsonWriter::write(std::string key, double n)
{
    json_string += spaces + "\"" + key + "\": " + Utils::toStringPrecision(n, double_precision) + ",\n";
}

void JsonWriter::write(std::string key, const char* s)
{
    json_string += spaces + "\"" + key + "\": \"" + s + "\",\n";
}

void JsonWriter::write(std::string key, std::string s)
{
    json_string += spaces + "\"" + key + "\": \"" + s + "\",\n";
}

void JsonWriter::write(std::string key, std::vector<bool>& v)
{
    json_string += spaces + "\"" + key + "\": " + Utils::vectorToString(v) + ",\n";
}

void JsonWriter::write(std::string key, std::vector<unsigned int>& v)
{
    json_string += spaces + "\"" + key + "\": " + Utils::vectorToString(v) + ",\n";
}

void JsonWriter::write(std::string key, std::vector<int>& v)
{
    json_string += spaces + "\"" + key + "\": " + Utils::vectorToString(v) + ",\n";
}

void JsonWriter::write(std::string key, std::vector<float>& v)
{
    json_string += spaces + "\"" + key + "\": " + Utils::vectorToString(v, float_precision) + ",\n";
}

void JsonWriter::write(std::string key, std::vector<double>& v)
{
    json_string += spaces + "\"" + key + "\": " + Utils::vectorToString(v, double_precision) + ",\n";
}

void JsonWriter::write(std::string key, std::vector<std::string>& v)
{
    json_string += spaces + "\"" + key + "\": " + Utils::vectorToString(v) + ",\n";
}

void JsonWriter::writeJsonObjectString(std::string key, std::string json_object_string)
{
    json_string += spaces + "\"" + key + "\": " + json_object_string + ",\n";
}

