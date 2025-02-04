<a id="readme-top"></a>

<!-- SHIELDS -->
<div align="center">
  <img alt="License" src=https://img.shields.io/badge/License-MIT-green?style=flat-square>
  <img alt="OS" src=https://img.shields.io/badge/OS-Linux-yellow?style=flat-square>
  <img alt="Platforms" src=https://img.shields.io/badge/Platforms-x86__64,_ARM64-blue?style=flat-square>
  <img alt="Languages" src=https://img.shields.io/badge/Languages-C++,_Python-red?style=flat-square>
</div>

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <img src="doc/DATABEAM-pbVV-Logo_FINAL.png" alt="DataBeam logo" width="600">
  <h3>Complete DAQ framework to enable complex measurement scenarios.</h3>
</div>

<!-- TABLE OF CONTENTS -->
<div align="center">
  <table border=0 frame=void align="center">
    <tr>
      <th style="text-align: center"><a href="#overview">Overview</a></th>
      <th style="text-align: center"><a href="#software-structure">Software Structure</a></th>
      <th style="text-align: center"><a href="#development">Development</a></th>
      <th style="text-align: center"><a href="#deployment">Deployment</a></th>
      <th style="text-align: center"><a href="#daq-data-post-processing">Post-Processing</a></th>
      <th style="text-align: center"><a href="#license">License and Contact</a></th>
    </tr>
  </table>
</div>

