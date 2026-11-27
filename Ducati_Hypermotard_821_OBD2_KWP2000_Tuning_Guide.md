# Ducati Hypermotard 821 (2013–2015) — OBD2 / KWP2000 Telemetry, AFR & Virtual Dyno Guide

Complete technical reference for logging live engine telemetry from a **2013–2015 Ducati Hypermotard 821 (Magneti Marelli 7SM ECU)** using a Bluetooth **ELM327 v1.5** adapter on Android, macOS, or Windows.

---

## 1. Hardware & Wiring Requirements

### Adapter Compatibility
* **Required Chipset:** Genuine **ELM327 v1.4 or v1.5** (e.g., Lonelec Bluetooth v1.5). Budget `v2.1` clones lack `ATCAF0` and raw ISO-TP framing commands and will fail to handshake with the Marelli 7SM.
* **Ducati 4-Pin DDA to 16-Pin OBD2 Pinout:**
  * **Ducati Pin 1** (Red/White) → **OBD2 Pin 16** (+12V Battery)
  * **Ducati Pin 2** (Black) → **OBD2 Pins 4 & 5** (Ground)
  * **Ducati Pin 3** (White/Yellow, CAN-High) → **OBD2 Pin 6** (CAN-H)
  * **Ducati Pin 4** (White/Blue, CAN-Low) → **OBD2 Pin 14** (CAN-L)

### Connection Behavior by Module
* **Engine ECU (`7E0` / `7E8`):** Responds continuously to KWP2000 diagnostic queries (`021001` → `025001`) both stationary and while riding. Requires ignition key ON and red engine kill-switch in **RUN**.
* **BBS / ABS Module (`7E2` / `7EA`):** Responds to `021081` → `025081` only when stationary; locks out diagnostic polling once the motorcycle is in motion as a safety precaution. Always poll vehicle speed from the Engine ECU (`02217A`) instead.

---

## 2. ELM327 Initialization Sequence

Standard passenger-car OBD2 apps fail because the pre-Euro 5 Marelli 7SM rejects standard Mode `01` (`0100`) and UDS Mode `22` (`0322...`) requests, and requires manual ISO-TP PCI length formatting (`ATCAF0`).

```text
ATZ          # Reset ELM327
ATE0         # Echo off
ATL0         # Linefeeds off
ATS0         # Spaces off
ATH0         # Headers off
ATSP6        # Protocol 6: ISO 15765-4 CAN (11-bit ID, 500 kbaud)
ATCAF0       # CAN Auto-Formatting OFF (manual PCI length bytes required)
ATSH7E0      # Set transmit header to Engine ECU (7E0)
ATCRA7E8     # Filter receive address to Engine ECU reply (7E8)
021001       # Open KWP2000 Standard Diagnostic Session -> replies 025001
```

* **Session Keep-Alive:** Resend `021001` every ~3 seconds (`25–30` polling cycles) so the diagnostic session does not time out.
* **Clean Session Exit:** Send `0120` (KWP2000 `StopDiagnosticSession` → replies `0160`) followed by `ATPC` (`Protocol Close`) before closing the serial socket.

---

## 3. Verified Magneti Marelli 7SM KWP2000 PID Map (`0221xx`)

All commands below use **KWP2000 Service `0x21` (`ReadDataByLocalIdentifier`)** sent as `0221<PID>` (or `0221<PID>1` with trailing `1` for immediate single-frame ELM327 reply). Responses follow the format `04 61 <PID> <BYTE_A> <BYTE_B>` (or `03 61 <PID> <BYTE_A>` for 1-byte flags).

### A. Core Engine, Throttle & Speed Channels

