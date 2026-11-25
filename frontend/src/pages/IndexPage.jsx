import { Link } from "react-router";
import Icon from "../components/Icon";
import logo from "../assets/logo.png";

const FEATURES = [
    ["satellite","Sentinel-1 radar","Detectăm apa prin nori și noaptea, comparând imaginile radar dinainte și din timpul inundației."],
    ["layers","Sentinel-2 optic","Indicii NDWI și MNDWI confirmă suprafețele acoperite de apă acolo unde cerul este senin."],
    ["road","Expunere OpenStreetMap","Drumuri, clădiri și terenuri agricole din zona afectată, pentru o estimare rapidă a impactului."],
    ["shield","Validare Copernicus EMS","Rezultatele sunt comparate cu hărțile oficiale de urgență, unde acestea există."],
];
const STEPS = [
    ["Desenează zona","Alegi pe hartă zona afectată și perioada inundației."],
    ["Procesăm datele","Pipeline-ul descarcă și analizează imaginile satelitare disponibile."],
    ["Analizezi harta","Vezi straturile suprapuse, datele de achiziție și limitările analizei."],
    ["Colaborezi","Partajezi evenimentul cu echipa firmei și cu clienții tăi."],
];
const grid = "grid gap-4 grid-cols-[repeat(auto-fill,minmax(min(220px,100%),1fr))]";

function SectionHeader({eyebrow,title,children}) {
    return <div className="mb-8 max-w-2xl"><div className="eyebrow">{eyebrow}</div>
        <h2 className="text-[1.7rem]">{title}</h2>{children && <p className="mt-2 text-muted">{children}</p>}</div>;
}

export default function IndexPage() {
    return <>
        <section className="grid items-center gap-8 pb-16 pt-4 md:grid-cols-[1.15fr_.85fr] md:gap-12 md:pt-12">
            <div>
                <div className="eyebrow">Monitorizare inundații din satelit</div>
                <h1 className="mb-5 text-[clamp(2.1rem,4.5vw,3.3rem)] leading-[1.08] tracking-[-0.025em]">
                    Vezi unde a ajuns apa, <span className="text-dusty-aqua">fără să aștepți la fața locului.</span></h1>
                <p className="mb-7 max-w-xl text-lg text-muted">FloodLens combină imagini Sentinel-1 și Sentinel-2 cu date OpenStreetMap pentru a cartografia rapid zonele inundate și infrastructura expusă.</p>
                <div className="flex flex-wrap gap-3">
                    <Link to="/demo" className="btn btn-lg">Vezi demo <Icon name="arrowRight" className="size-[18px]"/></Link>
                    <Link to="/signup" className="btn btn-lg btn-secondary">Creează cont</Link>
                </div>
                <div className="mt-8 flex flex-wrap gap-6 text-sm text-muted">
                    {[["10 m","rezoluție spațială"],["Radar + optic","surse combinate"],["Copernicus","date deschise"]].map(([value,label])=>
                        <div key={value}><strong className="block text-base text-deep-teal">{value}</strong>{label}</div>)}
                </div>
            </div>
            <div className="relative aspect-square w-full max-w-[260px] justify-self-center max-md:order-first md:max-w-[420px]">
                <div className="absolute inset-[6%] rounded-full bg-[radial-gradient(circle_at_30%_30%,var(--color-mist),var(--color-cloud)_70%)]"/>
                <img src={logo} alt="Logo FloodLens: satelit deasupra unui râu" className="relative size-full rounded-full object-contain mix-blend-multiply"/>
            </div>
        </section>

        <section className="py-14">
            <SectionHeader eyebrow="Ce primești" title="Surse multiple, o singură hartă">
                Fiecare strat este însoțit de data observației și de o explicație a limitărilor, ca să știi cât de mult te poți baza pe el.
            </SectionHeader>
            <div className={grid}>{FEATURES.map(([icon,title,text],i)=>
                <div key={title} className="card">
                    <div className={`icon-chip mb-4 ${i%2 ? "icon-chip-sand" : ""}`}><Icon name={icon} className="size-5"/></div>
                    <h3 className="mb-1.5 text-[1.05rem]">{title}</h3><p className="text-[0.92rem] text-muted">{text}</p>
                </div>)}
            </div>
        </section>

        <section className="py-14">
            <SectionHeader eyebrow="Cum funcționează" title="De la zonă desenată la hartă analizată"/>
            <ol className={grid}>{STEPS.map(([title,text],i)=>
                <li key={title} className="card">
                    <div className="mb-2 text-xl font-extrabold text-sand">{String(i+1).padStart(2,"0")}</div>
                    <h3 className="mb-1.5">{title}</h3><p className="text-[0.92rem] text-muted">{text}</p>
                </li>)}
            </ol>
        </section>

        <section className="py-14">
            <div className="flex flex-wrap items-center justify-between gap-6 rounded-2xl bg-deep-teal p-7 text-white sm:p-12">
                <div><h2 className="mb-1.5 text-2xl">Lucrezi într-o echipă?</h2>
                    <p className="text-mist">Creează o firmă, invită angajați și gestionează evenimentele și clienții într-un singur loc.</p></div>
                <div className="flex flex-wrap gap-3">
                    <Link to="/signup" className="btn btn-lg btn-sand">Începe acum</Link>
                    <Link to="/demo" className="btn btn-lg btn-ghost text-white hover:bg-white/10">Explorează demo-ul</Link>
                </div>
            </div>
        </section>
    </>;
}
