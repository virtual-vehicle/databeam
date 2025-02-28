#include "ULDAQWrapper.h"
#include <vector>

ULDAQWrapper::ULDAQWrapper()
{

}

ULDAQWrapper::~ULDAQWrapper()
{

}

void ULDAQWrapper::init(Logger* logger)
{
    this->logger = logger;
}

void ULDAQWrapper::discover()
{
    //query daq devices
    err = ulGetDaqDeviceInventory(DaqDeviceInterface::ANY_IFC, device_descriptors, &num_devices);

    for(unsigned int i = 0; i < num_devices; i++)
    {
        logger->debug("Found Device: " + std::string(device_descriptors[i].uniqueId));
    }

    if(err != UlError::ERR_NO_ERROR)
    {
        logger->error("ULDAQ error from ulGetDaqDeviceInventory(): " + std::to_string(err));
    }
}

bool ULDAQWrapper::connect(std::string device_id)
{
    logger->debug("Connect DAQ device.");

    DaqDeviceDescriptor* dev_descriptor = getDevice(device_id);

    if(dev_descriptor == nullptr) return false;

    //create daq device
    daq_device_handle = ulCreateDaqDevice(*dev_descriptor);

    //log error
    if(daq_device_handle == 0){
        logger->error("ULDAQ: Could not create device handle");
        return false;
    }

    //connect to device
    err = ulConnectDaqDevice(daq_device_handle);

    //log error
    if(err != ERR_NO_ERROR){
        logger->error("ULDAQ: Could not connect to device");
        return false;
    } 

    return true;
}

void ULDAQWrapper::disconnect()
{
    //disconnect device
    ulDisconnectDaqDevice(daq_device_handle);

    //release device handle
    if(daq_device_handle) ulReleaseDaqDevice(daq_device_handle);
}

DaqDeviceDescriptor* ULDAQWrapper::getDevice(std::string device_id)
{
    for(unsigned int i = 0; i < num_devices; i++)
    {
        if(std::string(device_descriptors[i].uniqueId) == device_id)
        {
            return &device_descriptors[i];
        }
    }

    logger->error("ULDAQWrapper: No device found for id \"" + device_id + "\".");

    return nullptr;
}

void ULDAQWrapper::logDeviceInfo(std::string device_id)
{
    //get device with for id
    DaqDeviceDescriptor* device = getDevice(device_id);

    //leave if there is no such device
    if(device == nullptr) return;

    //log device
    logger->debug("Device info: ");
    logger->debug("- Product Name: " + std::string(device->productName));
    logger->debug("- Device String: " + std::string(device->devString));
    logger->debug("- Product ID: " + std::to_string(device->productId));
    logger->debug("- Unique ID: " + std::string(device->uniqueId));
}

void ULDAQWrapper::logTriggerTypes()
{
    //holds supported trigger types
	long long trigger_types = 0;

    //get all trigger types
	err = ulAIGetInfo(daq_device_handle, AI_INFO_TRIG_TYPES, 0, &trigger_types);

    //print supported trigger types
    if(err == ERR_NO_ERROR && trigger_types > 0)
    {
        logger->debug("Supported Trigger Types:");

        for(unsigned int i = 0; i < 20; i++)
        {
            long long mask = 1 << i;

            if(mask & trigger_types)
            {
                std::string trigger_type_str = triggerTypeEnumToString((TriggerType)mask);
                logger->debug(std::string("- ") + trigger_type_str);
            }
        }
    }
}

