from pathlib import Path
import stat


def create_directory(directory: Path, permissions_all: bool = True):
    directory.mkdir(parents=True, exist_ok=True)
    if permissions_all:
        # set directory write access for all users
        directory.chmod(stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
