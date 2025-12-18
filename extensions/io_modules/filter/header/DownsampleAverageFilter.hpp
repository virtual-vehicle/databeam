#pragma once

#include "FilterBase.hpp"

class DownsampleAverageFilter : public FilterBase
{
    public:
    DownsampleAverageFilter();
    ~DownsampleAverageFilter();

    void configure(Json& config);
    double compute(std::string channel);
    void reset();

    bool ready_to_publish();
    void publishing();

    private:
    size_t _samples_recorded = 0;
    long long _time_first_sample = 0;
    long long _time_last_sample = 0;
};