import { useState, useEffect } from "react";
import { Link } from "react-router";

import { useAuth } from "../hooks/useAuth";
import { logout } from "../services/authService";
import { listEvents } from "../services/eventService";

function HomePage(){
    const {user} = useAuth();
    const [error,setError] = useState("");
    const [events,setEvents] = useState([]);
    const [eventsLoading,setEventsLoading] = useState(true);
    const [eventsError,setEventsError] = useState("");

    useEffect(() => {
        let ignore = false;

        async function loadEvents(){
            try{
                const data = await listEvents();

                if(!ignore){
                    setEvents(data);
                }
            }catch(err){
                if(!ignore){
                    setEventsError(err.message);
                }
            }finally{
                if(!ignore){
                    setEventsLoading(false);
                }
            }
        }

        loadEvents();

        return () => {
            ignore = true;
        };
    }, []);

    async function handleLogout(){
        setError("");

        try{
            const result = await logout();

            if(result.error){
                setError(result.error.message);
            }
        }catch(err){
            setError(err.message || "Logout failed");
        }
    }

    return(
        <div>
            <h1>Flood Assessment</h1>
            <p>Logged in as: {user?.email}</p>

            <button onClick={handleLogout}>
                Logout
            </button>

            {error && <p role="alert">{error}</p>}

            <h2>Flood events</h2>

            <Link to="/events/new">+ New event</Link>

            {eventsLoading && <p>Loading events...</p>}
            {eventsError && <p role="alert">{eventsError}</p>}

            {!eventsLoading && !eventsError && events.length === 0 && (
                <p>No events yet.</p>
            )}

            <ul>
                {events.map((event) => (
                    <li key={event.id}>
                        <Link to={`/events/${event.slug}`}>{event.title}</Link>
                        {" — "}
                        {new Date(event.started_at).toLocaleDateString("ro-RO", {
                            timeZone: "Europe/Bucharest"
                        })}
                        {!event.ended_at && " (ongoing)"}
                        {event.visibility === "private" && " (private)"}
                    </li>
                ))}
            </ul>
        </div>
    );
}

export default HomePage;