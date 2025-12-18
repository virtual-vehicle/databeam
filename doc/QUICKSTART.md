## Quickstart

Please read the [Development](DEVELOPMENT.md) and [Deployment](DEPLOYMENT.md) documents for more details.

One can quickly start the stack with:

**Requires Ubuntu 24.04 or newer and Docker being installed** (done by `make develop` - see [Development](DEVELOPMENT.md))

```
sudo apt-get install git git-lfs make
git lfs install

git clone https://github.com/virtual-vehicle/databeam.git
cd databeam

make develop
(reboot)

BUILD_LOCAL=1 make update
BUILD_LOCAL=1 make core-apps module-ping
```

Edit `docker-compose.yml`:
```
# uncomment the line:
  - deploy/compose-files/docker-compose.ping.yml
```

Run:
```
make run
(quit with CTRL-C)
```

Go to http://localhost:5000 and login with `databeam` / `default`.

<div align="right">(<a href="../README.md">back to README</a>)</div>
