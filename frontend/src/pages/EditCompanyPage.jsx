import {useState} from "react";
import {Link, useNavigate} from "react-router";
import {useCompany} from "../hooks/useCompany";
import {useCompanyDetails} from "../hooks/useCompanyDetails";
import {updateCompany} from "../services/companyService";
import CompanyFields from "../components/CompanyFields";
import PageHeader from "../components/PageHeader";
function EditForm({data,refresh}) {
    const [details,setDetails]=useState(data),[busy,setBusy]=useState(false),[error,setError]=useState("");
    const navigate=useNavigate();
    async function save(event) {event.preventDefault();setBusy(true);setError("");
        try {await updateCompany(data.id,details);await refresh();navigate("/company");}
        catch(err){setError(err.message);}finally{setBusy(false);}}
    return <form onSubmit={save} className="grid gap-4"><CompanyFields value={details} onChange={setDetails} disabled={busy}/>
        {error && <p role="alert">{error}</p>}
        <div className="flex flex-wrap gap-2.5"><button className="btn" disabled={busy}>{busy ? "Se salvează…" : "Salvează firma"}</button>
            <Link to="/company" className="btn btn-secondary">Anulează</Link></div></form>;
}
export default function EditCompanyPage() {
    const {company,membership,refresh}=useCompany(); const {data,loading,error}=useCompanyDetails(company.id);
    return <><PageHeader eyebrow="Firmă" title="Editare firmă" description="Telefonul și website-ul sunt opționale."/>
        <div className="grid gap-5">
            {!membership.company_complete && <p className="notice">Completează datele firmei înainte de a invita angajați.</p>}
            <section className="card">{loading ? <p className="loading">Se încarcă…</p> : error ? <p role="alert">{error}</p> : <EditForm key={company.id} data={data} refresh={refresh}/>}</section>
        </div></>;
}
