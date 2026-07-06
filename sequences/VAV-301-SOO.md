# Sequence Of Operations -- VAV-301

## Purpose

VAV-301 is a synthetic VAV box with reheat serving a floor-3 open office
zone at the synthetic Riverside Office Tower, downstream of RTU-1.

## Normal Operation

- Zone temperature setpoint is 72 F (comfort control, not life-safety).
- Damper modulates airflow to satisfy zone temperature on cooling calls.
- Reheat valve modulates only when the zone calls for heat below minimum
  airflow, tempering supply air from RTU-1.

## Troubleshooting Signals

- Zone temperature vs. setpoint.
- Reheat valve position relative to zone temperature trend (a valve
  stuck open drives the zone warm independent of the damper's response).
- Comparison against RTU-1 discharge air temperature to rule out an
  upstream AHU problem before assuming a zone-level fault.

## Safety Note

This is a synthetic training sequence. It is not a real design sequence and
is not code/life-safety approval. Comfort-zone faults here are lower
priority than the hospital's life-safety-driven sequences and are alarmed
accordingly (medium, not critical).
