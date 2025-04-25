"""
Haversine formula to calculate the distance between coordinates on earth
"""

import numpy as np
import typing

T = typing.TypeVar('T', float, np.ndarray)

_radius_earth = 6371e3  # m


class ResultType(typing.NamedTuple):
    distance: T
    bearing_initial: T
    bearing_final: T


def haversine(lat1: T, lon1: T, lat2: T, lon2: T, alt1: T = 0, alt2: T = 0) -> ResultType:
    """
    Haversine formula
    Calculates distance on earth between two sets of coordinates
    Parameters are either single coordinates or numpy arrays of coordinates
    :param lat1: latitude coordinate 1, in degrees
    :param lon1: longitude coordinate 1, in degrees
    :param lat2: latitude coordinate 2, in degrees
    :param lon2: longitude coordinate 1, in degrees
    :param alt1: altitude 1, in meter
    :param alt2: altitude 2, in meter
    :return: distance between coordinates, in meter, bearing of entity 1, bearing of entity 2
    """

    phi1 = np.deg2rad(lat1)
    phi2 = np.deg2rad(lat2)

    cos_phi1 = np.cos(phi1)
    cos_phi2 = np.cos(phi2)
    sin_phi1 = np.sin(phi1)
    sin_phi2 = np.sin(phi2)

    d_phi = phi2 - phi1
    d_lambda = np.deg2rad(lon2 - lon1)

    a = np.square(np.sin(d_phi / 2)) + cos_phi1 * cos_phi2 * np.square(np.sin(d_lambda / 2))

    distance = _radius_earth * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    # take altitude differences into account
    distance = np.sqrt(np.square(distance) + np.square(alt2 - alt1))

    # heading
    x = cos_phi2 * np.sin(d_lambda)
    y = cos_phi1 * sin_phi2 - sin_phi1 * cos_phi2 * np.cos(d_lambda)

    # atan2 return +-180 -> normalize to 0...360
    bearing_initial = np.fmod(np.rad2deg(np.arctan2(x, y)) + 360, 360)

    # calculate final bearing
    d_lambda = np.deg2rad(lon1 - lon2)
    x = cos_phi1 * np.sin(d_lambda)
    y = cos_phi2 * sin_phi1 - sin_phi2 * cos_phi1 * np.cos(d_lambda)
    bearing_final = np.fmod(np.rad2deg(np.arctan2(x, y)) + 180, 360)

    return ResultType(distance, bearing_initial, bearing_final)
