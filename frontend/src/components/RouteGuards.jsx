import { Navigate, Outlet, useLocation } from "react-router";
import { useAuth } from "../hooks/useAuth";
import { useCompany } from "../hooks/useCompany";

export function RequireAuth() {
    const {user,loading} = useAuth();
    const location=useLocation();
    if(loading) return <p className="loading">Se verifică sesiunea…</p>;
    return user ? <Outlet/> : <Navigate to="/login" state={{from:location.pathname+location.search}} replace/>;
}
export function RequireCompany({admin=false}) {
    const {company,membership,isAdmin,loading,error} = useCompany();
    if(loading) return <p className="loading">Se încarcă firma…</p>;
    if(error) return <p role="alert">{error}</p>;
    if(!company) return <Navigate to="/company/setup" replace/>;
    if(!membership.profile_complete) return <Navigate to="/profile" replace/>;
    if(admin && !isAdmin) return <p role="alert">Pagina este disponibilă doar administratorului firmei.</p>;
    return <Outlet/>;
}

export function RequireProfile() {
    const {membership,loading,error}=useCompany();
    if(loading) return <p className="loading">Se verifică profilul…</p>;
    if(error) return <p role="alert">{error}</p>;
    return membership && !membership.profile_complete ? <Navigate to="/profile" replace/> : <Outlet/>;
}
