-- Remove old granular permissions (cascades into role_permissions)
delete from permissions;

-- Standard CRUD-style actions per resource
insert into permissions (resource, action, description) values
  ('consultations', 'create', 'Create a consultation'),
  ('consultations', 'view', 'View a consultation'),
  ('consultations', 'edit', 'Edit a consultation (audio upload, transcribe, review, sign)'),
  ('consultations', 'delete', 'Delete a consultation'),

  ('labs', 'create', 'Create a lab result'),
  ('labs', 'view', 'View lab results / queue'),
  ('labs', 'edit', 'Edit a lab result (acknowledge)'),
  ('labs', 'delete', 'Delete a lab result'),

  ('followups', 'view', 'View the follow-up worklist'),

  ('analytics', 'view', 'Run analytics queries'),

  ('staff', 'create', 'Create a staff account'),
  ('staff', 'view', 'View staff accounts'),
  ('staff', 'edit', 'Edit a staff account'),
  ('staff', 'delete', 'Delete a staff account'),

  ('roles', 'create', 'Create a role'),
  ('roles', 'view', 'View roles and their permissions'),
  ('roles', 'edit', 'Assign/revoke a permission on a role'),
  ('roles', 'delete', 'Delete a role');

-- Re-seed 'doctor' role permissions, matching current access exactly
insert into role_permissions (role_id, permission_id)
select r.id, p.id
from roles r, permissions p
where r.name = 'doctor'
  and (p.resource, p.action) in (
    ('consultations', 'create'),
    ('consultations', 'edit'),
    ('labs', 'create'),
    ('labs', 'view'),
    ('labs', 'edit'),
    ('followups', 'view')
  );
