#pragma once

#include <string>
#include <vector>
#include "Json.h"
#include "Logger.h"
#include "DataBroker.h"
#include "McapSchema.h"

class ModuleInterface;

class IOModule
{
public:
    IOModule();
    virtual ~IOModule();

    virtual void init(ModuleInterface* data_interface, Logger* logger, DataBroker* data_broker);

    void setName(std::string module_name);
    void setType(std::string module_type);

    std::string getName();
    std::string getType();

    std::string setConfig(Json& json);
    std::string getMeasurementName();
    bool isUp();

    virtual bool prepareStartCapture();
    virtual bool startCapture();
    virtual bool prepareStopCapture();
    virtual bool stopCapture();
    virtual bool prepareStartSampling();
    virtual bool startSampling();
    virtual bool prepareStopSampling();
    virtual bool stopSampling();
    virtual std::string validateConfig(Json& json);
    virtual void applyConfig(Json& json);
    virtual std::string getConfig();
    virtual std::string getDefaultConfig();
    std::string getMetaDataTemplate();
    virtual void getMetaData(JsonWriter& json_writer);
    virtual std::vector<McapSchema> getMcapSchemas();
    virtual void configEvent(std::string cfg_key);
    

    Logger* getLogger();
    DataBroker* getDataBroker();
    ModuleInterface* getDataInterface();

protected:
    ModuleInterface* data_interface = nullptr;
    Logger* logger = nullptr;
    DataBroker* data_broker = nullptr;

private:
    std::string measurement_name = "Default";
    std::string module_name = "";
    std::string module_type = "";
};