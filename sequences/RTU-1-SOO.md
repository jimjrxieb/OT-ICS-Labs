# Sequence Of Operations -- RTU-1

## Purpose

RTU-1 is a synthetic rooftop VAV air handling unit serving office floors 3-8
at the synthetic Riverside Office Tower. It maintains discharge air
temperature using an economizer/mechanical cooling changeover sequence.

## Normal Operation

- Supply fan runs during occupied schedule.
- Discharge air temperature setpoint is 55 F.
- Outside air (economizer) damper modulates to bring in free cooling when
  outside air temperature is favorable relative to mixed air temperature
  target; otherwise the damper holds at minimum position and mechanical
  cooling handles the load.
- Mixed air temperature is monitored to confirm the economizer damper is
  actually responding to its commanded position.

## Troubleshooting Signals

- RTU discharge air temperature vs. setpoint.
- Mixed air temperature vs. outside air temperature and damper position
  (a damper commanded open that does not move the mixed air temperature is
  a stuck-actuator signature, not a control-loop signature).
- Supply fan command/status.
- Downstream VAV zone temperatures.

## Safety Note

This is a synthetic training sequence. It is not a real design sequence and is
not code/life-safety approval.
