# Sequence Of Operations -- MAU-822 (Makeup Air Units MAU-01 through MAU-13)

## Purpose

The MAU-822 units are synthetic Trane makeup air units serving the corridors and
rooms of the synthetic Building 822 barracks. Each unit conditions a mix of
outside air and corridor return air with a single chilled water cooling coil,
and holds a supply air temperature setpoint. There is no heating coil and no
reheat: the coil either cools or it does not.

## Normal Operation

- Supply fan runs continuously. `MAU__FAN_CMD` commands it; `MAU__FAN_STATUS`
  proves it. With the fan off the coil is bypassed entirely and supply air
  equals entering air.
- Supply air temperature setpoint is 65 F (`MAU__SAT_SP`, normal range 60-66 F).
- The chilled water valve modulates on a PI loop with a 0.5 F deadband and a
  5 %/step actuator slew rate to hold supply air at setpoint. Healthy operation
  is a valve sitting part-open and moving -- roughly 70-80 % at design summer
  load.
- The outside air damper holds a fixed commanded position (`MAU__OA_DMPR_CMD`,
  normal range 40-60 %). Entering air is the mix of outside air and corridor
  return air at that ratio, so the damper position directly sets how much
  outdoor moisture the coil has to remove. Opening the damper raises both the
  sensible and the latent load on the coil.
- The coil removes sensible and latent heat together. Supply air leaves close to
  saturation (85-95 % RH), so supply air dewpoint -- not supply air temperature
  alone -- is what determines corridor humidity downstream.

## Troubleshooting Signals

- `MAU__SAT` vs `MAU__SAT_SP`. At setpoint with the valve modulating is healthy.
- `MAU__CHW_VLV_POS` vs `MAU__SAT`. A valve pegged at 100 % with supply air
  still above setpoint is a capacity problem, not a control problem. The loop is
  asking correctly and not being answered -- check water before you check
  controls: entering water temperature at the service entrance, then building
  delta-T, then the chiller.
- `MAU__COIL_DT` (entering air minus leaving air). A near-zero coil delta-T with
  the valve open means no water is moving through that coil.
- `MAU__EAT` and `MAU__EA_RH` vs `MAU__OA_DMPR_POS`. Entering conditions that do
  not track the commanded damper position are a stuck-actuator signature.
- `MAU__SA_RH`. Supply air well below saturation with the valve open means the
  coil is running dry and not dehumidifying.

## Safety Note

This is a synthetic training sequence. It is not a real design sequence and is
not code/life-safety approval.
