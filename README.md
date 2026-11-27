This is a small project to log ECU and BBS data from hypermotard 821.
prerequisite: android device, reliable bluetooth ELM357 adapter (recommended: lonelec), pydroid 3, pydroid repository plugin, pydroid permission plugin, location enabled.
end goal is to log bike data on android device for later analysis and potential virtual dyno visualisation.

(to make this work on iOS, one would require BLE ELM adapter)

the streamlined, high-speed DucatiFastLoggerApp script for Pydroid 3 on an Android device polls only the 7 verified Engine ECU (7E0) channels needed for both Virtual Road Dyno and AFR / Closed-Loop Fuel Trim Analysis, using the ELM327 single-frame fast-reply suffix (0221xx1) and zero header switching—pushing sample rate to ~8–10 Hz (~0.10–0.13s per row).

What This Script Logs (hypermotard_fastlog_YYYYMMDD_HHMMSS.csv)

• Time_s: High-precision monotonic timestamp (0.001s resolution).
• RPM (0221301): Engine speed (rpm).
• Speed_kmh (02217A1): Verified vehicle speed (km/h).
• TPS_pct (02213C1): Throttle body 1 opening (%).
• Twistgrip_pct (02213B1): Handlebar twistgrip demand (%).
• MAP1_kPa (02213D1): Horizontal cylinder manifold pressure (kPa).
• Inj1_ms (0221441): Horizontal cylinder actual injector pulse width (ms).
• STFT1_pct (0221591): Closed-loop short-term fuel trim percentage ((raw - 40000) / 400, showing -15% to +15% live trim).
• OilTemp_C (0221341, polled once every 50 cycles so it adds zero overhead): Engine oil/head temperature (°C) for warm-engine filtering.



Quick Note on the 0221xx1 Fast-Reply Suffix

• When you run this on the bike, watch the top line FAST LOGGING (X.X Hz):
	• If RPM and Speed populate immediately at 7–10 Hz, the trailing 1 optimization is working at full speed.
	• If any channel shows None because your specific ELM327 firmware prefers standard 6-character requests without the trailing 1, simply change "0221301" → "022130" (and the same for the other 7 commands)—it will still run at a clean ~5–6 Hz with zero header-switching delays.
