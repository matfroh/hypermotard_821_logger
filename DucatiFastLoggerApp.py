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


class DucatiFastLoggerApp(App):
    def build(self):
        self.status_label = Label(
            text="Starting High-Speed 10 Hz Logger...\nEnsure key & kill-switch are ON.",
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

    def send_cmd(self, in_s, out_s, cmd, timeout=0.25):
        out_s.write((cmd + "\r").encode("ascii"))
        out_s.flush()
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
                time.sleep(0.002)
        text = buf.decode("ascii", errors="ignore")
        lines = [
            l.strip().replace(" ", "")
            for l in text.splitlines()
            if l.strip() and l.strip() != ">" and cmd not in l
        ]
        return lines[-1] if lines else ""

    def parse_u16(self, resp, pid_hex):
        prefix = "61" + pid_hex
        idx = resp.find(prefix)
        if idx != -1 and len(resp) >= idx + len(prefix) + 4:
            try:
                return int(resp[idx + len(prefix) : idx + len(prefix) + 4], 16)
            except ValueError:
                return None
        return None

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

            self.update_ui("Connected! Configuring 10 Hz Fast-Reply Mode...")
            init_cmds = [
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
            ]
            for cmd, d in init_cmds:
                self.send_cmd(in_s, out_s, cmd, timeout=0.8)
                time.sleep(d)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            try:
                Environment = autoclass("android.os.Environment")
                out_dir = Environment.getExternalStoragePublicDirectory(
                    Environment.DIRECTORY_DOWNLOADS
                ).getAbsolutePath()
                os.makedirs(out_dir, exist_ok=True)
            except Exception:
                out_dir = "/sdcard/Download" if os.path.exists("/sdcard/Download") else "."

            csv_path = os.path.join(out_dir, f"hypermotard_fastlog_{ts}.csv")

            headers = [
                "Time_s",
                "RPM",
                "Speed_kmh",
                "TPS_pct",
                "Twistgrip_pct",
                "MAP1_kPa",
                "Inj1_ms",
                "STFT1_pct",
                "OilTemp_C",
            ]

            start_t = time.monotonic()
            cycle = 0
            oil_temp = ""

            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(headers)

                while self.running:
                    # Keep KWP2000 session alive every 30 cycles (~3 seconds)
                    if cycle > 0 and cycle % 30 == 0:
                        self.send_cmd(in_s, out_s, "021001")

                    # Poll 7 core channels with trailing '1' for immediate ELM327 reply
                    r_rpm = self.parse_u16(self.send_cmd(in_s, out_s, "0221301"), "6130")
                    r_spd = self.parse_u16(self.send_cmd(in_s, out_s, "02217A1"), "617A")
                    r_tps = self.parse_u16(self.send_cmd(in_s, out_s, "02213C1"), "613C")
                    r_aps = self.parse_u16(self.send_cmd(in_s, out_s, "02213B1"), "613B")
                    r_map = self.parse_u16(self.send_cmd(in_s, out_s, "02213D1"), "613D")
                    r_inj = self.parse_u16(self.send_cmd(in_s, out_s, "0221441"), "6144")
                    r_trm = self.parse_u16(self.send_cmd(in_s, out_s, "0221591"), "6159")

                    # Poll Engine Oil/Head Temp once every 50 cycles
                    if cycle % 50 == 0:
                        r_oil = self.parse_u16(self.send_cmd(in_s, out_s, "0221341"), "6134")
                        if r_oil is not None:
                            oil_temp = r_oil - 40

                    t_now = round(time.monotonic() - start_t, 3)
                    tps = round(r_tps / 10.0, 1) if r_tps is not None else ""
                    aps = round(r_aps / 10.0, 1) if r_aps is not None else ""
                    map1 = round(r_map / 10.0, 1) if r_map is not None else ""
                    inj1 = round(r_inj / 100.0, 2) if r_inj is not None else ""
                    stft1 = round((r_trm - 40000) / 400.0, 2) if r_trm is not None else ""

                    w.writerow([
                        t_now,
                        r_rpm if r_rpm is not None else "",
                        r_spd if r_spd is not None else "",
                        tps,
                        aps,
                        map1,
                        inj1,
                        stft1,
                        oil_temp,
                    ])
                    f.flush()

                    if cycle % 5 == 0:
                        hz = round(cycle / t_now, 1) if t_now > 0.5 else 0.0
                        self.update_ui(
                            f"FAST LOGGING ({hz} Hz | {t_now:.1f}s)\n\n"
                            f"RPM: {r_rpm}   |   Speed: {r_spd} km/h\n"
                            f"TPS: {tps}%   |   Grip: {aps}%\n"
                            f"MAP: {map1} kPa   |   Inj: {inj1} ms\n"
                            f"Closed-Loop Trim: {stft1}%   |   Oil: {oil_temp}°C\n\n"
                            f"File: hypermotard_fastlog_{ts}.csv"
                        )
                    cycle += 1

        except Exception as e:
            self.update_ui(f"Error:\n{e}")
        finally:
            if in_s and out_s:
                try:
                    self.send_cmd(in_s, out_s, "0120")
                    self.send_cmd(in_s, out_s, "ATPC")
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
    DucatiFastLoggerApp().run()
