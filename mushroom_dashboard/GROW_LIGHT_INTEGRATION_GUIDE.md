# Grow Light Integration Guide
## ESP32 + Relay + Dashboard (Mushroom Farm)

This guide explains how to safely add grow lights to your current automation system.

## 1) Important Safety First

- Mains electricity (110V/220V AC) can cause fire, injury, or death.
- If you are switching AC power, have a licensed electrician verify the final wiring.
- Use an RCD/GFCI-protected circuit, correct wire gauge, proper fusing, and enclosed terminals.
- Keep high-voltage wiring physically separated from low-voltage ESP32 wiring.

## 2) Your Current Controller Capacity

Your current ESP32 sketch is already using three relay outputs:

- Fan relay: GPIO 26
- Mist relay: GPIO 27
- Heater relay: GPIO 25

To add grow lights, use one of these:

1. Replace current relay board with a 4-channel (or 8-channel) isolated relay board.
2. Add a second 1-channel relay module dedicated to lights.

Recommended new control pin for lights:

- Light relay: GPIO 33 (safe general-purpose output on ESP32)

## 3) Choose the Right Light Wiring Topology

Grow lights usually fall into one of these categories:

1. AC fixture with built-in driver (most common)
2. External LED driver + LED board/bar
3. Low-voltage DC light bars (12V/24V)

Wire based on the actual light type, not the label "grow light" alone.

## 4) Wiring Option A: AC Grow Light (Built-In Driver)

Use relay/contactor to switch only the LIVE/HOT conductor.

### Control side (low voltage)

- ESP32 5V/VIN -> Relay VCC (if module requires 5V)
- ESP32 GND -> Relay GND
- ESP32 GPIO 33 -> Relay IN4 (or IN1 on separate 1-channel module)

### Load side (mains)

- Mains LIVE/HOT -> breaker/fuse -> Relay COM
- Relay NO -> Light fixture LIVE/HOT
- Mains NEUTRAL -> Light fixture NEUTRAL (direct, unswitched)
- Mains EARTH/GROUND -> Fixture metal body ground terminal

ASCII overview:

```
AC Live ---- Breaker/Fuse ---- Relay COM
                                 Relay NO ---- Light Live

AC Neutral ---------------------------------- Light Neutral
AC Earth   ---------------------------------- Light Ground
```

Why NO (Normally Open): light stays OFF if controller fails or loses power.

## 5) Wiring Option B: External LED Driver (Constant Current)

For COB or high-power LED boards, you often have:

- AC input to driver (L/N/PE)
- DC constant-current output from driver (+/-) to LED board

Recommended switching point:

- Switch AC LIVE feeding the driver using relay/contactor.

Do not place a random relay on the driver output unless driver datasheet explicitly supports it.

Driver grounding:

- If driver has PE/FG terminal, connect it to protective earth.
- Ground all exposed metal fixtures and heatsinks if required by fixture design.

## 6) Wiring Option C: 12V/24V DC Grow Bars

If lights are low-voltage DC:

- DC PSU (+) -> Relay COM
- Relay NO -> Light (+)
- DC PSU (-) -> Light (-) direct

For higher current DC loads, a DC-rated MOSFET module is often better than a mechanical relay.

## 7) Grounding and Bonding Rules

1. Ground all metal enclosures and fixture chassis to protective earth.
2. Keep AC earth separate from ESP32 logic ground (they are not interchangeable).
3. Keep relay high-voltage terminals covered; use DIN rail terminal blocks or enclosed junction boxes.
4. Use ferrules/crimp lugs and strain relief at cable entries.
5. Never switch earth/ground; never leave metal fixtures ungrounded.

## 8) Driver and Relay Sizing

### Relay/contact rating

- Use at least 125% current headroom over steady current.
- LED drivers can have inrush current spikes; choose a relay/contactor rated for LED loads.

Current estimate:

- I = P / V

Examples:

- 120W light at 220V: ~0.55A steady
- 120W light at 110V: ~1.09A steady

Even if steady current is low, inrush can be much higher. If your light is >150W or has high inrush, use:

1. Relay module output to drive a contactor coil, or
2. An SSR/contactor designed for LED driver inrush behavior

### Fuse/cable quick guide

- 0 to 2A branch: 18 AWG minimum
- 2 to 5A branch: 16 AWG minimum
- 5 to 10A branch: 14 AWG minimum

Always follow local electrical code if it requires a larger conductor.

## 9) Timer and Control Integration Options

## Option 1: Hardware timer only (simplest)

- Add a DIN rail programmable timer before the relay-controlled light feed.
- ESP32 can still do ON/OFF within the timer window.
- Good fail-safe if network/server is down.

## Option 2: Dashboard schedule (recommended)

Add a light schedule policy in backend:

- `lights_auto = true`
- `lights_on` used for manual override when auto is disabled
- schedule fields: `lights_start_time`, `lights_end_time`, `lights_timezone`

Control logic:

1. If `lights_auto` is true, ON when current time is inside schedule window.
2. If `lights_auto` is false, follow `lights_on` toggle directly.
3. Keep fail-safe default OFF on communication loss.

## Option 3: Hybrid (best reliability)

- Dashboard schedule is primary.
- ESP32 keeps last valid schedule locally and uses RTC fallback if server unavailable.
- Optional hardware timer as hard cut-off backup.

## 10) Recommended Mushroom Light Schedules

General baseline (adjust per species/strain):

- Incubation: dark or very low light
- Fruiting: 8 to 12 hours per day, low to moderate intensity
- Typical intensity target near canopy: 100 to 500 lux for many species

Avoid excess heat at canopy level. Verify temperature rise after lights are installed.

## 11) Commissioning Checklist

1. Bench test relay output with no mains load first.
2. Verify GPIO toggles relay indicator LED.
3. Verify NO/COM continuity changes correctly.
4. Connect load and test with breaker and fuse in place.
5. Confirm earth continuity from panel ground to fixture body.
6. Run 1-hour thermal test and monitor enclosure/wire temperatures.
7. Confirm fail-safe OFF behavior on ESP32 reset and server disconnect.

## 12) Practical Integration Notes for Your Setup

- Your backend already stores `lights_on`, `lights_auto`, and `lights_value`.
- Hardware integration mostly requires adding the new relay channel and wiring the light power path safely.
- Firmware needs one new relay pin and one control block for lights, similar to fan/mist/heater handling.

If you want, the next step is a direct code patch that adds the light relay logic in the ESP32 sketch (GPIO define, pinMode, failsafe behavior, and API response handling).