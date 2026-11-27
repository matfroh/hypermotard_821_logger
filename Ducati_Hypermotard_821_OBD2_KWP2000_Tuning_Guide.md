# Ducati Hypermotard 821 (Marelli 7SM ECU) — Complete OBD2 / KWP2000 Telemetry & Tuning Guide

This repository documents the physical wiring, ELM327 initialization commands, complete verified **KWP2000 (`Service 0x21`)** diagnostic sensor table (`0x30`–`0x92`), Android Python data-logging architecture, and formulas for **Fuel Mapping / AFR Analysis** and **Virtual Road Dyno** power/torque curves on the **Ducati Hypermotard 821 (2013–2015, Euro 3, Magneti Marelli 7SM ECU)**.

---

## 1. Hardware & Physical Wiring

### Ducati 4-Pin DDA to 16-Pin OBD2 Adapter Pinout
Pre-Euro 5 Ducatis use an under-seat 4-pin diagnostic connector (DDA) rather than a standard 16-pin J1962 port. Ensure your adapter cable maps the **CAN bus pins** (many cheap 3-wire K-Line Ducati cables leave CAN-H/CAN-L disconnected):

| Ducati 4-Pin DDA | Bike Wire Color (Typical) | Standard 16-Pin OBD2 | Signal Function |
| :--- | :--- | :--- | :--- |
| **Pin 1** | Red / White | **Pin 16** | +12V Switched Battery Power |
| **Pin 2** | Black | **Pins 4 & 5** | Chassis / Signal Ground |
| **Pin 3** | White / Yellow | **Pin 6** | CAN-High (500 kbps) |
| **Pin 4** | White / Blue | **Pin 14** | CAN-Low (500 kbps) |

### ELM327 Adapter Requirements
* **Required Chipset:** Genuine **ELM327 v1.4 or v1.5** (e.g., Lonelec Bluetooth 1.5, OBDLink LX/MX+).
* **Incompatible Chipsets:** Generic budget **ELM327 v2.1** clones frequently lack `ATCAF0` (manual ISO-TP PCI length byte formatting) and raw CAN header routing (`ATSH` / `ATCRA`), causing connection failures on the Marelli 7SM.
* **Bike State:** Ignition key **ON** and red engine kill-switch in **RUN** (the Marelli 7SM CAN diagnostic responder does not power up when the kill-switch is OFF).

---

## 2. Protocol Architecture & ELM327 Initialization

The 2013–2015 Hypermotard 821 predates mandatory Euro 5 OBD2 standardization:
1. **Standard OBD2 Mode `01` (`0100`, `010C`, `0111`) is unsupported** (returns `7F 01 11`).
2. **UDS Service `22` (`22 xxxx`) is unsupported** (returns `7F 22 11`).
3. **KWP2000-over-CAN (`ISO 15765-4`, 11-bit, 500 kbps) is active** on two diagnostic modules:
   * **Engine ECU (`7E0` / `7E8`):** Requires `ATCAF0` (manual PCI length byte) and session control `02 10 01` (replies `02 50 01`). Serves **89 active `02 21 xx` channels** (`0x30`–`0x92`) continuously—both stationary and while riding.
   * **BBS / Black Box System (`7E2` / `7EA`):** Opens with `02 10 81` (`02 50 81`), **but locks out diagnostic queries while the motorcycle is in motion** as an ABS/DTC safety measure. All riding telemetry—including **Vehicle Speed (`02217A`)**—must therefore be polled from the **Engine ECU (`7E0`)**.

### Exact ELM327 Initialization Sequence
```text
ATZ          # Reset ELM327
ATE0         # Echo OFF
ATL0         # Linefeeds OFF
ATS0         # Spaces OFF
ATH0         # Headers OFF
ATSP6        # Protocol 6: ISO 15765-4 CAN (11-bit ID, 500 kbaud)
ATCAF0       # CAN Auto-Formatting OFF (mandatory so 02xx length bytes pass raw)
ATSH7E0      # Set Tx Header to Engine ECU (7E0)
ATCRA7E8     # Filter Rx Header from Engine ECU (7E8)
021001       # Start KWP2000 Diagnostic Session -> Expected reply: 025001
```
*(Note: Keep the `021001` session alive every ~2–3 seconds during polling, and send `0120` [`StopDiagnosticSession`] + `ATPC` [`Protocol Close`] on clean disconnect).*

