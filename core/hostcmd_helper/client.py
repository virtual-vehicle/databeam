import os.path
import socket

SockAddr = "/tmp/databeam_hostcmd.sock"


def main():
    if not os.path.exists(SockAddr):
        print("socket path does not exist")
        exit(1)

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(SockAddr)

        sock.send(b"dothedockerrestart")
    except Exception as e:
        print(f'EX: {e}')


if __name__ == "__main__":
    main()
