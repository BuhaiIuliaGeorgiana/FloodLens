import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { useAuth } from "../hooks/useAuth";
import { useCompany } from "../hooks/useCompany";
import { saveMemberProfile } from "../services/companyService";
import MemberProfileFields, { emptyProfile } from "../components/MemberProfileFields";
import PageHeader from "../components/PageHeader";
import Icon from "../components/Icon";
// Butoanele exista deja in UI; actiunile vor fi conectate la backend ulterior.
function DangerZone({membership}) {
    const [notice,setNotice]=useState("");
    const actions=[
        membership && ["leave","logout","Părăsește firma",`Nu vei mai avea acces la datele firmei ${membership.companies.name}.`],
        membership?.role==="admin" && ["deleteCompany","trash","Șterge firma","Firma, membrii și evenimentele ei vor fi șterse definitiv."],
        ["deleteAccount","trash","Șterge contul","Contul și datele tale personale vor fi șterse definitiv."],
    ].filter(Boolean);
    function run(label) { if(window.confirm(`${label}? Acțiunea nu poate fi anulată.`)) setNotice(`„${label}” nu este încă disponibilă.`); }
    return <section className="card border-danger/25">
        <div className="card-header"><h2 className="card-title">Gestionare cont și firmă</h2></div>
        <div className="grid gap-4">{actions.map(([key,icon,label,description])=><div key={key} className="flex flex-wrap items-center justify-between gap-3">
            <div><strong className="block">{label}</strong><span className="text-sm text-muted">{description}</span></div>
            <button type="button" className="btn btn-danger" onClick={()=>run(label)}><Icon name={icon} className="size-[18px]"/>{label}</button></div>)}</div>
        {notice && <p className="notice mt-4">{notice}</p>}
    </section>;
}
function ProfileForm({membership,user,refresh}) {
    const [profile,setProfile]=useState(membership.profile ?? emptyProfile);
    const [error,setError]=useState(""),[busy,setBusy]=useState(false); const navigate=useNavigate();
    async function save(event) {
        event.preventDefault();setBusy(true);setError("");
        try { await saveMemberProfile(membership.company_id,user.id,profile); await refresh();
            navigate(membership.role==="admin" && !membership.company_complete ? "/company/edit" : "/dashboard");
        } catch(err) {setError(err.message);} finally {setBusy(false);}
    }
    return <section className="card">
        <div className="card-header"><h2 className="card-title">{membership.companies.name}</h2>
            <span className="badge">{membership.role==="admin" ? "Administrator" : "Angajat"}</span></div>
        {!membership.profile_complete && <p className="notice mb-4">Completează toate câmpurile pentru a accesa datele firmei.</p>}
        <form onSubmit={save} className="grid gap-4"><MemberProfileFields value={profile} onChange={setProfile} disabled={busy}/>
            {error && <p role="alert">{error}</p>}
            <div><button className="btn" disabled={busy}>{busy ? "Se salvează…" : "Salvează profilul"}</button></div></form>
        <p className="mt-4 text-sm text-muted">Profilul este vizibil doar pentru tine și administratorii acestei firme. Ambele părți îl pot modifica direct.</p>
    </section>;
}
export default function ProfilePage() {
    const {user}=useAuth(); const {membership,loading,error,refresh}=useCompany();
    if(loading) return <p className="loading">Se încarcă profilul…</p>;
    return <><PageHeader eyebrow="Cont" title="Profil" description={`Autentificat ca ${user.email}`}/>
        <div className="grid gap-5">
            {error && <p role="alert">{error}</p>}
            {membership ? <ProfileForm key={membership.company_id} membership={membership} user={user} refresh={refresh}/>
            : <div className="empty"><strong className="block text-deep-teal">Nu faci parte dintr-o firmă</strong>
                Profilul profesional se completează după asocierea cu o firmă.
                <div className="mt-4 flex flex-wrap justify-center gap-2.5">
                    <Link to="/company/setup" className="btn">Creează firma</Link>
                    <Link to="/join" className="btn btn-secondary">Acceptă invitația</Link></div></div>}
            <DangerZone membership={membership}/>
        </div>
    </>;
}
