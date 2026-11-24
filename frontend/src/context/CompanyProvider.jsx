import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "../hooks/useAuth";
import { getMemberships } from "../services/companyService";
import { CompanyContext } from "./CompanyContext";
export default function CompanyProvider({children}) {
    const {user}=useAuth();
    const userId=user?.id;
    const [state,setState]=useState({owner:null,rows:[],loading:true,error:""});
    const [selected,setSelected]=useState("");
    const sequence=useRef(0);
    const refresh=useCallback(async()=>{
        const request=++sequence.current;
        if(!userId) { setState({owner:null,rows:[],loading:false,error:""}); return []; }
        try {
            const rows=await getMemberships();
            if(request===sequence.current) setState({owner:userId,rows,loading:false,error:""});
            return rows;
        } catch(error) {
            if(request===sequence.current) setState({owner:userId,rows:[],loading:false,error:error.message});
            throw error;
        }
    },[userId]);
    useEffect(()=>{ refresh().catch(()=>{}); return ()=>{sequence.current++;}; },[refresh]);
    // Ignoram raspunsurile pentru sesiunea anterioara.
    const rows=userId && state.owner===userId ? state.rows : [];
    const membership=rows.find(row=>row.company_id===selected) ?? rows[0] ?? null;
    return <CompanyContext.Provider value={{memberships:rows,membership,company:membership?.companies ?? null,
        isAdmin:membership?.role==="admin",loading:Boolean(userId && (state.owner!==userId || state.loading)),
        error:userId && state.owner===userId ? state.error : "",selectCompany:setSelected,refresh}}>{children}</CompanyContext.Provider>;
}
