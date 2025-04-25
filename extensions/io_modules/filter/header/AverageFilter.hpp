#pragma once

#include "FilterBase.hpp"

class AverageFilter : public FilterBase
{
    public:
    AverageFilter();
    ~AverageFilter();

    void configure(Json& config);
    double compute(std::string channel);
};