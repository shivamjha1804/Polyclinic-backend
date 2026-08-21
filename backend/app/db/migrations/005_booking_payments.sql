alter table appointments add column hold_expires_at timestamptz;

create table payments (
  id                   uuid primary key default gen_random_uuid(),
  appointment_id       uuid not null references appointments(id),
  patient_id           uuid not null references profiles(id),
  razorpay_order_id    text,
  razorpay_payment_id  text,
  amount               numeric not null,
  currency             text default 'INR',
  status               text default 'created',
  created_at           timestamptz default now()
);

create index on payments (appointment_id);
create index on payments (razorpay_order_id);

alter table payments enable row level security;

create policy "patient reads own payments" on payments
for select using (auth.uid() = patient_id);

create policy "owner reads all payments" on payments
for select using (current_role_is('owner'));
