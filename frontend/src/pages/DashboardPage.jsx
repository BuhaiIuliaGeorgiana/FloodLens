import { useState, useEffect } from "react";
import { Link } from "react-router";

import { useCompany } from "../hooks/useCompany";
import { listEvents } from "../services/eventService";
import Icon from "../components/Icon";
import PageHeader from "../components/PageHeader";
import EventList from "../components/EventList";

function Tile({to,icon,title,text,sand}) {
    return <Link to={to} className="flex flex-col gap-1.5 rounded-xl border border-line bg-white p-5 text-deep-teal no-underline transition hover:-translate-y-px hover:border-mist hover:shadow-soft">
        <span className={`icon-chip mb-1 ${sand ? "icon-chip-sand" : ""}`}><Icon name={icon} className="size-5"/></span>
        <strong className="text-[0.95rem]">{title}</strong><span className="text-sm text-muted">{text}</span>
    </Link>;
}

const grid = "grid gap-4 grid-cols-[repeat(auto-fill,minmax(min(220px,100%),1fr))]";

function Stat({value,label}) {
    return <div className="card px-5 py-4"><div className="text-3xl font-bold leading-tight">{value}</div><div className="text-sm text-muted">{label}</div></div>;
}

function DashboardPage(){
    const {company,membership,isAdmin} = useCompany();
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

    const companyReady = company && membership.profile_complete;
    const ongoing = events.filter((event) => !event.ended_at).length;
    const companyEvents = company ? events.filter((event) => event.company_id === company.id).length : 0;

    return(
        <>
            <PageHeader eyebrow="Dashboard" title={company ? company.name : "Spațiul tău de lucru"}
                description={company ? (isAdmin ? "Administrezi firma, echipa și clienții." : "Ai acces la datele, clienții și evenimentele firmei.")
                    : "Evenimentele tale personale. Creează o firmă sau acceptă o invitație pentru a lucra în echipă."}>
                <Link to="/events/new" className="btn"><Icon name="plus" className="size-[18px]"/>Eveniment nou</Link>
            </PageHeader>

            <div className="grid gap-5">
            <div className={grid}>
                <Stat value={eventsLoading ? "–" : events.length} label="Evenimente vizibile"/>
                <Stat value={eventsLoading ? "–" : ongoing} label="În desfășurare"/>
                {company && <Stat value={eventsLoading ? "–" : companyEvents} label="Evenimente ale firmei"/>}
            </div>

            <section className="card" aria-labelledby="actions-title">
                <div className="card-header"><h2 id="actions-title" className="card-title">Acțiuni rapide</h2>
                    {company && <span className="badge">{isAdmin ? "Administrator" : "Angajat"}</span>}</div>
                <div className={grid}>
                    <Tile to="/events/new" icon="plus" title="Eveniment nou" text="Desenează zona afectată și pornește analiza."/>
                    <Tile to="/profile" icon="user" title="Profil" text="Datele tale profesionale." sand/>
                    {companyReady && isAdmin && <>
                        <Tile to="/company/employees" icon="users" title="Gestionare angajați" text="Invitații, profiluri și membri."/>
                        <Tile to="/company/clients" icon="briefcase" title="Gestionare clienți" text="Adaugă și editează clienții firmei." sand/>
                        <Tile to="/company/edit" icon="edit" title="Editare date firmă" text="CUI, adresă, contact."/>
                        <Tile to="/company/events" icon="map" title="Evenimentele firmei" text="Toate evenimentele echipei." sand/>
                    </>}
                    {companyReady && !isAdmin && <>
                        <Tile to="/company" icon="building" title="Date firmă" text="Informațiile oficiale ale firmei."/>
                        <Tile to="/company/clients" icon="briefcase" title="Clienți" text="Lista clienților firmei." sand/>
                        <Tile to="/company/events" icon="map" title="Evenimente firmă" text="Evenimentele create de echipă."/>
                    </>}
                    {!company && <Tile to="/company/setup" icon="building" title="Creează o firmă" text="Sau intră cu un cod de invitație."/>}
                </div>
            </section>

            <section className="card" aria-labelledby="events-title">
                <div className="card-header"><h2 id="events-title" className="card-title">Evenimente de inundație</h2></div>

                {eventsLoading && <p className="loading">Se încarcă evenimentele…</p>}
                {eventsError && <p role="alert">{eventsError}</p>}

                {!eventsLoading && !eventsError && (
                    <EventList events={events} empty={<><strong className="block text-deep-teal">Niciun eveniment încă</strong>
                        <Link to="/events/new">Creează primul eveniment</Link> sau explorează <Link to="/demo">demo-ul</Link>.</>}/>
                )}
            </section>
            </div>
        </>
    );
}

export default DashboardPage;
