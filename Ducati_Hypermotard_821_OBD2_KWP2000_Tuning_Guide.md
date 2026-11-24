# Ducati Hypermotard 821 (Marelli 7SM) & Porsche 991.1 OBD2 / KWP2000 Data Logging & Telemetry Guide

A comprehensive technical reference for logging live engine telemetry over Bluetooth ELM327 (`v1.5`) on Android (**Car Scanner ELM OBD2**), decoding Magneti Marelli 7SM KWP2000-over-CAN parameters, calculating Virtual Road Dyno power/torque curves, and building RPM vs. TPS fuel/usage heatmaps.

---

## 1. Hardware & Physical Layer Setup

### Ducati Hypermotard 821 (2013–2015, Euro 3, Magneti Marelli 7SM ECU)
* **Adapter:** Genuine **ELM327 v1.5** Bluetooth adapter (e.g., Lonelec). Budget `v2.1` clones lack raw ISO-TP / CAN formatting commands (`ATCAF0`, `ATSP6`) and will fail to handshake.
* **Diagnostic Cable:** Ducati 4-pin DDA connector (located under the seat) to 16-pin OBD2 female adapter.
  * **Ducati Pin 1** (Red/White) $\rightarrow$ **OBD2 Pin 16** (`+12V` Battery)
  * **Ducati Pin 2** (Black) $\rightarrow$ **OBD2 Pin 4 & 5** (`GND`)
  * **Ducati Pin 3** (White/Yellow) $\rightarrow$ **OBD2 Pin 6** (`CAN-High`, 500 kbps)
  * **Ducati Pin 4** (White/Blue) $\rightarrow$ **OBD2 Pin 14** (`CAN-Low`, 500 kbps)
* **Bike State:** Ignition key **ON** and red engine kill-switch in **RUN** (the Marelli 7SM CAN diagnostic responder does not power up when the kill-switch is in STOP).

### Porsche 991.1 Carrera S (2012, 3.8L MA1.03 DFI, Siemens SDI 9.1 ECU)
* **Port:** Standard 16-pin OBD2 port under the driver's footwell dashboard (no adapter cable required).
* **Profile:** Select **Porsche / VAG OBD-II** in Car Scanner. Supports standard OBD2 Mode `01` PIDs including factory wideband LSU O2 Lambda (`0124`/`0128` or `0134`/`0138`), Calculated Engine Load (`0104`), MAF (`0110`), Fuel Trims (`0106`–`0109`), and Ignition Timing Advance (`010E`).

---

## 2. Why Standard OBD2 Fails on the Hypermotard 821 (And How to Fix It)

The 2013–2015 Hypermotard 821 predates mandatory Euro 4/5 motorcycle OBD2 standardization:
1. **Ignores Functional Broadcast (`7DF`):** The ECU only responds to physical CAN header **`7E0`** (replying on **`7E8`**). The BBS / dashboard module responds on **`7E2`** (replying on **`7EA`**).
2. **Rejects Standard OBD2 (`Mode 01`) and UDS (`Service 22`):**
   * `02 10 81` $\rightarrow$ `03 7F 10 12` (Sub-function not supported)
   * `03 22 F1 84` $\rightarrow$ `03 7F 22 11` (UDS Service `22` not supported)
3. **Uses KWP2000-over-CAN (`ISO 15765-4`, 500 kbps) with Manual ISO-TP PCI Length Bytes (`ATCAF0`):**
   * Opening a standard diagnostic session requires sending **`02 10 01`**, which returns **`02 50 01`**.
   * Live engine parameters are read via **KWP2000 `ReadDataByLocalIdentifier` (`Service 21`)** using 2-byte requests (`02 21 xx`).

---

## 3. Android App Setup: Car Scanner ELM OBD2 (Free Tier)

The free tier of **Car Scanner ELM OBD2** supports custom initialization strings, custom KWP2000 PIDs, and native **CSV export** without requiring a paid upgrade.

### A. Connection & Advanced ELM327 Settings
Navigate to **Settings $\rightarrow$ Connection**:
* **Connection Profile:** `OBD-II / EOBD` (generic)
* **Protocol:** `6 - ISO 15765-4 CAN (11 bit ID, 500 kbaud)`

