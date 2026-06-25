# Sequence Of Operations -- AHU-OR-1

## Purpose

AHU-OR-1 serves the synthetic OR suite and maintains discharge air temperature
for downstream OR VAV control.

## Normal Operation

- Supply fan runs during occupied OR schedule.
- Discharge air temperature setpoint is 55 F.
- Cooling valve modulates to maintain discharge air temperature.
- Heating valve remains closed unless discharge air temperature falls below
  low limit.
- Critical alarms are generated for fan failure, discharge air temperature
  outside expected range, and downstream OR humidity/temperature excursions.

## Troubleshooting Signals

- AHU discharge air temperature.
- Fan command/status.
- OR room temperature.
- OR relative humidity.
- Chilled water supply temperature and differential pressure.

## Safety Note

This is a synthetic training sequence. It is not a real design sequence and is
not code/life-safety approval.

