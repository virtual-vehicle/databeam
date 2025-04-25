#include "MedianFilter.hpp"
#include <iostream>
#include <algorithm>

MedianFilter::MedianFilter()
{
    
}

MedianFilter::~MedianFilter()
{
    
}

void MedianFilter::configure(Json& config)
{
    
}

double MedianFilter::compute(std::string channel)
{
    // This here can be optimized further. Now it works with O(n*log(n)), where n = window size
    // for every datapoint. With 3 channels, 10000 samples window size and 1kHz data frequency,
    // it needed ~40% of a 4.7Ghz CPU core. So it is ok, but can make problems in high frequency
    // applications.
    std::vector<double> sorted_data;
    std::vector<FilterDataPoint>* data_pointer = this->_filter_data[channel];
    sorted_data.resize(data_pointer->size());
    std::transform(data_pointer->begin(), data_pointer->end(), sorted_data.begin(),
                   [](const FilterDataPoint& datapoint) { return datapoint.data; });
    std::sort(sorted_data.begin(), sorted_data.end());
    return sorted_data.at(sorted_data.size() / 2);
}