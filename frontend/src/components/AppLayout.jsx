import { Link, NavLink, Outlet } from "react-router";
import { useAuth } from "../hooks/useAuth";
import { useCompany } from "../hooks/useCompany";
import { logout } from "../services/authService";
import { useState } from "react";
import Icon from "./Icon";
import logo from "../assets/logo.png";

export function Brand({to="/",light=false}) {
    return <Link to={to} className={`inline-flex items-center gap-2.5 text-lg font-extrabold tracking-tight no-underline ${light ? "text-white" : "text-deep-teal"}`}>
        <img src={logo} alt="" className="size-9"/>FloodLens</Link>;
}

function NavItem({to,icon,children,end}) {
    return <NavLink to={to} end={end} className={({isActive})=>`flex items-center gap-3 rounded-lg px-3 py-2 text-[0.92rem] font-medium no-underline transition
        ${isActive ? "bg-mist/20 text-white [&>svg]:text-sand" : "text-[#C9D6D1] hover:bg-white/7 hover:text-white"}`}>
        <Icon name={icon} className="size-[18px] shrink-0"/>{children}</NavLink>;
}

function SectionLabel({children}) {
    return <span className="mb-1.5 px-3 text-[0.7rem] font-bold uppercase tracking-widest text-dusty-aqua">{children}</span>;
}

function AppShell() {
    const {user} = useAuth();
    const {memberships,membership,company,isAdmin,selectCompany,error} = useCompany();
    const [logoutError,setLogoutError] = useState("");
    const [open,setOpen] = useState(false);
    async function leave() {
        try { const result=await logout(); if(result.error) throw result.error; }
        catch(err) { setLogoutError(err.message); }
    }
    const profile=membership?.profile;
    const displayName=profile?.first_name ? `${profile.first_name} ${profile.last_name}` : user.email;
    const initials=profile?.first_name ? profile.first_name[0]+profile.last_name[0] : user.email[0];
    const companyReady=company && membership.profile_complete;
    return <div className="min-h-screen lg:grid lg:grid-cols-[264px_1fr]">
        <div className="sticky top-0 z-[1001] flex items-center justify-between gap-4 bg-deep-teal px-4 py-3 lg:hidden">
            <Brand to="/home" light/>
            <button className="btn p-2 border-white/20 bg-transparent" aria-label={open ? "Închide meniul" : "Deschide meniul"}
                aria-expanded={open} onClick={()=>setOpen(!open)}><Icon name={open ? "close" : "menu"} className="size-5"/></button>
        </div>
        <aside onClick={e=>{ if(e.target.closest("a")) setOpen(false); }}
            className={`fixed inset-y-0 left-0 z-[1002] flex w-[min(264px,85vw)] flex-col gap-5 overflow-y-auto bg-deep-teal px-4 py-5 text-[#DDE6E2] transition-transform
                lg:sticky lg:top-0 lg:h-screen lg:w-auto lg:translate-x-0 ${open ? "translate-x-0 shadow-[0_0_0_100vmax_rgb(15_28_30/.45)]" : "-translate-x-full"}`}>
            <div className="px-1.5"><Brand to="/home" light/></div>
            {company && <div className="grid gap-1 rounded-lg bg-white/6 p-3">
                <span className="text-[0.7rem] font-bold uppercase tracking-widest text-dusty-aqua">Firma activă</span>
                {memberships.length>1
                    ? <select aria-label="Firma activă" value={company.id} onChange={e=>selectCompany(e.target.value)}
                        className="!border-white/15 !bg-white/10 !py-1.5 !text-sm !text-white [&>option]:text-deep-teal">
                        {memberships.map(row=><option key={row.company_id} value={row.company_id}>{row.companies?.name}</option>)}
                    </select>
                    : <strong className="truncate text-[0.92rem] text-white">{company.name}</strong>}
            </div>}
            <NavLink to="/events/new" className="btn btn-sand"><Icon name="plus" className="size-[18px]"/>Eveniment nou</NavLink>
            <nav className="grid gap-0.5" aria-label="Navigare principală">
                <SectionLabel>General</SectionLabel>
                <NavItem to="/home" icon="home">Acasă</NavItem>
                <NavItem to="/dashboard" icon="dashboard">Dashboard</NavItem>
                <NavItem to="/profile" icon="user">Profil</NavItem>
            </nav>
            <nav className="grid gap-0.5" aria-label="Firmă">
                <SectionLabel>Firmă</SectionLabel>
                {companyReady && <>
                    <NavItem to="/company" icon="building" end>Date firmă</NavItem>
                    <NavItem to="/company/events" icon="map">Evenimente firmă</NavItem>
                    <NavItem to="/company/clients" icon="briefcase">{isAdmin ? "Gestionare clienți" : "Clienți"}</NavItem>
                    {isAdmin && <>
                        <NavItem to="/company/employees" icon="users">Angajați</NavItem>
                        <NavItem to="/company/edit" icon="edit">Editare firmă</NavItem>
                    </>}
                </>}
                <NavItem to="/company/setup" icon="mail">{company ? "Firmă nouă / invitație" : "Creează firmă / invitație"}</NavItem>
            </nav>
            <div className="mt-auto grid gap-2 border-t border-white/10 pt-4">
                <div className="flex min-w-0 items-center gap-2.5 px-1.5 py-1">
                    <span className="grid size-9 shrink-0 place-items-center rounded-full bg-sand text-sm font-bold uppercase text-deep-teal">{initials}</span>
                    <span className="grid min-w-0"><strong className="truncate text-sm text-white">{displayName}</strong>
                        <span className="text-xs text-mist">{company ? (isAdmin ? "Administrator" : "Angajat") : "Cont personal"}</span></span>
                </div>
                <button className="btn justify-start border-white/15 bg-transparent font-medium text-[#C9D6D1] hover:border-white/25 hover:bg-white/7 hover:text-white"
                    onClick={leave}><Icon name="logout" className="size-[18px]"/>Deconectare</button>
            </div>
        </aside>
        <main className="min-w-0 px-4 pb-12 pt-5 sm:px-8 lg:pt-8">
            <div className="mx-auto grid max-w-[1120px] gap-5">
                {(error || logoutError) && <p role="alert">{error || logoutError}</p>}
                {membership && !membership.profile_complete && <p className="notice">Completează <Link to="/profile">profilul profesional</Link> pentru {company.name} ca să ai acces la datele firmei.</p>}
                <div><Outlet/></div>
            </div>
        </main>
    </div>;
}

