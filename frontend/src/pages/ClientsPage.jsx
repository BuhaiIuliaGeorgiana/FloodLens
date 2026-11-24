import { useCompany } from "../hooks/useCompany";
export default function ClientsPage() {
    const {isAdmin}=useCompany();
    return <main><h1>{isAdmin ? "Gestionare clienți" : "Clienți"}</h1><section aria-label="Lista clienților"/></main>;
}
