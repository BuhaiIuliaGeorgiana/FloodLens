import { Link , useNavigate, useLocation, Navigate} from "react-router";
import {useState} from "react";
import { useAuth } from "../hooks/useAuth";
import { safeReturnPath } from "../utils/eventInput";
import {register} from "../services/authService";
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
            setError("Passwords do not match.");
            return;
        }
        if(password.length < 6){
            setError("Password must have at least 6 characters!");
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
                setMessage("Check email confirmation link.");
            }
        }catch(err){
            setError(err.message || "An unexpected error occured.");
        }finally{
            setLoading(false);
        }
    }
    if(user) return <Navigate to={next} replace/>;
    return(
        <div>
            <h1>Welcome</h1>
            <form onSubmit={handleSignUp}>
                <label htmlFor="email">Email:</label>
                <input  id ="email" 
                        type ="email" 
                        value = {email}
                        onChange = {(e)=> setEmail(e.target.value)}
                        required
                        />

                <label htmlFor="password">Password:</label>
                <input id ="password" 
                        type ="password" 
                        value = {password}
                        onChange = {(e)=> setPassword(e.target.value)}
                        required
                        />

                <label htmlFor="confirmPassword">Password:</label>
                <input id ="confirmPassword" 
                        type ="password" 
                        value = {confirmPassword}
                        onChange = {(e)=> setConfirmPassword(e.target.value)}
                        required
                        />

                {error && <p role = "alert">{error}</p>}

                <button type = "submit" disabled={loading}>Sign up</button>
            </form>

            <p>
                Already have an account?
                <Link to="/login" state={{from:next}}>
                {loading ? "Logging in.." : "Log in"}
                </Link>

                {message ? <p>{message} </p> : <p></p>}
            </p>
        </div>
    );
}

export default SignUpPage;