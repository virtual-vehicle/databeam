from typing import Mapping

from vif.data_interface.base_config import BaseConfig
from vif.data_interface.config_factory import ConfigFactory

class CameraConfig(BaseConfig):

    Name = 'camera'

    @classmethod
    def _schema(cls) -> Mapping:
        cfg = ConfigFactory()
        cfg.string('resolution', '1280 x 720').select(
            ['1920 x 1080', '1280 x 720', '1024 x 768', '960 x 540', '848 x 480', '800 x 600', '640 x 480', '640 x 360', '424 x 240', '320 x 240',
             '320 x 180'])
        cfg.string('fps', '30').select(['60', '30', '15', '6', '5']).label('FPS')
        cfg.string('codec', 'MJPG').select(['MJPG', 'YUYV'])
        cfg.string('rotation', 'None').select(['None', '90 deg CW', '90 deg CCW', '180 deg'])
        cfg.integer('dot_in_center_size', 0)
        cfg.integer('crosshair_size', 0)
        cfg.boolean('print_timestamp', False)
        cfg.boolean('enable_mp4', True)
        cfg.number('mp4_interval', 0).label('Mp4 Interval [s]')
        cfg.boolean('enable_mcap', True)
        cfg.string('mcap_resolution', '240p').select(['1080p', '720p', '540p', '480p', '360p', '240p', '180p'])
        cfg.number('mcap_interval', 0).label('Mcap Interval [s]')
        cfg.boolean('enable_preview', True)
        cfg.string('preview_resolution', '180p').select(['1080p', '720p', '540p', '480p', '360p', '240p', '180p'])
        cfg.string('live_source', 'mcap').select(['mp4', 'mcap', 'preview'])

        return cfg.get_config()
