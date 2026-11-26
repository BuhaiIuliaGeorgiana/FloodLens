export default function PageHeader({eyebrow,title,description,children}) {
    return <div className="mb-7 flex flex-wrap items-end justify-between gap-4"><div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1 className="text-[1.75rem]">{title}</h1>{description && <p className="mt-1.5 text-muted">{description}</p>}
    </div>{children && <div className="flex flex-wrap items-center gap-2.5">{children}</div>}</div>;
}