---

## 3. Complete Verified Marelli 7SM Sensor Map (`7E0` / `7E8`)

All commands below were empirically verified on a live Hypermotard 821 across stationary key-on, cold/warm idle, and street riding (`0x01`–`0xFE` full-spectrum scan). Every command uses the format `0221<PID>` and returns `0461<PID><HI><LO>` (or `0361<PID><BYTE>` for 8-bit flags), where **`X = A*256 + B`** is the 16-bit unsigned integer payload.

### A. Core Engine, Throttle & Speed Channels
| PID | Command | Parameter | Unit | Formula (`X = A*256+B`) | Verified Real-World Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`30`** | `022130` | **Engine RPM** | `rpm` | `X` | `0` off; `1350–1720` idle; tracks live engine speed |
| **`7A`** | `02217A` | **Vehicle Speed** | `km/h` | `X` | `0` stationary; tracks true road speed (`1–59+ km/h`) |
| **`3B`** | `02213B` | **Twistgrip Position (APS)** | `%` | `X / 10` | `0.0%` closed grip; scales `0.0–100.0%` |
| **`3C`** | `02213C` | **Throttle Body 1 Plate (TPS 1)** | `%` | `X / 10` | `16.6%` key-on; `12.0–13.4%` idle; RbW capped below ~7,500 RPM |
| **`3E`** | `02213E` | **Throttle Body 2 Plate (TPS 2)** | `%` | `X / 10` | `16.7%` key-on; tracks Horizontal/Vertical butterfly sync |
| **`8E`** | `02218E` | **Gear / Transmission Status** | `flag` | `A` (1-byte) | `1` = Neutral, `2` = 1st gear, `8` = 2nd+ gear |

### B. Air Pressure & Temperature Channels
| PID | Command | Parameter | Unit | Formula (`X = A*256+B`) | Verified Real-World Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`38`** | `022138` | **Barometric / Ambient Pressure** | `kPa` | `X / 10` | `96.8 kPa` (~968 mbar at ~400m elevation; `10.4` status toggle) |
| **`3D`** | `02213D` | **MAP Cylinder 1 (Horizontal)** | `kPa` | `X / 10` | `85.4 kPa` key-on; `88–90 kPa` idle; drops to `~61 kPa` under load |
| **`3F`** | `02213F` | **MAP Cylinder 2 (Vertical)** | `kPa` | `X / 10` | `85.6 kPa` key-on; tracks Cylinder 1 intake vacuum |
| **`31`** | `022131` | **Coolant / Sensor Temp 1** | `°C` | `X - 40` | `46` (`6°C` cold start) → `50` (`10°C`) |
| **`32`** | `022132` | **Intake Air Temp (IAT)** | `°C` | `X - 40` | `55` (`15°C` ambient) → `69` (`29°C` airbox heat-soak) |
| **`33`** | `022133` | **Engine Coolant Temp (ECT)** | `°C` | `X - 40` | `48` (`8°C` cold) → `145` (`105°C` full operating temperature) |
| **`34`** | `022134` | **Engine Oil / Head Temp** | `°C` | `X - 40` | `48` (`8°C` cold) → `145` (`105°C` full operating temperature) |

