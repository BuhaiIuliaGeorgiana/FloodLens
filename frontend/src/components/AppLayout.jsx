import { Link, Outlet } from "react-router";
import { useAuth } from "../hooks/useAuth";
import { useCompany } from "../hooks/useCompany";
import { logout } from "../services/authService";
import { useState } from "react";

export default function AppLayout() {
    const {user} = useAuth();
    const {memberships,membership,company,isAdmin,selectCompany,error} = useCompany();
    const [logoutError,setLogoutError] = useState("");
    async function leave() {
        try { const result=await logout(); if(result.error) throw result.error; }
        catch(err) { setLogoutError(err.message); }
    }
    return <>
        <header><Link to={user ? "/dashboard" : "/"}>FloodLens</Link>
            <nav aria-label="Navigare principala">
                {user ? <>
                    <Link to="/home">Home</Link>{" · "}<Link to="/dashboard">Dashboard</Link>{" · "}
                    <Link to="/events/new">Eveniment nou</Link>{" · "}<Link to="/profile">Profil</Link>{" · "}
                    <Link to="/company/setup">Firma / invitație</Link>{" · "}
                    {company && membership.profile_complete && <><Link to="/company">Date firmă</Link>{" · "}
                        <Link to="/company/clients">Clienți</Link>{" · "}
                        <Link to="/company/events">Evenimente firmă</Link>{" · "}
                        {isAdmin && <><Link to="/company/employees">Angajați</Link>{" · "}<Link to="/company/edit">Editare firmă</Link>{" · "}</>}
                    </>}
                    <button onClick={leave}>Logout</button>
                </> : <><Link to="/login">Login</Link>{" · "}<Link to="/signup">Signup</Link>{" · "}<Link to="/demo">Demo</Link></>}
            </nav>
            {memberships.length>1 && <label>Firma activă <select value={company?.id ?? ""} onChange={e=>selectCompany(e.target.value)}>
                {memberships.map(row=><option key={row.company_id} value={row.company_id}>{row.companies?.name}</option>)}
            </select></label>}
        </header>
        {(error || logoutError) && <p role="alert">{error || logoutError}</p>}
        {membership && !membership.profile_complete && <p>Completează <Link to="/profile">profilul profesional</Link> pentru {company.name}.</p>}
        <Outlet/>
    </>;
}
