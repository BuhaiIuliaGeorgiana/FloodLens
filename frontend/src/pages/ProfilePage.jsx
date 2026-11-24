import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { useAuth } from "../hooks/useAuth";
import { useCompany } from "../hooks/useCompany";
import { saveMemberProfile } from "../services/companyService";
import MemberProfileFields, { emptyProfile } from "../components/MemberProfileFields";
function ProfileForm({membership,user,refresh}) {
    const [profile,setProfile]=useState(membership.profile ?? emptyProfile);
    const [error,setError]=useState(""),[busy,setBusy]=useState(false); const navigate=useNavigate();
    async function save(event) {
        event.preventDefault();setBusy(true);setError("");
        try { await saveMemberProfile(membership.company_id,user.id,profile); await refresh();
            navigate(membership.role==="admin" && !membership.company_complete ? "/company/edit" : "/dashboard");
        } catch(err) {setError(err.message);} finally {setBusy(false);}
    }
    return <><h2>{membership.companies.name}</h2>
        {!membership.profile_complete && <p>Completează toate câmpurile pentru a accesa datele firmei.</p>}
        <p>Profilul este vizibil doar pentru tine și administratorii acestei firme. Ambele părți îl pot modifica direct.</p>
        <form onSubmit={save}><MemberProfileFields value={profile} onChange={setProfile} disabled={busy}/>
            <button disabled={busy}>Salvează profilul</button></form>{error && <p role="alert">{error}</p>}</>;
}
export default function ProfilePage() {
    const {user}=useAuth(); const {membership,loading,error,refresh}=useCompany();
    if(loading) return <p>Se încarcă profilul…</p>;
    return <main><h1>Profil</h1><p>Email cont: {user.email}</p>{error && <p role="alert">{error}</p>}
        {membership ? <ProfileForm key={membership.company_id} membership={membership} user={user} refresh={refresh}/>
        : <p>Profilul profesional se completează după asocierea cu o firmă. <Link to="/company/setup">Creează firma</Link> sau <Link to="/join">acceptă invitația</Link>.</p>}
    </main>;
}
