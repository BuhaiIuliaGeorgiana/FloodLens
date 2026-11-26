import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { useAuth } from "../hooks/useAuth";
import { useCompany } from "../hooks/useCompany";
import { acceptInvitation } from "../services/companyService";
import Icon from "../components/Icon";
import PageHeader from "../components/PageHeader";
export default function JoinCompanyPage() {
    const [params]=useSearchParams();
    const navigate=useNavigate();
    const {user}=useAuth();
    const {refresh,selectCompany}=useCompany();
    const [token,setToken]=useState(()=>params.get("code") ?? sessionStorage.getItem("floodlens_invitation") ?? "");
    const [error,setError]=useState(""), [busy,setBusy]=useState(false);
    useEffect(()=>{
        const code=params.get("code");
        if(code) { sessionStorage.setItem("floodlens_invitation",code); navigate("/join",{replace:true}); }
    },[params,navigate]);
    async function join(event) {
        event.preventDefault(); setBusy(true); setError("");
        try {
            const id=await acceptInvitation(token); sessionStorage.removeItem("floodlens_invitation");
            selectCompany(id); await refresh(); navigate("/profile");
        } catch(err) { setError(err.message); } finally { setBusy(false); }
    }
    return <div className="mx-auto max-w-xl">
        <PageHeader eyebrow="Invitație" title="Alătură-te firmei" description="Folosește contul cu adresa invitată și confirmă emailul înainte de acceptare."/>
        <section className="card">
            {user ? <form onSubmit={join} className="grid gap-4">
                <p className="text-sm text-muted">Cont: <strong className="text-deep-teal">{user.email}</strong></p>
                <label className="field">Cod invitație<input value={token} onChange={e=>setToken(e.target.value)} required/></label>
                {error && <p role="alert">{error}</p>}
                <button className="btn" disabled={busy}>{busy ? "Se verifică…" : "Acceptă invitația"}</button>
            </form>
            : <div className="grid gap-4"><p>Autentifică-te sau creează un cont pentru a accepta invitația. Codul este păstrat.</p>
                <div className="flex flex-wrap gap-2.5">
                    <Link to="/login" state={{from:"/join"}} className="btn">Autentificare</Link>
                    <Link to="/signup" state={{from:"/join"}} className="btn btn-secondary">Cont nou</Link>
                </div>{error && <p role="alert">{error}</p>}</div>}
        </section>
        {user && <p className="mt-4 text-sm"><Link to="/company/setup" className="inline-flex items-center gap-1"><Icon name="arrowLeft" className="size-3.5"/> Creează o firmă nouă în schimb</Link></p>}
    </div>;
}
