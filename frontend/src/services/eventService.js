import { supabase } from "../config/supabase";

const EVENT_FIELDS = `
    id,
    slug,
    title,
    locality,
    county,
    started_at,
    ended_at,
    aoi_geojson,
    visibility,
    created_by,
    company_id
`;

export async function getEventBySlug(slug){

    const {data,error} = await supabase
        .from("flood_events")
        .select(`
            ${EVENT_FIELDS},
            event_layers (
                    id,
                    source,
                    period,
                    layer_type,
                    kind,
                    status,
                    reason,
                    storage_path,
                    acquired_at,
                    bounds
                )
        `)
        .eq("slug",slug)
        .maybeSingle();

    if(error){
        throw error;
    }

    // null when the event does not exist or is private to someone else
    return data;
}

// RLS returns public events plus the user's own private ones
export async function listEvents(companyId = null){

    let query = supabase.from("flood_events").select(EVENT_FIELDS).order("started_at", {ascending:false});
    if(companyId) query = query.eq("company_id",companyId);
    const {data,error} = await query;

    if(error){
        throw error;
    }

    return data;
}

// Build a URL-friendly slug from the name and start date,
// e.g. "Inundatii Galați" + 2026-11-18 -> "inundatii-galati-2026-11-18"
export function makeSlug(title, startDate){
    const name = title
        .normalize("NFD")
        .replace(/[̀-ͯ]/g, "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .slice(0, 60);

    return `${name || "event"}-${startDate}`;
}

// Zilele introduse in formular reprezinta miezul noptii UTC.
export function localDayToIso(startDate){
    return new Date(`${startDate}T00:00:00Z`).toISOString();
}

export async function createEvent({title,startDate,endDate,locality,county,aoi,companyId}) {
    const {data,error} = await supabase.rpc("fl_create_event", {p_event:{
        title:title.trim(), company_id:companyId || null,
        event_start:localDayToIso(startDate), ended_at:endDate ? localDayToIso(endDate) : null,
        locality:locality.trim(), county:county.trim(), aoi,
    }});
    if(error) throw error;
    return data;
}