<!-- <div align="center">
[Overview](#overview) •
[Software Structure](#software-structure) •
[Development](#development) •
[Deployment](#deployment) •
[Post-Processing](#daq-data-post-processing) •
[License and Contact](#license)
</div> -->

## Overview
DataBeam provides a **software solution to quickly set up complex measurement setups** where data from multiple devices need to be synchronized and recorded simultaneously.

It provides a **scalable, easy and standardized** method to integrate different types of data inputs and algorithms into a **centralized system**. DataBeam can support anything from low level hardware drivers to AI processing pipelines to create a **unified acquisition framework** which can be accessed conveniently via a **web browser**. Its web UI offers an intuitive interface for on-the-edge device management and monitoring from anywhere.

**Core Features:**
* **Combine any devices** to form a complete data acquisition system.
  - Unified output data format ([MCAP](https://mcap.dev/))
  - Timestamp synchronization
  - Fast & efficient implementation

* **Diverse use cases and fast integration** 
  - Interfaces can be USB, Ethernet, CAN-bus, RS-485, etc. - everything which can be connected to a computer.
  - Combine data acquisition and real-time data processing.
  - Documented code templates are available in **Python** and **C++** to quickly start with development.

* **Intuitive and easy to use** 
  - Run the system on any Linux-computer from Raspberry Pi to a workstation.
  - A web-interface allows easy access to dedicated lab-PC or embedded device running DataBeam 24/7 for unattended automation.
  - External time synchronization can be done by GPS 1PPS or PTP.

<br />
<div align="center">
  <img alt="What is DataBeam?" src="doc/what_is_databeam-small_logo.png">
</div>
<br />



## Usage

(let's assume the stack is installed and running - see <a href="#development">Development</a>/<a href="#deployment">Deployment</a>)

For a quick spin, follow the **<a href="QUICKSTART.md">Quickstart document</a>**.

### Open Web-UI

DataBeam may be running locally on a workstation or on an embedded Linux device --> navigate to the hostname at port 5000: e.g.: http://localhost:5000

You are greeted by the login screen. Default credentials are user: `databeam` and password: `default`. Change or extend the credentials in the `docker-compose.yml` file.

<div align="center">
  <a href="doc/login_screen.png"><img alt="DataBeam login screen" src="doc/login_screen.png" width="200"></a>
</div>

After successful login, the web-interface will be available:

<div align="center">
  <a href="doc/webinterface_config.png"><img alt="DataBeam module overview" src="doc/webinterface_config.png"></a>
</div>

The *modules* overview allows to:
* start/stop sampling or capturing to file-system
* modify the configuration of individual modules
* configure live data (file capturing, forward all samples or set maximum live frequency)
* view live preview data (numeric or images)
* view documentation of modules

Other tabs offer listing and download of measurement data and system information (logs, restart options, etc.).

<div align="right">(<a href="#readme-top">back to top</a>)</div>



## Software Structure

The DataBeam stack consists of multiple **core** and **extension** Docker containers forming a flexible **microservice architecture**.

Use-case specific configurations are built using Docker Compose and a .env configuration.

<div align="center">
  <img alt="Module concept of DataBeam" src="doc/stack_overview_bg.png">
</div>

### Core Apps

#### Controller
* module registration
* handle requests to start/stop sampling or capturing
* manage GUI messages

#### REST-API / Web-GUI
* offer commands to start/stop sampling or capturing
* configure modules
* query latest data
* list DAQ directories and files
* download files


### IO-Modules
* implement a specific device to collect data
* subscribe to other modules live-data and perform calculations
* use template to quickly set up new module
* provided callbacks offer complete stack functionality
* single function call hands data over to stack and provides DAQ and live data

Multiple IO-Modules and algorithms may be added to the docker-compose.yml file at will. All "extensions" register with the controller and are listed in the web-dashboard provided by the REST-API.

Since all modules are given a separate config and data directory, any type of data may be saved in addition to the defaults (JSON for config, meta-data and [MCAP](https://mcap.dev/) for data).

Measurement-start synchronization is provided by the stack: during a preparation phase the controller waits for all modules. After successful preparation, a "start" broadcast is issued simultaneously to all modules.


### File System Organization (runtime)
The stack is configured in the `.env` file to use `/opt/databeam` (default) as it's base directory.

Configuration files, DAQ- and metadata-files are structured like this:
```
/opt/databeam
 |- .env
 |- docker-compose.yml
 |- config
     |- DEPLOY_VERSION (Docker tag)
         |- MODULE_TYPE-MODULE_NAME
             |- config.json
             |- data_config.json
         |- other-module
             |- ...
 |- data
     |- DEPLOY_VERSION
         |- YYYY-MM-DD_hh-mm-ss.sss_RUN-ID_RUN-TAG
             |- meta.json
             |- MODULE_NAME
                 |- module_meta.json
                 |- MODULE_NAME.mcap
             |- other-module
                 |- ...
         |- 2024-01-31_14-56-46.207_02_demo-drive
             |- ...
```
#### Config files
* `config.json`: configuration of individual module
* `data_config.json`: capturing and live data configuration

#### Data files
* `meta.json`: general metadata like start-/stop-time, run-id/-tag, hostname, etc.
* `module_meta.json`: module specific metadata
* `MODULE_NAME.mcap`: MCAP file storing DAQ data

<div align="right">(<a href="#readme-top">back to top</a>)</div>



## Development

Please consult the **<a href="DEVELOPMENT.md">development document</a>** for more details on how to create custom extensions and run the stack as a developer.

<div align="right">(<a href="#readme-top">back to top</a>)</div>



## Deployment

The makefile offers a lot of documentation for options. Just run `make` to get help.

For more details, please consult the **<a href="DEPLOYMENT.md">deployment document</a>**.

<div align="right">(<a href="#readme-top">back to top</a>)</div>



## DAQ Data Post-Processing

### MCAP tooling
* official homepage: https://mcap.dev/
* PlotJuggler: https://plotjuggler.io/
  - very good for quick plotting of numeric data
* Foxglove Studio: https://foxglove.dev/product
  - supports plotting of numeric data, camera images and geo-locations

### Conversion Scripts

`tools/mcap_reader.py` allows easy parsing of MCAP files to numpy-arrays.

`tools/mcap_convert.py` converts MCAP files to CSV files.

**TODO: further documentation and examples**

<div align="right">(<a href="#readme-top">back to top</a>)</div>



<!-- LICENSE -->
## License
Distributed under the MIT license. See `LICENSE.txt` file for more information.

<div align="right">(<a href="#readme-top">back to top</a>)</div>



<!-- CONTACT -->
## Contact
Virtual Vehicle Research GmbH: [https://www.v2c2.at](https://www.v2c2.at)

Project Lead: Peter Sammer - peter.sammer@v2c2.at

We gladly offer support, custom installations and extensions for test-benches, experiments and more.

<div align="right">(<a href="#readme-top">back to top</a>)</div>



<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

Virtual Vehicle Research GmbH has received funding within COMET Competence Centers for Excellent Technologies from the Austrian Federal Ministry for Climate Action, the Austrian Federal Ministry for Labour and Economy, the Province of Styria (Dept. 12) and the Styrian Business Promotion Agency (SFG). The Austrian Research Promotion Agency (FFG) has been authorised for the programme management.

Thanks to the following open-source projects:
* [ZeroMQ](https://zeromq.org/) is used for internal communication.
* [Flask](https://github.com/pallets/flask) helps users interact with DataBeam.
* [uPlot](https://github.com/leeoniya/uPlot) produces nice plots for live-data.
* [Leaflet](https://github.com/Leaflet/Leaflet) renders beautiful maps.
* and many, many other useful libraries and frameworks ...

<div align="right">(<a href="#readme-top">back to top</a>)</div>
