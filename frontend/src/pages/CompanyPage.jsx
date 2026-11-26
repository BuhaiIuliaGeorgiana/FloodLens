import {Link} from "react-router";
import {useCompany} from "../hooks/useCompany";
import {useCompanyDetails} from "../hooks/useCompanyDetails";
import Icon from "../components/Icon";
import PageHeader from "../components/PageHeader";
export default function CompanyPage() {
    const {company,isAdmin}=useCompany(); const {data,loading,error}=useCompanyDetails(company.id);
    const fields=[["name","Denumire legală"],["tax_id","CUI / identificator fiscal"],["country","Țară"],["address","Adresă sediu"],["contact_email","Email contact"],["phone","Telefon"],["website","Website"]];
    return <><PageHeader eyebrow="Firmă" title="Date firmă" description="Informațiile oficiale ale firmei, vizibile tuturor membrilor.">
            {isAdmin && <Link to="/company/edit" className="btn btn-secondary"><Icon name="edit" className="size-[18px]"/>Editează datele firmei</Link>}
        </PageHeader>
        <section className="card">{loading ? <p className="loading">Se încarcă…</p> : error ? <p role="alert">{error}</p> :
            <dl className="grid grid-cols-[repeat(auto-fit,minmax(min(220px,100%),1fr))] gap-x-8 gap-y-5">{fields.map(([key,label])=><div key={key}>
                <dt className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted">{label}</dt>
                <dd className={data[key] ? "break-words font-medium" : "italic text-muted"}>{data[key] || "Necompletat"}</dd></div>)}</dl>}
        </section></>;
}
