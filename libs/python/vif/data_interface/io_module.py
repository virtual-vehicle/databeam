from typing import List, Dict, Union

from vif.logger.logger import LoggerMixin
from vif.data_interface.config_handler import ConfigHandler
from vif.data_interface.data_broker import DataBroker

from vif.data_interface.network_messages import Status, IOEvent


class IOModule(LoggerMixin):
    def __init__(self, *args, module_interface, **kwargs):
        super().__init__()
        self.name = 'default_name'
        # convenience assignments for easier access (skipping self.module_interface.xxx)
        self.module_interface = module_interface
        self.data_broker: DataBroker = module_interface.data_broker
        self.config_handler: ConfigHandler = module_interface.config_handler

    def start(self) -> None:
        """
        Called by module interface during startup.
        Perform any initialization needed only once here.
        """
        self.logger.debug("Module Start.")

    def stop(self) -> None:
        """
        Called by module interface during shutdown.
        Perform any cleanup here.
        """
        self.logger.debug("Module Stop.")

    def command_validate_config(self, config: Dict) -> Status:
        """
        Called by module interface when a new config is received, before command_apply_config.
        Validate the given config for plausibility and value ranges.
        :param config: the config dict to validate
        :return: Status object with optional error title and message
        """
        return Status(error=False)

    def command_apply_config(self) -> Status:
        """
        Called by module interface when a new config is received.
        Apply the new config values to the running service.
        :return: Status object with optional error title and message
        """
        return Status(error=False)

    def command_config_event(self, cfg_key: str) -> None:
        """
        Called by module interface when a config event is received.
        :param cfg_key: Contains the event name
        :return: None
        """
        pass

    def command_prepare_sampling(self) -> None:
        """
        Called by module interface when sampling is prepared globally.
        Controller waits for all modules to finish this command.
        Perform lengthy preparations for sampling start here.
        """
        self.logger.debug("Module Prepare Sampling.")

    def command_start_sampling(self) -> None:
        """
        Called by module interface when sampling is actually started.
        Controller does not wait for a reply - all modules should start sampling immediately.
        Only needed if last-millisecond changes are necessary.
        self.data_broker.data_in is aware of this and can be called beforehand.
        """
        self.logger.debug("Module Start Sampling.")

    def command_stop_sampling(self) -> None:
        """
        Called by module interface when sampling is stopped.
        Stop sample generation / power down device, etc.
        """
        self.logger.debug("Module Stop Sampling.")

    def command_prepare_capturing(self) -> None:
        """
        Called by module interface when capturing is prepared globally.
        Controller waits for all modules to finish this command.
        Perform lengthy preparations for capturing start here.
        Sampling is already active, when capturing is prepared/started.
        """
        self.logger.debug("Module Prepare Capturing.")

    def command_start_capturing(self) -> None:
        """
        Called by module interface when capturing is actually started.
        Controller does not wait for a reply - all modules should start capturing immediately.
        Only needed if last-millisecond changes are necessary.
        self.data_broker.data_in is aware of this and can be called beforehand (will ignore capturing).
        """
        self.logger.debug("Module Start Capturing.")

    def command_stop_capturing(self) -> None:
        """
        Called by module interface when capturing is stopped.
        Sampling may remain active after this call.
        Only stop any custom (file-)capture related tasks.
        """
        self.logger.debug("Module Stop Capturing.")

    def get_meta_data(self) -> Dict[str, Union[str, int, float, bool, List[str]]]:
        module_schemas = self.command_get_schemas()
        module_meta = self.command_get_meta_data()
        topics: List[str] = [self.name if 'topic' not in s else s['topic'] for s in module_schemas]
        module_meta['mcap_topics'] = topics
        return module_meta

    def command_get_meta_data(self) -> Dict[str, Union[str, int, float, bool, List[str]]]:
        """
        Called by module interface when the module is queried for meta-data.
        Return any relevant information about the device, channel units etc.
        :return: Flat dict with meta-data key-values
        """
        return {}

    def command_get_schemas(self) -> List[Dict]:
        """
        Called by module interface when the module is queried for schema information.
        Return a list of schemas that can be used by self.data_broker.data_in.
        Schemas are used to decode data saved to MCAP files.
        Channel names must be equal to dict-keys in self.data_broker.data_in.
        :return: List of one or more schemas for self.data_broker.data_in
        """
        return [{
            'type': 'object',
            'properties': {
                # TODO list all possible channel names and data types ('number', 'integer', 'string')
                # 'channel_1': {'type': 'number'},
                # 'channel_2': {'type': 'integer'},
            }
        }]

    def event_received(self, io_event: IOEvent) -> None:
        """
        Called by module interface when an asynchronous event is received.
        Events are used to trigger actions on a single module.
        :param io_event: contains "json_data" field with custom data
        """
        self.logger.debug('event received: %s', io_event.json_data)
        # for key, value in json.loads(io_event.json_data):
        #     self.logger.debug(f'JSON {key}: {value}')
