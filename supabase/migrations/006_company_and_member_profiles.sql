-- Rulati o singura data, dupa 005. Nu adaugam procesare Sentinel-1.
begin;

alter table public.companies add column tax_id text;
alter table public.companies add column address text;
alter table public.companies add column contact_email text;
alter table public.companies add column phone text;
alter table public.company_invitations add column email text;
-- Linkurile vechi, fara destinatar, nu mai pot fi acceptate.
update public.company_invitations set revoked_at=coalesce(revoked_at,now()) where email is null and used_at is null;
grant select(email) on public.company_invitations to authenticated;

create table public.company_member_profiles (
 company_id uuid not null,
 user_id uuid not null,
 first_name text not null check (length(trim(first_name)) between 1 and 100),
 last_name text not null check (length(trim(last_name)) between 1 and 100),
 job_title text not null check (length(trim(job_title)) between 1 and 120),
 department text not null check (length(trim(department)) between 1 and 120),
 updated_at timestamptz not null default now(),
 updated_by uuid references auth.users(id),
 primary key(company_id,user_id),
 foreign key(company_id,user_id) references public.company_members(company_id,user_id) on delete cascade
);
alter table public.company_member_profiles enable row level security;
revoke all on public.company_member_profiles from anon,authenticated;
grant select on public.company_member_profiles to authenticated;
grant all on public.company_member_profiles to service_role;

create function public.fl_profile_complete(p_company uuid) returns boolean
language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.company_member_profiles where company_id=p_company and user_id=auth.uid());
$$;
create function public.fl_company_complete(p_company uuid) returns boolean
language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.companies where id=p_company
 and length(trim(name))>0 and length(trim(tax_id))>0 and length(trim(country))>0
 and length(trim(address))>0 and contact_email ~ '^[^[:space:]@]+@[^[:space:]@]+[.][^[:space:]@]+$');
$$;
create function public.fl_can_access_company(p_company uuid) returns boolean
language sql stable security definer set search_path='' as $$
 select public.fl_is_member(p_company) and public.fl_profile_complete(p_company);
$$;
revoke all on function public.fl_profile_complete(uuid),public.fl_company_complete(uuid),public.fl_can_access_company(uuid) from public;
grant execute on function public.fl_profile_complete(uuid),public.fl_can_access_company(uuid) to authenticated;

create policy fl_profile_read on public.company_member_profiles for select to authenticated
 using (user_id=auth.uid() or (public.fl_is_admin(company_id) and public.fl_profile_complete(company_id)));
-- Numai RPC-ul poate modifica profilul; nu primeste rolul de acces din browser.
create function public.fl_save_member_profile(p_company uuid,p_user uuid,p_profile jsonb) returns void
language plpgsql security definer set search_path='' as $$
begin
 if auth.uid() is null or not public.fl_is_member(p_company) then raise exception 'Acces refuzat la firma.'; end if;
 if p_user is distinct from auth.uid() and not (public.fl_is_admin(p_company) and public.fl_profile_complete(p_company)) then
   raise exception 'Poti modifica numai profilul propriu.';
 end if;
 if not exists(select 1 from public.company_members where company_id=p_company and user_id=p_user) then
   raise exception 'Utilizatorul nu este membru al firmei.';
 end if;
 if coalesce(length(trim(p_profile->>'first_name')),0) not between 1 and 100
 or coalesce(length(trim(p_profile->>'last_name')),0) not between 1 and 100
 or coalesce(length(trim(p_profile->>'job_title')),0) not between 1 and 120
 or coalesce(length(trim(p_profile->>'department')),0) not between 1 and 120 then
   raise exception 'Completeaza numele, prenumele, functia si departamentul.';
 end if;
 insert into public.company_member_profiles(company_id,user_id,first_name,last_name,job_title,department,updated_by)
 values(p_company,p_user,trim(p_profile->>'first_name'),trim(p_profile->>'last_name'),trim(p_profile->>'job_title'),trim(p_profile->>'department'),auth.uid())
 on conflict(company_id,user_id) do update set first_name=excluded.first_name,last_name=excluded.last_name,
 job_title=excluded.job_title,department=excluded.department,updated_at=now(),updated_by=auth.uid();
end;
$$;

-- Un singur validator pentru crearea si editarea firmei.
create function public.fl_check_company_details(p_details jsonb) returns void
language plpgsql set search_path='' as $$
begin
 if coalesce(length(trim(p_details->>'name')),0) not between 1 and 200
 or coalesce(length(trim(p_details->>'tax_id')),0) not between 1 and 100
 or coalesce(length(trim(p_details->>'country')),0) not between 1 and 100
 or coalesce(length(trim(p_details->>'address')),0) not between 1 and 500
 or coalesce(length(trim(p_details->>'contact_email')),0) not between 3 and 254
 or coalesce(trim(p_details->>'contact_email'),'') !~ '^[^[:space:]@]+@[^[:space:]@]+[.][^[:space:]@]+$' then
   raise exception 'Completeaza denumirea, identificatorul fiscal, tara, adresa si un email valid.';
 end if;
 if length(coalesce(p_details->>'phone',''))>50 or length(coalesce(p_details->>'website',''))>500 then
   raise exception 'Telefonul sau website-ul este prea lung.';
 end if;
 if nullif(trim(p_details->>'website'),'') is not null and trim(p_details->>'website') !~* '^https?://[^[:space:]]+$' then
   raise exception 'Website-ul trebuie sa inceapa cu https:// sau http://.';
 end if;
