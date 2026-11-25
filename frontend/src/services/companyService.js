import { supabase } from "../config/supabase";

async function unwrap(request) {
    const { data, error } = await request;
    if (error) throw error;
    return data;
}

export const getMemberships = () => unwrap(supabase.rpc("fl_my_memberships"));
export const createCompany = (company, profile) => unwrap(supabase.rpc("fl_create_company", {p_company:company,p_profile:profile}));
export const acceptInvitation = token => unwrap(supabase.rpc("fl_accept_invitation", {p_token:token.trim()}));
export const createInvitation = (companyId,email) => unwrap(supabase.rpc("fl_create_invitation", {p_company:companyId,p_email:email.trim()}));
export const revokeInvitation = id => unwrap(supabase.rpc("fl_revoke_invitation", {p_invitation:id}));
export const removeMember = (companyId,userId) => unwrap(supabase.rpc("fl_remove_member", {p_company:companyId,p_user:userId}));
export const getMembers = companyId => unwrap(supabase.rpc("fl_list_members", {p_company:companyId}));
export const getInvitations = companyId => unwrap(supabase.from("company_invitations")
    .select("id,email,expires_at,used_at,revoked_at").eq("company_id",companyId).order("created_at",{ascending:false}));
export const getCompany = id => unwrap(supabase.from("companies")
    .select("id,name,tax_id,country,address,contact_email,phone,website").eq("id",id).single());
export const updateCompany = (id,details) => unwrap(supabase.rpc("fl_update_company", {p_company:id,p_details:details}));
export const saveMemberProfile = (companyId,userId,profile) => unwrap(supabase.rpc("fl_save_member_profile", {p_company:companyId,p_user:userId,p_profile:profile}));
// Angajatii au SELECT; scrierea este verificata prin RLS pentru admin.
export const getClients = (companyId) => unwrap(supabase.from("company_clients").select("id,name,email,phone").eq("company_id",companyId));
export const addClient = (companyId, client) => unwrap(supabase.from("company_clients")
    .insert({company_id:companyId,name:client.name,email:client.email,phone:client.phone}).select("id").single());
export const updateClient = (id, client) => unwrap(supabase.from("company_clients")
    .update({name:client.name,email:client.email,phone:client.phone}).eq("id",id).select("id").single());
export const deleteClient = (id) => unwrap(supabase.from("company_clients").delete().eq("id",id).select("id").single());