Navigate to **Settings $\rightarrow$ Connection $\rightarrow$ Advanced settings**:
* **ELM327 adaptive timings:** `Automatic 1` *(switch to `Off` if rapid throttle transitions drop packets)*
* **ELM327 send ATST:** `Don't send` *(or `Send 32`)*
* **Custom functional header:** `7E0`
* **PID command to check connection:** `021001`
* **Decode positive response to confirm successful connection:** `OFF` *(crucial—ECU returns `025001`, not OBD2 `4100`)*
* **Tester present command:** `023E00` *(or `021001` to keep the KWP2000 session from timing out after ~4 seconds)*
* **Use OBD2 PIDs:** `OFF` *(prevents polling unsupported Mode `01` PIDs once Custom PIDs are added)*
* **OBDonUDS support:** `OFF`
* **Request ECU information:** `OFF`

### B. Raw ELM327 Terminal Initialization Sequence
For manual verification in **Car Scanner Terminal** (or `PuTTY` / `Tera Term` / `CoolTerm` / `pyserial` on desktop):

```text
ATZ
ATSP6
ATE0
ATH0
ATS0
ATCAF0
ATSH7E0
ATCRA7E8
021001
```
Expected handshake response: `025001`

---

## 4. Decoded Ducati Hypermotard 821 (Marelli 7SM) KWP2000 PIDs

All commands below are strictly **read-only** (`Service 0x21`) sent to header `7E0` (receiving from `7E8`) with `ATCAF0` enabled after opening session `021001`.

### Complete Verified PID Table (`022130` – `022166`)

| Command (Hex) | Sample Key-On Reply | Sample Idling Reply | Decoded Sensor | Primary Formula (`A,B` = payload) | Shifted Formula (`D,E` if `04 61 xx` included) | Unit |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`022130`** | `0461300000` | `0461300661` | **Engine RPM** (`0x0661` = `1633 rpm`) | `A*256+B` | `D*256+E` | `rpm` |
| **`022131`** | `046131002D` | — | **Engine Coolant Temp (ECT)** (`45 - 40 = 5°C`) | `B-40` | `E-40` | `°C` |
| **`022132`** | `0461320031` | — | **Intake Air Temp (IAT)** (`49 - 40 = 9°C`) | `B-40` | `E-40` | `°C` |
| **`022134`** | `046134002D` | — | **Oil / Secondary Temp** (`45 - 40 = 5°C`) | `B-40` | `E-40` | `°C` |
| **`022135`** | `0461350000` | — | **Vehicle Speed (_wrong_to be corrected_)** | `A*256+B` | `D*256+E` | `km/h` |
| **`022136`** | `04613600CC` | — | **Battery Voltage** (`204 * 0.0625 = 12.75V`) | `(A*256+B)*0.0625` | `(D*256+E)*0.0625` | `V` |
| **`022138`** | `04613803C8` | — | **Barometric Pressure** (`968 / 10 = 96.8 kPa`) | `(A*256+B)/10` | `(D*256+E)/10` | `kPa` |
| **`02213A`** | `04613A00CC` | — | **Switched / Reference Voltage** (`12.75V`) | `(A*256+B)*0.0625` | `(D*256+E)*0.0625` | `V` |
| **`02213B`** | `04613B0000` | `04613B0000` | **Twistgrip Position (APS)** (`0.0%` closed) | `(A*256+B)/10` | `(D*256+E)/10` | `%` |
| **`02213C`** | `04613C00A6` | `04613C0080` | **Throttle Body 1 (TPS)** (`16.6%` key-on, `12.8%` idle) | `(A*256+B)/10` | `(D*256+E)/10` | `%` |
| **`02213D`** | `04613D0356` | `04613D037C` | **MAP Cylinder 1 (Horizontal)** (`85.4`–`89.2 kPa`) | `(A*256+B)/10` | `(D*256+E)/10` | `kPa` |
| **`02213E`** | `04613E00A7` | — | **Throttle Body 2 (TPS 2)** (`16.7%`) | `(A*256+B)/10` | `(D*256+E)/10` | `%` |
| **`02213F`** | `04613F0359` | `04613F0381` | **MAP Cylinder 2 (Vertical)** (`85.7`–`89.7 kPa`) | `(A*256+B)/10` | `(D*256+E)/10` | `kPa` |
| **`022140`** | `0461400043` | `046140001C` | **Lambda O2 Voltage Cyl 1 (Horizontal)** (`0.335V` / `0.140V`) | `(A*256+B)*0.005` | `(D*256+E)*0.005` | `V` |
| **`022141`** | — | `046141001B` | **Lambda O2 Voltage Cyl 2 (Vertical)** (`0.135V`) | `(A*256+B)*0.005` | `(D*256+E)*0.005` | `V` |
| **`022144`** | — | `0461440262` | **Actual Injector Pulse Width Cyl 1** (`6.10 ms`) | `(A*256+B)/100` | `(D*256+E)/100` | `ms` |
| **`022145`** | — | `0461450247` | **Actual Injector Pulse Width Cyl 2** (`5.83 ms`) | `(A*256+B)/100` | `(D*256+E)/100` | `ms` |
| **`022146`** | — | `04614601EE` | **Base Fuel Table Pulse Width Cyl 1** (`4.94 ms`) | `(A*256+B)/100` | `(D*256+E)/100` | `ms` |
| **`022147`** | — | `04614701E5` | **Base Fuel Table Pulse Width Cyl 2** (`4.85 ms`) | `(A*256+B)/100` | `(D*256+E)/100` | `ms` |
| **`022148`** | — | `046148025D` | **Secondary / Target Fuel Time Cyl 1** (`6.05 ms`) | `(A*256+B)/100` | `(D*256+E)/100` | `ms` |
| **`022149`** | — | `0461490243` | **Secondary / Target Fuel Time Cyl 2** (`5.79 ms`) | `(A*256+B)/100` | `(D*256+E)/100` | `ms` |
| **`02214A`** | — | `04614A006F` | **Ignition Timing Advance** (`11.1° BTDC`) | `(A*256+B)/10` | `(D*256+E)/10` | `°` |
| **`022150`** | — | `0461500483` | **Idle Stepper / Air Control Target** (`1155`) | `A*256+B` | `D*256+E` | `steps` |
| **`022161`** | — | `04616100DF` | **Closed-Loop Lambda Integrator Cyl 1** (`223`) | `A*256+B` | `D*256+E` | `raw` |
| **`022162`** | — | `04616200E0` | **Closed-Loop Lambda Integrator Cyl 2** (`224`) | `A*256+B` | `D*256+E` | `raw` |
| **`022163`** | — | `046163128B` | **Engine Run Counter / Cumulative Revs** | `A*256+B` | `D*256+E` | `raw` |
| **`022165`** | — | `03616505` | **Gear / Engine State Flag** (`0x05`) | `A` | `D` | `state` |

