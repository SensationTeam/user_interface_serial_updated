import time
import json
import threading
import serial
import serial.tools.list_ports


class SerialCtrl:
    """
    STM32 için sağlam seri haberleşme denetleyicisi.
    - Portu **yalnızca bir kez** açar ve açık tutar (START'ta).
    - Her gönderimi **tek satırlık** kompakt JSON olarak yollar.
    - F103 CDC'nin düşmesine neden olan sürekli aç/kapa döngülerini engeller.
    - Port açılınca bir **okuyucu thread** başlatır (FW'den gelen status/heartbeat mesajlarını görmek için).
    """

    def __init__(self):
        self.ser = None
        self.port = None
        self.baud = None
        self._stop_reader = True
        self._reader_thread = None
        # Gönderimde kullanılacak satır sonu. F103 için genelde b"\n" daha uyumlu.
        # F407 FW'in özellikle CRLF istiyorsa b"\r\n" yap.
        self.terminator = b"\n"
        # Opsiyonel: gelen satırları GUI'ye aktarmak istersen callback set edebilirsin.
        self.on_line_callback = None

    # ----------------------------
    # Yardımcılar
    # ----------------------------
    def getCOMList(self):
        ports = serial.tools.list_ports.comports()
        self.com_list = [com[0] for com in ports]
        self.com_list.insert(0, "-")  # GUI placeholder

    def _coerce_baud(self, val, default=115200):
        try:
            return int(str(val).strip())
        except Exception:
            print(f"Geçersiz baud '{val}', {default} kullanılacak.")
            return int(default)

    # ----------------------------
    # Aç/Kapat
    # ----------------------------
    def SerialOpen(self, ComGUI):
        """
        Portu bir kez aç ve açık tut.
        Aynı port+baud ile tekrar çağrılırsa **NO-OP** (yeniden açmaz).
        Farklı ayarlar geldiyse kapatıp yeni ayarla açar.
        """
        # GUI'den oku
        port = ComGUI.clicked_com.get()
        baud = self._coerce_baud(ComGUI.clicked_bd.get(), default=115200)

        if port == "-" or not baud:
            print("Error: Select a valid COM port and baud rate.")
            return

        # Zaten açık ve aynı ayarlar ise çık
        if self.ser and self.ser.is_open and self.port == port and self.baud == baud:
            return

        # Port açık ve ayar farklı ise kapat
        if self.ser and self.ser.is_open:
            self.close()  # reader'ı da durdurur

        try:
            # Aç
            self.ser = serial.Serial(
                port=port,
                baudrate=baud,
                timeout=0.1,        # read timeout
                write_timeout=0.2   # write timeout
            )
            # Bazı CDC cihazları için kısa settle iyi olur
            time.sleep(0.15)

            # Eski baytları temizle
            try:
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
            except Exception:
                pass

            # Ayarları hatırla
            self.port = port
            self.baud = baud

            # DTR'yi assert et (bazı FW'ler DTR=1'i "host hazır" sayar)
            try:
                self.ser.dtr = True
            except Exception:
                pass

            print(f"✅ Serial open: {self.port} @ {self.baud}")
            # Uyum için ser objesine status attribute ekleyelim (bazı eski kodlar bakıyor olabilir)
            try:
                self.ser.status = True
            except Exception:
                pass

            # Otomatik okuyucuyu başlat
            self.start_reader()

        except Exception as e:
            print(f"❌ Error opening serial port: {e}")
            try:
                self.ser.status = False
            except Exception:
                pass
            self.ser = None

    def close(self):
        """Reader'ı durdur ve portu kapat."""
        self.stop_reader()
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
                print("🔌 Serial closed.")
            except Exception as e:
                print(f"Close error: {e}")
        self.ser = None

    # ----------------------------
    # Okuyucu Thread
    # ----------------------------
    def start_reader(self, on_line=None):
        """FW'den gelen satırları arka planda oku. on_line varsa callback çağırır."""
        if not (self.ser and self.ser.is_open):
            print("Reader: port closed")
            return

        # Harici callback set edildiyse güncelle
        if on_line is not None:
            self.on_line_callback = on_line

        # Eski thread'i durdur
        self.stop_reader()

        self._stop_reader = False

        def loop():
            while self.ser and self.ser.is_open and not self._stop_reader:
                try:
                    line = self.ser.readline()  # FW \r\n gönderse de \n'de biter
                    if not line:
                        continue
                    text = line.decode("utf-8", "ignore").strip()
                    print(f"⬅️ RX: {text}")
                    cb = self.on_line_callback
                    if cb:
                        try:
                            cb(text)
                        except Exception as cb_e:
                            print(f"on_line callback error: {cb_e}")
                except Exception as e:
                    print(f"Reader error: {e}")
                    break

        t = threading.Thread(target=loop, daemon=True)
        t.start()
        self._reader_thread = t

    def stop_reader(self):
        self._stop_reader = True
        # Thread'e nazikçe kapanma şansı ver
        t = self._reader_thread
        if t and t.is_alive():
            # join kullanmıyoruz; GUI'yi bloklamasın
            pass
        self._reader_thread = None

    # ----------------------------
    # Gönderim
    # ----------------------------
    def send_json(self, payload: dict):
        """Kompakt JSON üret ve tek satır olarak gönder."""
        try:
            data = json.dumps(payload, separators=(",", ":"))
        except Exception as e:
            print(f"JSON encode error: {e}; payload={payload}")
            return
        self.send_data(data)

    def send_data(self, data: str):
        """Ham metni terminatör ekleyerek gönder."""
        if not (self.ser and self.ser.is_open):
            print("Error: Serial port is not open.")
            return
        try:
            self.ser.write(data.encode("utf-8"))
            self.ser.write(self.terminator)  # b"\n" veya b"\r\n"
            try:
                self.ser.flush()
            except Exception:
                pass
            print(f"➡️  Sent: {data}")
        except Exception as e:
            print(f"❌ Send error: {e}")


if __name__ == "__main__":
    # Basit manuel test (doğrudan çalıştırırsan):
    # - COM ve baud'u elle ayarlayıp deneyebilirsin.
    # - Normalde GUI ComGUI üzerinden çağırır.
    class _Dummy:
        def __init__(self, port="COM3", baud="115200"):
            class _Val:
                def __init__(self, v): self._v = v
                def get(self): return self._v
            self.clicked_com = _Val(port)
            self.clicked_bd  = _Val(baud)

    sc = SerialCtrl()
    dummy = _Dummy()
    sc.SerialOpen(dummy)
    for i in range(3):
        sc.send_json({"cmd":"set","deney_no":1,"motor1_duty":i,"motor2_duty":i*2,"period":50})
        time.sleep(0.2)
    time.sleep(1.0)
    sc.close()
