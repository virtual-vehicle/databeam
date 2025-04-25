#pragma once

#include "FilterBase.hpp"

class MedianFilter : public FilterBase
{
    public:
    MedianFilter();
    ~MedianFilter();

    void configure(Json& config);
    double compute(std::string channel);
};