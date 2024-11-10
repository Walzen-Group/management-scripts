import json
import sys
import requests
import subprocess
import argparse
from loguru import logger
from pathlib import Path
from influxdb_client import InfluxDBClient, Point, WriteOptions


with open("config.json") as json_file:
    config = json.load(json_file)


def ascii_art():
    return """
      .----.
     /      \\
    |  0  0  |
    |   __   | <--- Anime Character
     \      /
      '----'
       /||\\
      //||\\\\
     // || \\\\
    //  ||  \\\\
   //   ||   \\\\
  //    ||    \\\\
 //     ||     \\\\
        ||
        ||
        ||
        ||
    .-\"\"\"\"\"\"-.
   /          \\
  |            |
  |(- -) (- -) | <--- Hard Disk
  |   o     o  |
  |    \___/   |
   \          /
    '-......-'
"""

def get_all_sessions():
    auth = f"MediaBrowser Client='Jelsi', Device='Firefox', DeviceId='TW96aWxsYS81LjAgKFgxMTsgTGludXggeDg2XzY0OyBydjo5NC4wKSBHZWNrby8yMDEwMDEwMSBGaXJlZm94Lzk0LjB8MTYzODA1MzA2OTY4Mw11', Version='10.7.6', Token={config.get('api_token')}"
    headers = {"Authorization": auth}

    response = requests.get(
        "https://jellyfin.walzen.org/Sessions",
        headers=headers,
        params={"activeWithinSeconds": config.get("active_within_seconds")},
    )
    return response.json()


def get_media_source_ids(all_sessions):
    """
    Returns a list of all media source ids that are currently being played

    :param all_sessions: list of session dicts
    :returns list of media source ids
    """
    media_source_ids = set()
    for session in all_sessions:
        if "PlayState" in session and "PlayMethod" in session["PlayState"]:
            media_source_ids.add(session["PlayState"]["MediaSourceId"])
    return list(media_source_ids)


def calculate_filesize_of_dir(path):
    result = subprocess.run(
        ['du', '-sh', path], stdout=subprocess.PIPE, text=True)
    result = result.stdout.split()[0]
    return result



def find_logs_with_id(media_id):
    """
    Returns all ts chunk prefixes belonging to a certain media id
    """
    ts_ids = set()
    for file in Path(config.get("jf_log_dir")).rglob("*.log"):
        if not media_id in file.name:
            continue

        logger.debug(f"found log file {file}")
        with open(file) as f:
            lines = f.readlines()
            filtered = list(
                filter(lambda x: ".m3u8" in x and x.startswith("Output"), lines))
            if filtered:
                try:
                    elem = filtered[0]
                    ts_id = elem[elem.rfind("/") + 1:elem.rfind(".")]
                    ts_ids.add(ts_id)
                except ValueError:
                    logger.error(
                        f"Could not find ts_id in {file} and line {filtered}")
    return ts_ids


def find_ts_ids_in_use():
    """
    Returns a list of all ts identifier prefixes that should not be deleted
    Looks like this: ["id_a", "id_b", "id_c"]

    :returns list of ts ids
    """
    sessions = get_all_sessions()
    media_source_ids = get_media_source_ids(sessions)
    return [value for media_id in media_source_ids for value in find_logs_with_id(media_id)]


def find_ts_ids_to_delete(ts_ids_in_use):
    ts_files = list(Path(config.get("jf_transcode_ramdisk")).rglob("*.ts"))
    ts_files_to_delete = [file for file in ts_files if not any(file.name.startswith(ts_id) for ts_id in ts_ids_in_use)]
    size = 0
    for file in ts_files_to_delete:
        size += file.stat().st_size
    return ts_files_to_delete, size


def write_to_influx(cleanable_size, cleanable_count):
    with InfluxDBClient(url=f"http://{config.get('influxdb_host')}:{config.get('influxdb_port')}", token=config.get("influxdb_token"), org=config.get("influxdb_org")) as _client:
        with _client.write_api(write_options=WriteOptions(batch_size=500,
                                                        flush_interval=2_000,
                                                        jitter_interval=2_000,
                                                        retry_interval=5_000,
                                                        max_retries=5,
                                                        max_retry_delay=10_000,
                                                        max_close_wait=20_000,
                                                        exponential_base=2)) as _write_client:
            _write_client.write(config.get("influxdb_bucket"), config.get("influxdb_org"), f"jellyfin cleanable_size={cleanable_size},cleanable_count={cleanable_count}")



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", action="store_true")

    log_level = "INFO"
    logger.level("INFO", color="<cyan>")
    logger.level("DEBUG", color="<yellow>")

    if parser.parse_args().debug:
        log_level = "DEBUG"

    logger.remove()
    logger.add(sys.stderr, level=log_level, format="<bold>{time:YYYY-MM-DD HH:mm:ss.SS}</> | <bold><level>{level: <6}</level></bold> | {message}")
    logger.info("UwU I am the jellyfin cleanup maid *~*")
    logger.info(ascii_art())
    ts_ids_in_use = find_ts_ids_in_use()
    logger.info(f"potentially active ts ids in use: {ts_ids_in_use}")
    ids_to_delete, size_to_delete = find_ts_ids_to_delete(ts_ids_in_use)

    if log_level == "DEBUG":
        logger.info("ts files to delete:")
        for file in find_ts_ids_to_delete(ts_ids_in_use)[0]:
            logger.debug(f"cleanable ts file: {file}")
    logger.info(f"cleanable ts file count: {len(ids_to_delete)}")
    logger.info(f"cleanable ts file size: {round(size_to_delete / 1024 / 1024)}M")
    size = calculate_filesize_of_dir(config.get("jf_transcode_ramdisk"))
    logger.info(f"current ramdisk size: {size}")

    if len(ids_to_delete) > 0 and not log_level == "DEBUG":
        write_to_influx(size_to_delete, len(ids_to_delete))

        for file in ids_to_delete:
            file.unlink()
        size = calculate_filesize_of_dir(config.get("jf_transcode_ramdisk"))
        logger.info(f"ramdisk size after cleanup: {size}")