end;
$$;
revoke all on function public.fl_check_company_details(jsonb) from public;
drop function public.fl_create_company(text,text);
create function public.fl_create_company(p_company jsonb,p_profile jsonb) returns uuid
language plpgsql security definer set search_path='' as $$
declare cid uuid;
begin
 if auth.uid() is null then raise exception 'Autentificare necesara.'; end if;
 perform public.fl_check_company_details(p_company);
 insert into public.companies(name,company_type,tax_id,country,address,contact_email,phone,website)
 values(trim(p_company->>'name'),'insurer',trim(p_company->>'tax_id'),trim(p_company->>'country'),trim(p_company->>'address'),
 lower(trim(p_company->>'contact_email')),nullif(trim(p_company->>'phone'),''),nullif(trim(p_company->>'website'),'')) returning id into cid;
 insert into public.company_members(company_id,user_id,role) values(cid,auth.uid(),'admin');
 perform public.fl_save_member_profile(cid,auth.uid(),p_profile);
 return cid;
end;
$$;
create function public.fl_update_company(p_company uuid,p_details jsonb) returns void
language plpgsql security definer set search_path='' as $$
begin
 if not (public.fl_is_admin(p_company) and public.fl_profile_complete(p_company)) then raise exception 'Acces de administrator necesar; completeaza profilul propriu.'; end if;
 perform public.fl_check_company_details(p_details);
 update public.companies set name=trim(p_details->>'name'),tax_id=trim(p_details->>'tax_id'),country=trim(p_details->>'country'),
 address=trim(p_details->>'address'),contact_email=lower(trim(p_details->>'contact_email')),
 phone=nullif(trim(p_details->>'phone'),''),website=nullif(trim(p_details->>'website'),'') where id=p_company;
end;
$$;
revoke update on public.companies from authenticated;
revoke update(name,website,country) on public.companies from authenticated;

-- Returnam doar asocierile proprii si datele necesare pentru completarea profilului.
create function public.fl_my_memberships() returns jsonb
language sql stable security definer set search_path='' as $$
 select coalesce(jsonb_agg(jsonb_build_object('company_id',m.company_id,'role',m.role,
 'companies',jsonb_build_object('id',c.id,'name',c.name),'profile_complete',p.user_id is not null,
 'company_complete',public.fl_company_complete(c.id),'profile',case when p.user_id is null then null else to_jsonb(p) end)
 order by m.created_at,m.company_id),'[]'::jsonb)
 from public.company_members m join public.companies c on c.id=m.company_id
 left join public.company_member_profiles p on p.company_id=m.company_id and p.user_id=m.user_id
 where m.user_id=auth.uid();
$$;
create function public.fl_list_members(p_company uuid) returns jsonb
language plpgsql stable security definer set search_path='' as $$
declare result jsonb;
begin
 if not (public.fl_is_admin(p_company) and public.fl_profile_complete(p_company)) then raise exception 'Acces de administrator necesar.'; end if;
 select coalesce(jsonb_agg(jsonb_build_object('user_id',m.user_id,'role',m.role,'email',u.email,
 'profile',case when p.user_id is null then null else to_jsonb(p) end) order by m.created_at,m.user_id),'[]'::jsonb)
 into result from public.company_members m join auth.users u on u.id=m.user_id
 left join public.company_member_profiles p on p.company_id=m.company_id and p.user_id=m.user_id
 where m.company_id=p_company;
 return result;
end;
$$;

drop function public.fl_create_invitation(uuid);
create function public.fl_create_invitation(p_company uuid,p_email text) returns text
language plpgsql security definer set search_path='' as $$
declare token text; target_email text;
begin
 if not (public.fl_is_admin(p_company) and public.fl_profile_complete(p_company)) then raise exception 'Acces de administrator necesar; completeaza profilul propriu.'; end if;
 -- Blocam randul firmei pentru a verifica datele si a genera invitatia impreuna.
 perform 1 from public.companies where id=p_company for update;
 if not public.fl_company_complete(p_company) then raise exception 'Completeaza datele firmei inainte de a invita angajati.'; end if;
 target_email := lower(trim(p_email));
 if coalesce(length(target_email),0) not between 3 and 254 or target_email !~ '^[^[:space:]@]+@[^[:space:]@]+[.][^[:space:]@]+$' then
   raise exception 'Introdu un email valid pentru invitatie.';
 end if;
 update public.company_invitations set revoked_at=now() where company_id=p_company and email=target_email and used_at is null and revoked_at is null;
 token := replace(gen_random_uuid()::text||gen_random_uuid()::text,'-','');
 insert into public.company_invitations(company_id,token_hash,created_by,email)
 values(p_company,sha256(convert_to(token,'UTF8')),auth.uid(),target_email);
 return token;
