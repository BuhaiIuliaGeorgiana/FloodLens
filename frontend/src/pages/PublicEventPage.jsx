
import { supabase } from "../config/supabase";
import { useState, useEffect, useMemo } from "react";
import { Link, useParams } from "react-router";
import { getEventBySlug } from "../services/eventService";
import EventMap from "../components/EventMap";
import Icon from "../components/Icon";

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
        return <p className="loading">Se încarcă evenimentul…</p>;
    }

    if(error){
        return <p role="alert">Eroare: {error}</p>;
    }

    if(!event){
        return(
            <div className="empty">
                <strong className="block text-deep-teal">Evenimentul nu a fost găsit</strong>
                <p>Este posibil să fie privat sau să nu mai existe.</p>
                <Link to="/" className="btn btn-secondary mt-4">Înapoi</Link>
            </div>
        );
    }

    // Get all layers belonging to the event
    const layers = event.event_layers ?? [];
    const place = [event.locality, event.county].filter(Boolean).join(", ");

    return(
        <>
            <Link to="/" className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted no-underline hover:text-deep-teal"><Icon name="arrowLeft" className="size-4"/>Înapoi</Link>

            <div className="mb-7">
                <div>
                    <div className="eyebrow">Eveniment de inundație</div>
                    <h1 className="text-[1.75rem]">{event.title}</h1>
                    <div className="mt-2.5 flex flex-wrap gap-2">
                        <span className="badge badge-muted"><Icon name="calendar" className="size-3"/>
                            {formatDay(event.started_at)}{event.ended_at && ` – ${formatDay(event.ended_at)}`}</span>
                        {place && <span className="badge badge-muted"><Icon name="pin" className="size-3"/>{place}</span>}
                        {!event.ended_at && <span className="badge badge-warning">În desfășurare</span>}
                        {event.visibility === "private" && <span className="badge badge-muted"><Icon name="lock" className="size-3"/>Privat</span>}
                    </div>
                </div>
            </div>

            <div className="grid gap-5">
                {/* Display the event zone, real roads and EMS flood zones */}
                {(event.aoi_geojson || roadsLayer || emsLayers.length > 0 || imageLayers.length > 0) && (
                    <EventMap
                        aoi={event.aoi_geojson}
                        roadsLayer={roadsLayer}
                        emsLayers={emsLayers}
                        imageLayers={imageLayers}
                    />
                )}

                <section className="card">
                    <div className="card-header"><h2 className="card-title">Surse de date disponibile</h2>
                        <span className="badge badge-muted">{layers.length}</span></div>

                    {layers.length === 0 && (
                        <div className="empty">Încă nu există rezultate pentru acest eveniment.</div>
                    )}

                    <ul className="grid gap-3 grid-cols-[repeat(auto-fill,minmax(min(240px,100%),1fr))]">
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
                                <li key={layer.id} className="grid content-start gap-1.5 rounded-lg border border-line p-4 text-sm [&_p]:text-muted">
                                    <div className="flex items-center justify-between gap-2">
                                        <h3 className="text-[0.95rem]">{layer.source}</h3>
                                        <span className={`badge ${layer.status === "available" ? "badge-success" : layer.status === "unavailable" ? "badge-danger" : "badge-muted"}`}>
                                            {STATUS_LABELS[layer.status] ?? layer.status}
                                        </span>
                                    </div>

                                    <p>Perioadă: {layer.period ?? "Static"}</p>
                                    <p>Tip: {layer.layer_type}</p>

                                    {/* Explanation for unavailable layers */}
                                    {layer.status === "unavailable" && (
                                        <p>Motiv: {layer.reason}</p>
                                    )}

                                    {/* Link to the real file */}
                                    {fileUrl && (
                                        <a href={fileUrl} target="_blank" rel="noopener noreferrer" className="text-sm">
                                            Deschide fișierul ↗
                                        </a>
                                    )}
                                </li>
                            );
                        })}
                    </ul>
                </section>
            </div>
        </>
    );
}

const STATUS_LABELS = {available: "Disponibil", unavailable: "Indisponibil", pending: "În așteptare"};

// Show a date as a Romanian calendar day
function formatDay(value){
    return new Date(value).toLocaleDateString("ro-RO", {
        timeZone: "Europe/Bucharest"
    });
}

export default PublicEventPage;
