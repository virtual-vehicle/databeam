import logging
import shutil
import subprocess
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
import json
import re
from typing import Union

backup_dir_name = 'bak_recovery'


def check_mcap_binary(mcap_cli_path: str = '/usr/local/bin/mcap'):
    # check if executable exists
    # noinspection LongLine
    if shutil.which(mcap_cli_path) is None:
        raise RuntimeError(f"MCAP cli not found in {mcap_cli_path}.\n"
                           f"    download from https://github.com/foxglove/mcap/releases?q=mcap-cli\n"
                           f"    and install to {mcap_cli_path}")
        # for devs, install with: sudo curl -L "$(curl -s https://api.github.com/repos/foxglove/mcap/releases | jq -r '[.[] | select(.tag_name | startswith("releases/mcap-cli/"))][0].assets[] | select(.name == "'mcap-linux-amd64'") | .browser_download_url')" -o /usr/local/bin/mcap && sudo chmod +x /usr/local/bin/mcap


def get_mcap_end_timestamp(mcap_file: Union[str, Path], mcap_cli_path: str = '/usr/local/bin/mcap'):
    logger = logging.getLogger('mcap_recover')
    mcap_file = Path(mcap_file)
    check_mcap_binary(mcap_cli_path)
    try:
        result = subprocess.run([mcap_cli_path, "info", mcap_file.absolute()],
                                capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return None
        end_match = re.search(r"end:\s+.*\(([\d.]+)\)", result.stdout)
        if not end_match:
            logger.warning(f'end timestamp parsing failed for mcap file: {mcap_file.name}')
            return None
        end_ts = float(end_match.group(1))
        return end_ts
    except Exception as e:
        logger.error(f'get_mcap_infos failed ({type(e).__name__}): {e}\n{traceback.format_exc()}')
        return None


def fix_unfinished_measurements_meta(_data_dir: Union[str, Path], mcap_cli_path: str = '/usr/local/bin/mcap'):
    _data_dir = Path(_data_dir)
    logger = logging.getLogger('mcap_recover')
    try:
        # find unfinished measurements
        for measurement_dir in _data_dir.iterdir():
            if measurement_dir.is_dir() and (measurement_dir / "meta.json").is_file():
                try:
                    with (measurement_dir / "meta.json").open('r') as f:
                        meta = json.load(f)
                except Exception as e:
                    logger.error(f'failed to read meta.json in {measurement_dir} ({type(e).__name__}): {e}')
                    continue

                if len(meta['stop_time_utc']):
                    continue  # everything is fine - we have a stop time

                logger.info(f'found unfinished measurement: {measurement_dir}')

                try:
                    # find last timestamp in mcap files of measurement
                    end_ts_list = [get_mcap_end_timestamp(mcap_file, mcap_cli_path)
                                   for mcap_file in measurement_dir.glob('**/*.mcap')]
                    if not any(end_ts_list):
                        raise ValueError('no mcap timestamps available')
                    latest_ts = max(t for t in end_ts_list if t is not None)

                    # calculate duration of measurement
                    duration = str(datetime.fromtimestamp(latest_ts, tz=timezone.utc) -
                                   datetime.fromisoformat(meta['start_time_utc']))

                    stop_time = datetime.fromtimestamp(latest_ts, tz=timezone.utc).isoformat(timespec='microseconds')
                    meta['stop_time_utc'] = stop_time
                    meta['duration'] = duration

                    # update meta-data (stop_time_utc, duration)
                    with (measurement_dir / "meta.json").open('w') as f:
                        json.dump(meta, f, indent=2, ensure_ascii=False)

                    logger.info(f'fixed unfinished measurement: {measurement_dir}')
                except RuntimeError as e:
                    logger.error(f'fix_unfinished_measurements {type(e).__name__}: {e}')
                except Exception as e:
                    logger.error(f'fix_unfinished_measurements ({measurement_dir}) failed ({type(e).__name__}): {e}\n'
                                 f'{traceback.format_exc()}')

    except Exception as e:
        logger.error(f'fix_unfinished_measurements failed ({type(e).__name__}): {e}\n{traceback.format_exc()}')


def recover_unfinalized_mcaps(_data_dir: Union[str, Path], mcap_cli_path: str = '/usr/local/bin/mcap'):
    _data_dir = Path(_data_dir)
    logger = logging.getLogger('mcap_recover')
    try:
        # find unfinalized mcap files
        for mcap_file in _data_dir.glob('**/*.mcap'):
            # check if mcap file contains in name: "*.part0123456789.mcap" (regex)
            # AND make sure it's not a backup of a previously recovered file
            if re.search(r'.*\.part[0-9]+\.mcap', mcap_file.name) and mcap_file.parent.name != backup_dir_name:
                logger.info(f'found unfinished mcap file: {mcap_file}')
                # check if there is a mcap file, named like mcap_file.name but without ".part0123456789" (regex)
                correct_file_name = mcap_file.parent / Path(re.sub(r'\.part[0-9]+\.mcap', '.mcap', mcap_file.name))
                if correct_file_name.is_file():
                    logger.warning(f'recovered file already exists: {correct_file_name.name}')
                    continue

                if mcap_file.stat().st_size == 0:
                    # if file is empty, still move to backup-dir (avoid repeated recovery attempts)
                    logger.warning(f'mcap file is empty: {mcap_file.name}')
                else:
                    # run mcap recover
                    check_mcap_binary(mcap_cli_path)
                    time_start = time.time()
                    cmd = [mcap_cli_path, "--strict-message-order", "recover", mcap_file.absolute(),
                           "-o", correct_file_name.absolute()]
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    for line in process.stdout:
                        logger.info(f'MCAP-CLI>> {line.decode("utf-8").strip()}')
                    process.stdout.close()
                    process.wait()
                    if process.returncode != 0:
                        logger.error(f'mcap recover failed after {time.time() - time_start:.2f} seconds')
                        if correct_file_name.is_file():
                            correct_file_name.unlink()
                        continue
                    logger.info(f'mcap recover took {time.time() - time_start:.2f} seconds. '
                                f'corrected file name: {correct_file_name.name}')

                # make sure backup dir exists
                if not (mcap_file.parent / backup_dir_name).is_dir():
                    (mcap_file.parent / backup_dir_name).mkdir(parents=True)
                # move mcap file to backup-dir
                mcap_file.rename(mcap_file.parent / backup_dir_name / mcap_file.name)

    except RuntimeError as e:
        logger.error(f'fix_unfinilazied_mcaps {type(e).__name__}: {e}')
    except Exception as e:
        logger.error(f'fix_unfinilazied_mcaps failed ({type(e).__name__}): {e}\n{traceback.format_exc()}')


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(levelname)-7s | %(message)s', level=logging.DEBUG)

    fix_unfinished_measurements_meta(Path('/opt/databeam/data/latest'))
    recover_unfinalized_mcaps(Path('/opt/databeam/data/latest'))
