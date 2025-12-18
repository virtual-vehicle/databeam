#include "DownsampleAverageFilter.hpp"
#include <iostream>

DownsampleAverageFilter::DownsampleAverageFilter()
{
    
}

DownsampleAverageFilter::~DownsampleAverageFilter()
{
    
}

void DownsampleAverageFilter::configure(Json& config)
{

}

void DownsampleAverageFilter::reset()
{
    this->_samples_recorded = 0;
    this->_time_first_sample = 0;
    this->_time_last_sample = 0;
}

double DownsampleAverageFilter::compute(std::string channel)
{
    static long long last_timestamp = 0;
    double sum = 0.0;
    size_t data_size = this->_filter_data.at(channel)->size();
    if(data_size == 0)
        return 0.0;

    this->_time_last_sample = this->_filter_data[channel]->at(data_size - 1).time_ns;
    if (this->_time_first_sample == 0) {
        this->_time_first_sample = this->_time_last_sample;
    }

    // only increase once per packet not per channel!
    if (last_timestamp != this->_time_last_sample) {
        this->_samples_recorded += 1;
        last_timestamp = this->_time_last_sample;
    }

    for(const FilterDataPoint& datapoint : *this->_filter_data.at(channel))
    {
        sum += datapoint.data;
    }

    return sum / (double)data_size;
}

bool DownsampleAverageFilter::ready_to_publish()
{
    if (this->_time_based)
    {
        if (this->_time_last_sample - this->_time_first_sample < this->_timebase_value * 1e9)
            return false;
    }
    else
    {
        // sample count based
        if (this->_samples_recorded < this->_timebase_value)
            return false;
    }
    return true;
}

void DownsampleAverageFilter::publishing()
{
    this->_samples_recorded = 0;
    this->_time_first_sample = 0;
    this->_time_last_sample = 0;
}
