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
    created_by
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
export async function listEvents(){

    const {data,error} = await supabase
        .from("flood_events")
        .select(EVENT_FIELDS)
        .order("started_at", {ascending: false});

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

// The start date is picked as a local (Romanian) calendar day and stored
// as local midnight in UTC, the same way the Pechea event was entered
export function localDayToIso(startDate){
    const [year, month, day] = startDate.split("-").map(Number);

    return new Date(year, month - 1, day).toISOString();
}

export async function createEvent({ title, startDate, endDate, locality, county, aoi, isPrivate }){
    const baseSlug = makeSlug(title, startDate);

    const row = {
        title: title.trim(),
        started_at: localDayToIso(startDate),
        // Empty end date = ongoing event
        ended_at: endDate ? localDayToIso(endDate) : null,
        locality: locality.trim() || null,
        county: county.trim() || null,
        aoi_geojson: aoi,
        visibility: isPrivate ? "private" : "public",
    };

    // Retry with a numeric suffix if the slug is already taken
    for(let attempt = 1; attempt <= 5; attempt++){
        const slug = attempt === 1 ? baseSlug : `${baseSlug}-${attempt}`;

        const {data,error} = await supabase
            .from("flood_events")
            .insert({ ...row, slug })
            .select("id, slug")
            .single();

        if(!error){
            return data;
        }

        // 23505 = unique_violation (slug already exists)
        if(error.code !== "23505"){
            throw error;
        }
    }

    throw new Error("Could not generate a unique slug for this event.");
}
