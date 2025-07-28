import platform
import subprocess
import requests
from pathlib import Path

if __name__ == "__main__":
    API_URL = "https://api.github.com/repos/foxglove/mcap/releases"
    HEADERS = {"Accept": "application/vnd.github+json"}
    releases = requests.get(API_URL, headers=HEADERS).json()

    # Find latest `mcap-cli` release
    cli_release = next((r for r in releases if r["tag_name"].startswith("releases/mcap-cli/")), None)
    if not cli_release:
        raise RuntimeError("MCAP CLI release not found.")

    version = cli_release["tag_name"].split("/")[-1]
    print(f'Latest MCAP CLI release: {version}')

    # check if binary already exists and is up to date
    if platform.system() == "Windows":
        asset_bin_name = "mcap-windows-amd64.exe"
        output_bin_name = "mcap_cli.exe"
    elif platform.system() == "Linux":
        asset_bin_name = "mcap-linux-amd64"
        output_bin_name = "mcap_cli"
    else:
        raise RuntimeError("Unsupported platform.")

    if Path(output_bin_name).exists():
        current_version = subprocess.check_output([Path(output_bin_name).absolute(), "version"]).decode().strip()
        print(f'MCAP CLI version: {current_version}')
        if current_version == version:
            print("Binary already up to date. Exiting.")
            exit(0)

    # find correct asset
    asset = next((a for a in cli_release["assets"] if asset_bin_name in a["name"]), None)
    if not asset:
        raise RuntimeError("Binary not found in assets.")

    # download the binary
    download_url = asset["browser_download_url"]
    print(f"Downloading {download_url}")

    r = requests.get(download_url)
    with open(output_bin_name, "wb") as f:
        f.write(r.content)

    if platform.system() == "Linux":
        subprocess.run(["chmod", "+x", Path(output_bin_name).absolute()])

    print("Download complete.")
