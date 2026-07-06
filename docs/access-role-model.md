# Access Role Model

This role model is synthetic lab scaffolding for the slot-3 hospital BAS
simulator. It does not contain real usernames, directory groups, credentials,
or facility access records.

## Roles

| Role | Read points/alarms/trends | Acknowledge alarms | Command/release points | Manage roles | Read audit log |
|---|---|---|---|---|---|
| viewer | yes | no | no | no | no |
| operator | yes | yes | no | no | no |
| technician | yes | yes | yes | no | no |
| vendor | yes, session-gated by the remote-access workflow | no | no, planned but not implemented this slice | no | no |
| admin | yes | yes | yes | yes | yes |
| security reviewer | yes | no | no | no | yes |

## Implemented In BP-005

- `GET /api/roles` returns the six synthetic roles for front-end selection.
- `POST /api/points/{point_name}/command` accepts a self-declared `role`
  query parameter and allows only `technician` and `admin`.
- `POST /api/points/{point_name}/release` accepts a self-declared `role`
  query parameter and allows only `technician` and `admin`.
- Operator action log entries include `role` and `operator_id` attribution.

## Residual Risk

The `role` value is self-declared by the caller. This is acceptable for the
single-user local lab slice, but it is not real authentication or enforced RBAC.
A later build must add a real login/session model before this lab claims
production-grade command authorization.
