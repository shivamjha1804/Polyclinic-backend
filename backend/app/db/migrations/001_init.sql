create extension if not exists vector;
create extension if not exists pg_cron;
create extension if not exists pg_trgm;

create type user_role      as enum ('patient','doctor','owner');
create type consult_status as enum ('pending','transcribed','drafted','in_review','signed');
create type lab_severity   as enum ('normal','abnormal','critical');


create table profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  role        user_role not null default 'patient',
  full_name   text not null,
  specialty   text,                       -- doctors only
  dob         date,                       -- patients only
  created_at  timestamptz default now()
);


create table appointments (
  id          uuid primary key default gen_random_uuid(),
  patient_id  uuid not null references profiles(id),
  doctor_id   uuid not null references profiles(id),
  starts_at   timestamptz not null,
  ends_at     timestamptz not null,
  status      text default 'booked',      -- booked|completed|cancelled|no_show
  reason      text,
  created_at  timestamptz default now()
);

create index on appointments (doctor_id, starts_at);
create index on appointments (patient_id, starts_at desc);


create table consultations (
  id               uuid primary key default gen_random_uuid(),
  appointment_id   uuid references appointments(id),
  patient_id       uuid not null references profiles(id),
  doctor_id        uuid not null references profiles(id),
  audio_path       text,                  -- Storage object path
  transcript       text,
  soap_note        jsonb,
  validation_flags jsonb default '[]',
  status           consult_status default 'pending',
  revision_count   int default 0,
  signed_at        timestamptz,
  follow_up_days   int,                   -- extracted: "return in 3 months"
  created_at       timestamptz default now()
);

create index on consultations (doctor_id, status);
create index on consultations (patient_id, created_at desc);


create table medical_records (
  id          uuid primary key default gen_random_uuid(),
  patient_id  uuid not null references profiles(id),
  title       text,
  doc_type    text,                       -- lab|imaging|discharge|referral|note
  file_path   text,
  summary     text,                       -- Haiku-generated
  recorded_at date,
  created_at  timestamptz default now()
);

create table record_chunks (
  id          uuid primary key default gen_random_uuid(),
  record_id   uuid not null references medical_records(id) on delete cascade,
  patient_id  uuid not null references profiles(id),
  section     text,                       -- Chief Complaint, Medications, ...
  content     text not null,
  content_tsv tsvector generated always as (to_tsvector('english', content)) stored,
  embedding   vector(1024),
  chunk_index int
);

create index on record_chunks using hnsw (embedding vector_cosine_ops);
create index on record_chunks using gin  (content_tsv);
create index on record_chunks (patient_id);


create table lab_results (
  id            uuid primary key default gen_random_uuid(),
  patient_id    uuid not null references profiles(id),
  ordering_doc  uuid references profiles(id),
  analyte       text not null,            -- e.g. 'creatinine'
  value         numeric,
  unit          text,
  ref_low       numeric,
  ref_high      numeric,
  severity      lab_severity,
  llm_context   text,                     -- baseline comparison, advisory only
  acknowledged_by uuid references profiles(id),
  acknowledged_at timestamptz,
  created_at    timestamptz default now()
);

create index on lab_results (severity, acknowledged_at);

create table referrals (
  id            uuid primary key default gen_random_uuid(),
  patient_id    uuid not null references profiles(id),
  from_doctor   uuid references profiles(id),
  to_specialty  text,
  sent_at       timestamptz default now(),
  report_received_at timestamptz
);

create table audit_log (
  id            bigserial primary key,
  actor_id      uuid,
  actor_role    user_role,
  action        text not null,            -- rag_query|note_signed|record_viewed
  resource_type text,
  resource_id   uuid,
  metadata      jsonb,                    -- retrieved chunk ids, model, tokens
  created_at    timestamptz default now()
);

create index on audit_log (actor_id, created_at desc);
create index on audit_log (resource_id);


alter table profiles        enable row level security;
alter table appointments    enable row level security;
alter table consultations   enable row level security;
alter table medical_records enable row level security;
alter table record_chunks   enable row level security;
alter table lab_results     enable row level security;
alter table audit_log       enable row level security;
alter table referrals       enable row level security;


create or replace function current_role_is(r user_role)
returns boolean language sql stable security definer as $$
  select exists (select 1 from profiles where id = auth.uid() and role = r);
$$;


create policy "patient reads own consultations" on consultations
for select using (auth.uid() = patient_id);

create policy "doctor reads assigned consultations" on consultations
for select using (auth.uid() = doctor_id);

create policy "owner reads all consultations" on consultations
for select using (current_role_is('owner'));

create policy "doctor updates unsigned" on consultations
for update using (auth.uid() = doctor_id and signed_at is null);


create policy "patient reads own chunks" on record_chunks
for select using (auth.uid() = patient_id);

create policy "clinician reads chunks" on record_chunks
for select using (current_role_is('doctor') or current_role_is('owner'));

create policy "owner reads audit" on audit_log
for select using (current_role_is('owner'));
