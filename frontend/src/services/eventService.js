import { supabase } from "../config/supabase";

export async function getPecheaEvent(){

    const {data,error} = await supabase
        .from("flood_events")
        .select(`
            id,
            slug,
            title,
            locality,
            county,
            started_at,
            ended_at,
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
        .eq("slug","pechea-2024-09")
        .single();

    if(error){
        throw error;
    }

    return data;
}
