import { Brand } from "./AppLayout";

export default function AuthLayout({title,subtitle,asideTitle,asideText,children}) {
    return <div className="mx-auto my-4 grid max-w-[980px] overflow-hidden rounded-2xl border border-line bg-white shadow-soft md:min-h-[560px] md:grid-cols-2">
        <aside className="relative hidden flex-col justify-between gap-8 overflow-hidden bg-deep-teal p-10 text-white md:flex">
            <div className="absolute -bottom-20 -right-20 size-72 rounded-full bg-dusty-aqua/35"/>
            <div className="absolute bottom-16 right-10 size-36 rounded-full bg-sand/35"/>
            <div className="relative"><Brand light/></div>
            <div className="relative"><h2 className="mb-3 text-2xl">{asideTitle}</h2><p className="text-mist">{asideText}</p></div>
            <p className="relative text-sm text-mist">Date Copernicus Sentinel · OpenStreetMap</p>
        </aside>
        <div className="flex flex-col justify-center gap-5 p-7 sm:p-12">
            <div><h1 className="text-[1.75rem]">{title}</h1>{subtitle && <p className="mt-1 text-muted">{subtitle}</p>}</div>
            {children}
        </div>
    </div>;
}