end;
$$;
create or replace function public.fl_accept_invitation(p_token text) returns uuid
language plpgsql security definer set search_path='' as $$
declare invitation public.company_invitations; account_email text; confirmed timestamptz;
begin
 if auth.uid() is null then raise exception 'Autentificare necesara.'; end if;
 select lower(trim(email)),email_confirmed_at into account_email,confirmed from auth.users where id=auth.uid();
 if confirmed is null then raise exception 'Confirma emailul contului inainte de acceptarea invitatiei.'; end if;
 if p_token is null or length(trim(p_token))<>64 then raise exception 'Invitatie invalida.'; end if;
 select * into invitation from public.company_invitations where token_hash=sha256(convert_to(trim(p_token),'UTF8')) for update;
 if not found or invitation.revoked_at is not null or invitation.expires_at<=now() or invitation.email is null then
   raise exception 'Invitatie invalida sau expirata.';
 end if;
 if account_email is distinct from invitation.email then raise exception 'Invitatia este pentru alt email. Autentifica-te cu adresa invitata.'; end if;
 if invitation.used_by=auth.uid() then return invitation.company_id; end if;
 if invitation.used_by is not null then raise exception 'Invitatia a fost deja folosita.'; end if;
 insert into public.company_members(company_id,user_id,role) values(invitation.company_id,auth.uid(),'member') on conflict do nothing;
 update public.company_invitations set used_by=auth.uid(),used_at=now() where id=invitation.id;
 return invitation.company_id;
end;
$$;

-- Datele firmei se deschid numai dupa completarea profilului propriu.
create policy fl_company_profile_gate on public.companies as restrictive for select to authenticated
 using (public.fl_can_access_company(id));
create policy fl_clients_profile_gate on public.company_clients as restrictive for all to authenticated
 using (public.fl_can_access_company(company_id)) with check(public.fl_can_access_company(company_id));
create policy fl_invitation_profile_gate on public.company_invitations as restrictive for select to authenticated
 using (public.fl_profile_complete(company_id));
create policy fl_members_profile_gate on public.company_members as restrictive for select to authenticated
 using (user_id=auth.uid() or (public.fl_is_admin(company_id) and public.fl_profile_complete(company_id)));
create or replace function public.fl_can_read_event(p_event uuid) returns boolean
language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.flood_events e where e.id=p_event and (
 (e.company_id is null and (e.visibility='public' or e.created_by=auth.uid()))
 or public.fl_can_access_company(e.company_id)));
$$;
-- Păstram crearea simpla din 005; nu cream cereri de procesare.
create or replace function public.fl_create_event(p_event jsonb) returns jsonb
language plpgsql security definer set search_path='' as $$
declare eid uuid; cid uuid; slug_value text; start_date timestamptz; end_date timestamptz;
begin
 if auth.uid() is null then raise exception 'Authentication required'; end if;
 cid := nullif(p_event->>'company_id','')::uuid;
 if cid is not null and not public.fl_can_access_company(cid) then raise exception 'Completeaza profilul pentru firma selectata.'; end if;
 if coalesce(length(trim(p_event->>'title')),0) not between 1 and 120 then raise exception 'Invalid title'; end if;
 if p_event->'aoi'->>'type' is distinct from 'Polygon' or jsonb_typeof(p_event->'aoi'->'coordinates') is distinct from 'array' then raise exception 'A GeoJSON Polygon is required'; end if;
 start_date := (p_event->>'event_start')::timestamptz;
 end_date := nullif(p_event->>'ended_at','')::timestamptz;
 if start_date is null or start_date>now() then raise exception 'A valid event start is required'; end if;
 if end_date is not null and end_date<start_date then raise exception 'End date must follow event start'; end if;
 eid := gen_random_uuid(); slug_value := 'event-'||eid::text;
 insert into public.flood_events(id,slug,title,locality,county,started_at,ended_at,aoi_geojson,created_by,company_id,visibility)
 values(eid,slug_value,trim(p_event->>'title'),nullif(p_event->>'locality',''),nullif(p_event->>'county',''),start_date,end_date,p_event->'aoi',auth.uid(),cid,'private');
 return jsonb_build_object('id',eid,'slug',slug_value);
end;
$$;

revoke all on function public.fl_save_member_profile(uuid,uuid,jsonb),public.fl_create_company(jsonb,jsonb),
 public.fl_update_company(uuid,jsonb),public.fl_my_memberships(),public.fl_list_members(uuid),public.fl_create_invitation(uuid,text) from public;
grant execute on function public.fl_save_member_profile(uuid,uuid,jsonb),public.fl_create_company(jsonb,jsonb),
 public.fl_update_company(uuid,jsonb),public.fl_my_memberships(),public.fl_list_members(uuid),public.fl_create_invitation(uuid,text) to authenticated;
-- Functiile inlocuite isi pastreaza permisiunile de la migrarile anterioare.
notify pgrst, 'reload schema';
commit;
