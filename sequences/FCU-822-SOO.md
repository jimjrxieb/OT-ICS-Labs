# Sequence Of Operations -- FCU-822 (Room Fan Coil Units)

## Purpose

The FCU-822 units are synthetic Trane room fan coil units serving individual
barracks rooms in the synthetic Building 822. Each unit is a chilled water
cooling coil with a multi-speed fan, controlling its own room temperature.
Ventilation air is not supplied by the fan coil -- it arrives from the MAU
serving that wing, so a fan coil cannot fix a room humidity problem on its own.

## Normal Operation

- Room temperature setpoint is 73 F (`FCU___SPACE_TEMP_SP`, normal range
  72-74 F).
- The chilled water valve modulates on the same PI loop used by the makeup air
  units -- 0.5 F deadband, 5 %/step actuator slew -- to hold space temperature.
- The fan runs in one of five modes (`FCU___FAN_MODE`), which set the fraction
  of design airflow through the coil:

  | Mode | Name | Airflow fraction |
  |------|------|------------------|
  | 0 | Off  | 0.00 |
  | 1 | Auto | 0.65 |
  | 2 | Low  | 0.35 |
  | 3 | Mid  | 0.65 |
  | 4 | High | 1.00 |

  Airflow scales both the air moved and the coil capacity available, so a unit
  in Low has roughly a third of the capacity it has in High. Mode 0 stops the
  fan and the coil delivers nothing.
- Because the room is on a PI loop, coil capacity changes are absorbed by valve
  position at steady state. A larger coil does not make a room colder -- it
  makes the valve sit further closed for the same room temperature.

## Troubleshooting Signals

- `FCU___SPACE_TEMP` vs `FCU___SPACE_TEMP_SP`. A room above setpoint with the
  valve part-open is a control question; above setpoint with the valve at 100 %
  is a capacity question.
- `FCU___FAN_MODE` and `FCU___FAN_STATUS`. A room that will not hold setpoint
  with the valve wide open is very often a fan left in Low or Off, not a water
  problem. Check the mode before you chase the coil.
- `FCU___CHW_VLV_POS` across several rooms on the same wing. One room pegged is
  a unit problem; every room on the wing pegged at once points upstream to the
  service entrance or the chiller.
- Room temperature that tracks setpoint while corridor humidity stays high is
  expected behavior, not a fault. The fan coils control temperature only;
  corridor moisture is the makeup air unit's job.

## Safety Note

This is a synthetic training sequence. It is not a real design sequence and is
not code/life-safety approval.
