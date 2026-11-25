import { useState } from "react";
import { Link, useNavigate } from "react-router";

import AoiDrawMap from "../components/AoiDrawMap";
import { createEvent } from "../services/eventService";
import { useCompany } from "../hooks/useCompany";
import { polygonAreaKm2 } from "../utils/geo";
import Icon from "../components/Icon";
import PageHeader from "../components/PageHeader";

// Keep the zone small enough for the S1/S2/OSM processing
const MAX_AREA_KM2 = 250;

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
    const {company,loading:companyLoading}=useCompany();
    const [forCompany,setForCompany]=useState(true);
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
            setError("Desenează zona afectată pe hartă.");
            return;
        }

        if(areaKm2 > MAX_AREA_KM2){
            setError(`Zona este prea mare (max ${MAX_AREA_KM2} km²).`);
            return;
        }

        if(startDate > today){
            setError("Data de început nu poate fi în viitor.");
            return;
        }

        if(endDate && endDate < startDate){
            setError("Data de sfârșit nu poate fi înaintea datei de început.");
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
                companyId:forCompany ? company?.id : null,
            });

            navigate(`/events/${created.slug}`);
        }catch(err){
            setError(err.message || "Evenimentul nu a putut fi salvat.");
        }finally{
            setSaving(false);
        }
    }

    return(
        <>
            <Link to="/dashboard" className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted no-underline hover:text-deep-teal"><Icon name="arrowLeft" className="size-4"/>Înapoi la dashboard</Link>
            <PageHeader eyebrow="Eveniment nou" title="Eveniment nou de inundație"
                description="Completează detaliile și desenează zona afectată pe hartă."/>

            <form onSubmit={handleSubmit} className="grid gap-5">
                <section className="card">
                    <div className="card-header"><h2 className="card-title">Detalii</h2></div>
                    <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(min(220px,100%),1fr))]">
                        <label htmlFor="title" className="field col-span-full">Denumire eveniment
                            <input id="title" value={title} onChange={(e)=>setTitle(e.target.value)}
                                maxLength={120} placeholder="ex. Inundații Pechea, septembrie 2024" required/>
                        </label>
                        <label htmlFor="startDate" className="field">Data de început (UTC)
                            <input id="startDate" type="date" value={startDate} max={today}
                                onChange={(e)=>setStartDate(e.target.value)} required/>
                        </label>
                        <label htmlFor="endDate" className="field">Data de sfârșit
                            <input id="endDate" type="date" value={endDate} min={startDate || undefined} max={today}
                                onChange={(e)=>setEndDate(e.target.value)}/>
                            <span className="hint">Lasă gol dacă evenimentul este în desfășurare.</span>
                        </label>
                        <label htmlFor="locality" className="field"><span>Localitate <span className="hint">(opțional)</span></span>
                            <input id="locality" value={locality} onChange={(e)=>setLocality(e.target.value)}/>
                        </label>
                        <label htmlFor="county" className="field"><span>Județ <span className="hint">(opțional)</span></span>
                            <input id="county" value={county} onChange={(e)=>setCounty(e.target.value)}/>
                        </label>
                    </div>
                    <div className="mt-5">
                        {company && <label className="flex items-center gap-2.5 text-sm font-medium"><input type="checkbox" checked={forCompany} onChange={e=>setForCompany(e.target.checked)}/>Eveniment pentru {company.name}</label>}
                        <p className="mt-1.5 flex items-center gap-1 text-sm text-muted"><Icon name="lock" className="size-3.5"/> {company && forCompany ? "Vizibil doar membrilor firmei." : "Eveniment personal, privat."}</p>
                    </div>
                </section>

                <section className="card">
                    <div className="card-header">
                        <h2 className="card-title">Zona afectată</h2>
                        <span className={`badge ${!aoi ? "badge-muted" : areaKm2 > MAX_AREA_KM2 ? "badge-danger" : "badge-success"}`}>
                            {aoi ? `${areaKm2.toFixed(1)} km² / max ${MAX_AREA_KM2} km²` : "Nicio zonă desenată"}
                        </span>
                    </div>
                    <p className="mb-4 text-sm text-muted">
                        Folosește instrumentul poligon sau dreptunghi (stânga sus) pentru a desena zona.
                        O zonă nouă o înlocuiește pe cea anterioară.
                    </p>
                    <div className="overflow-hidden rounded-xl border border-line"><AoiDrawMap onChange={setAoi}/></div>
                </section>

                {error && <p role="alert">{error}</p>}

                <div className="flex flex-wrap gap-2.5">
                    <button type="submit" className="btn btn-lg" disabled={saving || companyLoading}>
                        {saving ? "Se salvează…" : "Creează evenimentul"}
                    </button>
                    <Link to="/dashboard" className="btn btn-lg btn-secondary">Anulează</Link>
                </div>
            </form>
        </>
    );
}

export default NewEventPage;
