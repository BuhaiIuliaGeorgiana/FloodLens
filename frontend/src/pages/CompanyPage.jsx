import {Link} from "react-router";
import {useCompany} from "../hooks/useCompany";
import {useCompanyDetails} from "../hooks/useCompanyDetails";
export default function CompanyPage() {
    const {company,isAdmin}=useCompany(); const {data,loading,error}=useCompanyDetails(company.id);
    const fields=[["name","Denumire legală"],["tax_id","CUI / identificator fiscal"],["country","Țară"],["address","Adresă sediu"],["contact_email","Email contact"],["phone","Telefon"],["website","Website"]];
    return <main><h1>Date firmă</h1>{loading ? <p>Se încarcă…</p> : error ? <p role="alert">{error}</p> :
        <dl>{fields.map(([key,label])=><div key={key}><dt>{label}</dt><dd>{data[key] || "Necompletat"}</dd></div>)}</dl>}
        {isAdmin && <Link to="/company/edit">Editează datele firmei</Link>}</main>;
}
