import zmq

sock_sub = zmq.Context().socket(zmq.SUB)
sock_sub.setsockopt(zmq.LINGER, 0)
sock_sub.setsockopt(zmq.RCVHWM, 100000)
sock_sub.setsockopt(zmq.SNDHWM, 100000)
sock_sub.connect(f"tcp://localhost:5558")
sock_sub.subscribe("")

print('ready')

try:
    while True:
        try:
            topic, msg = sock_sub.recv_multipart()
            print(f'{topic.decode()}:{msg.decode()}')
        except Exception as e:
            print(f'EX ({topic} | {msg}): {type(e).__name__}: {e}')
except KeyboardInterrupt:
    pass

sock_sub.close()
exit(0)
