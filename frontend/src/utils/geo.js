const EARTH_RADIUS_M = 6378137;

// Approximate area of a GeoJSON Polygon (lon/lat) in km².
// Spherical formula, good enough for validating the drawn zone.
export function polygonAreaKm2(polygon){
    const ring = polygon.coordinates[0];
    let total = 0;

    for(let i = 0; i < ring.length - 1; i++){
        const [lon1, lat1] = ring[i];
        const [lon2, lat2] = ring[i + 1];

        total += toRad(lon2 - lon1)
            * (2 + Math.sin(toRad(lat1)) + Math.sin(toRad(lat2)));
    }

    return Math.abs(total * EARTH_RADIUS_M * EARTH_RADIUS_M / 2) / 1e6;
}

// Leaflet bounds [[south, west], [north, east]] for a GeoJSON Polygon
export function polygonLeafletBounds(polygon){
    const ring = polygon?.coordinates?.[0];

    if(!ring || ring.length === 0){
        return null;
    }

    const lons = ring.map(([lon]) => lon);
    const lats = ring.map(([, lat]) => lat);

    return [
        [Math.min(...lats), Math.min(...lons)],
        [Math.max(...lats), Math.max(...lons)]
    ];
}

function toRad(degrees){
    return degrees * Math.PI / 180;
}
