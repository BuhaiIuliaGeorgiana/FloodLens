import { useEffect, useState } from "react";
import { useCompany } from "../hooks/useCompany";
import { getClients, addClient, updateClient, deleteClient } from "../services/companyService";
import Icon from "../components/Icon";
import PageHeader from "../components/PageHeader";

const emptyClient={name:"",email:"",phone:""};

function ClientForm({initial,onSubmit,onCancel,busy}) {
    const [value,setValue]=useState(initial);
    const set=key=>e=>setValue({...value,[key]:e.target.value});
    return <form onSubmit={e=>{e.preventDefault();onSubmit(value);}} className="grid gap-4">
        <fieldset disabled={busy} className="fieldset">
            <label className="field">Nume client<input required maxLength={200} value={value.name} onChange={set("name")}/></label>
            <label className="field">Email<input type="email" maxLength={254} value={value.email ?? ""} onChange={set("email")}/></label>
            <label className="field">Telefon<input type="tel" maxLength={50} value={value.phone ?? ""} onChange={set("phone")}/></label>
        </fieldset>
        <div className="flex flex-wrap gap-2.5"><button className="btn" disabled={busy}>{initial.id ? "Salvează" : "Adaugă clientul"}</button>
            <button type="button" className="btn btn-secondary" disabled={busy} onClick={onCancel}>Anulează</button></div>
    </form>;
}

function Clients({company,isAdmin}) {
    const [rows,setRows]=useState(null),[error,setError]=useState(""),[busy,setBusy]=useState(false);
    const [editing,setEditing]=useState(null),[revision,setRevision]=useState(0),[query,setQuery]=useState("");
    useEffect(()=>{let ignore=false;
        getClients(company.id).then(data=>{if(!ignore)setRows(data);}).catch(err=>{if(!ignore)setError(err.message);});
        return ()=>{ignore=true;};
    },[company.id,revision]);
    async function action(fn) {setBusy(true);setError("");
        try {await fn();setEditing(null);setRevision(n=>n+1);}catch(err){setError(err.message);}finally{setBusy(false);}}
    const save=client=>action(()=>client.id ? updateClient(client.id,client) : addClient(company.id,client));
    const remove=client=>{ if(window.confirm(`Ștergi clientul ${client.name}?`)) action(()=>deleteClient(client.id)); };
    const q=query.trim().toLowerCase();
    const visible=(rows ?? []).filter(row=>!q || [row.name,row.email,row.phone].some(v=>v?.toLowerCase().includes(q)))
        .sort((a,b)=>a.name.localeCompare(b.name,"ro"));
    return <><PageHeader eyebrow="Firmă" title={isAdmin ? "Gestionare clienți" : "Clienți"}
            description={isAdmin ? `Clienții firmei ${company.name}.` : `Clienții firmei ${company.name}. Doar administratorul îi poate modifica.`}>
            {isAdmin && !editing && <button className="btn" onClick={()=>setEditing(emptyClient)}><Icon name="plus" className="size-[18px]"/>Client nou</button>}
        </PageHeader>
        <div className="grid gap-5">
        {editing && <section className="card"><div className="card-header"><h2 className="card-title">{editing.id ? "Editare client" : "Client nou"}</h2></div>
            <ClientForm key={editing.id ?? "new"} initial={editing} onSubmit={save} onCancel={()=>setEditing(null)} busy={busy}/></section>}
        {error && <p role="alert">{error}</p>}
        <section className="card" aria-label="Lista clienților">
            <div className="card-header"><h2 className="card-title">Lista clienților <span className="badge badge-muted align-middle">{rows?.length ?? 0}</span></h2>
                <input type="search" placeholder="Caută…" aria-label="Caută client" value={query} onChange={e=>setQuery(e.target.value)} className="max-w-60"/></div>
            {!rows ? (!error && <p className="loading">Se încarcă clienții…</p>) : visible.length===0
                ? <div className="empty">{rows.length===0 ? <><strong className="block text-deep-teal">Niciun client încă</strong>{isAdmin && "Adaugă primul client cu butonul „Client nou”."}</> : "Niciun rezultat."}</div>
                : <div className="overflow-x-auto"><table className="table">
                    <thead><tr><th>Nume</th><th>Email</th><th>Telefon</th>{isAdmin && <th><span className="sr-only">Acțiuni</span></th>}</tr></thead>
                    <tbody>{visible.map(row=><tr key={row.id}>
                        <td><strong>{row.name}</strong></td>
                        <td>{row.email ? <a href={`mailto:${row.email}`}>{row.email}</a> : <span className="text-muted">–</span>}</td>
                        <td>{row.phone ? <a href={`tel:${row.phone}`}>{row.phone}</a> : <span className="text-muted">–</span>}</td>
                        {isAdmin && <td className="whitespace-nowrap text-right [&>*+*]:ml-1.5">
                            <button className="btn btn-secondary btn-sm" disabled={busy} onClick={()=>setEditing(row)}>Editează</button>
                            <button className="btn btn-danger btn-sm" disabled={busy} onClick={()=>remove(row)}>Șterge</button></td>}
                    </tr>)}</tbody></table></div>}
        </section></div></>;
}

export default function ClientsPage() {
    const {company,isAdmin}=useCompany();
    return <Clients key={company.id} company={company} isAdmin={isAdmin}/>;
}
