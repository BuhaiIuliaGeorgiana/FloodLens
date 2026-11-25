import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { useAuth } from "../hooks/useAuth";
import { useCompany } from "../hooks/useCompany";
import { saveMemberProfile } from "../services/companyService";
import MemberProfileFields, { emptyProfile } from "../components/MemberProfileFields";
import PageHeader from "../components/PageHeader";
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
        </div>
    </>;
}
