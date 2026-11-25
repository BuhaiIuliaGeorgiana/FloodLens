import { Link } from "react-router";
import Icon from "./Icon";
import { formatDay } from "../utils/format";

export default function EventList({events,empty}) {
    if(events.length===0) return <div className="empty">{empty}</div>;
    return <ul className="divide-y divide-line">{events.map(event=><li key={event.id} className="flex flex-wrap items-center justify-between gap-4 py-3.5 first:pt-0 last:pb-0">
        <div className="grid min-w-0 gap-0.5">
            <Link to={`/events/${event.slug}`} className="font-semibold">{event.title}</Link>
            <span className="flex flex-wrap items-center gap-1 text-sm text-muted">
                <Icon name="calendar" className="size-3.5"/> {formatDay(event.started_at)}
                {event.ended_at && ` – ${formatDay(event.ended_at)}`}
                {(event.locality || event.county) && <> · <Icon name="pin" className="size-3.5"/> {[event.locality,event.county].filter(Boolean).join(", ")}</>}
            </span>
        </div>
        <div className="flex flex-wrap gap-1.5">
            {!event.ended_at && <span className="badge badge-warning">În desfășurare</span>}
            {event.company_id ? <span className="badge">Firmă</span>
                : event.visibility==="private" ? <span className="badge badge-muted"><Icon name="lock" className="size-3"/> Privat</span>
                : <span className="badge badge-sand">Public</span>}
        </div>
    </li>)}</ul>;
}
