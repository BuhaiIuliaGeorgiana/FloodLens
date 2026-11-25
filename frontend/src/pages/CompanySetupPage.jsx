import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { createCompany } from "../services/companyService";
import { useCompany } from "../hooks/useCompany";
import { useAuth } from "../hooks/useAuth";
import CompanyFields, { emptyCompany } from "../components/CompanyFields";
import MemberProfileFields, { emptyProfile } from "../components/MemberProfileFields";
export default function CompanySetupPage() {
    const [details,setDetails]=useState(emptyCompany), [profile,setProfile]=useState(emptyProfile);
    const [error,setError]=useState(""), [busy,setBusy]=useState(false);
    const {refresh,selectCompany}=useCompany(); const {user}=useAuth(); const navigate=useNavigate();
    async function save(event) {
        event.preventDefault(); setBusy(true); setError("");
        try { const id=await createCompany(details,profile); selectCompany(id); await refresh(); navigate("/dashboard"); }
        catch(err) { setError(err.message); } finally { setBusy(false); }
    }
    return <main><h1>Creare firmă</h1><p><Link to="/join">Am o invitație</Link></p>
        <p>Completează firma și profilul tău de administrator. Doar telefonul și website-ul sunt opționale.</p>
        <p>Email cont: {user.email}</p><form onSubmit={save}>
            <CompanyFields value={details} onChange={setDetails} disabled={busy}/>
            <MemberProfileFields value={profile} onChange={setProfile} disabled={busy} legend="Profilul administratorului"/>
            <button disabled={busy}>{busy ? "Se salvează…" : "Creează firma"}</button>
        </form>{error && <p role="alert">{error}</p>}</main>;
}
