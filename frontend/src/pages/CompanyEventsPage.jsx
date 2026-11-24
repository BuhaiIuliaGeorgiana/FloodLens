import { useState, useEffect } from "react";
import { Link } from "react-router";
import { useCompany } from "../hooks/useCompany";
import { listEvents } from "../services/eventService";
export default function CompanyEventsPage() {
    const {company}=useCompany();
    const [rows,setRows]=useState([]),[error,setError]=useState("");
    useEffect(()=>{
        let ignore=false;
        listEvents(company.id).then(data=>{if(!ignore)setRows(data);}).catch(err=>{if(!ignore)setError(err.message);});
        return ()=>{ignore=true;};
    },[company.id]);
    return <main><h1>Evenimentele firmei</h1><Link to="/events/new">Eveniment nou</Link>
        {error && <p role="alert">{error}</p>}<ul>{rows.map(row=><li key={row.id}><Link to={`/events/${row.slug}`}>{row.title}</Link></li>)}</ul>
    </main>;
}
