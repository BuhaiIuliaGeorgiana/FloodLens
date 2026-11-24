
import { supabase } from "../config/supabase";
import { useState, useEffect, useMemo } from "react";
import { Link, useParams } from "react-router";
import { getEventBySlug } from "../services/eventService";
import EventMap from "../components/EventMap";

function PublicEventPage(){
    const {slug} = useParams();
    const [event,setEvent] = useState(null);
    const [loading,setLoading] = useState(true);
    const [error,setError] = useState("");

    useEffect(() => {
        let ignore = false;

        async function loadEvent(){
            setLoading(true);
            setError("");

            try{
                const data = await getEventBySlug(slug);

                if(!ignore){
                    setEvent(data);
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

        loadEvent();

        return () => {
            ignore = true;
        };

    }, [slug]);

    // Pick the map layers once per event, so the map
    // does not download the files again on every render
    const { roadsLayer, emsLayers, imageLayers } = useMemo(() => {
    const available = (event?.event_layers ?? []).filter(
        (layer) => layer.status === "available" && layer.storage_path
    );

    return {
        roadsLayer:
            available.find((layer) => layer.layer_type === "roads") ?? null,

        emsLayers: available
            .filter((layer) => layer.layer_type === "ems_reference")
            .sort((a, b) => new Date(a.acquired_at) - new Date(b.acquired_at)),

        imageLayers: available.filter(
            (layer) => layer.kind === "image" && layer.bounds
        ),
    };
}, [event]);

    if(loading){
        return <p>Loading event...</p>;
    }

    if(error){
        return <p role="alert">Error: {error}</p>;
    }

    if(!event){
        return(
            <main>
                <p>Event not found.</p>
                <Link to="/">Back to events</Link>
            </main>
        );
    }

    // Get all layers belonging to the event
    const layers = event.event_layers ?? [];

    return(
        <main>
            <p><Link to="/">← Back to events</Link></p>

            <h1>{event.title}</h1>

            {event.locality && <p>Locality: {event.locality}</p>}
            {event.county && <p>County: {event.county}</p>}
            <p>Started: {formatDay(event.started_at)}</p>
            <p>
                {event.ended_at
                    ? `Ended: ${formatDay(event.ended_at)}`
                    : "Ongoing event"}
            </p>
            {event.visibility === "private" && <p>Private event</p>}

            {/* Display the event zone, real roads and EMS flood zones */}
            {(event.aoi_geojson || roadsLayer || emsLayers.length > 0 || imageLayers.length > 0) && (
                <EventMap
                    aoi={event.aoi_geojson}
                    roadsLayer={roadsLayer}
                    emsLayers={emsLayers}
                    imageLayers={imageLayers}
                />
            )}

            <h2>Available data sources</h2>

            {layers.length === 0 && (
                <p>No results yet for this event.</p>
            )}

            <ul>
                {layers.map((layer) => {

                    // Get the URL of an available file
                    let fileUrl = null;

                    if(layer.status === "available" && layer.storage_path){
                        const result = supabase.storage
                            .from("public-demo-layers")
                            .getPublicUrl(layer.storage_path);

                        fileUrl = result.data.publicUrl;
                    }

                    return(
                        <li key={layer.id}>
                            <h3>{layer.source}</h3>

                            <p>Period: {layer.period ?? "Static"}</p>
                            <p>Type: {layer.layer_type}</p>
                            <p>Status: {layer.status}</p>

                            {/* Link to the real file */}
                            {fileUrl && (
                                <a
                                    href={fileUrl}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                >
                                    View file
                                </a>
                            )}

                            {/* Explanation for unavailable layers */}
                            {layer.status === "unavailable" && (
                                <p>Reason: {layer.reason}</p>
                            )}
                        </li>
                    );
                })}
            </ul>
        </main>
    );
}

// Show a date as a Romanian calendar day
function formatDay(value){
    return new Date(value).toLocaleDateString("ro-RO", {
        timeZone: "Europe/Bucharest"
    });
}

export default PublicEventPage;
