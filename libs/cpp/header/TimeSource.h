#pragma once

#include <string>

class TimeSource
{
public:
    TimeSource(){};
    ~TimeSource(){};

    long long now();
    std::string now_str();
    std::string now_time_only_str();
private:
};