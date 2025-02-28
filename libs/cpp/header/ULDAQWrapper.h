#pragma once

#include <uldaq.h>
#include <string>
#include "Logger.h"

class ULDAQWrapper
{
public:
    ULDAQWrapper();
    ~ULDAQWrapper();

    //AiChanType conversion
    AiChanType aiChanTypeStringToEnum(std::string ai_chan_type_str);
    std::string aiChanTypeEnumToString(AiChanType ai_chan_type);

    //TcType conversion
    TcType tcTypeStringToEnum(std::string tc_type_str);
    std::string tcTypeEnumToString(TcType tc_type);

    //Range conversion
    Range rangeStringToEnum(std::string range_str);
    std::string rangeEnumToString(Range range);

    //TempScale conversion
    TempScale tempScaleStringToEnum(std::string temp_scale_str);
    std::string tempScaleEnumToString(TempScale temp_scale);

    //TriggerType conversion
    TriggerType triggerTypeStringToEnum(std::string trigger_type_str);
    std::string triggerTypeEnumToString(TriggerType trigger_type);

    //scan option conversion
    ScanOption scanOptionStringToEnum(std::string scan_option_str);
    std::string scanOptionEnumToString(ScanOption scan_option);

    void init(Logger* logger);
    void discover();
    bool connect(std::string device_id);
    void disconnect();
    DaqDeviceDescriptor* getDevice(std::string device_id);
    void logDeviceInfo(std::string device_id);
    void logTriggerTypes();
    void logAOInfo();
    

    void setChannelType(int channel_index, AiChanType chan_type);
    void setAllChannelTypes(AiChanType chan_type);

    void setTCType(int channel_index, TcType tc_type);
    void setAllTCTypes(TcType tc_type);
    void logTCTypes();

    DaqDeviceHandle getDaqDeviceHandle();
private:
    Logger* logger = nullptr;

    DaqDeviceDescriptor device_descriptors[20];
    unsigned int num_devices = 20;
    UlError err = ERR_NO_ERROR;

    //device handle to connected device
	DaqDeviceHandle daq_device_handle = 0;
};