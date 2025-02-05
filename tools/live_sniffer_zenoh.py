import os
import json
from functools import partial
import signal

import zenoh

if __name__ == '__main__':
    db_id = os.getenv('DB_ID', '')
    if len(db_id) == 0:
        print('ERROR: please specify the databeam id')
        exit(1)

    signal.signal(signal.SIGINT, lambda signum, frame: print(f'signal {signum} called'))
    signal.signal(signal.SIGTERM, lambda signum, frame: print(f'signal {signum} called'))

    zenoh.try_init_log_from_env()
    z_config = zenoh.Config()
    # TODO DEBUG: set client mode (instead of 'peer') to communicate brokered over router
    z_config.insert_json5('mode', json.dumps('client'))
    # # disable multicast-scouting and rely on router to connect peers
    z_config.insert_json5('scouting/multicast/enabled', json.dumps(False))
    # # router will gossip peer addresses to newly connected peers to allow mesh communication
    z_config.insert_json5('scouting/gossip/enabled', json.dumps(True))
    # z_config.insert_json5('transport/link/tx/queue/backoff', json.dumps(100))
    # # add endpoint to connect to router
    z_config.insert_json5('connect/endpoints', json.dumps([f"tcp/localhost:7447"]))
    zsession = zenoh.open(z_config)

    listen_key_all = f'{db_id}/m/*/liveall'
    listen_key_dec = f'{db_id}/m/*/livedec'

    def cb(tag: str, sample: zenoh.Sample):
        print(tag)
        # live_json = sample.payload.decode()
        # print(tag + ': ' + live_json)

    subs = [
        zsession.declare_subscriber(listen_key_all, partial(cb, 'all'), reliability=zenoh.Reliability.RELIABLE),
        zsession.declare_subscriber(listen_key_dec, partial(cb, 'dec'), reliability=zenoh.Reliability.RELIABLE)
    ]

    signal.pause()

    print("unsubscribing")
    for sub in subs:
        sub.undeclare()
    subs.clear()
    print("closing session")
    zsession.close()
    print("done")