*(Note: Unsupported IDs such as `022101`–`022110`, `022139`, and `022151` safely return `037F2131` = Request Out of Range).*

> **Byte Offset Verification Tip:** Because `ATCAF0` includes the `04` PCI length byte in the raw reply (`04 61 30 06 61`), test `022130` first using Car Scanner's built-in **Test** button. If `A*256+B` evaluates `04 61` (`1121`), shift all byte variables by 3 letters (`A` $\rightarrow$ `D`, `B` $\rightarrow$ `E`).

---

## 5. Passive CAN Bus Broadcast IDs (500 kbps)

When not polling via KWP2000, the Hypermotard 821 broadcasts continuous telemetry frames on the CAN bus (used by the instrument cluster, ABS, and DTC):

| CAN ID | Sample Payload | Broadcast Contents |
| :--- | :--- | :--- |
| **`020`** | `00 90 05 30 39 60 03 C0` | **Engine RPM** (`0x0396` = `918 rpm`) & **Coolant Temp** (`0x3C` = `60°C`) |
| **`080`** | `00 10 84 50 00 00 00 C8` | **Throttle Position (TPS)**, twistgrip torque request & engine status |
| **`024`** | `58 E0 AF 54 00 00 00 00` | **Front & Rear Wheel Speeds** (ABS / DTC wheel speed sensors) |
| **`018`** | `00 00 42 00 00 00 00 03` | **Battery Voltage** & **Gear Position / Neutral** |
| **`120`** | `84 0B 01 00 00 00 04 02` | **Riding Mode**, kill-switch & immobilizer status |
| **`022`** | `00 00 00 00 00 01 00 00` | **ABS / DTC Intervention** & brake switch status |

---

## 6. Fuel Mapping & AFR Analysis Methodology (Without Wideband O2)

1. **Riding Usage & Ride-by-Wire (RbW) Heatmaps:**
   * Bin data into **500-RPM rows** (`1,500–9,500 RPM`) and **non-linear TPS columns** (`0, 2, 5, 10, 20, 40, 60, 80, 95%`), since street riding concentrates heavily in the **2%–10% throttle plate** range.
   * Compare **Twistgrip (`02213B`)** against **Throttle Plate (`02213C`)** to observe how the RbW ECU progressively restricts butterfly opening below ~7,500 RPM even at 100% grip.
