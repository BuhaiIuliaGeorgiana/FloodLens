-- Allow logged-in users to create flood events from the app.
-- Run in the Supabase SQL editor. Safe to run more than once.
-- flood_events_visibility_check already exists on the table, so it is
-- not redefined here; it must allow 'public' and 'private'.

-- Who created the event (null for events added manually, e.g. Pechea)
alter table public.flood_events
    add column if not exists created_by uuid
    references auth.users(id)
    default auth.uid();

-- Ongoing events have no end date yet
alter table public.flood_events
    alter column ended_at drop not null;

-- New events are public unless the creator marks them private
alter table public.flood_events
    alter column visibility set default 'public';

-- Each event page is loaded by slug, so slugs must be unique
do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conname = 'flood_events_slug_key'
          and conrelid = 'public.flood_events'::regclass
    ) then
        alter table public.flood_events
            add constraint flood_events_slug_key unique (slug);
    end if;
end $$;

-- Table-level permission to insert; RLS below limits which rows
grant insert on public.flood_events to authenticated;

-- Logged-in users can create events, only in their own name
drop policy if exists "Authenticated users can create events" on public.flood_events;

create policy "Authenticated users can create events"
    on public.flood_events
    for insert
    to authenticated
    with check (created_by = auth.uid());

-- Creators can read their own events, including private ones.
-- Also needed so the app can read back the row it just inserted.
drop policy if exists "Creators can read own events" on public.flood_events;

create policy "Creators can read own events"
    on public.flood_events
    for select
    to authenticated
    using (created_by = auth.uid());
