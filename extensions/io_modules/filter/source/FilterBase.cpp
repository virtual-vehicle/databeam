#include "FilterBase.hpp"

FilterBase::~FilterBase()
{
    this->clearChannelNames();
    this->clearData();
    for(auto channel_data : this->_filter_data)
    {
        delete channel_data.second;
    }
    this->_filter_data.clear();
}

void FilterBase::reset()
{

}

void FilterBase::setChannelNames(std::vector<std::string> channel_names)
{
    for(const std::string& channel_name : channel_names)
    {
        this->_channel_names.push_back(channel_name);
        this->_filter_data[channel_name] = new std::vector<FilterDataPoint>();
        // Let's just reserve memory for 10000 data points.
        // This is still just 160kb per channel.
        this->_filter_data[channel_name]->reserve(CHANNEL_MEM_RESERVE);
    }
}

void FilterBase::configureBase(Json& config)
{
    this->_time_based = config.getString("timebase") == "time";
    this->_timebase_value = config.getDouble("timebase_value");
}

void FilterBase::clearChannelNames()
{
    this->_channel_names.clear();
}

const std::vector<std::string>* const FilterBase::getChannelNames()
{
    return &(this->_channel_names);
}

void FilterBase::updateData(long long time, double data, std::string channel)
{
    FilterDataPoint datapoint;
    datapoint.data = data;
    datapoint.time_ns = time;
    this->_filter_data[channel]->push_back(datapoint);

    if(this->_time_based)
        this->_removeByTimestamp(channel, time);
    else
        this->_removeByDataSize(channel);
}

void FilterBase::clearData()
{
    this->reset();

    for(auto channel_data : this->_filter_data)
    {
        channel_data.second->clear();
        channel_data.second->reserve(CHANNEL_MEM_RESERVE);
    }
}

void FilterBase::_removeByTimestamp(std::string& channel, long long compare_time)
{
    // This works because the data vectors are sorted by nature.
    bool all_data_new = false;
    while(!all_data_new)
    {
        long long data_time = this->_filter_data[channel]->at(0).time_ns;
        long long time_diff = compare_time - data_time;
        if(time_diff > this->_timebase_value * 1e9)
            this->_filter_data[channel]->erase(this->_filter_data[channel]->begin());
        else
            all_data_new = true;
    }
}

void FilterBase::_removeByDataSize(std::string& channel)
{
    size_t data_size = this->_filter_data[channel]->size();
    long long excess_data = data_size - this->_timebase_value;
    if(excess_data > 0)
    {
        for(long long i = 0; i < excess_data; i++)
        {
            this->_filter_data[channel]->erase(this->_filter_data[channel]->begin());
        }
    }
}
