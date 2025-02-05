#include "Utils.h"
#include <sstream>
#include <iostream>
#include <sys/types.h>
#include <sys/stat.h>
#include <fstream>
#include <algorithm>

void Utils::read_file_to_string(std::string file_path, std::string &content)
{
    content.clear();

    std::ifstream infile(file_path, std::ifstream::in);

    if(infile.is_open())
    {
        std::stringstream ss;
        ss << infile.rdbuf();
        content = ss.str();
    }

    return;
}

bool Utils::write_string_to_file(std::string file_path, std::string content)
{
  std::ofstream outfile(file_path, std::ofstream::trunc);

  if(outfile.is_open())
  {
    outfile << content;
    outfile.close();
    return true;
  }

  return false;
}

bool Utils::create_directory(std::string path)
{
  int status = mkdir(path.c_str(), S_IRWXU | S_IRWXG | S_IROTH | S_IXOTH);
  return status == 0;
}

std::string Utils::replaceCharWithString(std::string input_string, char c, std::string replace_string)
{
    std::string str = "";

    for(unsigned int i = 0; i < input_string.size(); i++)
    {
        if(input_string[i] == c)
        {
            for(unsigned int j = 0; j < replace_string.size(); j++) str += replace_string[j];
        }
        else
        {
            str += input_string[i];
        }
        
    }

    return str;
}

void Utils::split(std::string str, std::vector<std::string>& tokens, char delimiter)
{
    std::istringstream iss(str);

    std::string token;

    while (std::getline(iss, token, delimiter)) 
    {
        if (!token.empty()) tokens.push_back(token);
    }
}

std::vector<int> Utils::BoolToIntVector(std::vector<bool> b)
{
    std::vector<int> v;

    for(unsigned int i = 0; i < b.size(); i++)
    {
        v.push_back(b[i] ? 1 : 0);
    }

    return v;
}

std::string Utils::vectorToString(std::vector<bool>& v)
{
    std::string str = "[";

    for(unsigned int i = 0; i < v.size(); i++){
        str += (v[i] ? std::string("true") : std::string("false")) + (i < v.size() - 1 ? ", " : "]");
    }

    return str;
}

std::string Utils::vectorToString(std::vector<unsigned int>& v)
{
    std::string str = "[";

    for(unsigned int i = 0; i < v.size(); i++){
        str += std::to_string(v[i]) + (i < v.size() - 1 ? ", " : "]");
    }

    return str;
}

std::string Utils::vectorToString(std::vector<int>& v)
{
    std::string str = "[";

    for(unsigned int i = 0; i < v.size(); i++){
        str += std::to_string(v[i]) + (i < v.size() - 1 ? ", " : "]");
    }

    return str;
}

std::string Utils::vectorToString(std::vector<float>& v, int precision)
{
    std::string str = "[";

    for(unsigned int i = 0; i < v.size(); i++){
        str += (precision == 6 ? std::to_string(v[i]) : toStringPrecision(v[i], precision)) + 
            (i < v.size() - 1 ? ", " : "]");
    }

    return str;
}

std::string Utils::vectorToString(std::vector<double>& v, int precision)
{
    std::string str = "[";

    for(unsigned int i = 0; i < v.size(); i++){
        str += (precision == 6 ? std::to_string(v[i]) : toStringPrecision(v[i], precision)) + 
            (i < v.size() - 1 ? ", " : "]");
    }

    return str;
}

std::string Utils::vectorToString(std::vector<std::string>& v)
{
    std::string str = "[";

    for(unsigned int i = 0; i < v.size(); i++){
        str += "\"" + v[i] + "\"" + (i < v.size() - 1 ? ", " : "]");
    }

    return str;
}

std::string Utils::toStringPrecision(float n, unsigned int precision)
{
    std::ostringstream ss;
    ss.precision(precision);
    ss << std::fixed << n;
    return ss.str();
}

std::string Utils::toStringPrecision(double n, unsigned int precision)
{
    std::ostringstream ss;
    ss.precision(precision);
    ss << std::fixed << n;
    return ss.str();
}

