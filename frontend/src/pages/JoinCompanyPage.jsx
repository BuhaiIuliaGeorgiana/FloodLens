import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { useAuth } from "../hooks/useAuth";
import { useCompany } from "../hooks/useCompany";
import { acceptInvitation } from "../services/companyService";
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
    return <main><h1>Alătură-te firmei</h1><p>Folosește contul cu adresa invitată și confirmă emailul înainte de acceptare.</p>{user && <p>Email cont: {user.email}</p>}
        {user ? <form onSubmit={join}><label>Cod invitație <input value={token} onChange={e=>setToken(e.target.value)} required/></label>
            <button disabled={busy}>Acceptă invitația</button></form>
            : <p><Link to="/login" state={{from:"/join"}}>Autentificare</Link>{" / "}<Link to="/signup" state={{from:"/join"}}>Cont nou</Link></p>}
        {error && <p role="alert">{error}</p>}
    </main>;
}
