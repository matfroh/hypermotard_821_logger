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


class DucatiLoggerApp(App):
    def build(self):
        self.status_label = Label(
            text="Starting Ducati 821 Logger...\nMake sure key & kill-switch are ON.",
            font_size="18sp",
            halign="center",
        )
        self.running = True
        threading.Thread(target=self.log_loop, daemon=True).start()
        return self.status_label

    def update_ui(self, msg):
        Clock.schedule_once(lambda dt: setattr(self.status_label, "text", msg))

    def send_cmd(self, in_s, out_s, cmd, wait=0.04, timeout=0.4):
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
                time.sleep(0.005)
        text = buf.decode("ascii", errors="ignore")
        lines = [
            l.strip().replace(" ", "")
            for l in text.splitlines()
            if l.strip() and l.strip() != ">" and cmd not in l
        ]
        return lines[-1] if lines else ""

    def parse_u16(self, resp, prefix):
        idx = resp.find(prefix)
        if idx != -1 and len(resp) >= idx + len(prefix) + 4:
            try:
                return int(resp[idx + len(prefix) : idx + len(prefix) + 4], 16)
            except ValueError:
                return None
        return None

    def log_loop(self):
        sock = None
        try:
            BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
            UUID = autoclass("java.util.UUID")
            adapter = BluetoothAdapter.getDefaultAdapter()
            device = adapter.getRemoteDevice(MAC_ADDRESS)
#            if adapter.isDiscovering():
#                adapter.cancelDiscovery()

#            sock = device.createRfcommSocketToServiceRecord(UUID.fromString(SPP_UUID))
#            sock.connect()
            try:
                sock = device.createInsecureRfcommSocketToServiceRecord(UUID.fromString(SPP_UUID))
                sock.connect()
            except Exception:
                # Samsung S7 / Android 8.0 direct RFCOMM Channel 1 reflection fallback
                Integer = autoclass("java.lang.Integer")
                method = device.getClass().getMethod("createRfcommSocket", [Integer.TYPE])
                sock = method.invoke(device, [1])
                sock.connect()
            in_s = sock.getInputStream()
            out_s = sock.getOutputStream()

            self.update_ui("Connected! Initializing Marelli 7SM...")
            for cmd, d in [
                ("ATZ", 0.5), ("ATE0", 0.1), ("ATL0", 0.1), ("ATS0", 0.1),
                ("ATH0", 0.1), ("ATSP6", 0.1), ("ATCAF0", 0.1),
                ("ATSH7E0", 0.1), ("ATCRA7E8", 0.1), ("021001", 0.2),
            ]:
                self.send_cmd(in_s, out_s, cmd, wait=d, timeout=1.0)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir = "/sdcard/Download" if os.path.exists("/sdcard/Download") else "."
            csv_path = os.path.join(out_dir, f"hypermotard_log_{ts}.csv")

            start_t = time.monotonic()
            cycle = 0
            ect = ""

            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Time_s", "RPM", "TPS_pct", "Twistgrip_pct", "Speed_kmh", "MAP1_kPa", "Inj1_ms", "ECT_C"])

                while self.running:
                    if cycle > 0 and cycle % 25 == 0:
                        self.send_cmd(in_s, out_s, "021001", 0.04)

                    rpm = self.parse_u16(self.send_cmd(in_s, out_s, "022130", 0.03), "6130")
                    tps_r = self.parse_u16(self.send_cmd(in_s, out_s, "02213C", 0.03), "613C")
                    aps_r = self.parse_u16(self.send_cmd(in_s, out_s, "02213B", 0.03), "613B")
                    spd = self.parse_u16(self.send_cmd(in_s, out_s, "022135", 0.03), "6135")
                    map_r = self.parse_u16(self.send_cmd(in_s, out_s, "02213D", 0.03), "613D")
                    inj_r = self.parse_u16(self.send_cmd(in_s, out_s, "022144", 0.03), "6144")

                    if cycle % 20 == 0:
                        ect_r = self.parse_u16(self.send_cmd(in_s, out_s, "022131", 0.03), "6131")
                        if ect_r is not None:
                            ect = ect_r - 40

                    t_now = round(time.monotonic() - start_t, 3)
                    tps = round(tps_r / 10.0, 1) if tps_r is not None else ""
                    aps = round(aps_r / 10.0, 1) if aps_r is not None else ""
                    map1 = round(map_r / 10.0, 1) if map_r is not None else ""
                    inj1 = round(inj_r / 100.0, 2) if inj_r is not None else ""

                    w.writerow([t_now, rpm or "", tps, aps, spd if spd is not None else "", map1, inj1, ect])
                    f.flush()

                    if cycle % 3 == 0:
                        self.update_ui(
                            f"RECORDING ({t_now:.1f}s)\n\n"
                            f"RPM: {rpm}   |   Speed: {spd} km/h\n"
                            f"TPS: {tps}%   |   Grip: {aps}%\n"
                            f"MAP: {map1} kPa   |   Inj: {inj1} ms\n"
                            f"ECT: {ect} °C\n\n"
                            f"Saved to Download/hypermotard_log_{ts}.csv"
                        )
                    cycle += 1

        except Exception as e:
            self.update_ui(f"Error:\n{e}")
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    def on_stop(self):
        self.running = False


if __name__ == "__main__":
    DucatiLoggerApp().run()
