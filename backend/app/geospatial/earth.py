import math


EARTH_RADIUS_M = 6371000.0


def haversine_m(lat1, lon1, lat2, lon2):
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    rlon1, rlon2 = math.radians(lon1), math.radians(lon2)
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def meters_to_deg_lat(m):
    return m / 111320.0


def meters_to_deg_lon(m, lat):
    return m / (111320.0 * max(0.01, math.cos(math.radians(lat))))


def line_length_m(coords):
    total = 0.0
    for i in range(1, len(coords)):
        total += haversine_m(coords[i - 1][1], coords[i - 1][0], coords[i][1], coords[i][0])
    return total


def midpoint(coords):
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    return sum(ys) / len(ys), sum(xs) / len(xs)