2. **Closed-Loop Fuel Trim & Correction Map:**
   * **Effective Fuel Trim (%):** Compare **Actual Injector Pulse Width (`022144` / `022145`)** against **Base Fuel Pulse Width (`022146` / `022147`)**:
     $$\text{Total Fuel Correction (\%)} = \left(\frac{\text{PW}_{\text{actual}}}{\text{PW}_{\text{base}}} - 1\right) \times 100$$
   * **Closed-Loop vs. Open-Loop Boundary:** Monitor **Narrowband O2 Voltage (`022140` / `022141`)**. Rapid oscillation between `~0.1V` and `~0.85V` indicates closed-loop `14.7:1` stoichiometric operation; steady voltage (`>0.8V`) under load indicates open-loop enrichment.
   * **Estimated AFR (Speed-Density Calculation):** Combining **MAP (`02213D`)**, **IAT (`022132`)**, **RPM (`022130`)**, and **Actual Injector Pulse Width (`022144`)** allows estimating cylinder air mass vs. injected fuel mass across the map.
3. **Data Filtering Best Practices:**
   * Keep active logged PIDs to **5–6 channels max** per session to maintain high ELM327 sample rates (~8–12 Hz).
   * Filter out cold-start warm-up (`ECT < 75°C`) and overrun deceleration fuel-cut (`TPS < 1.5%`).
   * In Car Scanner **Settings $\rightarrow$ Data recording**, disable **Record GPS data** and **Record calculated sensors** to keep CSV exports clean.

---

## 7. Virtual Road Dyno Physics Equations (Power & Torque vs. RPM)

Using timestamped **RPM**, **Vehicle Speed ($v$ in m/s)**, and **Twistgrip/Throttle ($\ge 90\%$ WOT)** during a single-gear pull (2nd or 3rd gear) averaged in both directions on a flat road:

1. **Acceleration ($a$):**
   $$a = \frac{\Delta v}{\Delta t} \quad (\text{m/s}^2)$$
2. **Total Tractive Force at the Wheel ($F_{\text{total}}$):**
   $$F_{\text{total}} = \underbrace{m_{\text{eff}} \cdot a}_{\text{Inertia}} + \underbrace{\frac{1}{2} \rho C_d A v^2}_{\text{Aero Drag}} + \underbrace{C_{rr} m g}_{\text{Rolling Resistance}}$$
   * *Hypermotard 821 Defaults:* Wet mass + rider $m \approx 278\text{ kg}$ ($m_{\text{eff}} \approx 1.07 m$ for rotational inertia), $C_d A \approx 0.56\text{ m}^2$, $C_{rr} \approx 0.015$, drivetrain loss $\approx 10\%$.
   * *Porsche 991.1 Carrera S PDK Defaults:* Mass + driver $m \approx 1,495\text{ kg}$, $C_d = 0.29$, $A = 2.02\text{ m}^2$, drivetrain loss $\approx 14\%$.
3. **Wheel & Crank Power ($P$) and Torque ($\tau$):**
   $$P_{\text{wheel}} (\text{W}) = F_{\text{total}} \cdot v \quad \Longrightarrow \quad P_{\text{crank}} (\text{hp}) = \frac{P_{\text{wheel}}}{745.7 \times (1 - \text{Loss}\%)}$$
   $$\tau_{\\text{crank}} (\text{Nm}) = \frac{P_{\text{crank}} (\text{W}) \times 60}{2\pi \times \text{RPM}}$$

---

## 8. Python Mac/Windows KWP2000 Diagnostic Scanner Script

```python
import serial
import time

PORT = "/dev/cu.OBDII"  # Use "COM8" on Windows
ser = serial.Serial(PORT, 38400, timeout=0.5)

def send(cmd, wait=0.15):
    ser.write((cmd + "\r").encode())
    time.sleep(wait)
    return ser.read_all().decode(errors="ignore").replace("\r", " ").strip()

init_cmds = ["ATZ", "ATSP6", "ATE0", "ATH0", "ATS0", "ATCAF0", "ATSH7E0", "ATCRA7E8"]
for cmd in init_cmds:
    print(f"{cmd} -> {send(cmd, 0.4 if cmd == 'ATZ' else 0.1)}")

print(f"Session -> {send('021001', 0.2)}")

for pid in range(0x30, 0x70):
    if pid % 10 == 0:
        send("021001", 0.1)  # Keep KWP2000 diagnostic session alive
    req = f"0221{pid:02X}"
    resp = send(req, 0.12)
    if "61" in resp:
        print(f"FOUND {req} -> {resp}")

ser.close()
```