| Command | ECU ID | Parameter | Unit | Scaling Formula | Verified Empirical Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`022130`** | `ECU_30` | **Engine RPM** | `rpm` | `A*256 + B` | `0` off; `~1,350–1,650` idle; `1:1` direct integer |
| **`02217A`** | `ECU_7A` | **Vehicle Speed** | `km/h` | `A*256 + B` | `0` stationary; tracks true road speed (`1:1` integer) |
| **`02213B`** | `ECU_3B` | **Twistgrip Position (APS)** | `%` | `(A*256 + B) / 10` | Handlebar grip demand (`0.0%` closed to `100.0%` WOT) |
| **`02213C`** | `ECU_3C` | **Throttle Body 1 (TPS1)** | `%` | `(A*256 + B) / 10` | `16.6%` key-on resting; `~12.4%` warm idle; RbW-capped |
| **`02213E`** | `ECU_3E` | **Throttle Body 2 (TPS2)** | `%` | `(A*256 + B) / 10` | `16.7%` key-on resting; tracks `TPS1` across rev range |

### B. Air Pressure & Temperature Channels

| Command | ECU ID | Parameter | Unit | Scaling Formula | Verified Empirical Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`02213D`** | `ECU_3D` | **MAP Cylinder 1 (Horizontal)** | `kPa` | `(A*256 + B) / 10` | Manifold absolute pressure (`~89 kPa` idle, drops on open throttle) |
| **`02213F`** | `ECU_3F` | **MAP Cylinder 2 (Vertical)** | `kPa` | `(A*256 + B) / 10` | Manifold absolute pressure (`~89 kPa` idle) |
| **`022138`** | `ECU_38` | **Barometric Pressure** | `kPa` | `(A*256 + B) / 10` | Ambient atmospheric pressure (`96.8 kPa` at ~400 m elevation) |
| **`022131`** | `ECU_31` | **Engine Coolant Temp (ECT)** | `°C` | `(A*256 + B) - 40` | Standard `+40` offset (`46` raw = `6°C`) |
| **`022132`** | `ECU_32` | **Intake Air Temp (IAT)** | `°C` | `(A*256 + B) - 40` | Airbox sensor (`55` raw = `15°C` cold, rises with heat soak) |
| **`022134`** | `ECU_34` | **Engine Oil / Head Temp** | `°C` | `(A*256 + B) - 40` | Reaches `~100–105°C` (`140–145` raw) during warm street riding |

### C. Fuel Injection, O2 Sensors & Closed-Loop Fuel Trims

| Command | ECU ID | Parameter | Unit | Scaling Formula | Verified Empirical Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`022144`** | `ECU_44` | **Actual Injector Pulse Cyl 1** | `ms` | `(A*256 + B) / 100` | Final injector open time (`~6.2 ms` idle, `0 ms` DFCO decel) |
| **`022145`** | `ECU_45` | **Actual Injector Pulse Cyl 2** | `ms` | `(A*256 + B) / 100` | Final injector open time (`~6.1 ms` idle) |
| **`022146`** | `ECU_46` | **Base Fuel Table Pulse Cyl 1** | `ms` | `(A*256 + B) / 100` | Pre-trim base map pulse width (`~5.1 ms` idle) |
| **`022147`** | `ECU_47` | **Base Fuel Table Pulse Cyl 2** | `ms` | `(A*256 + B) / 100` | Pre-trim base map pulse width (`~5.0 ms` idle) |
| **`022157`** | `ECU_57` | **Narrowband O2 Voltage Cyl 1** | `mV` | `A*256 + B` | Oscillates `~15–1050 mV` during closed-loop cruise |
| **`022158`** | `ECU_58` | **Narrowband O2 Voltage Cyl 2** | `mV` | `A*256 + B` | Oscillates `~15–980 mV` during closed-loop cruise |
| **`022159`** | `ECU_59` | **Closed-Loop Fuel Trim Cyl 1** | `%` | `((A*256 + B) - 40000) / 400` | Centered at `40000` (`0.0%`); swings `~36000` (`-10%`) to `46000` (`+15%`) |
| **`02215A`** | `ECU_5A` | **Closed-Loop Fuel Trim Cyl 2** | `%` | `((A*256 + B) - 40000) / 400` | Centered at `40000` (`0.0%`); tracks Cyl 2 closed-loop correction |

### D. Ignition, Air Load & Status Flags