### C. Fuel Injection, Lambda O2 & Closed-Loop Trim Channels
| PID | Command | Parameter | Unit | Formula (`X = A*256+B`) | Verified Real-World Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`44`** | `022144` | **Actual Injector Pulse Width — Cyl 1** | `ms` | `X / 100` | `9.34 ms` key-on prime; `4.5–6.5 ms` idle; `8.88 ms` load |
| **`45`** | `022145` | **Actual Injector Pulse Width — Cyl 2** | `ms` | `X / 100` | `9.40 ms` key-on prime; `4.4–6.3 ms` idle; `8.64 ms` load |
| **`46`** | `022146` | **Base Fuel Map Pulse Width — Cyl 1** | `ms` | `X / 100` | Pre-correction base map time (`5.32 ms` idle vs `6.41 ms` actual) |
| **`47`** | `022147` | **Base Fuel Map Pulse Width — Cyl 2** | `ms` | `X / 100` | Pre-correction base map time (`5.28 ms` idle vs `6.29 ms` actual) |
| **`48`** | `022148` | **Effective Fuel Time (Post-Deadtime) — Cyl 1** | `ms` | `X / 100` | Tracks net fuel pulse (`9.34` key-on, `0` on decel fuel cut) |
| **`49`** | `022149` | **Effective Fuel Time (Post-Deadtime) — Cyl 2** | `ms` | `X / 100` | Tracks net fuel pulse (`9.34` key-on, `0` on decel fuel cut) |
| **`57`** | `022157` | **Narrowband O2 Sensor — Cyl 1** | `mV` | `X` | Actively oscillates `14–1059 mV` during closed-loop cruise |
| **`58`** | `022158` | **Narrowband O2 Sensor — Cyl 2** | `mV` | `X` | Actively oscillates `14–845 mV` during closed-loop cruise |
| **`59`** | `022159` | **Closed-Loop Fuel Trim Multiplier — Cyl 1** | `%` | `(X - 40000) / 400` | Centered at `40000` (`0.0%`); swings `36186` (`-9.5%`) to `46096` (`+15.2%`) |
| **`5A`** | `02215A` | **Closed-Loop Fuel Trim Multiplier — Cyl 2** | `%` | `(X - 40000) / 400` | Centered at `40000` (`0.0%`); swings `36408` (`-9.0%`) to `45240` (`+13.1%`) |
| **`61`** | `022161` | **Long-Term Adaptive Integrator — Cyl 1** | `raw` | `X` | Steady baseline `223` |
| **`62`** | `022162` | **Long-Term Adaptive Integrator — Cyl 2** | `raw` | `X` | Steady baseline `224` |

### D. Ignition, Air Mass, Electrical & Secondary Channels
| PID | Command | Parameter | Unit | Formula (`X = A*256+B`) | Verified Real-World Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`4A`** | `02214A` | **Ignition Timing Advance — Cyl 1** | `° BTDC` | `X / 10` | `5.5°` off; `11–13°` idle; advances to `41.2°` under cruise |
| **`4B`** | `02214B` | **Ignition Timing Advance — Cyl 2** | `° BTDC` | `X / 10` | Tracks Cylinder 1 spark advance (`5.5°` to `42.5°`) |
| **`4C`** | `02214C` | **Target / Base Ignition Advance** | `° BTDC` | `X / 10` | `7.0°` off; `10–44°` running |
| **`4F`** | `02214F` | **Cylinder 1 Air Load / Mass** | `mg/str` | `X / 10` | `0` off & decel cut; `130–292 mg` running |
| **`50`** | `022150` | **Cylinder 2 Air Load / Mass** | `mg/str` | `X / 10` | `0` off & decel cut; `125–241 mg` running |
| **`36`** | `022136` | **Battery / System Voltage** | `V` | `X * 0.0625` | `204` = `12.75V` key-on; rises to `14.2–14.4V` charging |
| **`53` / `54`** | `022153` | **Idle Target RPM — Cyl 1 / Cyl 2** | `rpm` | `X` | `1600–1700` cold fast-idle target → drops to `1350` warm idle |
| **`63`** | `022163` | **Engine Run / Crank Counter** | `raw` | `X` | Increments continuously while engine is running |
| **`65` / `66`** | `022165` | **Engine State Flags 1 & 2** | `flag` | `A` (1-byte) | `0` when engine stopped; `1–5` running |

### E. Passive CAN Broadcast Frames (`ATSP6` + `ATH1` + `ATMA`)
For reference, the Marelli 7SM and BBS also broadcast passive 500 kbps CAN frames continuously (used by MelcoDiag and the instrument cluster):
* **`020`**: Engine RPM (bytes 4–5) & Coolant Temp (byte 7)
* **`080`**: Throttle Plate Position & Torque Request flags
* **`024`**: Front & Rear ABS Wheel Speed tooth counters (bytes 0–1 Front, bytes 2–3 Rear)
* **`018`**: Battery Voltage & Gear/Neutral flags
* **`120` / `022` / `200` / `230`**: Riding Mode, ABS/DTC status, Odometer, and Heartbeat

---

## 4. High-Speed 10 Hz Logging Strategy (`~0.1s` Interval)

