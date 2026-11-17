
import { useState, useEffect } from "react";
import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import { supabase } from "../config/supabase";
import "leaflet/dist/leaflet.css";

function RoadsPreview({storagePath}){
    const [roads,setRoads] = useState(null);
    const [loading,setLoading] = useState(true);
    const [error,setError] = useState("");

    useEffect(() => {
        let ignore = false;

        async function loadRoads(){
            setLoading(true);
            setError("");
            setRoads(null);

            try{
                // Get the URL from Supabase Storage
                const result = supabase.storage
                    .from("public-demo-layers")
                    .getPublicUrl(storagePath);

                // Download the actual GeoJSON
                const response = await fetch(result.data.publicUrl);

                if(!response.ok){
                    throw new Error("Could not load roads GeoJSON");
                }

                // Convert JSON text into a JavaScript object
                const data = await response.json();

                if(data.type !== "FeatureCollection"){
                    throw new Error("Invalid GeoJSON file");
                }

                if(!ignore){
                    setRoads(data);
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

        loadRoads();

        return () => {
            ignore = true;
        };

    }, [storagePath]);

    if(loading){
        return <p>Loading roads...</p>;
    }

    if(error){
        return <p role="alert">{error}</p>;
    }

    return(
        <section style={{maxWidth: "750px", margin: "20px auto"}}>
            <h2>Roads preview</h2>

            <p>Real road segments: {roads.features.length}</p>

            <MapContainer
                bounds={[[45.58,27.74],[45.68,27.86]]}
                scrollWheelZoom={false}
                style={{height: "350px", width: "100%"}}
            >
                <TileLayer
                    attribution='&copy; OpenStreetMap contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />

                <GeoJSON
                    data={roads}
                    style={{
                        color: "#0077cc",
                        weight: 2
                    }}
                />
            </MapContainer>

            <p>
                Blue lines represent mapped roads,
                not confirmed flood damage.
            </p>
        </section>
    );
}

export default RoadsPreview;
