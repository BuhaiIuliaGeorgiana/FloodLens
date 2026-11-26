import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { createCompany } from "../services/companyService";
import { useCompany } from "../hooks/useCompany";
import { useAuth } from "../hooks/useAuth";
import CompanyFields, { emptyCompany } from "../components/CompanyFields";
import MemberProfileFields, { emptyProfile } from "../components/MemberProfileFields";
import Icon from "../components/Icon";
import PageHeader from "../components/PageHeader";
export default function CompanySetupPage() {
    const [details,setDetails]=useState(emptyCompany), [profile,setProfile]=useState(emptyProfile);
    const [error,setError]=useState(""), [busy,setBusy]=useState(false);
    const {refresh,selectCompany}=useCompany(); const {user}=useAuth(); const navigate=useNavigate();
    async function save(event) {
        event.preventDefault(); setBusy(true); setError("");
        try { const id=await createCompany(details,profile); selectCompany(id); await refresh(); navigate("/dashboard"); }
        catch(err) { setError(err.message); } finally { setBusy(false); }
    }
    return <><PageHeader eyebrow="Firmă" title="Creare firmă"
            description={`Completează firma și profilul tău de administrator. Contul folosit: ${user.email}`}>
            <Link to="/join" className="btn btn-secondary"><Icon name="mail" className="size-[18px]"/>Am o invitație</Link>
        </PageHeader>
        <form onSubmit={save} className="grid gap-5">
            <section className="card"><CompanyFields value={details} onChange={setDetails} disabled={busy}/></section>
            <section className="card"><MemberProfileFields value={profile} onChange={setProfile} disabled={busy} legend="Profilul administratorului"/></section>
            {error && <p role="alert">{error}</p>}
            <div className="flex flex-wrap items-center gap-3"><button className="btn" disabled={busy}>{busy ? "Se salvează…" : "Creează firma"}</button>
                <span className="text-sm text-muted">Doar telefonul și website-ul sunt opționale.</span></div>
        </form></>;
}
