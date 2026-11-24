import {useState} from "react";
import {useNavigate} from "react-router";
import {useCompany} from "../hooks/useCompany";
import {useCompanyDetails} from "../hooks/useCompanyDetails";
import {updateCompany} from "../services/companyService";
import CompanyFields from "../components/CompanyFields";
function EditForm({data,refresh}) {
    const [details,setDetails]=useState(data),[busy,setBusy]=useState(false),[error,setError]=useState("");
    const navigate=useNavigate();
    async function save(event) {event.preventDefault();setBusy(true);setError("");
        try {await updateCompany(data.id,details);await refresh();navigate("/company");}
        catch(err){setError(err.message);}finally{setBusy(false);}}
    return <form onSubmit={save}><CompanyFields value={details} onChange={setDetails} disabled={busy}/>
        <button disabled={busy}>Salvează firma</button>{error && <p role="alert">{error}</p>}</form>;
}
export default function EditCompanyPage() {
    const {company,membership,refresh}=useCompany(); const {data,loading,error}=useCompanyDetails(company.id);
    return <main><h1>Editare firmă</h1>{!membership.company_complete && <p>Completează datele firmei înainte de a invita angajați.</p>}
        {loading ? <p>Se încarcă…</p> : error ? <p role="alert">{error}</p> : <EditForm key={company.id} data={data} refresh={refresh}/>}</main>;
}
