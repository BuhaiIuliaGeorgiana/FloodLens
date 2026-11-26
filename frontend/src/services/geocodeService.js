import countyBounds from "../data/countyBounds.json";
import { splitLocality } from "../utils/places";

// Serviciul public de geocodare OpenStreetMap; limita: o cerere pe secunda
const NOMINATIM_URL = "https://nominatim.openstreetmap.org";

async function nominatim(path, params, signal){
    const query = new URLSearchParams({ format: "jsonv2", "accept-language": "ro", ...params });
    const response = await fetch(`${NOMINATIM_URL}/${path}?${query}`, { signal });

    if(!response.ok){
        throw new Error(`Geocoding error (${response.status}).`);
    }

    return response.json();
}

// Localitatile deja cautate, ca alegerea repetata sa nu mai astepte reteaua
const localityCache = new Map();

// Leaflet bounds [[south, west], [north, east]] pentru un judet sau o localitate, sau null.
// Judetele sunt salvate local (src/data/countyBounds.json), localitatile se cauta in Nominatim.
export async function locatePlace(county, locality, signal){
    if(!locality){
        return countyBounds[county] ?? null;
    }

    const key = `${county}|${locality}`;

    if(!localityCache.has(key)){
        const { name, commune } = splitLocality(locality);
        const [result] = await nominatim("search", {
            q: [name, commune, county, "România"].filter(Boolean).join(", "),
            countrycodes: "ro",
            limit: "1",
        }, signal);

        const [south, north, west, east] = result ? result.boundingbox.map(Number) : [];
        localityCache.set(key, result ? [[south, west], [north, east]] : null);
    }

    return localityCache.get(key);
}

// Adresa (judet, comuna, sat...) a unui punct de pe harta
export async function describePoint(lat, lon, signal){
    const result = await nominatim("reverse", { lat: String(lat), lon: String(lon), zoom: "14" }, signal);

    return result.address ?? {};
}
