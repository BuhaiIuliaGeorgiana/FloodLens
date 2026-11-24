import {useState,useEffect} from "react";
import {Link} from "react-router";
import {useCompany} from "../hooks/useCompany";
import {getMembers,getInvitations,createInvitation,revokeInvitation,removeMember,saveMemberProfile} from "../services/companyService";
import MemberProfileFields,{emptyProfile} from "../components/MemberProfileFields";
function MemberEditor({member,companyId,onSaved,onCancel}) {
    const [profile,setProfile]=useState(member.profile ?? emptyProfile),[busy,setBusy]=useState(false),[error,setError]=useState("");
    async function save(event) {event.preventDefault();setBusy(true);setError("");
        try {await saveMemberProfile(companyId,member.user_id,profile);await onSaved();}
        catch(err){setError(err.message);}finally{setBusy(false);}}
    return <form onSubmit={save}><p>Email cont: {member.email}</p>
        <MemberProfileFields value={profile} onChange={setProfile} disabled={busy}/>
        <button disabled={busy}>Salvează profilul</button><button type="button" disabled={busy} onClick={onCancel}>Anulează</button>
        {error && <p role="alert">{error}</p>}</form>;
}
function Employees({company,membership,refresh}) {
    const [members,setMembers]=useState([]),[invitations,setInvitations]=useState([]),[editing,setEditing]=useState(null);
    const [email,setEmail]=useState(""),[invitation,setInvitation]=useState(null),[error,setError]=useState("");
    const [busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[revision,setRevision]=useState(0);
    useEffect(()=>{let ignore=false;
        Promise.all([getMembers(company.id),getInvitations(company.id)]).then(([people,invites])=>{
            if(!ignore){setMembers(people);setInvitations(invites);setLoading(false);}
        }).catch(err=>{if(!ignore){setError(err.message);setLoading(false);}});
        return ()=>{ignore=true;};
    },[company.id,revision]);
    async function action(fn) {setBusy(true);setError("");
        try {await fn();setRevision(n=>n+1);}catch(err){setError(err.message);}finally{setBusy(false);}}
    async function invite(event) {event.preventDefault();setInvitation(null);await action(async()=>{
        const code=await createInvitation(company.id,email);
        setInvitation({email:email.trim().toLowerCase(),link:`${window.location.origin}/join?code=${encodeURIComponent(code)}`});
    });}
    return <main><h1>Gestionare angajați</h1>
        {!membership.company_complete && <p>Completează <Link to="/company/edit">datele firmei</Link> înainte de a invita angajați.</p>}
        <form onSubmit={invite}><label>Email angajat<input type="email" required maxLength={254} value={email} onChange={e=>setEmail(e.target.value)} disabled={busy}/></label>
            <button disabled={busy || !membership.company_complete}>Creează invitație</button></form>
        <p>Trimite personal linkul persoanei invitate. Aplicația nu trimite automat emailuri.</p>
        {invitation && <label>Link pentru {invitation.email}<input aria-label="Link invitație" readOnly value={invitation.link} onFocus={e=>e.target.select()}/></label>}
        {error && <p role="alert">{error}</p>}{loading && <p>Se încarcă angajații…</p>}
        <h2>Membri</h2><ul>{members.map(member=><li key={member.user_id}>
            <p>{member.profile ? `${member.profile.last_name} ${member.profile.first_name}` : "Profil necompletat"} — {member.email} — {member.role==="admin" ? "Administrator" : "Angajat"}</p>
            {member.profile && <p>{member.profile.job_title} · {member.profile.department}</p>}
            <button disabled={busy} onClick={()=>setEditing(member)}>Editează profilul</button>{" "}
            {member.role==="member" && <button disabled={busy} onClick={()=>action(async()=>{
                await removeMember(company.id,member.user_id);if(editing?.user_id===member.user_id)setEditing(null);
            })}>Elimină din firmă</button>}
        </li>)}</ul>
        {editing && <MemberEditor key={editing.user_id} member={editing} companyId={company.id} onCancel={()=>setEditing(null)}
            onSaved={async()=>{await refresh();setEditing(null);setRevision(n=>n+1);}}/>}
        <h2>Invitații</h2><ul>{invitations.map(item=><li key={item.id}>{item.email || "Invitație veche"} — {item.used_at ? "Folosită" : item.revoked_at ? "Revocată" : new Date(item.expires_at)<=new Date() ? "Expirată" : `Expiră: ${new Date(item.expires_at).toLocaleString("ro-RO")}`}{" "}
            {!item.used_at && !item.revoked_at && new Date(item.expires_at)>new Date() && <button disabled={busy} onClick={()=>action(()=>revokeInvitation(item.id))}>Revocă</button>}
        </li>)}</ul></main>;
}
export default function EmployeesPage() {
    const {company,membership,refresh}=useCompany();return <Employees key={company.id} company={company} membership={membership} refresh={refresh}/>;
}
