import traceback
import os
import json
from pathlib import Path

from vif.logger.logger import LoggerMixin


plot_juggler_xml_header="""<?xml version='1.0' encoding='UTF-8'?>
<root>
 <tabbed_widget name="Main Window" parent="main_window">
  <Tab tab_name="tab1" containers="1">
   <Container>
    <DockSplitter sizes="1" count="1" orientation="-">
     <DockArea name="...">
      <plot flip_y="false" style="Lines" mode="TimeSeries" flip_x="false">
       <range right="1.000000" bottom="0.000000" left="0.000000" top="1.000000"/>
       <limitY/>
      </plot>
     </DockArea>
    </DockSplitter>
   </Container>
  </Tab>
  <currentTabIndex index="0"/>
 </tabbed_widget>
 <use_relative_time_offset enabled="0"/>
 <!-- - - - - - - - - - - - - - - -->
 <previouslyLoaded_Datafiles>
 """


class PlotJugglerWriter(LoggerMixin):
    def __init__(self, data_dir: Path):
        super().__init__()

        # store data dir
        self._data_dir: Path = data_dir

        # holds plot juggler xml header string
        self._plot_juggler_xml_head_str = plot_juggler_xml_header

    def create_plot_juggler_xml(self, measurement_name):
        self.logger.debug("Create XML for measurment: %s", measurement_name)

        # path to measurement directory
        path = self._data_dir / measurement_name

        # path to plot juggler xml file within measurement directory
        xml_path = path / "plot_juggler.xml"

        # leave if plot juggler xml file already exists
        if os.path.exists(xml_path):
            self.logger.debug("XML file already exists: %s", xml_path)
            return

        # get list of modules
        modules = [x for x in os.listdir(path) if os.path.isdir(os.path.join(path, x))]
        xml_str = ""

        # iterate all modules and generate plot juggler entry string
        for m in modules:
            module_meta_path = path / m / "module_meta.json"

            # skip if there is no module meta json file or there is no mcap file
            if (not os.path.exists(module_meta_path) or
                    not any(f.startswith(m) and f.endswith('.mcap') for f in os.listdir(path / m))):
                continue

            try:
                # get mcap topic from module meta
                with open(module_meta_path, "r") as f:
                    meta_dict = json.load(f)

                    if "_mcap_topics" in meta_dict:
                        for mcap_topic in meta_dict['_mcap_topics']:
                            xml_str += self.create_plot_juggler_entry(measurement_name, m, mcap_topic)
            except Exception as e:
                self.logger.error(f'loading meta ({module_meta_path}) failed ({type(e).__name__}): {e}\n'
                                  f'{traceback.format_exc()}')

        # create plot juggler xml file content
        if len(xml_str) > 0:
            xml_content = self._plot_juggler_xml_head_str + xml_str
            xml_content += ' </previouslyLoaded_Datafiles>\n</root>\n'

            try:
                # write xml file
                with open(xml_path, "w") as f:
                    f.write(xml_content)
            except Exception as e:
                self.logger.error(f'writing XML failed ({type(e).__name__}): {e}\n{traceback.format_exc()}')

        return

    def create_plot_juggler_entry(self, measurement_name, module_name, topic_name):
        entry_str = f'  <fileInfo prefix="" filename="../{measurement_name}/{module_name}/{module_name}.mcap">\n'
        entry_str += '   <plugin ID="DataLoad MCAP">\n'
        entry_str += f'    <parameters max_array_size="500" use_timestamp="0" clamp_large_arrays="1" selected_topics="{topic_name}"/>\n'
        entry_str += '   </plugin>\n'
        entry_str += '  </fileInfo>\n'
        return entry_str


if __name__ == "__main__":
    plot_juggler_writer: PlotJugglerWriter = PlotJugglerWriter(Path('.'))
    plot_juggler_writer.create_plot_juggler_xml('test_measurement_dir')
