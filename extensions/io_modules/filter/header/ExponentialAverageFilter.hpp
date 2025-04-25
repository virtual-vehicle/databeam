#pragma once

#include "FilterBase.hpp"

// source: https://en.wikipedia.org/wiki/Exponential_smoothing
class ExponentialAverageFilter : public FilterBase
{
    public:
    ExponentialAverageFilter();
    ~ExponentialAverageFilter();

    void configure(Json& config);
    double compute(std::string channel);
    void reset();

    private:
    std::unordered_map<std::string, double> _prev_filter_output;
    double _smoothing_factor;
};