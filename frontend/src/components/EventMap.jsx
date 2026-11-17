import { useState, useEffect } from "react";
import { MapContainer, TileLayer, GeoJSON, LayersControl } from "react-leaflet";
import { supabase } from "../config/supabase";
import "leaflet/dist/leaflet.css";

// One color per EMS date, from the earliest to the latest
const EMS_COLORS = ["#f4a261", "#d62828", "#6a0dad", "#2a9d8f"];

// Download a GeoJSON file from Supabase Storage
async function loadGeoJson(storagePath){
    // Get the URL from Supabase Storage
    const result = supabase.storage
        .from("public-demo-layers")
        .getPublicUrl(storagePath);

    // Download the actual GeoJSON
    const response = await fetch(result.data.publicUrl);

    if(!response.ok){
        throw new Error(`Could not load ${storagePath}`);
    }

    // Convert JSON text into a JavaScript object
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

    if(props.area_ha !== undefined) lines.push(`Flooded area: ${props.area_ha} ha`);
    if(props.acq_utc) lines.push(`Image acquired: ${props.acq_utc} UTC`);

    if(lines.length > 0){
        leafletLayer.bindPopup(lines.join("<br>"));
    }
}

function EventMap({roadsLayer, emsLayers}){
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
                // Download roads and all EMS files at the same time
                const [roadsData, ...emsData] = await Promise.all([
                    roadsLayer ? loadGeoJson(roadsLayer.storage_path) : null,
                    ...emsLayers.map((layer) => loadGeoJson(layer.storage_path))
                ]);

                if(!ignore){
                    setRoads(roadsData);
                    setFloods(emsLayers.map((layer, index) => ({
                        layer,
                        data: emsData[index]
                    })));
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

            {roads && <p>Real road segments: {roads.features.length}</p>}

            <MapContainer
                bounds={[[45.58,27.74],[45.68,27.86]]}
                scrollWheelZoom={false}
                style={{height: "450px", width: "100%"}}
            >
                <TileLayer
                    attribution='&copy; OpenStreetMap contributors | Flood data &copy; Copernicus EMS (EMSR758)'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />

                {/* Checkboxes in the top right corner to show/hide each layer */}
                <LayersControl position="topright" collapsed={false}>
                    {roads && (
                        <LayersControl.Overlay name="Roads (OpenStreetMap)" checked>
                            <GeoJSON
                                data={roads}
                                style={{
                                    color: "#0077cc",
                                    weight: 2
                                }}
                            />
                        </LayersControl.Overlay>
                    )}

                    {/* One overlay per EMS date, only the latest is shown at first */}
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

            <p>
                Blue lines represent mapped roads,
                not confirmed flood damage.
            </p>

            {floods.length > 0 && (
                <p>
                    Colored areas are flood zones mapped by Copernicus EMS
                    from satellite images. EMS only mapped the Pechea area,
                    so no flood zone outside it does not mean no flooding.
                </p>
            )}
        </section>
    );
}

export default EventMap;
