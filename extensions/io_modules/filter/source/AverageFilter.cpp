#include "AverageFilter.hpp"
#include <iostream>

AverageFilter::AverageFilter()
{
    
}

AverageFilter::~AverageFilter()
{
    
}

void AverageFilter::configure(Json& config)
{
    
}

double AverageFilter::compute(std::string channel)
{
    double sum = 0.0;
    size_t data_size = this->_filter_data.at(channel)->size();
    if(data_size == 0)
        return 0.0;

    for(const FilterDataPoint& datapoint : *this->_filter_data.at(channel))
    {
        sum += datapoint.data;
    }

    return sum / (double)data_size;
}