Because ELM327 adapters poll one PID at a time over Bluetooth serial (`~20–35 ms` round-trip per PID):
* Polling **all 89 channels** takes ~7–10 seconds per row (useful only for static/slow discovery).
* Polling **5–6 core channels** on `7E0` (without switching headers to `7E2`) achieves **~6–10 Hz (`0.10–0.16s` interval)**, ideal for **Virtual Road Dyno** pulls and **AFR/Fuel Trim** heatmaps.

### Recommended 6-PID Fast Logging Set (`7E0` Only)
1. `022130` — **Engine RPM** (`rpm`)
2. `02217A` — **Vehicle Speed** (`km/h`)
3. `02213C` — **Throttle Plate TPS 1** (`%`)
4. `02213B` — **Twistgrip APS** (`%`)
5. `02213D` — **MAP Cylinder 1** (`kPa`)
6. `022144` — **Actual Injector Time Cyl 1** (`ms`) *(or `022159` for Closed-Loop Fuel Trim `%`)*

---

## 5. Fuel Mapping & Virtual Road Dyno Formulas

### A. Closed-Loop Fuel Trim & Total Enrichment
1. **Closed-Loop Short-Term Trim (`%`) from `ECU_59` / `ECU_5A`:**
   $$\text{STFT (\%)} = \frac{\text{ECU\_59} - 40000}{400}$$
2. **Total ECU Fuel Correction (`%`) from Actual (`ECU_44`) vs. Base (`ECU_46`) Injector Time:**
   $$\text{Total Correction (\%)} = \left(\frac{\text{ECU\_44}}{\text{ECU\_46}} - 1\right) \times 100$$

### B. Speed-Density Estimated AFR
Using per-cylinder displacement $V_d = 0.4105\text{ L}$ (821cc twin), intake manifold pressure $P_{\text{MAP}}$ (`kPa`), intake air temperature $T_{\text{IAT}}$ (`°C`), volumetric efficiency $\eta_v \approx 0.88$, injector flow rate $\dot{m}_{\text{inj}} \approx 3.65\text{ mg/ms}$, and injector dead-time $t_0 \approx 0.85\text{ ms}$:
$$m_{\text{air}} \text{ (mg)} = \frac{P_{\text{MAP}} \times V_d \times 28.97}{8.314 \times (T_{\text{IAT}} + 273.15)} \times \eta_v \times 1000$$
$$m_{\text{fuel}} \text{ (mg)} = (\text{Inj\_ms} - t_0) \times \dot{m}_{\text{inj}}, \qquad \text{Estimated AFR} = \frac{m_{\text{air}}}{m_{\text{fuel}}}$$

### C. Virtual Road Dyno (Wheel & Crank Power / Torque)
During a single-gear full-throttle pull on a flat road (with vehicle + rider mass $m \approx 278\text{ kg}$, supermoto drag area $C_d A \approx 0.56\text{ m}^2$, air density $\rho \approx 1.18\text{ kg/m}^3$, rolling resistance $C_{rr} \approx 0.015$, and chain drivetrain loss $\approx 10\%$):
$$v = \frac{\text{Speed}_{\text{km/h}}}{3.6} \text{ (m/s)}, \qquad a = \frac{\Delta v}{\Delta t} \text{ (m/s}^2\text{)}$$
$$F_{\text{total}} = m \cdot a + \frac{1}{2} \rho C_d A v^2 + m g C_{rr}$$
$$P_{\text{wheel}} \text{ (hp)} = \frac{F_{\text{total}} \cdot v}{745.7}, \qquad P_{\text{crank}} \text{ (hp)} = \frac{P_{\text{wheel}}}{0.90}, \qquad \tau_{\text{crank}} \text{ (Nm)} = \frac{P_{\text{crank}} \times 745.7 \times 60}{2\pi \times \text{RPM}}$$

---

## 6. Android Logging Notes (Pydroid 3 + Kivy + Pyjnius)
* **Bluetooth Socket Fallback:** On Android 8.0+ (e.g., Samsung Galaxy S7 Edge), standard `createRfcommSocketToServiceRecord` can fail SDP lookup on ELM327 `v1.5` modules. Use `createInsecureRfcommSocketToServiceRecord` with a Java reflection fallback to `createRfcommSocket(1)`.
* **Preventing Sleep Mid-Ride:** Add `WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON` in `App.on_start()` and whitelist Pydroid 3 under Android's unmonitored battery apps so Doze does not throttle Bluetooth polling.
