import { useEffect, useState } from "react";
import { Link } from "react-router";
import { useAuth } from "../hooks/useAuth";
import { useCompany } from "../hooks/useCompany";
import { listEvents } from "../services/eventService";
import { NEWS } from "../content/news";
import Icon from "../components/Icon";
import PageHeader from "../components/PageHeader";
import EventList from "../components/EventList";
import { formatDay } from "../utils/format";

export default function HomePage() {
    const {user}=useAuth(); const {membership}=useCompany();
    const [events,setEvents]=useState(null),[error,setError]=useState("");
    useEffect(()=>{let ignore=false;
        listEvents().then(data=>{if(!ignore)setEvents(data);}).catch(err=>{if(!ignore)setError(err.message);});
        return ()=>{ignore=true;};
    },[]);
    const name=membership?.profile?.first_name ?? user.email.split("@")[0];
    return <>
        <PageHeader eyebrow="Acasă" title={`Bună, ${name}!`} description="Noutățile platformei și ultimele actualizări ale evenimentelor tale.">
            <Link to="/events/new" className="btn"><Icon name="plus" className="size-[18px]"/>Eveniment nou</Link>
        </PageHeader>
        <div className="grid items-start gap-5 md:grid-cols-2">
            <section className="card" aria-labelledby="news-title">
                <div className="card-header"><h2 id="news-title" className="card-title">Noutăți</h2><span className="badge badge-sand">FloodLens</span></div>
                <div className="grid gap-5">{NEWS.map(item=><article key={item.title} className="grid grid-cols-[auto_1fr] gap-4">
                    <span className="icon-chip"><Icon name={item.icon} className="size-[18px]"/></span>
                    <div><div className="mb-1 flex items-center gap-2 text-xs text-muted"><span className="badge badge-muted">{item.tag}</span>{formatDay(item.date)}</div>
                        <h3 className="mb-0.5">{item.title}</h3><p className="text-[0.92rem] text-muted">{item.text}</p></div>
                </article>)}</div>
            </section>
            <section className="card" aria-labelledby="updates-title">
                <div className="card-header"><h2 id="updates-title" className="card-title">Updates</h2><Link to="/dashboard" className="text-sm">Toate evenimentele</Link></div>
                {error ? <p role="alert">{error}</p> : !events ? <p className="loading">Se încarcă…</p> :
                    <EventList events={events.slice(0,6)} empty={<><strong className="block text-deep-teal">Niciun eveniment încă</strong>Creează primul eveniment pentru a vedea actualizări aici.</>}/>}
            </section>
        </div>
    </>;
}
