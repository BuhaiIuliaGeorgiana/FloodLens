import { useState, useEffect } from "react";
import { Link } from "react-router";
import { useCompany } from "../hooks/useCompany";
import { listEvents } from "../services/eventService";
import Icon from "../components/Icon";
import PageHeader from "../components/PageHeader";
import EventList from "../components/EventList";
export default function CompanyEventsPage() {
    const {company,isAdmin}=useCompany();
    const [rows,setRows]=useState(null),[error,setError]=useState("");
    useEffect(()=>{
        let ignore=false;
        listEvents(company.id).then(data=>{if(!ignore)setRows(data);}).catch(err=>{if(!ignore)setError(err.message);});
        return ()=>{ignore=true;};
    },[company.id]);
    return <><PageHeader eyebrow="Firmă" title={isAdmin ? "Gestionare evenimente firmă" : "Evenimentele firmei"}
            description={`Evenimente vizibile doar membrilor ${company.name}.`}>
            <Link to="/events/new" className="btn"><Icon name="plus" className="size-[18px]"/>Eveniment nou</Link>
        </PageHeader>
        <section className="card">{error ? <p role="alert">{error}</p> : !rows ? <p className="loading">Se încarcă…</p> :
            <EventList events={rows} empty={<><strong className="block text-deep-teal">Niciun eveniment al firmei</strong>Evenimentele create pentru firmă vor apărea aici.</>}/>}
        </section></>;
}