void ULDAQWrapper::logAOInfo()
{
    long long info_resolution = 0;
    long long info_num_chans = 0;
    long long info_scan_options = 0;
    long long info_has_pacer = 0;
    long long info_num_ranges = 0;
    long long info_range = 0;
    long long info_trig_types = 0;
    long long info_fifo_size = 0;

    //get all trigger types
	if(ulAOGetInfo(daq_device_handle, AO_INFO_RESOLUTION, 0, &info_resolution) != ERR_NO_ERROR ||
       ulAOGetInfo(daq_device_handle, AO_INFO_NUM_CHANS, 0, &info_num_chans) != ERR_NO_ERROR ||
       ulAOGetInfo(daq_device_handle, AO_INFO_SCAN_OPTIONS, 0, &info_scan_options) != ERR_NO_ERROR ||
       ulAOGetInfo(daq_device_handle, AO_INFO_HAS_PACER, 0, &info_has_pacer) != ERR_NO_ERROR ||
       ulAOGetInfo(daq_device_handle, AO_INFO_NUM_RANGES, 0, &info_num_ranges) != ERR_NO_ERROR ||
       ulAOGetInfo(daq_device_handle, AO_INFO_TRIG_TYPES, 0, &info_trig_types) != ERR_NO_ERROR ||
       ulAOGetInfo(daq_device_handle, AO_INFO_FIFO_SIZE, 0, &info_fifo_size) != ERR_NO_ERROR)
    {
        logger->error("ULDAQ Error " + std::to_string(err) + " in logAOInfo().");
    }
    else
    {
        

        

        logger->debug(std::string("Anlog Out Info:"));
        logger->debug(std::string("- AO_INFO_RESOLUTION: ") + std::to_string(info_resolution));
        logger->debug(std::string("- AO_INFO_NUM_CHANS: ") + std::to_string(info_num_chans));
        
        std::string scan_options = "[";
        std::string trigger_types = "[";
        std::string ranges = "[";

        for(unsigned int i = 0; i < info_num_ranges; i++)
        {
            long long range = 0;

            if(ulAOGetInfo(daq_device_handle, AO_INFO_RANGE, i, &range) != ERR_NO_ERROR)
            {
                logger->error("ULDAQ Error " + std::to_string(err) + " in logAOInfo() AO_INFO_RANGE.");
                return;
            }
            else
            {
                ranges += rangeEnumToString((Range)range) + ", ";
            }
        }

        for(unsigned int i = 0; i < 32; i++){
            long long mask = 1 << i;
            if(mask & info_scan_options) scan_options += scanOptionEnumToString((ScanOption)mask) + ", ";
            if(mask & info_trig_types) trigger_types += triggerTypeEnumToString((TriggerType)mask) + ", ";
        }

        if(scan_options.length() > 2){
            scan_options.pop_back();
            scan_options[scan_options.length() - 1] = ']';
        }

        if(scan_options.length() > 2){
            trigger_types.pop_back();
            trigger_types[trigger_types.length() - 1] = ']';
        }

        if(ranges.length() > 2){
            ranges.pop_back();
            ranges[ranges.length() - 1] = ']';
        }

        logger->debug(std::string("- AO_INFO_SCAN_OPTIONS: ") + scan_options);
        logger->debug(std::string("- AO_INFO_TRIG_TYPES: ") + trigger_types);
        logger->debug(std::string("- AO_INFO_HAS_PACER: ") + std::to_string(info_has_pacer));
        logger->debug(std::string("- AO_INFO_NUM_RANGES: ") + std::to_string(info_num_ranges) + std::string(" ") + ranges);
        logger->debug(std::string("- AO_INFO_RANGE: ") + std::to_string(info_range));
        logger->debug(std::string("- AO_INFO_FIFO_SIZE: ") + std::to_string(info_fifo_size));
    }

}

void ULDAQWrapper::setChannelType(int channel_index, AiChanType chan_type)
{
    UlError err = ulAISetConfig(daq_device_handle, AiConfigItem::AI_CFG_CHAN_TYPE, channel_index, chan_type);

    if(err != ERR_NO_ERROR) logger->error("ULDAQ Error " + std::to_string(err) + " in setChannelType().");
}

void ULDAQWrapper::setAllChannelTypes(AiChanType chan_type)
{
    for(int i = 0; i < 8; i++)
    {
        setChannelType(i, chan_type);
    }
}

