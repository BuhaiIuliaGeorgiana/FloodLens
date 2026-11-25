import { supabase } from "../config/supabase";


export async function register(email,password){
    return await supabase.auth.signUp({
        email,
        password,
        options: {
            emailRedirectTo: window.location.origin + (sessionStorage.getItem("floodlens_invitation") ? "/join" : "/dashboard")
        }
    });
}

export async function login(email,password){
    return await supabase.auth.signInWithPassword({
        email,
        password
    });
}

export async function logout(){
    return await supabase.auth.signOut();
}