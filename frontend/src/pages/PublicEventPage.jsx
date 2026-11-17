
import { useState, useEffect } from "react";
import { getPecheaEvent } from "../services/eventService";

function PublicEventPage(){
    const [event,setEvent] = useState(null);

    const [loading,setLoading] = useState(true);
    const [error,setError] = useState("");

    useEffect(() => {

        let ignore = false;

        async function loadEvent(){
            try {
                const data = await getPecheaEvent();

                if(!ignore){
                    setEvent(data);
                }

            } catch(err) {
                if(!ignore){
                    setError(err.message);
                }

            } finally {
                if(!ignore){
                    setLoading(false);
                }
            }
        }

        loadEvent();

        return () => {
            ignore = true;
        };

    }, []);

    if(loading){
        return (<p>Loading event...</p>);
    }

    if(error){
        return <p role="alert">Error: {error}</p>;
    }

    if(!event){
        return <p>Event not found.</p>;
    }

    return(
        <main>
            <h1>{event.title}</h1>

            <p>Locality: {event.locality}</p>
            <p>County: {event.county}</p>

            <h2>Available data sources</h2>

            <ul>
                {event.event_layers.map((layer) => (
                    <li key={layer.id}>
                        <h3>{layer.source}</h3>
                        <p>Type: {layer.layer_type}</p>
                        <p>Period: {layer.period ?? "Static"}</p>
                        <p>Status: {layer.status}</p>

                        {layer.reason && <p>Reason: {layer.reason}</p>}
                    </li>
                ))}
            </ul>
        </main>
    );
}

export default PublicEventPage;