void ULDAQWrapper::setTCType(int channel_index, TcType tc_type)
{
    UlError ul_error = ulAISetConfig(daq_device_handle, AiConfigItem::AI_CFG_CHAN_TC_TYPE, channel_index, tc_type);
    if(ul_error != ERR_NO_ERROR) logger->error("ULDAQ Error " + std::to_string(err) + " in setTCType().");
}

void ULDAQWrapper::setAllTCTypes(TcType tc_type)
{
    for(int i = 0; i < 8; i++) setTCType(i, tc_type);
}

void ULDAQWrapper::logTCTypes()
{
    logger->debug("logTCTypes:");

    for(int i = 0; i < 8; i++)
    {
        long long config_value;
        UlError ul_error = ulAIGetConfig(daq_device_handle, AiConfigItem::AI_CFG_CHAN_TC_TYPE, i, &config_value);
        
        if(ul_error != ERR_NO_ERROR)
        {
            logger->error("ULDAQ Error " + std::to_string(err) + " in logTCTypes().");
        }
        else
        {
            logger->debug(std::string("- Channel ") + std::to_string(i) + std::string(" set to ") + tcTypeEnumToString((TcType)config_value));
        }
    }
}

DaqDeviceHandle ULDAQWrapper::getDaqDeviceHandle()
{
    return daq_device_handle;
}


Range ULDAQWrapper::rangeStringToEnum(std::string range_str)
{
    if(range_str == "BIP60VOLTS") return BIP60VOLTS;
    if(range_str == "BIP30VOLTS") return BIP30VOLTS;
    if(range_str == "BIP15VOLTS") return BIP15VOLTS;
    if(range_str == "BIP20VOLTS") return BIP20VOLTS;
    if(range_str == "BIP10VOLTS") return BIP10VOLTS;
    if(range_str == "BIP5VOLTS") return BIP5VOLTS;
    if(range_str == "BIP4VOLTS") return BIP4VOLTS;
    if(range_str == "BIP2PT5VOLTS") return BIP2PT5VOLTS;
    if(range_str == "BIP2VOLTS") return BIP2VOLTS;
    if(range_str == "BIP1PT25VOLTS") return BIP1PT25VOLTS;
    if(range_str == "BIP1VOLTS") return BIP1VOLTS;
    if(range_str == "BIPPT625VOLTS") return BIPPT625VOLTS;
    if(range_str == "BIPPT25VOLTS") return BIPPT25VOLTS;
    if(range_str == "BIPPT125VOLTS") return BIPPT125VOLTS;
    if(range_str == "BIPPT2VOLTS") return BIPPT2VOLTS;
    if(range_str == "BIPPT1VOLTS") return BIPPT1VOLTS;
    if(range_str == "BIPPT078VOLTS") return BIPPT078VOLTS;
    if(range_str == "BIPPT05VOLTS") return BIPPT05VOLTS;
    if(range_str == "BIPPT01VOLTS") return BIPPT01VOLTS;
    if(range_str == "BIPPT005VOLTS") return BIPPT005VOLTS;
    if(range_str == "BIP3VOLTS") return BIP3VOLTS;
    if(range_str == "BIPPT312VOLTS") return BIPPT312VOLTS;
    if(range_str == "BIPPT156VOLTS") return BIPPT156VOLTS;
    if(range_str == "UNI60VOLTS") return UNI60VOLTS;
    if(range_str == "UNI30VOLTS") return UNI30VOLTS;
    if(range_str == "UNI15VOLTS") return UNI15VOLTS;
    if(range_str == "UNI20VOLTS") return UNI20VOLTS;
    if(range_str == "UNI10VOLTS") return UNI10VOLTS;
    if(range_str == "UNI5VOLTS") return UNI5VOLTS;
    if(range_str == "UNI4VOLTS") return UNI4VOLTS;
    if(range_str == "UNI2PT5VOLTS") return UNI2PT5VOLTS;
    if(range_str == "UNI2VOLTS") return UNI2VOLTS;
    if(range_str == "UNI1PT25VOLTS") return UNI1PT25VOLTS;
    if(range_str == "UNI1VOLTS") return UNI1VOLTS;
    if(range_str == "UNIPT625VOLTS") return UNIPT625VOLTS;
    if(range_str == "UNIPT5VOLTS") return UNIPT5VOLTS;
    if(range_str == "UNIPT25VOLTS") return UNIPT25VOLTS;
    if(range_str == "UNIPT125VOLTS") return UNIPT125VOLTS;
    if(range_str == "UNIPT2VOLTS") return UNIPT2VOLTS;
    if(range_str == "UNIPT1VOLTS") return UNIPT1VOLTS;
    if(range_str == "UNIPT078VOLTS") return UNIPT078VOLTS;
    if(range_str == "UNIPT05VOLTS") return UNIPT05VOLTS;
    if(range_str == "UNIPT01VOLTS") return UNIPT01VOLTS;
    if(range_str == "UNIPT005VOLTS") return UNIPT005VOLTS;
    if(range_str == "MA0TO20") return MA0TO20;

    return MA0TO20;
}

