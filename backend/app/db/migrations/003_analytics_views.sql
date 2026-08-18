create or replace view v_appointments_by_doctor_month as
select
  a.doctor_id,
  p.full_name as doctor_name,
  date_trunc('month', a.starts_at) as month,
  count(*) as total_appointments,
  count(*) filter (where a.status = 'completed') as completed,
  count(*) filter (where a.status = 'cancelled') as cancelled,
  count(*) filter (where a.status = 'no_show') as no_show
from appointments a
join profiles p on p.id = a.doctor_id
group by a.doctor_id, p.full_name, date_trunc('month', a.starts_at);

create or replace view v_noshow_rate as
select
  a.doctor_id,
  p.full_name as doctor_name,
  date_trunc('month', a.starts_at) as month,
  count(*) as total_appointments,
  count(*) filter (where a.status = 'no_show') as no_shows,
  round(100.0 * count(*) filter (where a.status = 'no_show') / nullif(count(*), 0), 1) as noshow_rate_pct
from appointments a
join profiles p on p.id = a.doctor_id
group by a.doctor_id, p.full_name, date_trunc('month', a.starts_at);

create or replace view v_lab_severity_summary as
select
  date_trunc('month', created_at) as month,
  analyte,
  severity,
  count(*) as result_count
from lab_results
group by date_trunc('month', created_at), analyte, severity;
