import csv
import os
import threading
import time
from datetime import datetime
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.label import Label
from jnius import autoclass

MAC_ADDRESS = "00:1D:A5:09:04:4D"
SPP_UUID = "00001101-0000-1000-8000-00805F9B34FB"


class DucatiFullScanApp(App):
    def build(self):
        self.status_label = Label(
            text="Starting 100% Full-Range Scanner (0x01-0xFE)...\nEnsure key & kill-switch are ON.",
            font_size="16sp",
            halign="center",
        )
        self.running = True
        threading.Thread(target=self.log_loop, daemon=True).start()
        return self.status_label

    def on_start(self):
        try:
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            WindowManager_LayoutParams = autoclass(
                "android.view.WindowManager$LayoutParams"
            )
            PythonActivity.mActivity.getWindow().addFlags(
                WindowManager_LayoutParams.FLAG_KEEP_SCREEN_ON
            )
        except Exception:
            pass

    def update_ui(self, msg):
        Clock.schedule_once(lambda dt: setattr(self.status_label, "text", msg))

    def send_cmd(self, in_s, out_s, cmd, wait=0.02, timeout=0.35):
        out_s.write((cmd + "\r").encode("ascii"))
        out_s.flush()
        time.sleep(wait)
        buf = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            avail = in_s.available()
            if avail > 0:
                for _ in range(avail):
                    b = in_s.read()
                    if b == -1:
                        break
                    buf.append(b & 0xFF)
                if b">" in buf:
                    break
            else:
                time.sleep(0.004)
        text = buf.decode("ascii", errors="ignore")
        lines = [
            l.strip().replace(" ", "")
            for l in text.splitlines()
            if l.strip() and l.strip() != ">" and cmd not in l
        ]
        return lines[-1] if lines else ""

    def decode_payload(self, resp, pid_hex):
        prefix = "61" + pid_hex
        idx = resp.find(prefix)
        if idx == -1:
            return ""
        payload = resp[idx + len(prefix) :]
        if not payload:
            return ""
        # Return integer for 1-byte or 2-byte values; raw hex if multi-byte
        if len(payload) in (2, 4):
            try:
                return int(payload, 16)
            except ValueError:
                return payload
        return payload

    def log_loop(self):
        sock = None
        in_s = None
        out_s = None
        csv_path = None
        try:
            BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
            UUID = autoclass("java.util.UUID")
            Integer = autoclass("java.lang.Integer")
            dev = BluetoothAdapter.getDefaultAdapter().getRemoteDevice(MAC_ADDRESS)

            try:
                sock = dev.createInsecureRfcommSocketToServiceRecord(
                    UUID.fromString(SPP_UUID)
                )
                sock.connect()
            except Exception:
                m = dev.getClass().getMethod("createRfcommSocket", [Integer.TYPE])
                sock = m.invoke(dev,)
                sock.connect()

            in_s = sock.getInputStream()
            out_s = sock.getOutputStream()

            self.update_ui("Connected! Initializing Marelli 7SM (7E0)...")
            for cmd, d in [
                ("ATZ", 0.5),
                ("ATE0", 0.08),
                ("ATL0", 0.08),
                ("ATS0", 0.08),
                ("ATH0", 0.08),
                ("ATSP6", 0.08),
                ("ATCAF0", 0.08),
                ("ATSH7E0", 0.08),
                ("ATCRA7E8", 0.08),
                ("021001", 0.15),
            ]:
                self.send_cmd(in_s, out_s, cmd, wait=d, timeout=1.0)

            # Phase 1: Auto-discover EVERY active PID from 0x01 to 0xFE on 7E0
            active_pids = []
            for pid_num in range(0x01, 0xFF):
                if not self.running:
                    return
                if pid_num % 15 == 0:
                    self.send_cmd(in_s, out_s, "021001", 0.03)
                    self.update_ui(
                        f"Scanning 100% of ECU PIDs...\n"
                        f"Progress: 0x{pid_num:02X} / 0xFE\n"
                        f"Active PIDs found so far: {len(active_pids)}"
                    )
                pid_hex = f"{pid_num:02X}"
                resp = self.send_cmd(in_s, out_s, f"0221{pid_hex}", 0.025)
                if ("61" + pid_hex) in resp:
                    active_pids.append(pid_hex)

            self.update_ui(
                f"Scan Complete! Found {len(active_pids)} active ECU PIDs:\n"
                f"{', '.join(active_pids[:18])}...\nStarting CSV Ride Log..."
            )
            time.sleep(1.5)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            try:
                Environment = autoclass("android.os.Environment")
                out_dir = Environment.getExternalStoragePublicDirectory(
                    Environment.DIRECTORY_DOWNLOADS
                ).getAbsolutePath()
                os.makedirs(out_dir, exist_ok=True)
            except Exception:
                out_dir = "/sdcard/Download" if os.path.exists("/sdcard/Download") else "."

            csv_path = os.path.join(out_dir, f"hypermotard_fullscan_{ts}.csv")
            headers = ["Time_s"] + [f"ECU_{p}" for p in active_pids]

            start_t = time.monotonic()
            cycle = 0

            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(headers)

                while self.running:
                    self.send_cmd(in_s, out_s, "021001", 0.025)
                    row_map = {}

                    for i, pid_hex in enumerate(active_pids):
                        if i > 0 and i % 15 == 0:
                            self.send_cmd(in_s, out_s, "021001", 0.02)
                        resp = self.send_cmd(in_s, out_s, f"0221{pid_hex}", 0.02)
                        row_map[pid_hex] = self.decode_payload(resp, pid_hex)

                    t_now = round(time.monotonic() - start_t, 3)
                    row = [t_now] + [row_map.get(p, "") for p in active_pids]
                    w.writerow(row)
                    f.flush()

                    rpm_disp = row_map.get("30", "?")
                    tps_raw = row_map.get("3C", "")
                    tps_disp = round(tps_raw / 10.0, 1) if isinstance(tps_raw, int) else "?"

                    self.update_ui(
                        f"FULL-COVERAGE LOGGING (Cycle {cycle} | {t_now:.1f}s)\n\n"
                        f"Tracking {len(active_pids)} active ECU channels\n"
                        f"RPM: {rpm_disp}  |  TPS: {tps_disp}%\n\n"
                        f"File: hypermotard_fullscan_{ts}.csv"
                    )
                    cycle += 1

        except Exception as e:
            self.update_ui(f"Error:\n{e}")
        finally:
            if in_s and out_s:
                try:
                    self.send_cmd(in_s, out_s, "0120", 0.05)
                    self.send_cmd(in_s, out_s, "ATPC", 0.05)
                except Exception:
                    pass
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
            if csv_path:
                try:
                    PythonActivity = autoclass("org.kivy.android.PythonActivity")
                    MediaScanner = autoclass("android.media.MediaScannerConnection")
                    MediaScanner.scanFile(
                        PythonActivity.mActivity, [csv_path], ["text/csv"], None
                    )
                except Exception:
                    pass

    def on_stop(self):
        self.running = False


if __name__ == "__main__":
    DucatiFullScanApp().run()