function PublicShell() {
    const link=({isActive})=>`rounded-lg px-3 py-2 text-[0.92rem] font-medium no-underline hover:bg-subtle ${isActive ? "bg-subtle" : ""}`;
    return <div className="flex min-h-screen flex-col">
        <header className="sticky top-0 z-[1001] border-b border-line bg-canvas/90 backdrop-blur">
            <div className="mx-auto flex max-w-[1180px] items-center justify-between gap-4 px-4 py-3 sm:px-8">
                <Brand/>
                <nav className="flex items-center gap-1.5" aria-label="Navigare principală">
                    <NavLink to="/demo" className={`${link({})} max-sm:hidden`}>Demo</NavLink>
                    <NavLink to="/login" className={link}>Autentificare</NavLink>
                    <Link to="/signup" className="btn btn-sm">Creează cont</Link>
                </nav>
            </div>
        </header>
        <main className="mx-auto w-full max-w-[1180px] flex-1 px-4 pb-16 pt-8 sm:px-8"><Outlet/></main>
        <footer className="border-t border-line px-4 py-6 text-center text-sm text-muted">
            © {new Date().getFullYear()} FloodLens · Date Copernicus Sentinel &amp; OpenStreetMap
        </footer>
    </div>;
}

export default function AppLayout() {
    const {user} = useAuth();
    return user ? <AppShell/> : <PublicShell/>;
}
