#pragma once

#include <string>
#include <vector>

namespace Utils
{
    //splits a string <str> by <delimiter> into <tokens>
    void split(std::string str, std::vector<std::string>& tokens, char delimiter);

    //convert vector of ints to vector of bools
    std::vector<int> BoolToIntVector(std::vector<bool> b);

    //convert std::vector to string
    std::string vectorToString(std::vector<bool>& v);
    std::string vectorToString(std::vector<unsigned int>& v);
    std::string vectorToString(std::vector<int>& v);
    std::string vectorToString(std::vector<float>& v, int precision = 6);
    std::string vectorToString(std::vector<double>& v, int precision = 6);
    std::string vectorToString(std::vector<std::string>& v);

    //convert float or double to string with precision
    std::string toStringPrecision(float n, unsigned int precision);
    std::string toStringPrecision(double n, unsigned int precision);

    std::string replaceCharWithString(std::string input_string, char c, std::string replace_string);

    bool create_directory(std::string path);

    bool write_string_to_file(std::string file_path, std::string content);
    void read_file_to_string(std::string file_path, std::string &content);

    //config validation
    std::string validateConfigShortNames(std::vector<std::string> ch_names);
    void convertTimestampString(std::string& old_timestamp, std::string& new_timestamp);

    //path string operations
    void getPathSubstr(std::string& file_path, std::string& target_path);
    void getFileSubstr(std::string& file_path, std::string& target_filename);

    bool isNumeric(const std::string& str);

    std::string escapeJsonString(std::string str);

    std::string base64_encode(const std::vector<unsigned char>& data);
}