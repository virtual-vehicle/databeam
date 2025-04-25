#include "ExponentialAverageFilter.hpp"
#include <iostream>
#include <cmath>

ExponentialAverageFilter::ExponentialAverageFilter():
_smoothing_factor(0.0)
{
    
}

ExponentialAverageFilter::~ExponentialAverageFilter()
{
    
}

void ExponentialAverageFilter::configure(Json& config)
{
    if(this->_time_based)
    {
        // Do nothing. Smoothing factor is not constant, but needs to be recomputed in every timestep.
    }
    else
    {
        this->_smoothing_factor = 2.0 / (this->_timebase_value + 1);
    }
    
}

double ExponentialAverageFilter::compute(std::string channel)
{
    double new_filter_output = 0.0;
    size_t data_size = this->_filter_data[channel]->size();
    bool first_iteration = this->_filter_data[channel]->size() == 1;

    if(first_iteration)
    {
        new_filter_output = this->_filter_data[channel]->at(data_size - 1).data;
    }
    else
    {
        double new_data = this->_filter_data[channel]->at(data_size - 1).data;
        double prev_data = this->_prev_filter_output[channel];
        if(this->_time_based)
        {
            // Recompute new smoothing factor for current filter timestep.
            double time_delta_s = (double)(this->_filter_data[channel]->at(data_size - 1).time_ns -
                                           this->_filter_data[channel]->at(data_size - 2).time_ns) / 1e9;
            // Smoothing factor is closer to comparable sampling based method when using half of time delta
            double half_time_delta_s = time_delta_s / 2;
            this->_smoothing_factor = 1 - std::exp(-half_time_delta_s / this->_timebase_value);
        }

        new_filter_output = this->_smoothing_factor * new_data + (1 - this->_smoothing_factor) * prev_data;
    }

    this->_prev_filter_output[channel] = new_filter_output;
    return new_filter_output;
}

void ExponentialAverageFilter::reset()
{
    this->_prev_filter_output.clear();
}