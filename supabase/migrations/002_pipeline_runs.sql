-- Processing runs started from the "Proceseaza / Actualizeaza" button.
-- The Python service writes here with the service role key (bypasses RLS);
-- the app only reads. Run in the Supabase SQL editor. Safe to run more than once.

create table if not exists public.pipeline_runs (
    id uuid primary key default gen_random_uuid(),
    event_id uuid not null references public.flood_events(id) on delete cascade,
    status text not null default 'queued'
        check (status in ('queued', 'processing', 'ready', 'partial', 'waiting_for_data', 'failed')),
    -- Per source, e.g. {"sentinel1": "ready", "sentinel2": "waiting_for_data", "osm": "processing"}
    source_status jsonb not null default '{}'::jsonb,
    -- Reason for failed / waiting_for_data
    message text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists pipeline_runs_event_created_idx
    on public.pipeline_runs (event_id, created_at desc);

-- Keep updated_at current on every status change
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists pipeline_runs_set_updated_at on public.pipeline_runs;

create trigger pipeline_runs_set_updated_at
    before update on public.pipeline_runs
    for each row execute function public.set_updated_at();

alter table public.pipeline_runs enable row level security;

grant select on public.pipeline_runs to anon, authenticated;

-- Runs are visible to whoever can see the event. The subquery on
-- flood_events applies its own RLS, so private events stay private.
drop policy if exists "Read runs of visible events" on public.pipeline_runs;

create policy "Read runs of visible events"
    on public.pipeline_runs
    for select
    to anon, authenticated
    using (
        exists (
            select 1 from public.flood_events e
            where e.id = pipeline_runs.event_id
        )
    );

-- Link each layer to the run that produced it, so older results are kept
-- and the evolution can be shown. Null for layers added manually (Pechea).
alter table public.event_layers
    add column if not exists run_id uuid
    references public.pipeline_runs(id)
    on delete set null;
