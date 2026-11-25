import { Route, Routes, Navigate } from "react-router";
import { useAuth } from "./hooks/useAuth";
import CompanyProvider from "./context/CompanyProvider";
import AppLayout from "./components/AppLayout";
import { RequireAuth, RequireCompany, RequireProfile } from "./components/RouteGuards";
import PublicEventPage from "./pages/PublicEventPage";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import SignUpPage from "./pages/SignUpPage";
import NewEventPage from "./pages/NewEventPage";
import IndexPage from "./pages/IndexPage";
import HomePage from "./pages/HomePage";
import ProfilePage from "./pages/ProfilePage";
import CompanyPage from "./pages/CompanyPage";
import CompanySetupPage from "./pages/CompanySetupPage";
import JoinCompanyPage from "./pages/JoinCompanyPage";
import EmployeesPage from "./pages/EmployeesPage";
import EditCompanyPage from "./pages/EditCompanyPage";
import ClientsPage from "./pages/ClientsPage";
import CompanyEventsPage from "./pages/CompanyEventsPage";
import NotFoundPage from "./pages/NotFoundPage";

export default function App() {
    const {user,loading}=useAuth();
    if(loading) return <div className="grid min-h-screen place-content-center"><p className="loading">Se verifică sesiunea…</p></div>;
    return <CompanyProvider key={user?.id ?? "guest"}><Routes><Route element={<AppLayout/>}>
        <Route path="/" element={user ? <Navigate to="/home" replace/> : <IndexPage/>}/>
        <Route path="/login" element={<LoginPage/>}/>
        <Route path="/signup" element={<SignUpPage/>}/>
        <Route path="/demo" element={<Navigate to="/events/pechea-2024-09" replace/>}/>
        <Route path="/join" element={<JoinCompanyPage/>}/>
        <Route path="/events/:slug" element={<PublicEventPage/>}/>
        <Route element={<RequireAuth/>}>
            <Route element={<RequireProfile/>}>
            <Route path="/home" element={<HomePage/>}/>
            <Route path="/dashboard" element={<DashboardPage/>}/>
            <Route path="/events/new" element={<NewEventPage/>}/>
            </Route>
            <Route path="/profile" element={<ProfilePage/>}/>
            <Route path="/company/setup" element={<CompanySetupPage/>}/>
            <Route element={<RequireCompany/>}>
                <Route path="/company" element={<CompanyPage/>}/>
                <Route path="/company/clients" element={<ClientsPage/>}/>
                <Route path="/company/events" element={<CompanyEventsPage/>}/>
            </Route>
            <Route element={<RequireCompany admin/>}>
                <Route path="/company/employees" element={<EmployeesPage/>}/>
                <Route path="/company/edit" element={<EditCompanyPage/>}/>
            </Route>
        </Route>
        <Route path="*" element={<NotFoundPage/>}/>
    </Route></Routes></CompanyProvider>;
}