| Command | ECU ID | Parameter | Unit | Scaling Formula | Verified Empirical Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`02214A`** | `ECU_4A` | **Ignition Advance** | `° BTDC` | `(A*256 + B) / 10` | `5.5°` key-on; `~12–13°` idle; up to `~41°` light cruise |
| **`02214F`** | `ECU_4F` | **Cylinder 1 Air Load** | `raw` | `A*256 + B` | `0` on DFCO decel; scales with cylinder air charge |
| **`022150`** | `ECU_50` | **Cylinder 2 Air Load** | `raw` | `A*256 + B` | `0` on DFCO decel; scales with cylinder air charge |
| **`022136`** | `ECU_36` | **Battery Voltage** | `V` | `(A*256 + B) * 0.0625` | `204` (`12.75V`) key-on engine off |
| **`022165`** | `ECU_65` | **ECU Operating State Flag** | `raw` | `A` | `0–4` during stationary/idle/cruise; `253–255` on overrun/transients |
| **`022186`** | `ECU_86` | **Engine Stopped / Neutral Flag** | `flag` | `A` | `1` when engine stopped / neutral; `0` while engine is running |

> **Gear Position Note:** The 2013–2015 Hypermotard 821 has no physical gear position sensor or dash gear indicator. Calculate active gear (`1st` through `6th`) in post-processing from `Speed_kmh / (RPM / 1000)` (`1st ≈ 11.5`, `2nd ≈ 14.2`, `3rd ≈ 16.9`, `4th ≈ 19.7`, `5th ≈ 22.2`, `6th ≈ 24.5 km/h per 1,000 RPM`).

---

## 4. High-Speed 10 Hz Logging Strategy

Because ELM327 Bluetooth adapters poll sequentially (`~15–20 ms` per single-frame command), polling all 89 channels takes ~8–10 seconds per row. For high-resolution **Virtual Road Dyno** and **AFR / Fuel Trim** logging (~8–10 Hz):

1. Poll **only 7 core channels** on `7E0`: `0221301` (RPM), `02217A1` (Speed), `02213C1` (TPS), `02213B1` (Twistgrip), `02213D1` (MAP1), `0221441` (Inj1), and `0221591` (Closed-Loop Trim 1).
2. Append trailing **`1`** to each command (`0221301`) so the ELM327 returns the `>` prompt immediately after receiving 1 CAN frame instead of waiting for its `ATST` timeout.
3. Poll slow temperature channels (`0221341` Oil Temp) once every 50 cycles.

### Android (Samsung S7 Edge / Pydroid 3) Implementation Notes
* **RFCOMM Connection:** Use `device.createInsecureRfcommSocketToServiceRecord(UUID)` with a reflection fallback to `device.createRfcommSocket(1)` for older Android Classic Bluetooth stacks.
* **Prevent Sleep Throttling:** Add `WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON` in `on_start()` and exempt Pydroid 3 from battery optimization so Android does not throttle Bluetooth polling mid-ride.

---

## 5. Post-Processing Formulas (AFR & Virtual Road Dyno)

* **Closed-Loop Fuel Trim (%):**
  $$	ext{STFT (\%)} = rac{	ext{ECU\_59} - 40000}{400}$$
* **Total Enrichment vs. Base Map (%):**
  $$	ext{Total Fuel Correction (\%)} = \left(rac{	ext{ECU\_44}}{	ext{ECU\_46}} - 1ight) 	imes 100$$
* **Speed-Density Air Mass per Cylinder (`mg`):**
  $$m_{	ext{air}} = V_{	ext{cyl}} 	imes \eta_v 	imes rac{P_{	ext{MAP}}}{R_{	ext{air}} \cdot T_{	ext{IAT}}}$$
  *(where $V_{	ext{cyl}} = 410.5	ext{ cm}^3$ per cylinder on the 821cc twin)*
* **Virtual Road Dyno Wheel Power (`W`):**
  $$P_{	ext{wheel}} = \left( m_{	ext{total}} \cdot rac{\Delta v}{\Delta t} + rac{1}{2} ho C_d A v^2 + m_{	ext{total}} g C_{rr} ight) \cdot v$$
  *(Baseline Hypermotard 821 constants: $m_{	ext{total}} pprox 278	ext{ kg}$ wet bike + rider, $C_d A pprox 0.56	ext{ m}^2$, $C_{rr} pprox 0.015$, drivetrain loss $pprox 10\%$)*
