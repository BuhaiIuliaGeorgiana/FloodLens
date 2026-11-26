import { Link , useNavigate, useLocation, Navigate} from "react-router";
import {useState} from "react";
import { useAuth } from "../hooks/useAuth";
import { safeReturnPath } from "../utils/eventInput";
import {register} from "../services/authService";
import AuthLayout from "../components/AuthLayout";
function SignUpPage(){
    const [email,setEmail] = useState("");
    const [password,setPassword] = useState("");
    const [confirmPassword,setConfirmPassword] = useState("");
    const [error,setError] = useState("");
    const [message,setMessage] = useState("");
    const [loading,setLoading] = useState(false);

    const navigate = useNavigate();
    const location=useLocation();
    const {user}=useAuth();
    const next=safeReturnPath(location.state?.from);
    async function handleSignUp(event){
        event.preventDefault();

        setError("");
        setMessage("");
        if(password !== confirmPassword){
            setError("Parolele nu coincid.");
            return;
        }
        if(password.length < 6){
            setError("Parola trebuie să aibă cel puțin 6 caractere.");
            return;
        }

        setLoading(true);


        try{
            const result = await register(email,password);

            if (result.error){
                setError(result.error.message);
                return;
            }
            //session checking

            if(result.data.session){
                navigate(next, {replace:true});
            }else{
                setMessage("Ți-am trimis un email de confirmare. Deschide linkul din el pentru a activa contul.");
            }
        }catch(err){
            setError(err.message || "A apărut o eroare neașteptată.");
        }finally{
            setLoading(false);
        }
    }
    if(user) return <Navigate to={next} replace/>;
    return(
        <AuthLayout title="Creează cont" subtitle="Durează mai puțin de un minut."
            asideTitle="Analiză de inundații pentru echipa ta." asideText="Creează o firmă sau acceptă o invitație după ce îți confirmi adresa de email.">
            {message ? <p className="notice notice-success">{message}</p> :
            <form onSubmit={handleSignUp} className="grid gap-4">
                <label htmlFor="email" className="field">Email
                    <input id="email" type="email" autoComplete="email" value={email}
                        onChange={(e)=>setEmail(e.target.value)} required/>
                </label>
                <label htmlFor="password" className="field">Parolă
                    <input id="password" type="password" autoComplete="new-password" value={password}
                        onChange={(e)=>setPassword(e.target.value)} required/>
                    <span className="hint">Minimum 6 caractere.</span>
                </label>
                <label htmlFor="confirmPassword" className="field">Confirmă parola
                    <input id="confirmPassword" type="password" autoComplete="new-password" value={confirmPassword}
                        onChange={(e)=>setConfirmPassword(e.target.value)} required/>
                </label>
                {error && <p role="alert">{error}</p>}
                <button type="submit" className="btn w-full" disabled={loading}>
                    {loading ? "Se creează contul…" : "Creează cont"}
                </button>
            </form>}
            <p className="text-center text-sm text-muted">
                Ai deja cont? <Link to="/login" state={{from:next}}>Autentifică-te</Link>
            </p>
        </AuthLayout>
    );
}

export default SignUpPage;