std::string ULDAQWrapper::rangeEnumToString(Range range)
{
    if(range == BIP60VOLTS) return std::string("BIP60VOLTS");
    if(range == BIP30VOLTS) return std::string("BIP30VOLTS");
    if(range == BIP15VOLTS) return std::string("BIP15VOLTS");
    if(range == BIP20VOLTS) return std::string("BIP20VOLTS");
    if(range == BIP10VOLTS) return std::string("BIP10VOLTS");
    if(range == BIP5VOLTS) return std::string("BIP5VOLTS");
    if(range == BIP4VOLTS) return std::string("BIP4VOLTS");
    if(range == BIP2PT5VOLTS) return std::string("BIP2PT5VOLTS");
    if(range == BIP2VOLTS) return std::string("BIP2VOLTS");
    if(range == BIP1PT25VOLTS) return std::string("BIP1PT25VOLTS");
    if(range == BIP1VOLTS) return std::string("BIP1VOLTS");
    if(range == BIPPT625VOLTS) return std::string("BIPPT625VOLTS");
    if(range == BIPPT25VOLTS) return std::string("BIPPT25VOLTS");
    if(range == BIPPT125VOLTS) return std::string("BIPPT125VOLTS");
    if(range == BIPPT2VOLTS) return std::string("BIPPT2VOLTS");
    if(range == BIPPT1VOLTS) return std::string("BIPPT1VOLTS");
    if(range == BIPPT078VOLTS) return std::string("BIPPT078VOLTS");
    if(range == BIPPT05VOLTS) return std::string("BIPPT05VOLTS");
    if(range == BIPPT01VOLTS) return std::string("BIPPT01VOLTS");
    if(range == BIPPT005VOLTS) return std::string("BIPPT005VOLTS");
    if(range == BIP3VOLTS) return std::string("BIP3VOLTS");
    if(range == BIPPT312VOLTS) return std::string("BIPPT312VOLTS");
    if(range == BIPPT156VOLTS) return std::string("BIPPT156VOLTS");
    if(range == UNI60VOLTS) return std::string("UNI60VOLTS");
    if(range == UNI30VOLTS) return std::string("UNI30VOLTS");
    if(range == UNI15VOLTS) return std::string("UNI15VOLTS");
    if(range == UNI20VOLTS) return std::string("UNI20VOLTS");
    if(range == UNI10VOLTS) return std::string("UNI10VOLTS");
    if(range == UNI5VOLTS) return std::string("UNI5VOLTS");
    if(range == UNI4VOLTS) return std::string("UNI4VOLTS");
    if(range == UNI2PT5VOLTS) return std::string("UNI2PT5VOLTS");
    if(range == UNI2VOLTS) return std::string("UNI2VOLTS");
    if(range == UNI1PT25VOLTS) return std::string("UNI1PT25VOLTS");
    if(range == UNI1VOLTS) return std::string("UNI1VOLTS");
    if(range == UNIPT625VOLTS) return std::string("UNIPT625VOLTS");
    if(range == UNIPT5VOLTS) return std::string("UNIPT5VOLTS");
    if(range == UNIPT25VOLTS) return std::string("UNIPT25VOLTS");
    if(range == UNIPT125VOLTS) return std::string("UNIPT125VOLTS");
    if(range == UNIPT2VOLTS) return std::string("UNIPT2VOLTS");
    if(range == UNIPT1VOLTS) return std::string("UNIPT1VOLTS");
    if(range == UNIPT078VOLTS) return std::string("UNIPT078VOLTS");
    if(range == UNIPT05VOLTS) return std::string("UNIPT05VOLTS");
    if(range == UNIPT01VOLTS) return std::string("UNIPT01VOLTS");
    if(range == UNIPT005VOLTS) return std::string("UNIPT005VOLTS");
    if(range == MA0TO20) return std::string("MA0TO20");

	return std::string("UNDEFINED");
}

