#include "IOModule.h"
#include <string>
#include "Json.h"
#include <vector>
#include <pthread.h>
#include <mutex>
#include "EnvConfig.h"
#include "FilterBase.hpp"

class FilterModule : public IOModule, public INetworkSubscriber
{
public:
FilterModule() = delete;
    explicit FilterModule(EnvConfig* env_config);
    ~FilterModule();

    void init(ModuleInterface* data_interface, Logger* logger, DataBroker* data_broker) override;
    std::string getConfig() override;
    std::string getDefaultConfig() override;
    std::string validateConfig(Json& json) override;
    void applyConfig(Json& json) override;
    bool prepareStartSampling() override;
    bool startSampling() override;
    bool prepareStopSampling() override;
    bool stopSampling() override;
    std::vector<McapSchema> getMcapSchemas() override;
    void notify_subscriber(std::string key, std::string payload) override;

    ModuleInterface* getDataInterface()
    {
        return data_interface;
    }

    void subscribeChannels(std::string topic);
    void unsubscribeChannels(std::string topic);

private:
    // the environment variables config
    EnvConfig* env_config = nullptr;

    // default config json string
    std::string default_config;

    // the current json config
    Json config_json;

    FilterBase* filter;
    std::mutex filter_lock;
    std::string subscribed_topic = "";
    std::string channel_suffix = "";
};
