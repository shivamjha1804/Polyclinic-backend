-- 1. New RBAC tables
create table roles (
  id uuid primary key default gen_random_uuid(),
  name text unique not null,
  created_at timestamptz default now()
);

create table permissions (
  id uuid primary key default gen_random_uuid(),
  resource text not null,
  action text not null,
  description text,
  unique (resource, action)
);

create table role_permissions (
  role_id uuid references roles(id) on delete cascade,
  permission_id uuid references permissions(id) on delete cascade,
  primary key (role_id, permission_id)
);

-- 2. Drop RLS policies that depend on current_role_is(user_role) before we change types
drop policy "owner reads all consultations" on consultations;
drop policy "clinician reads chunks" on record_chunks;
drop policy "owner reads audit" on audit_log;
drop policy "owner reads all payments" on payments;

-- 3. Drop the old function (safe now, nothing references it)
drop function current_role_is(user_role);

-- 4. Convert profiles.role from enum to plain text BEFORE recreating the function,
--    so the function body's "role = r" comparison is text = text.
alter table profiles alter column role type text using role::text;
alter table profiles alter column role set default 'patient';

-- 5. Recreate current_role_is with a text parameter
create or replace function current_role_is(r text)
returns boolean language sql stable security definer as $$
  select exists (select 1 from profiles where id = auth.uid() and role = r);
$$;

-- 6. Recreate the dropped policies (identical logic, now against the text version)
create policy "owner reads all consultations" on consultations
for select using (current_role_is('owner'));

create policy "clinician reads chunks" on record_chunks
for select using (current_role_is('doctor') or current_role_is('owner'));

create policy "owner reads audit" on audit_log
for select using (current_role_is('owner'));

create policy "owner reads all payments" on payments
for select using (current_role_is('owner'));

-- 7. Seed roles: existing 3 + the 6 new staff roles discussed
insert into roles (name) values
  ('patient'), ('doctor'), ('owner'),
  ('receptionist'), ('nurse'), ('compounder'),
  ('lab_assistant'), ('lab_doctor'), ('lab_reporter');

-- 8. Permission catalog -- matches every route currently gated by require_role()
insert into permissions (resource, action, description) values
  ('consultations', 'create', 'Create a new consultation shell'),
  ('consultations', 'upload_audio', 'Request a signed audio upload URL'),
  ('consultations', 'transcribe', 'Trigger ASR + scribe graph'),
  ('consultations', 'review', 'Submit doctor review decision'),
  ('consultations', 'sign', 'Sign and finalize a consultation'),
  ('followups', 'read', 'View the follow-up worklist'),
  ('analytics', 'ask', 'Run a natural-language analytics query'),
  ('labs', 'create', 'Upload a lab result'),
  ('labs', 'queue', 'View the lab review queue'),
  ('labs', 'acknowledge', 'Acknowledge a lab result'),
  ('staff', 'manage', 'Create/manage staff accounts and role permissions');

-- 9. Give 'doctor' role the permissions it currently has, so behavior doesn't change
insert into role_permissions (role_id, permission_id)
select r.id, p.id
from roles r, permissions p
where r.name = 'doctor'
  and (p.resource, p.action) in (
    ('consultations', 'create'), ('consultations', 'upload_audio'),
    ('consultations', 'transcribe'), ('consultations', 'review'),
    ('consultations', 'sign'), ('followups', 'read'),
    ('labs', 'create'), ('labs', 'queue'), ('labs', 'acknowledge')
  );

-- 'owner' gets no explicit rows here -- it bypasses all permission checks
-- at the application layer (deps.py), since owner is the superadmin.

-- 10. The function the app calls to check "does this role have this permission?"
create or replace function role_has_permission(role_name text, res text, act text)
returns boolean language sql stable as $$
  select exists (
    select 1
    from role_permissions rp
    join roles r on r.id = rp.role_id
    join permissions p on p.id = rp.permission_id
    where r.name = role_name and p.resource = res and p.action = act
  );
$$;
