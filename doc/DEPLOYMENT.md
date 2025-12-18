## Deployment

The makefile offers a lot of documentation for options. Just run `make` to get help.

Before attempting to deploy, make sure you have configured the `.env`, `docker-compose.yml` files and built the required images using the `make` command.

### Prepare target computer

Check out the `setup_remote.sh` and `setup.sh` scripts in *deploy/scripts*.

Make sure to adjust values in `.env` file:
* `DEPLOY_TIMESERVER`: choose an NTP server for time synchronization
* `DOCKER_REGISTRY`: a registry to use for docker images
* `DOCKER_TAG_PREFIX`: docker registry path

Run with (e.g.):
```
./deploy/scripts/setup_remote.sh databeam targethost.local dockerrepouser 123dockerdeploykey123
```

This copies files and sets up Docker (plus configuration) and other requirements on the target computer.

The current configuration in `.env` and `docker-compose.yml` will be copied to the target machine. Make sure to adjust values there.

> **_NOTE:_** To allow for more complicated USB device setups, the deployment scripts increase the USB memory in the target systems Grub configuration to 1000 MB.


### docker-compose.yml

Existing modules already have entries in the `docker-compose.yml` file and examples in the `deploy/compose-files` directory.

Some hardware devices might require setting `privileged: true` or mapping of host resources.

This is also the place to edit environment variables on a per-module basis.

### Environment Variables for IO-Modules
| Variable     |              Description              |
| :----------- | ------------------------------------- |
| **LOGLEVEL** | Available log-levels: DEBUG, INFO, WARNING, ERROR |
| **CONFIG_DIR** | Directory used to store configuration files.<br>Will be suffixed with *DEPLOY_VERSION*. |
| **DATA_DIR** | Directory used to store data files.<br>Will be suffixed with *DEPLOY_VERSION*. |
| **DEPLOY_VERSION** | Tag used for docker images.
| **DB_ID** | DataBeam domain name for communication.<br>Must be unique in interconnected instances. |
| **DB_ROUTER** | DataBeam router hostname for communication.<br>Either `zmq_router` or `localhost` (if container runs in network mode `host`). |

### Environment Variables for Controller
| Variable     |              Description              |
| :----------- | ------------------------------------- |
| **.. all above ..** | Module parameters apply. |
| **HOST_NAME_FILE** | Internal path to host-OS hostname. |
| **DBID_LIST** | Optional: specify comma-separated list of tuples of DataBeam IDs and hostnames.<br>Format: `dbid1/192.168.1.10,dbid2/192.168.1.1`<br>Prefer IPs! Only use local mDNS hostnames if accessing containers run Avahi daemon and are configured to run in network mode `host`.|

<div align="right">(<a href="../README.md">back to README</a>)</div>