TcType ULDAQWrapper::tcTypeStringToEnum(std::string tc_type_str)
{
    if(tc_type_str == "J") return TcType::TC_J;
    else if(tc_type_str == "K") return TcType::TC_K;
    else if(tc_type_str == "T") return TcType::TC_T;
    else if(tc_type_str == "E") return TcType::TC_E;
    else if(tc_type_str == "R") return TcType::TC_R;
    else if(tc_type_str == "S") return TcType::TC_S;
    else if(tc_type_str == "B") return TcType::TC_B;
    else if(tc_type_str == "N") return TcType::TC_N;
    else return TcType::TC_N;
}

std::string ULDAQWrapper::tcTypeEnumToString(TcType tc_type)
{
    if(tc_type == TcType::TC_J) return std::string("J");
    else if(tc_type == TcType::TC_K) return std::string("K");
    else if(tc_type == TcType::TC_T) return std::string("T");
    else if(tc_type == TcType::TC_E) return std::string("E");
    else if(tc_type == TcType::TC_R) return std::string("R");
    else if(tc_type == TcType::TC_S) return std::string("S");
    else if(tc_type == TcType::TC_B) return std::string("B");
    else if(tc_type == TcType::TC_N) return std::string("N");
    else return std::string("UNDEFINED");
}

AiChanType ULDAQWrapper::aiChanTypeStringToEnum(std::string ai_chan_type_str)
{
    if(ai_chan_type_str == "AI_VOLTAGE") return AiChanType::AI_VOLTAGE;
    else if(ai_chan_type_str == "AI_TC") return AiChanType::AI_TC;
    else if(ai_chan_type_str == "AI_RTD") return AiChanType::AI_RTD;
    else if(ai_chan_type_str == "AI_THERMISTOR") return AiChanType::AI_THERMISTOR;
    else if(ai_chan_type_str == "AI_SEMICONDUCTOR") return AiChanType::AI_SEMICONDUCTOR;
    else if(ai_chan_type_str == "AI_DISABLED") return AiChanType::AI_DISABLED;
    else return AiChanType::AI_DISABLED;
}

std::string ULDAQWrapper::aiChanTypeEnumToString(AiChanType ai_chan_type)
{
    if(ai_chan_type == AiChanType::AI_VOLTAGE) return std::string("AI_VOLTAGE");
    else if(ai_chan_type == AiChanType::AI_TC) return std::string("AI_TC");
    else if(ai_chan_type == AiChanType::AI_RTD) return std::string("AI_RTD");
    else if(ai_chan_type == AiChanType::AI_THERMISTOR) return std::string("AI_THERMISTOR");
    else if(ai_chan_type == AiChanType::AI_SEMICONDUCTOR) return std::string("AI_SEMICONDUCTOR");
    else if(ai_chan_type == AiChanType::AI_DISABLED) return std::string("AI_DISABLED");
    else return std::string("AI_DISABLED");
}

