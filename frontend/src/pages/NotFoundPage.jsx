import { Link } from "react-router";
export default function NotFoundPage() {
    return <div className="px-4 py-20 text-center"><div className="text-7xl font-extrabold leading-none text-mist">404</div>
        <h1 className="mt-3 text-[1.75rem]">Pagina nu există</h1>
        <p className="mb-6 mt-2 text-muted">Linkul poate fi greșit sau pagina a fost mutată.</p><Link to="/" className="btn">Înapoi la început</Link></div>;
}
