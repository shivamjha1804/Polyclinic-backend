create role analytics_readonly with login password '<set via SQL Editor, not stored here>';
grant usage on schema public to analytics_readonly;
grant select on v_appointments_by_doctor_month, v_noshow_rate, v_lab_severity_summary to analytics_readonly;
