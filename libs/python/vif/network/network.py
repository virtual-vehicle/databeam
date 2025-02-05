import urllib.parse
import socket


def resolve_uri(uri: str) -> str:
    """
    Resolved the hostname of the given uri
    uri has to be in form scheme://hostname
    :raises ValueError if the uri is not valid, i.e. contains no hostname or IP address
    :param uri: the uri to resolve
    :return: resolved uri
    """
    uri_parts = urllib.parse.urlsplit(uri)
    if uri_parts.hostname is None:
        raise ValueError(f'Bad uri {uri}')
    ip_addr = socket.gethostbyname(uri_parts.hostname)
    uri_resolved = f'{uri_parts.scheme}://{ip_addr}:{uri_parts.port}'

    return uri_resolved
