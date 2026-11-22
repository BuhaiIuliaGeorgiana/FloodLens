import { useState, useEffect } from "react";
import {
    MapContainer,
    TileLayer,
    GeoJSON,
    LayersControl,
    ImageOverlay,
} from "react-leaflet";

import { supabase } from "../config/supabase";
import { polygonLeafletBounds } from "../utils/geo";
import "leaflet/dist/leaflet.css";

// Used only when an event has no zone saved
const DEFAULT_BOUNDS = [[43.6, 20.2], [48.3, 29.7]];

// One color per EMS date, from the earliest to the latest
const EMS_COLORS = ["#f4a261", "#d62828", "#6a0dad", "#2a9d8f"];

// Download a GeoJSON file from Supabase Storage
async function loadGeoJson(storagePath){
    const result = supabase.storage
        .from("public-demo-layers")
        .getPublicUrl(storagePath);

    const response = await fetch(result.data.publicUrl);

    if(!response.ok){
        throw new Error(`Could not load ${storagePath}`);
    }

    const data = await response.json();

    if(data.type !== "FeatureCollection"){
        throw new Error(`Invalid GeoJSON file: ${storagePath}`);
    }

    return data;
}

function formatDate(value){
    if(!value){
        return "unknown date";
    }

    return new Date(value).toLocaleString("ro-RO", {
        timeZone: "UTC",
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit"
    }) + " UTC";
}

// Show the attributes of a flood polygon when it is clicked
function bindFloodPopup(feature, leafletLayer){
    const props = feature.properties ?? {};
    const lines = [];

    if(props.area_ha !== undefined){
        lines.push(`Flooded area: ${props.area_ha} ha`);
    }

    if(props.acq_utc){
        lines.push(`Image acquired: ${props.acq_utc} UTC`);
    }

    if(lines.length > 0){
        // Use textContent so attribute values are displayed as plain text.
        const popup = document.createElement("div");
        popup.style.whiteSpace = "pre-line";
        popup.textContent = lines.join("\n");

        leafletLayer.bindPopup(popup);
    }
}
function getImageLabel(layer) {
    const path = (layer.storage_path ?? "").toLowerCase();

    let band = "";

    if (path.endsWith("_vv.png")) band = "VV";
    else if (path.endsWith("_vh.png")) band = "VH";
    else if (path.endsWith("_mndwi.png")) band = "MNDWI";
    else if (path.endsWith("_ndwi.png")) band = "NDWI";

    return [
        layer.source,
        band,
        layer.period,
        formatDate(layer.acquired_at),
    ].filter(Boolean).join(" — ");
}
function EventMap({ aoi, roadsLayer, emsLayers, imageLayers = [] }){
    const [roads,setRoads] = useState(null);
    const [floods,setFloods] = useState([]);
    const [loading,setLoading] = useState(true);
    const [error,setError] = useState("");

    useEffect(() => {
        let ignore = false;

        async function loadLayers(){
            setLoading(true);
            setError("");
            setRoads(null);
            setFloods([]);

            try{
                // Download roads and all EMS files at the same time.
                // Satellite PNGs are loaded separately by ImageOverlay.
                const [roadsData, ...emsData] = await Promise.all([
                    roadsLayer
                        ? loadGeoJson(roadsLayer.storage_path)
                        : null,

                    ...emsLayers.map(
                        (layer) => loadGeoJson(layer.storage_path)
                    )
                ]);

                if(!ignore){
                    setRoads(roadsData);

                    setFloods(
                        emsLayers.map((layer, index) => ({
                            layer,
                            data: emsData[index]
                        }))
                    );
                }

            }catch(err){
                if(!ignore){
                    setError(err.message);
                }
            }finally{
                if(!ignore){
                    setLoading(false);
                }
            }
        }

        loadLayers();

        return () => {
            ignore = true;
        };

    }, [roadsLayer, emsLayers]);

    if(loading){
        return <p>Loading map layers...</p>;
    }

    if(error){
        return <p role="alert">{error}</p>;
    }

    return(
        <section style={{maxWidth: "750px", margin: "20px auto"}}>
            <h2>Event map</h2>

            {roads && (
                <p>Real road segments: {roads.features.length}</p>
            )}

            <MapContainer
                bounds={polygonLeafletBounds(aoi) ?? DEFAULT_BOUNDS}
                scrollWheelZoom={false}
                style={{height: "450px", width: "100%"}}
            >
                <TileLayer
                    attribution={
                        floods.length > 0
                            ? "&copy; OpenStreetMap contributors | Flood data &copy; Copernicus EMS"
                            : "&copy; OpenStreetMap contributors"
                    }
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />

                {/* Checkboxes to show or hide each layer */}
                <LayersControl position="topright" collapsed={false}>

                    {/* Zone selected when the event was created */}
                    {aoi && (
                        <LayersControl.Overlay name="Event zone" checked>
                            <GeoJSON
                                data={aoi}
                                style={{
                                    color: "#333",
                                    weight: 2,
                                    dashArray: "6 4",
                                    fill: false
                                }}
                            />
                        </LayersControl.Overlay>
                    )}

                    {/* Satellite image previews: Sentinel-1 and Sentinel-2 */}
                    {imageLayers.map((layer) => {
                        const { data } = supabase.storage
                            .from("public-demo-layers")
                            .getPublicUrl(layer.storage_path);

                        // Database order: longitude, latitude.
                        const [west, south, east, north] = layer.bounds;

                        // Leaflet order: latitude, longitude.
                        const imageBounds = [
                            [south, west],
                            [north, east]
                        ];

                        return(
                            <LayersControl.Overlay
                                key={layer.id}
                                name={getImageLabel(layer)}
                            >
                                <ImageOverlay
                                    url={data.publicUrl}
                                    bounds={imageBounds}
                                    opacity={0.8}
                                    zIndex={1}
                                    attribution="Copernicus Sentinel data"
                                />
                            </LayersControl.Overlay>
                        );
                    })}

                    {/* OpenStreetMap roads */}
                    {roads && (
                        <LayersControl.Overlay
                            name="Roads (OpenStreetMap)"
                            checked
                        >
                            <GeoJSON
                                data={roads}
                                style={{
                                    color: "#0077cc",
                                    weight: 2
                                }}
                            />
                        </LayersControl.Overlay>
                    )}

                    {/* One EMS overlay per date; latest shown initially */}
                    {floods.map(({layer, data}, index) => (
                        <LayersControl.Overlay
                            key={layer.id}
                            name={`Flooded area - ${formatDate(layer.acquired_at)}`}
                            checked={index === floods.length - 1}
                        >
                            <GeoJSON
                                data={data}
                                style={{
                                    color: EMS_COLORS[index % EMS_COLORS.length],
                                    weight: 1,
                                    fillOpacity: 0.4
                                }}
                                onEachFeature={bindFloodPopup}
                            />
                        </LayersControl.Overlay>
                    ))}

                </LayersControl>
            </MapContainer>

            {roads && (
                <p>
                    Blue lines represent mapped roads,
                    not confirmed flood damage.
                </p>
            )}

            {imageLayers.length > 0 && (
                <p>
                    Enable a satellite preview using the map controls.
                    Image colors depend on the displayed band or index
                    and do not, by themselves, confirm flooding.
                </p>
            )}

            {floods.length > 0 && (
                <p>
                    Colored polygons are flood zones mapped by Copernicus EMS.
                    The absence of a polygon outside the mapped coverage
                    does not mean there was no flooding.
                </p>
            )}
        </section>
    );
}

export default EventMap;