std::string Utils::validateConfigShortNames(std::vector<std::string> ch_names)
{
    if(ch_names.size() != 8) return std::string("Names short array must contain exactly 8 strings.");

    //verify names short
    for(unsigned int i = 0; i < ch_names.size(); i++)
    {
        std::string name = ch_names[i];

        if(name.size() == 0) return std::string("Short name must be at least one character.");
        if(name.size() == 1 && name[0] == '_') return std::string("Short name can not be a single underline.");
        if(name.size() > 20) return std::string("Short name must be less than 20 characters.");

        //verify allowed characters
        for(unsigned int j = 0; j < name.size(); j++)
        {
            char c = name[j];

            if(!(isalpha(c) || isdigit(c) || c == '_')) 
            {
                return std::string("Invalid character at position ") + std::to_string(j) + 
                    std::string(" in names short. Use only [a-z, A-Z, _].");
            }
        }

        //verify unique short names
        for(unsigned int j = i+1; j < ch_names.size(); j++)
        {
            if(ch_names[i] == ch_names[j])
            {
                return std::string("Duplicate short channel name \"") + ch_names[i] + 
                    std::string("\". Short names must be unique.");
            }
        }
    }

    return std::string("");
}

/*
 * Converts the default timestamp string into a timestamp string for the config backup files.
 * Old timestamp: 2024-08-23 09:12:56,456
 * New timestamp: 20240823_091256
 */
void Utils::convertTimestampString(std::string& old_timestamp, std::string& new_timestamp)
{
  std::string::size_type sec_end = old_timestamp.find(',');
  new_timestamp = old_timestamp.substr(0, sec_end);
  std::replace(new_timestamp.begin(), new_timestamp.end(), ' ', '_');
  new_timestamp.erase(remove(new_timestamp.begin(), new_timestamp.end(), ':'), new_timestamp.end());
  new_timestamp.erase(remove(new_timestamp.begin(), new_timestamp.end(), '-'), new_timestamp.end());
}

/*
 * Returns only the path of a path with a file appended.
 */
void Utils::getPathSubstr(std::string& file_path, std::string& target_path)
{
  target_path = file_path.substr(0, file_path.find_last_of('/'));
}

void Utils::getFileSubstr(std::string& file_path, std::string& target_filename)
{
    target_filename = file_path.substr(file_path.find_last_of('/') + 1);
}

/*
 * Checks if a string is numeric.
 */
bool Utils::isNumeric(const std::string& str) {
  return !str.empty() && std::all_of(str.begin(), str.end(), isdigit);
}

std::string Utils::escapeJsonString(std::string str)
{
    str = Utils::replaceCharWithString(str, '\\', "\\\\");
    str = Utils::replaceCharWithString(str, '\"', "\\\"");
    str = Utils::replaceCharWithString(str, '\n', "\\n");
    str = Utils::replaceCharWithString(str, '\r', "\\r");
    str = Utils::replaceCharWithString(str, '\t', "\\t");
    str = Utils::replaceCharWithString(str, '\f', "\\f");
    str = Utils::replaceCharWithString(str, '\b', "\\b");
    return str;
}

std::string Utils::base64_encode(const std::vector<unsigned char>& data) {
    static const std::string base64_chars = 
             "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
             "abcdefghijklmnopqrstuvwxyz"
             "0123456789+/";

    std::string encoded_string;
    int i = 0;
    unsigned char char_array_3[3];
    unsigned char char_array_4[4];
    int data_size = data.size();
    
    // Always use 3 8-bit bytes to map into 4 6-bit characters.
    for (int idx = 0; idx < data_size; idx++) {
        char_array_3[i++] = data[idx];
        if (i == 3) {
            char_array_4[0] = (char_array_3[0] & 0xfc) >> 2;
            char_array_4[1] = ((char_array_3[0] & 0x03) << 4) + ((char_array_3[1] & 0xf0) >> 4);
            char_array_4[2] = ((char_array_3[1] & 0x0f) << 2) + ((char_array_3[2] & 0xc0) >> 6);
            char_array_4[3] = char_array_3[2] & 0x3f;

            for (i = 0; i < 4; i++)
                encoded_string += base64_chars[char_array_4[i]];
            i = 0;
        }
    }

    // If some bytes are left over, process them here.
    if (i) {
        for (int j = i; j < 3; j++)
            char_array_3[j] = '\0';

        char_array_4[0] = (char_array_3[0] & 0xfc) >> 2;
        char_array_4[1] = ((char_array_3[0] & 0x03) << 4) + ((char_array_3[1] & 0xf0) >> 4);
        char_array_4[2] = ((char_array_3[1] & 0x0f) << 2) + ((char_array_3[2] & 0xc0) >> 6);
        char_array_4[3] = char_array_3[2] & 0x3f;

        for (int j = 0; j < i + 1; j++)
            encoded_string += base64_chars[char_array_4[j]];

        while (i++ < 3)
            encoded_string += '=';
    }

    return encoded_string;
}