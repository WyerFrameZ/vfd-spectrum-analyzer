"""Silnik analizatora: dźwięk z głośników (WASAPI loopback) -> FFT -> Arduino z VFD po USB.

Ramka do Arduino: 0xFF, 9 pasm L, 9 pasm R (0..16), VU L, VU R (0..8), jasność (0..3).
Arduino rysuje lewy kanał lustrzanie (bas przy środku); układ „bas po lewej” robimy
tutaj, odwracając kolejność pasm lewego kanału.
"""
import os, subprocess, threading, time
import numpy as np
import pyaudiowpatch as pyaudio
import serial, serial.tools.list_ports

FPS = 40
N = 2048                 # długość okna FFT (~43 ms przy 48 kHz)
PASMA = 9                # pasm na kanał
F_MIN, F_MAX = 40, 16000
MIN_SZCZYT_DB = -45      # automatyczne wzmocnienie nie podbija ciszy ponad to
ZAKRES_VU_DB = 30
JASNOSCI = [100, 75, 50, 25]   # kod VFD 0..3
DOMYSLNE = "Default speakers"
AUTO = "Auto"
APP = "app:"             # ustawienie "audio" = "app:foobar2000.exe" -> dźwięk tylko z tego programu
APPLOOP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apploop.exe")
APP_RATE = 48000
POMIJANE = {"svchost.exe", "audiodg.exe", "python.exe", "pythonw.exe"}

USTAWIENIA = {
    "jasnosc": 0,        # kod 0..3
    "zakres_db": 40,     # dynamika słupka: mniej = bardziej skaczące
    "spadek": 0.6,       # o ile słupek opada na klatkę (skala 0..16)
    "lustro": True,      # bas obu kanałów przy środku
    "port": AUTO,
    "audio": DOMYSLNE,
}


def lista_portow():
    """[(port, opis)] - opis bez dopisku „(COMx)”, np. ('COM15', 'Arduino Uno')."""
    return sorted(((p.device, p.description.replace(f"({p.device})", "").strip())
                   for p in serial.tools.list_ports.comports()), key=lambda x: int(x[0][3:]) if x[0][3:].isdigit() else 0)


def znajdz_port():
    """Port Arduino, gdy jest dokładnie jedno; None gdy brak albo kilka (wtedy trzeba wybrać ręcznie)."""
    porty = list(serial.tools.list_ports.comports())
    ard = [p.device for p in porty
           if any(s in f"{p.description} {p.manufacturer}".lower() for s in ("arduino", "ch340", "usb-serial", "usb serial"))]
    if len(ard) == 1:
        return ard[0]
    return porty[0].device if len(porty) == 1 else None


def lista_aplikacji():
    """[(pid, nazwa.exe, gra_teraz)] programów, które mają sesję audio (apploop.exe list)."""
    try:
        wyj = subprocess.run([APPLOOP, "list"], capture_output=True, timeout=5,
                             creationflags=subprocess.CREATE_NO_WINDOW).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.TimeoutExpired):
        return []
    apps = []
    for linia in wyj.splitlines():
        pid, nazwa, gra = linia.split("\t")
        if nazwa.lower() not in POMIJANE:
            apps.append((int(pid), nazwa, gra == "1"))
    return apps


class Bufor:
    """Ostatnie N próbek stereo, uzupełniane z callbacku audio."""

    def __init__(self, kanaly):
        self.kanaly = kanaly
        self.dane = np.zeros((N, 2), np.float32)
        self.czas = 0.0
        self.lock = threading.Lock()

    def callback(self, in_data, frame_count, time_info, status):
        x = np.frombuffer(in_data, np.int16).reshape(-1, self.kanaly).astype(np.float32) / 32768
        x = x[:, :2] if self.kanaly >= 2 else np.repeat(x, 2, axis=1)
        n = min(len(x), N)
        with self.lock:
            self.dane = np.roll(self.dane, -n, axis=0)
            self.dane[-n:] = x[-n:]
            self.czas = time.time()
        return (None, pyaudio.paContinue)

    def probki(self):
        with self.lock:
            # przy ciszy WASAPI nic nie przysyła - wtedy traktujemy jak zera
            return self.dane.copy() if time.time() - self.czas < 0.2 else np.zeros((N, 2), np.float32)


