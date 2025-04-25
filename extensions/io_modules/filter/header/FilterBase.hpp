#pragma once

#include "Json.h"
#include <vector>
#include <unordered_map>

#define CHANNEL_MEM_RESERVE 10000

struct FilterDataPoint
{
    long long time_ns;
    double data;
};

class FilterBase
{
    public:
    virtual ~FilterBase();

    /**
     * Called whenever config is applied. Receives the whole config json. The constant filter
     * parameters needs to be configured here.
     */
    virtual void configure(Json& config) = 0;

    /**
     * Called for every iteration of the filter on a new datapoint. Gets the
     * currently requested channel name as a string and needs to return the filter result as a double.
     */
    virtual double compute(std::string channel) = 0;

    /**
     * Called whenever sampling is started. Should clear all additional data of the specific filter,
     * so that no old data spills over to the new sampling run.
     */
    virtual void reset();

    void configureBase(Json& config);
    void updateData(long long time, double data, std::string channel);
    void setChannelNames(std::vector<std::string> channel_names);
    void clearChannelNames();
    void clearData();
    const std::vector<std::string>* const getChannelNames();

    protected:
    std::vector<std::string> _channel_names;
    std::unordered_map<std::string, std::vector<FilterDataPoint>*> _filter_data;
    bool _time_based;
    // _timebase_value is either sample number or time in sec based on if _time_based is true or not.
    double _timebase_value;

    private:
    void _removeByTimestamp(std::string& channel, long long compare_time);
    void _removeByDataSize(std::string& channel);
};