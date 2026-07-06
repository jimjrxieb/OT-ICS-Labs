# Remote Access Workflow

This workflow is documentation scaffolding for the synthetic slot-3 hospital BAS
lab. It uses the `vendor` role as the example and does not describe a real
vendor, real identity provider, real MFA system, real hostname, or real
facility access path.

## Workflow

1. Request

   A synthetic vendor requests time-bounded BAS access for a named support task.
   The request records requested role, operator contact, affected equipment,
   reason, requested start time, requested end time, and whether command access
   is requested.

2. Approval

   A synthetic admin reviews the request. Approval must confirm the role,
   task scope, allowed equipment, session window, and whether the request is
   read-only or command-capable.

3. MFA Flag

   The request carries an `mfa_confirmed` boolean. In this BP-005 slice the
   flag is documented only. No real MFA integration or enforcement exists.

4. Session Start

   A session starts only after approval. The synthetic session record should
   capture role, operator_id, approved scope, start timestamp, and intended
   end timestamp.

5. Session End

   Session end records final timestamp, reason for closure, and whether any
   operator actions occurred during the session.

## Denial Cases

- Requested role is not one of the six documented synthetic roles.
- Vendor requests command/release authority during BP-005. Vendor command
  access is planned for a later slice and is denied in this slice.
- `mfa_confirmed` is false for a workflow that requires remote vendor access.
- Requested equipment or session window is outside the approved synthetic scope.

## Implemented In BP-005

No real remote-access request, approval, MFA, session start, or session end
workflow is implemented in code in this slice. BP-005 implements only the
self-declared API role gate for point command/release and attribution fields in
the operator action log.

## Planned Later

- Remote-access request records.
- Admin approval and denial records.
- Session start/end events.
- Real authentication and session handling for local lab users.
- MFA enforcement if the lab later models remote access.