TempScale ULDAQWrapper::tempScaleStringToEnum(std::string temp_scale_str)
{
    if(temp_scale_str == "Celsius") return TempScale::TS_CELSIUS;
    else if(temp_scale_str == "Fahrenheit") return TempScale::TS_FAHRENHEIT;
    else if(temp_scale_str == "Kelvin") return TempScale::TS_KELVIN;
    else if(temp_scale_str == "No Scale") return TempScale::TS_NOSCALE;
    else if(temp_scale_str == "Volts") return TempScale::TS_VOLTS;
    else return TempScale::TS_NOSCALE;
}
std::string ULDAQWrapper::tempScaleEnumToString(TempScale temp_scale)
{
    if(temp_scale == TempScale::TS_CELSIUS) return "Celsius";
    else if(temp_scale == TempScale::TS_FAHRENHEIT) return "Fahrenheit";
    else if(temp_scale == TempScale::TS_KELVIN) return "Kelvin";
    else if(temp_scale == TempScale::TS_NOSCALE) return "No Scale";
    else if(temp_scale == TempScale::TS_VOLTS) return "Volts";
    else return std::string("UNDEFINED");
}

TriggerType ULDAQWrapper::triggerTypeStringToEnum(std::string trigger_type_str)
{
    if(trigger_type_str == "TRIG_NONE") return TriggerType::TRIG_NONE;
    else if(trigger_type_str == "TRIG_POS_EDGE") return TriggerType::TRIG_POS_EDGE;
    else if(trigger_type_str == "TRIG_NEG_EDGE") return TriggerType::TRIG_NEG_EDGE;
    else if(trigger_type_str == "TRIG_HIGH") return TriggerType::TRIG_HIGH;
    else if(trigger_type_str == "TRIG_LOW") return TriggerType::TRIG_LOW;
    else if(trigger_type_str == "GATE_HIGH") return TriggerType::GATE_HIGH;
    else if(trigger_type_str == "GATE_LOW") return TriggerType::GATE_LOW;
    else if(trigger_type_str == "TRIG_RISING") return TriggerType::TRIG_RISING;
    else if(trigger_type_str == "TRIG_FALLING") return TriggerType::TRIG_FALLING;
    else if(trigger_type_str == "TRIG_ABOVE") return TriggerType::TRIG_ABOVE;
    else if(trigger_type_str == "TRIG_BELOW") return TriggerType::TRIG_BELOW;
    else if(trigger_type_str == "GATE_ABOVE") return TriggerType::GATE_ABOVE;
    else if(trigger_type_str == "GATE_BELOW") return TriggerType::GATE_BELOW;
    else if(trigger_type_str == "GATE_IN_WINDOW") return TriggerType::GATE_IN_WINDOW;
    else if(trigger_type_str == "GATE_OUT_WINDOW") return TriggerType::GATE_OUT_WINDOW;
    else if(trigger_type_str == "TRIG_PATTERN_EQ") return TriggerType::TRIG_PATTERN_EQ;
    else if(trigger_type_str == "TRIG_PATTERN_NE") return TriggerType::TRIG_PATTERN_NE;
    else if(trigger_type_str == "TRIG_PATTERN_ABOVE") return TriggerType::TRIG_PATTERN_ABOVE;
    else if(trigger_type_str == "TRIG_PATTERN_BELOW") return TriggerType::TRIG_PATTERN_BELOW;
    else return TriggerType::TRIG_NONE;
}
std::string ULDAQWrapper::triggerTypeEnumToString(TriggerType trigger_type)
{
    if(trigger_type == TriggerType::TRIG_NONE) return "TRIG_NONE";
    else if(trigger_type == TriggerType::TRIG_POS_EDGE) return "TRIG_POS_EDGE";
    else if(trigger_type == TriggerType::TRIG_NEG_EDGE) return "TRIG_NEG_EDGE";
    else if(trigger_type == TriggerType::TRIG_HIGH) return "TRIG_HIGH";
    else if(trigger_type == TriggerType::TRIG_LOW) return "TRIG_LOW";
    else if(trigger_type == TriggerType::GATE_HIGH) return "GATE_HIGH";
    else if(trigger_type == TriggerType::GATE_LOW) return "GATE_LOW";
    else if(trigger_type == TriggerType::TRIG_RISING) return "TRIG_RISING";
    else if(trigger_type == TriggerType::TRIG_FALLING) return "TRIG_FALLING";
    else if(trigger_type == TriggerType::TRIG_ABOVE) return "TRIG_ABOVE";
    else if(trigger_type == TriggerType::TRIG_BELOW) return "TRIG_BELOW";
    else if(trigger_type == TriggerType::GATE_ABOVE) return "GATE_ABOVE";
    else if(trigger_type == TriggerType::GATE_BELOW) return "GATE_BELOW";
    else if(trigger_type == TriggerType::GATE_IN_WINDOW) return "GATE_IN_WINDOW";
    else if(trigger_type == TriggerType::GATE_OUT_WINDOW) return "GATE_OUT_WINDOW";
    else if(trigger_type == TriggerType::TRIG_PATTERN_EQ) return "TRIG_PATTERN_EQ";
    else if(trigger_type == TriggerType::TRIG_PATTERN_NE) return "TRIG_PATTERN_NE";
    else if(trigger_type == TriggerType::TRIG_PATTERN_ABOVE) return "TRIG_PATTERN_ABOVE";
    else if(trigger_type == TriggerType::TRIG_PATTERN_BELOW) return "TRIG_PATTERN_BELOW";
    else return std::string("UNDEFINED");
}

