import { Link, useNavigate, useLocation, Navigate } from "react-router";
import { useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { safeReturnPath } from "../utils/eventInput";
import { login } from "../services/authService";

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
            setError(err.message || "An unexpected error occured.");
        }finally{
            setLoading(false);
        }
    }
    if(user) return <Navigate to={next} replace/>;
    return (
        <div>
            <h1>Login Page</h1>

            <form onSubmit = {handleLogin}>
                <label htmlFor="email">Email:</label>
                    <input  id="email"
                            value = {email}
                            type="email"
                            onChange={(e)=>setEmail(e.target.value)} 
                            required
                            />

                <label htmlFor="password">Password:</label>
                    <input  id="password" 
                            type="password"
                            value = {password}
                            onChange={(e)=>setPassword(e.target.value)} 
                            required
                            />

                <button type="submit" disabled = {loading} >
                    {loading ? "Logging in..." : "Login"}
                </button>
                {error ? <p>{error}</p> : <p></p>}
            </form>

            <p>
                Don't have an account?
                <Link to="/signup" state={{from:next}}>Sign up</Link>
            </p>
        </div>
    );
}

export default LoginPage;