class Silnik:
    """Wątek: łapie dźwięk, liczy widmo i wysyła je do Arduino. Sam łączy się ponownie
    po odpięciu kabla. Wyniki do podglądu: `wyslane` (18 pasm), `vu`, `stan_audio`, `stan_port`."""

    def __init__(self, ustawienia=None):
        self.u = dict(USTAWIENIA, **(ustawienia or {}))
        if self.u["audio"] == "Domyślne głośniki":      # ustawienia ze starszej, polskiej wersji
            self.u["audio"] = DOMYSLNE
        self.wyslane = np.zeros(2 * PASMA, int)
        self.vu = np.zeros(2, int)
        self.stan_audio = "starting..."
        self.stan_port = "looking for Arduino..."
        self.audio_ok = self.port_ok = False
        self.urzadzenia = []
        self.aplikacje = []          # nazwy .exe programów z dźwiękiem
        self.proces = None           # apploop.exe przy łapaniu jednej aplikacji
        self._stop = threading.Event()
        self._restart_audio = True
        self._rozlacz = False
        self.pa = self.stream = self.ser = None
        self._kolejna_proba = 0.0
        self._gotowy_od = 0.0
        self._watek = threading.Thread(target=self._petla, daemon=True)

    # --- sterowanie z zewnątrz ---
    def start(self):
        self._watek.start()

    def stop(self):
        self._stop.set()
        self._watek.join(timeout=2)

    def ustaw(self, **zmiany):
        if "audio" in zmiany and zmiany["audio"] != self.u["audio"]:
            self._restart_audio = True
        if "port" in zmiany and zmiany["port"] != self.u["port"]:
            self._rozlacz = True
        self.u.update(zmiany)

    def odswiez_audio(self):
        self._restart_audio = True

    # --- audio ---
    def _zamknij_audio(self):
        for f in (lambda: self.stream.stop_stream(), lambda: self.stream.close(), lambda: self.pa.terminate(),
                  lambda: self.proces.kill()):
            try:
                f()
            except Exception:
                pass
        self.pa = self.stream = self.proces = None

    def _czytaj_aplikacje(self, proces, bufor):
        """Wątek: PCM z apploop.exe -> bufor. Koniec strumienia = program zamknięty, szukamy od nowa."""
        while True:
            dane = proces.stdout.read(512 * 4)
            if not dane:
                break
            bufor.callback(dane[:len(dane) // 4 * 4], 0, None, 0)
        if proces is self.proces:
            self.audio_ok = False
            self.stan_audio = "app closed - waiting..."
            self._kolejna_audio = time.time() + 3

    def _otworz_aplikacje(self, nazwa, apps):
        if not os.path.exists(APPLOOP):
            self.stan_audio = "apploop.exe missing next to silnik.py (see README)"
            return None
        pasujace = sorted((a for a in apps if a[1].lower() == nazwa.lower()), key=lambda a: not a[2])
        if not pasujace:
            self.stan_audio = f"{nazwa} not running - waiting..."
            return None
        self.bufor = Bufor(2)
        self.proces = subprocess.Popen([APPLOOP, "capture", str(pasujace[0][0])], stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        threading.Thread(target=self._czytaj_aplikacje, args=(self.proces, self.bufor), daemon=True).start()
        self.stan_audio = f"only {nazwa}"
        return APP_RATE

    def _otworz_audio(self):
        self._restart_audio = False
        self._zamknij_audio()
        self.audio_ok = False
        apps = lista_aplikacji()
        self.aplikacje = sorted({a[1] for a in apps}, key=str.lower)
        try:
            if self.u["audio"].startswith(APP):
                rate = self._otworz_aplikacje(self.u["audio"][len(APP):], apps)
                if rate is None:
                    return
                self._ustaw_pasma(rate)
                self.audio_ok = True
                self.pa = pyaudio.PyAudio()          # tylko do listy urządzeń w oknie
                self.urzadzenia = [d["name"].replace(" [Loopback]", "")
                                   for d in self.pa.get_loopback_device_info_generator()]
                return
        except Exception as e:
            self.stan_audio = f"error: {e}"
            return
        try:
            self.pa = pyaudio.PyAudio()
            petle = list(self.pa.get_loopback_device_info_generator())
            self.urzadzenia = [d["name"].replace(" [Loopback]", "") for d in petle]
            if self.u["audio"] == DOMYSLNE:
                wasapi = self.pa.get_host_api_info_by_type(pyaudio.paWASAPI)
                nazwa = self.pa.get_device_info_by_index(wasapi["defaultOutputDevice"])["name"]
            else:
                nazwa = self.u["audio"]
            dev = next(d for d in petle if nazwa in d["name"])
            rate, kanaly = int(dev["defaultSampleRate"]), dev["maxInputChannels"]
            self.bufor = Bufor(kanaly)
            self.stream = self.pa.open(format=pyaudio.paInt16, channels=kanaly, rate=rate, input=True,
                                       input_device_index=dev["index"], frames_per_buffer=512,
                                       stream_callback=self.bufor.callback)
        except StopIteration:
            self.stan_audio = f"device not found: {self.u['audio']}"
            return
        except Exception as e:
            self.stan_audio = f"error: {e}"
            return
        self._ustaw_pasma(rate)
        self.stan_audio = dev["name"].replace(" [Loopback]", "")
        self.audio_ok = True

    def _ustaw_pasma(self, rate):
        self.okno = np.hanning(N).astype(np.float32)
        self.skala = 2 / self.okno.sum()                 # pełnoskalowy sinus = 0 dB
        freqs = np.fft.rfftfreq(N, 1 / rate)
        granice = np.geomspace(F_MIN, F_MAX, PASMA + 1)
        self.maski = []
        for lo, hi in zip(granice[:-1], granice[1:]):
            m = (freqs >= lo) & (freqs < hi)
            if not m.any():                              # pasmo węższe niż prążek FFT
                m = np.zeros_like(m)
                m[np.argmin(abs(freqs - (lo * hi) ** 0.5))] = True
            self.maski.append(m)

    # --- Arduino ---
    def _zamknij_port(self):
        if self.ser:
            try:
                self.ser.write(bytes([0xFF] + [0] * (2 * PASMA + 2) + [self.u["jasnosc"]]))
                self.ser.close()
            except Exception:
                pass
        self.ser = None
        self.port_ok = False

    def _polacz(self):
        port = znajdz_port() if self.u["port"] == AUTO else self.u["port"]
        if not port:
            ile = sum(1 for _, o in lista_portow() if any(s in o.lower() for s in ("arduino", "ch340", "serial")))
            self.stan_port = "several Arduinos - pick a port" if ile > 1 else "no Arduino found"
        else:
            try:
                self.ser = serial.Serial(port, 115200, timeout=0, write_timeout=0.5)
                self._gotowy_od = time.time() + 2            # Arduino restartuje się po otwarciu portu
                self.stan_port = f"{port} - connecting..."
                return
            except serial.SerialException as e:
                self.stan_port = f"{port} busy" if "Access" in str(e) or "denied" in str(e) else f"{port}: error"
        self._kolejna_proba = time.time() + 2

    def _wyslij(self, ramka):
        if not self.ser or time.time() < self._gotowy_od:
            return
        try:
            self.ser.write(ramka)
            self.ser.read(self.ser.in_waiting or 0)
            if not self.port_ok:
                self.port_ok = True
                self.stan_port = f"{self.ser.port} - connected"
        except (serial.SerialException, OSError):
            self.ser = None
            self.port_ok = False
            self.stan_port = "disconnected - searching..."
            self._kolejna_proba = time.time() + 2

    # --- główna pętla ---
    def _petla(self):
        szczyt_db = szczyt_vu = MIN_SZCZYT_DB
        slupki = np.zeros(2 * PASMA)
        vu = np.zeros(2)
        nastepna = time.perf_counter()
        while not self._stop.is_set():
            if self._restart_audio:
                self._otworz_audio()
                if not self.audio_ok:
                    self._kolejna_audio = time.time() + 3
            elif not self.audio_ok and time.time() > getattr(self, "_kolejna_audio", 0):
                self._restart_audio = True
            if self._rozlacz:
                self._rozlacz = False
                self._zamknij_port()
                self._kolejna_proba = 0
            if self.ser is None and time.time() >= self._kolejna_proba:
                self._polacz()

            if self.audio_ok:
                x = self.bufor.probki()
                db = []
                for k in range(2):
                    widmo = (np.abs(np.fft.rfft(x[:, k] * self.okno)) * self.skala) ** 2
                    db += [10 * np.log10(widmo[m].sum() + 1e-12) for m in self.maski]
                db = np.array(db)
                rms_db = 10 * np.log10((x ** 2).mean(axis=0) + 1e-12)
            else:
                db = np.full(2 * PASMA, -120.0)
                rms_db = np.full(2, -120.0)

            zakres = self.u["zakres_db"]
            spadek = self.u["spadek"]
            # automatyczne wzmocnienie: szczyt rośnie od razu, opada 2 dB/s
            szczyt_db = max(db.max(), szczyt_db - 2 / FPS, MIN_SZCZYT_DB)
            szczyt_vu = max(rms_db.max(), szczyt_vu - 2 / FPS, MIN_SZCZYT_DB)
            cel = np.clip((db - (szczyt_db - zakres)) / zakres * 16, 0, 16)
            slupki = np.maximum(cel, slupki - spadek)
            cel_vu = np.clip((rms_db - (szczyt_vu - ZAKRES_VU_DB)) / ZAKRES_VU_DB * 8, 0, 8)
            vu = np.maximum(cel_vu, vu - spadek / 2)

            wart = np.round(slupki).astype(int)
            if not self.u["lustro"]:
                wart[:PASMA] = wart[PASMA - 1::-1]
            self.wyslane = wart
            self.vu = np.round(vu).astype(int)
            self._wyslij(bytes([0xFF, *wart, *self.vu, self.u["jasnosc"]]))

            nastepna += 1 / FPS
            teraz = time.perf_counter()
            if nastepna < teraz - 0.5:                   # np. po uśpieniu komputera
                nastepna = teraz
            time.sleep(max(0, nastepna - teraz))
        self._zamknij_port()
        self._zamknij_audio()


def kolumny(wyslane, vu):
    """Zawartość ekranu 20x2 tak, jak rysuje ją Arduino.
    Zwraca (góra, dół): listy 20 elementów - liczba 1..8 = słupek, str = znak, None = pusto."""
    gora, dol = [None] * 20, [None] * 20
    for k in range(2):
        for i in range(PASMA):
            h = int(wyslane[k * PASMA + i])
            x = PASMA - 1 - i if k == 0 else PASMA + 2 + i
            if h:
                dol[x] = min(h, 8)
            if h > 8:
                gora[x] = h - 8
        dol[PASMA + k] = ("R" if k else "L") if vu[k] else "."
    return gora, dol