ScanOption ULDAQWrapper::scanOptionStringToEnum(std::string scan_option_str)
{
    if(scan_option_str == "DefaultIO") return ScanOption::SO_DEFAULTIO;
    else if(scan_option_str == "SingleIO") return ScanOption::SO_SINGLEIO;
    else if(scan_option_str == "BlockIO") return ScanOption::SO_BLOCKIO;
    else if(scan_option_str == "BurstIO") return ScanOption::SO_BURSTIO;
    else if(scan_option_str == "Continuous") return ScanOption::SO_CONTINUOUS;
    else if(scan_option_str == "ExtClock") return ScanOption::SO_EXTCLOCK;
    else if(scan_option_str == "ExtTrigger") return ScanOption::SO_EXTTRIGGER;
    else if(scan_option_str == "ReTrigger") return ScanOption::SO_RETRIGGER;
    else if(scan_option_str == "BurstMode") return ScanOption::SO_BURSTMODE;
    else if(scan_option_str == "PacerOut") return ScanOption::SO_PACEROUT;
    else if(scan_option_str == "ExtTimeBase") return ScanOption::SO_EXTTIMEBASE;
    else if(scan_option_str == "TimeBaseOut") return ScanOption::SO_TIMEBASEOUT;
    else return ScanOption::SO_DEFAULTIO;
}
std::string ULDAQWrapper::scanOptionEnumToString(ScanOption scan_option)
{
    if(scan_option == ScanOption::SO_DEFAULTIO) return "DefaultIO";
    else if(scan_option == ScanOption::SO_SINGLEIO) return "SingleIO";
    else if(scan_option == ScanOption::SO_BLOCKIO) return "BlockIO";
    else if(scan_option == ScanOption::SO_BURSTIO) return "BurstIO";
    else if(scan_option == ScanOption::SO_CONTINUOUS) return "Continuous";
    else if(scan_option == ScanOption::SO_EXTCLOCK) return "ExtClock";
    else if(scan_option == ScanOption::SO_EXTTRIGGER) return "ExtTrigger";
    else if(scan_option == ScanOption::SO_RETRIGGER) return "ReTrigger";
    else if(scan_option == ScanOption::SO_BURSTMODE) return "BurstMode";
    else if(scan_option == ScanOption::SO_PACEROUT) return "PacerOut";
    else if(scan_option == ScanOption::SO_EXTTIMEBASE) return "ExtTimeBase";
    else if(scan_option == ScanOption::SO_TIMEBASEOUT) return "TimeBaseOut";
    else return std::string("UNDEFINED");
}