from typing import List, Self, Dict, Union, Any

class ModuleMetaFactory:
    def __init__(self):
        self._meta_dict = {
            '_webinterfaces': [],
            '_video_streams': []
        }

    def add(self, key: str, value):
        if key.startswith("_"):
            return

        self._meta_dict[key] = value

    def add_dict(self, meta_dict):
        for k,v in meta_dict.items():
            self.add(k, v)

    def add_mcap_topics(self, mcap_topics: List[str]):
        self._meta_dict['_mcap_topics'] = mcap_topics

    def add_webinterface(self, label: str, port: str = "", url: str = ""):
        data_dict = {
            'label': label,
            'port': str(port),
            'url': url
        }

        self._meta_dict['_webinterfaces'].append(data_dict)

    def add_video_stream(self, label: str, port: str, path: str):
        data_dict = {
            'label': label,
            'port': str(port),
            'path': path
        }

        self._meta_dict['_video_streams'].append(data_dict)

    def get_meta_dict(self):
        return self._meta_dict

