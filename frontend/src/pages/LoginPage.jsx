import { Link, useNavigate, useLocation, Navigate } from "react-router";
import { useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { safeReturnPath } from "../utils/eventInput";
import { login } from "../services/authService";
import AuthLayout from "../components/AuthLayout";

function LoginPage() {
    const [email,setEmail] = useState("");
    const [password,setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    const navigate = useNavigate();
    const location=useLocation();
    const {user}=useAuth();
    const next=safeReturnPath(location.state?.from);
    async function handleLogin(event){
        event.preventDefault();

        setLoading(true)
        setError("");

        

        try{
            const result = await login(email,password)

            if(result.error){
                setError(result.error.message);
                return;
            }

            navigate(next, {replace:true});
        }catch(err){
            setError(err.message || "A apărut o eroare neașteptată.");
        }finally{
            setLoading(false);
        }
    }
    if(user) return <Navigate to={next} replace/>;
    return (
        <AuthLayout title="Bine ai revenit" subtitle="Autentifică-te pentru a continua."
            asideTitle="Inundațiile, văzute de sus." asideText="Evenimentele, hărțile și echipa ta te așteaptă în dashboard.">
            <form onSubmit={handleLogin} className="grid gap-4">
                <label htmlFor="email" className="field">Email
                    <input id="email" type="email" autoComplete="email" value={email}
                        onChange={(e)=>setEmail(e.target.value)} required/>
                </label>
                <label htmlFor="password" className="field">Parolă
                    <input id="password" type="password" autoComplete="current-password" value={password}
                        onChange={(e)=>setPassword(e.target.value)} required/>
                </label>
                {error && <p role="alert">{error}</p>}
                <button type="submit" className="btn w-full" disabled={loading}>
                    {loading ? "Se autentifică…" : "Autentificare"}
                </button>
            </form>
            <p className="text-center text-sm text-muted">
                Nu ai cont? <Link to="/signup" state={{from:next}}>Creează unul</Link>
            </p>
        </AuthLayout>
    );
}

export default LoginPage;