import json
import logging
from pathlib import Path
from typing import Union, Dict, List, Optional
from dataclasses import dataclass

from databeam_mcap_reader.reader import McapReader

# Define what should be publicly available from this module
__all__ = ['Collector', 'Module', 'Measurement']

logger = logging.getLogger("databeam_mcap")
logger.setLevel(logging.DEBUG)


@dataclass
class Module:
    name: str
    mcap_path: str
    metadata: Dict


@dataclass
class Measurement:
    name: str
    modules: Dict[str, Module]
    date_utc: str
    time_utc: str
    id: int
    tag: str
    metadata: Optional[Dict]


class Collector:
    def __init__(self):
        self._structure: Dict[str, Measurement] = {
            # 'YYYY-MM-DD_hh-mm-ss.sss_ID_tag': Measurement(
            #     name='YYYY-MM-DD_hh-mm-ss.sss_ID_tag',
            #     modules = {
            #         'MODULE_NAME': Module(
            #             mcap_path='/path/to/file.mcap',
            #             metadata=metadata-dict
            #         ),
            #         ...
            #     },
            #     metadata=metadata-dict
            #     date_utc='YYYY-MM-DD',
            #     time_utc='hh:mm:ss.sss',
            #     id=ID,
            #     tag=tag
            # ),
            # ...
        }
        pass

    def parse_directory(self, path: Union[str, Path]) -> None:
        path = Path(path)
        # TODO detect mcap files even if not in proper structure (e.g. all in measurement dir)
        #      --> add to structure under separate "uncategorized" measurement

        if not path.is_dir():
            raise ValueError(f"Path {path} is not a directory")

        # find .mcap files and add to structure
        for mcap_file in path.glob('**/*.mcap'):
            # logger.debug(mcap_file)
            mcap_path = mcap_file.absolute()
            module_name = mcap_path.parent.name
            measurement_name = mcap_path.parent.parent.name
            try:
                (mcap_file_measurement_date,
                 mcap_file_measurement_time,
                 mcap_file_measurement_id,
                 mcap_file_measurement_tag) = measurement_name.split('_')
            except Exception as e:
                logger.warning(f"Failed to parse mcap {mcap_file.name} {type(e).__name__}: {e}")
                continue

            try:
                module_meta_json = json.load(open(mcap_file.parent / 'module_meta.json'))
            except Exception as e:
                logger.error(f"Failed to load metadata for module {module_name} {type(e).__name__}: {e}")
                module_meta_json = None

            if measurement_name not in self._structure:
                # logger.debug(f"Creating measurement {measurement_name} in structure")
                self._structure[measurement_name] = Measurement(
                    name=measurement_name,
                    modules={},
                    metadata=None,
                    date_utc=mcap_file_measurement_date,
                    time_utc=mcap_file_measurement_time.replace('-', ':'),
                    id=int(mcap_file_measurement_id),
                    tag=mcap_file_measurement_tag
                )
                # try to add metadata
                try:
                    measurement_meta_json = json.load(open(mcap_path.parent.parent / 'meta.json'))
                    self._structure[measurement_name].metadata = measurement_meta_json
                except Exception as e:
                    logger.error(f"Failed to load metadata for measurement {measurement_name} {type(e).__name__}: {e}")

            if module_name in self._structure[measurement_name].modules:
                logger.error(f"Module {module_name} already exists in measurement {measurement_name}")

            # logger.debug(f"Adding module {module_name} to measurement {measurement_name}")
            self._structure[measurement_name].modules[module_name] = Module(
                name=module_name,
                mcap_path=str(mcap_path),
                metadata=module_meta_json
            )

    def get_structure(self) -> Dict[str, Measurement]:
        return self._structure

    def get_module_names_list(self) -> List[str]:
        module_list = []
        for measurement in self._structure:
            for module in self._structure[measurement].modules:
                if module not in module_list:
                    module_list.append(module)
        return module_list

    def get_measurement_with_module(self, module_name: str) -> List[Measurement]:
        measurements = []
        for measurement_name, measurement in self._structure.items():
            if module_name in self._structure[measurement_name].modules:
                measurements.append(measurement)
        # return measurements
        return sorted(measurements, key=lambda _m: _m.name)

    def get_measurement_by_name(self, measurement_name: str) -> Measurement:
        return self._structure[measurement_name]

    def get_mcap_reader(self, module: Union[str, Path, Module]) -> McapReader:
        reader = McapReader()
        if isinstance(module, Module):
            reader.open(module.mcap_path)
        elif isinstance(module, (str, Path)):
            reader.open(module)
        else:
            raise ValueError(f"module must be a Module, str or Path, not {type(module)}")
        return reader


if __name__ == "__main__":
    logging.basicConfig(format='%(asctime)s %(levelname)-7s | %(message)s', level=logging.DEBUG)

    collector = Collector()
    collector.parse_directory(path="../../testdata_multi_measurement")
    structure = collector.get_structure()
    # print(json.dumps(structure, indent=4))

    # li = collector.get_module_names_list()
    # print(li)

    # ms = collector.get_measurement_with_module('MyModule')
    # print(ms)

    # for m in collector.get_measurement_with_module('MyModule'):
    #     print(m.name)

    # fetch data from single module/MCAP
    # reader = collector.get_mcap_reader(module=structure['2025-03-17_14-30-29.499_75_xyz'].modules['MyModule'])
    # reader.get_info_string()
    # module_data = reader.get_all_data()

    # fetch data from all modules in a measurement
    for module in collector.get_measurement_by_name('2025-03-17_14-30-29.499_75_xyz').modules.values():
        reader = collector.get_mcap_reader(module)
        reader.get_all_data()
        # reader.get_info_string()

    # TODO:
    # fetch data from all measurements in structure for certain module
    # get sum of number of messages in all measurements
    # get first modules data
    # create big buffer to hold all data from dtype of first module
    # iterate over all measurements
    #   read data from module
    #   append data to big buffer

    # merged_reader = collector.get_collection_reader(structure)
    # # TODO not all modules may be available in all measurements
    # # collection_data = {module: reader.get_all_data() for module, reader in reader_iterator}
    # # TODO adopt reader to append data to pre-allocated array at index X
    # # TODO combine data from all measurements
