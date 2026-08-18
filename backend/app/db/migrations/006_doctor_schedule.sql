alter table profiles add column working_hours_start time;
alter table profiles add column working_hours_end time;
alter table profiles add column slot_duration_minutes int default 30;
