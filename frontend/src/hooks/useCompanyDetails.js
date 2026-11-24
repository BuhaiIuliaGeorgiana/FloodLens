import {useEffect,useState} from "react";
import {getCompany} from "../services/companyService";
export function useCompanyDetails(id) {
    const [state,setState]=useState({id:null,data:null,error:""});
    useEffect(()=>{let ignore=false;
        getCompany(id).then(data=>{if(!ignore)setState({id,data,error:""});})
            .catch(error=>{if(!ignore)setState({id,data:null,error:error.message});});
        return ()=>{ignore=true;};
    },[id]);
    return state.id===id ? {...state,loading:false} : {data:null,error:"",loading:true};
}
