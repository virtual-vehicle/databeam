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

### docker-compose.yml

Existing modules already have entries in the `docker-compose.yml` file and examples in the `deploy/compose-files` directory.

Some hardware devices might require setting `privileged: true` or mapping of host resources.

This is also the place to edit environment variables on a per-module basis.

### Environment Variables for IO-Modules
| Variable                                     | Description |
| :------------------------------------------- | ------ |
| **LOGLEVEL** | Available log-levels: DEBUG, INFO, WARNING, ERROR
| **CONFIG_DIR** | Directory used to store configuration files. Will be suffixed with *DEPLOY_VERSION*
| **DATA_DIR** | Directory used to store data files. Will be suffixed with *DEPLOY_VERSION*
| **DEPLOY_VERSION** | Tag used for docker images.
| **DB_ID** | DataBeam domain name for communication. Must be unique in network.
| **DB_ROUTER** | DataBeam router hostname to find other nodes.

<div align="right">(<a href="README.md">back to README</a>)</div>
