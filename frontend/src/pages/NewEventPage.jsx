import { useState } from "react";
import { Link, useNavigate } from "react-router";

import AoiDrawMap from "../components/AoiDrawMap";
import { createEvent } from "../services/eventService";
import { polygonAreaKm2 } from "../utils/geo";

// Keep the zone small enough for the S1/S2/OSM processing
const MAX_AREA_KM2 = 500;

// Today's date as YYYY-MM-DD in local time, for the date picker limit
function todayLocal(){
    const now = new Date();
    const offset = now.getTimezoneOffset() * 60000;

    return new Date(now - offset).toISOString().slice(0, 10);
}

function NewEventPage(){
    const [title,setTitle] = useState("");
    const [startDate,setStartDate] = useState("");
    const [endDate,setEndDate] = useState("");
    const [locality,setLocality] = useState("");
    const [county,setCounty] = useState("");
    const [isPrivate,setIsPrivate] = useState(false);
    const [aoi,setAoi] = useState(null);
    const [error,setError] = useState("");
    const [saving,setSaving] = useState(false);

    const navigate = useNavigate();
    const today = todayLocal();
    const areaKm2 = aoi ? polygonAreaKm2(aoi) : 0;

    async function handleSubmit(event){
        event.preventDefault();
        setError("");

        if(!aoi){
            setError("Draw the affected zone on the map.");
            return;
        }

        if(areaKm2 > MAX_AREA_KM2){
            setError(`The zone is too large (max ${MAX_AREA_KM2} km²).`);
            return;
        }

        if(startDate > today){
            setError("The start date cannot be in the future.");
            return;
        }

        if(endDate && endDate < startDate){
            setError("The end date cannot be before the start date.");
            return;
        }

        setSaving(true);

        try{
            const created = await createEvent({
                title,
                startDate,
                endDate,
                locality,
                county,
                aoi,
                isPrivate,
            });

            navigate(`/events/${created.slug}`);
        }catch(err){
            setError(err.message || "Could not save the event.");
        }finally{
            setSaving(false);
        }
    }

    return(
        <main>
            <p><Link to="/">← Back to events</Link></p>

            <h1>New flood event</h1>

            <form onSubmit={handleSubmit}>
                <div>
                    <label htmlFor="title">Event name:</label>
                    <input  id="title"
                            value={title}
                            onChange={(e)=>setTitle(e.target.value)}
                            maxLength={120}
                            required
                            />
                </div>

                <div>
                    <label htmlFor="startDate">Flood start date:</label>
                    <input  id="startDate"
                            type="date"
                            value={startDate}
                            max={today}
                            onChange={(e)=>setStartDate(e.target.value)}
                            required
                            />
                </div>

                <div>
                    <label htmlFor="endDate">Flood end date (optional, leave empty if ongoing):</label>
                    <input  id="endDate"
                            type="date"
                            value={endDate}
                            min={startDate || undefined}
                            max={today}
                            onChange={(e)=>setEndDate(e.target.value)}
                            />
                </div>

                <div>
                    <label htmlFor="locality">Locality (optional):</label>
                    <input  id="locality"
                            value={locality}
                            onChange={(e)=>setLocality(e.target.value)}
                            />
                </div>

                <div>
                    <label htmlFor="county">County (optional):</label>
                    <input  id="county"
                            value={county}
                            onChange={(e)=>setCounty(e.target.value)}
                            />
                </div>

                <div>
                    <label>
                        <input  type="checkbox"
                                checked={isPrivate}
                                onChange={(e)=>setIsPrivate(e.target.checked)}
                                />
                        Private (only visible to me)
                    </label>
                </div>

                <section style={{maxWidth: "750px", margin: "20px 0"}}>
                    <h2>Affected zone</h2>

                    <p>
                        Use the polygon or rectangle tool (top left) to draw the zone.
                        Drawing a new zone replaces the previous one.
                    </p>

                    <AoiDrawMap onChange={setAoi}/>

                    <p>
                        {aoi
                            ? `Zone area: ${areaKm2.toFixed(1)} km² (max ${MAX_AREA_KM2} km²)`
                            : "No zone drawn yet."}
                    </p>
                </section>

                <button type="submit" disabled={saving}>
                    {saving ? "Saving..." : "Create event"}
                </button>

                {error && <p role="alert">{error}</p>}
            </form>
        </main>
    );
}

export default NewEventPage;
