import { supabase } from "../config/supabase";

// URL of the Python processing service, e.g. http://localhost:8000
const PIPELINE_URL = import.meta.env.VITE_PIPELINE_URL;

export const isPipelineConfigured = Boolean(PIPELINE_URL);

// The run is still going; the page keeps checking its status
export const ACTIVE_STATUSES = ["queued", "processing"];

// Ask the service to process (or update) an event. Returns the run_id.
// The user's access token is sent so the service can check who asked.
export async function startProcessing(eventId){
    if(!isPipelineConfigured){
        throw new Error("Processing service not configured yet.");
    }

    const {data: {session}} = await supabase.auth.getSession();

    const response = await fetch(
        `${PIPELINE_URL.replace(/\/+$/, "")}/events/${eventId}/process`,
        {
            method: "POST",
            headers: session
                ? { Authorization: `Bearer ${session.access_token}` }
                : {},
        }
    );

    if(!response.ok){
        throw new Error(`Processing service error (${response.status}).`);
    }

    const data = await response.json();

    return data.run_id;
}

// Latest processing run of an event, or null if it was never processed
export async function getLatestRun(eventId){

    const {data,error} = await supabase
        .from("pipeline_runs")
        .select("id, status, source_status, message, created_at, updated_at")
        .eq("event_id", eventId)
        .order("created_at", {ascending: false})
        .limit(1)
        .maybeSingle();

    if(error){
        throw error;
    }

    return data;
}
