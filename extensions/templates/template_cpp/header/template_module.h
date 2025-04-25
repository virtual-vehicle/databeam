#include "IOModule.h"
#include <string>
#include "Json.h"
#include <vector>
#include <pthread.h>
#include "EnvConfig.h"

class TemplateModule : public IOModule
{
public:
    TemplateModule() = delete;
    explicit TemplateModule(EnvConfig* env_config);
    ~TemplateModule();

    void init(ModuleInterface* data_interface, Logger* logger, DataBroker* data_broker) override;
    std::string getConfig() override;
    std::string getDefaultConfig() override;
    std::string validateConfig(Json& json) override;
    void applyConfig(Json& json) override;
    bool prepareStartSampling() override;
    bool startSampling() override;
    bool prepareStopSampling() override;
    bool stopSampling() override;
    bool getThreadKillFlag() { return worker_thread_kill; }
    std::vector<McapSchema> getMcapSchemas() override;

    ModuleInterface* getDataInterface()
    {
        return data_interface;
    }

private:
    // the environment variables config
    EnvConfig* env_config = nullptr;

    // worker thread
    pthread_t worker_thread_id;
    bool worker_thread_kill = false;

    // default config json string
    std::string default_config;

    // the current json config
    Json config_json;
};
