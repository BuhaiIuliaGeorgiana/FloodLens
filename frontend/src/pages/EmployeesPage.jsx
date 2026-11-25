import {useState,useEffect} from "react";
import {Link} from "react-router";
import {useCompany} from "../hooks/useCompany";
import {getMembers,getInvitations,createInvitation,revokeInvitation,removeMember,saveMemberProfile} from "../services/companyService";
import MemberProfileFields,{emptyProfile} from "../components/MemberProfileFields";
import Icon from "../components/Icon";
import PageHeader from "../components/PageHeader";
function MemberEditor({member,companyId,onSaved,onCancel}) {
    const [profile,setProfile]=useState(member.profile ?? emptyProfile),[busy,setBusy]=useState(false),[error,setError]=useState("");
    async function save(event) {event.preventDefault();setBusy(true);setError("");
        try {await saveMemberProfile(companyId,member.user_id,profile);await onSaved();}
        catch(err){setError(err.message);}finally{setBusy(false);}}
    return <section className="card"><div className="card-header"><h2 className="card-title">Editare profil</h2><span className="text-sm text-muted">{member.email}</span></div>
        <form onSubmit={save} className="grid gap-4"><MemberProfileFields value={profile} onChange={setProfile} disabled={busy}/>
        {error && <p role="alert">{error}</p>}
        <div className="flex flex-wrap gap-2.5"><button className="btn" disabled={busy}>Salvează profilul</button>
            <button type="button" className="btn btn-secondary" disabled={busy} onClick={onCancel}>Anulează</button></div></form></section>;
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
    const status=item=>item.used_at ? ["Folosită","badge-success"] : item.revoked_at ? ["Revocată","badge-muted"]
        : new Date(item.expires_at)<=new Date() ? ["Expirată","badge-danger"] : ["Activă","badge-sand"];
    return <><PageHeader eyebrow="Firmă" title="Gestionare angajați" description={`Membrii și invitațiile pentru ${company.name}.`}/>
        <div className="grid gap-5">
        {!membership.company_complete && <p className="notice">Completează <Link to="/company/edit">datele firmei</Link> înainte de a invita angajați.</p>}
        <section className="card"><div className="card-header"><h2 className="card-title">Invită un angajat</h2></div>
            <form onSubmit={invite} className="grid items-end gap-3 sm:grid-cols-[1fr_auto]">
                <label className="field">Email angajat<input type="email" required maxLength={254} value={email} onChange={e=>setEmail(e.target.value)} disabled={busy}/></label>
                <button className="btn" disabled={busy || !membership.company_complete}><Icon name="mail" className="size-[18px]"/>Creează invitație</button></form>
            <p className="mt-3 text-sm text-muted">Trimite personal linkul persoanei invitate. Aplicația nu trimite automat emailuri.</p>
            {invitation && <div className="notice notice-success mt-4"><label className="field">Link pentru {invitation.email}
                <span className="flex gap-2"><input className="font-mono text-[0.82rem]" aria-label="Link invitație" readOnly value={invitation.link} onFocus={e=>e.target.select()}/>
                    <button type="button" className="btn btn-secondary" onClick={()=>navigator.clipboard?.writeText(invitation.link)}><Icon name="copy" className="size-4"/>Copiază</button></span></label></div>}
        </section>
        {error && <p role="alert">{error}</p>}
        {editing && <MemberEditor key={editing.user_id} member={editing} companyId={company.id} onCancel={()=>setEditing(null)}
            onSaved={async()=>{await refresh();setEditing(null);setRevision(n=>n+1);}}/>}
        <section className="card"><div className="card-header"><h2 className="card-title">Membri</h2><span className="badge badge-muted">{members.length}</span></div>
            {loading ? <p className="loading">Se încarcă angajații…</p> : <div className="overflow-x-auto"><table className="table">
                <thead><tr><th>Nume</th><th>Funcție</th><th>Rol</th><th><span className="sr-only">Acțiuni</span></th></tr></thead>
                <tbody>{members.map(member=><tr key={member.user_id}>
                    <td><strong>{member.profile ? `${member.profile.last_name} ${member.profile.first_name}` : <span className="text-muted">Profil necompletat</span>}</strong>
                        <div className="text-sm text-muted">{member.email}</div></td>
                    <td>{member.profile ? <>{member.profile.job_title}<div className="text-sm text-muted">{member.profile.department}</div></> : "–"}</td>
                    <td><span className={`badge ${member.role==="admin" ? "" : "badge-sand"}`}>{member.role==="admin" ? "Administrator" : "Angajat"}</span></td>
                    <td className="whitespace-nowrap text-right [&>*+*]:ml-1.5">
                        <button className="btn btn-secondary btn-sm" disabled={busy} onClick={()=>setEditing(member)}>Editează</button>
                        {member.role==="member" && <button className="btn btn-danger btn-sm" disabled={busy} onClick={()=>action(async()=>{
                            await removeMember(company.id,member.user_id);if(editing?.user_id===member.user_id)setEditing(null);
                        })}>Elimină</button>}
                    </td></tr>)}</tbody></table></div>}
        </section>
        <section className="card"><div className="card-header"><h2 className="card-title">Invitații</h2></div>
            {invitations.length===0 ? <div className="empty">Nicio invitație creată.</div> : <ul className="divide-y divide-line">{invitations.map(item=>{const [label,tone]=status(item);
                return <li key={item.id} className="flex flex-wrap items-center justify-between gap-4 py-3.5 first:pt-0 last:pb-0"><div className="grid gap-0.5"><span className="font-semibold">{item.email || "Invitație veche"}</span>
                    {label==="Activă" && <span className="text-sm text-muted">Expiră: {new Date(item.expires_at).toLocaleString("ro-RO")}</span>}</div>
                <div className="flex flex-wrap items-center gap-1.5"><span className={`badge ${tone}`}>{label}</span>
                    {label==="Activă" && <button className="btn btn-danger btn-sm" disabled={busy} onClick={()=>action(()=>revokeInvitation(item.id))}>Revocă</button>}</div></li>;})}</ul>}
        </section>
        </div></>;
}
export default function EmployeesPage() {
    const {company,membership,refresh}=useCompany();return <Employees key={company.id} company={company} membership={membership} refresh={refresh}/>;
}
