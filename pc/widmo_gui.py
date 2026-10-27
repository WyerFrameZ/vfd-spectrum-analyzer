"""Analizator VFD - okno programu.

Instalacja:  pip install pyaudiowpatch pyserial numpy customtkinter pystray pillow
Uruchomienie: pythonw widmo_gui.py        (--min = start schowany w zasobniku)
Zamknięcie okna chowa program do zasobnika (ikona przy zegarze) - tam jest „Zakończ”.
"""
import json, os, socket, sys
import customtkinter as ctk
import pystray
from PIL import Image, ImageDraw
from silnik import APP, AUTO, DOMYSLNE, JASNOSCI, USTAWIENIA, Silnik, kolumny, lista_portow

PREFIKS_APP = "Program: "     # na liście "Dźwięk z"; w ustawieniach zapisane jako "app:nazwa.exe"


def audio_na_liste(u):
    return PREFIKS_APP + u[len(APP):] if u.startswith(APP) else u


def audio_z_listy(v):
    return APP + v[len(PREFIKS_APP):] if v.startswith(PREFIKS_APP) else v

KATALOG = os.path.dirname(os.path.abspath(__file__))
PLIK_USTAWIEN = os.path.join(KATALOG, "ustawienia.json")
AUTOSTART = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup",
                         "Analizator VFD.vbs")

# wygląd VFD
TLO = "#050b0a"
ZGASZONY = "#0c201c"
SWIECI = ["#7dffe4", "#5ad9c0", "#40a896", "#2c7a6c"]   # jasność 100/75/50/25 %
KROK = 6          # rozstaw kropek w px
KROPKA = 4.6
ZNAK_W = 5 * KROK + 7
ZNAK_H = 8 * KROK + 14
MARGINES = 22

# znaki 5x8 (wiersze od góry, 5 bitów)
FONT = {
    "L": [0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F, 0x00],
    "R": [0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11, 0x00],
    ".": [0x00, 0x00, 0x00, 0x00, 0x00, 0x0C, 0x0C, 0x00],
}


def bitmapa(znak):
    if znak is None:
        return [0] * 8
    if isinstance(znak, int):                       # słupek wypełniony od dołu na `znak` wierszy
        return [0x1F if r >= 8 - znak else 0 for r in range(8)]
    return FONT[znak]


def wczytaj_ustawienia():
    try:
        with open(PLIK_USTAWIEN, encoding="utf-8") as f:
            return {k: v for k, v in json.load(f).items() if k in USTAWIENIA}
    except (OSError, ValueError):
        return {}


def ikona_zasobnika():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2, 8, 62, 56), 8, fill="#0b1a17")
    for i, h in enumerate([18, 30, 40, 26, 34, 14]):
        x = 8 + i * 8
        d.rectangle((x, 50 - h, x + 5, 50), fill="#5affd8")
    return img


class PodgladVFD(ctk.CTkCanvas):
    """Imitacja wyświetlacza 20x2 z kropek 5x8."""

    def __init__(self, master):
        w = 20 * ZNAK_W + 2 * MARGINES - 7
        h = 2 * ZNAK_H + 2 * MARGINES - 14
        super().__init__(master, width=w, height=h, bg=TLO, highlightthickness=0)
        self.kropki = {}                            # (wiersz, kolumna) -> 8x5 id
        for r in range(2):
            for c in range(20):
                x0, y0 = MARGINES + c * ZNAK_W, MARGINES + r * ZNAK_H
                self.kropki[r, c] = [[self.create_oval(x0 + x * KROK, y0 + y * KROK,
                                                       x0 + x * KROK + KROPKA, y0 + y * KROK + KROPKA,
                                                       fill=ZGASZONY, width=0)
                                      for x in range(5)] for y in range(8)]
        self.stan = {}
        self.kolor = None

    def pokaz(self, gora, dol, jasnosc):
        kolor = SWIECI[jasnosc]
        wszystko = kolor != self.kolor
        self.kolor = kolor
        for r, wiersz in enumerate((gora, dol)):
            for c, znak in enumerate(wiersz):
                bm = bitmapa(znak)
                if not wszystko and self.stan.get((r, c)) == bm:
                    continue
                self.stan[r, c] = bm
                for y in range(8):
                    for x in range(5):
                        self.itemconfigure(self.kropki[r, c][y][x],
                                           fill=kolor if bm[y] >> (4 - x) & 1 else ZGASZONY)


class Okno(ctk.CTk):
    def __init__(self, silnik, schowane):
        super().__init__()
        self.s = silnik
        self.title("Analizator VFD")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.schowaj)

        naglowek = ctk.CTkFrame(self, fg_color="transparent")
        naglowek.pack(fill="x", padx=20, pady=(16, 6))
        ctk.CTkLabel(naglowek, text="Analizator VFD", font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")
        self.lbl_port = ctk.CTkLabel(naglowek, text="", font=ctk.CTkFont(size=13))
        self.lbl_port.pack(side="right")
        self.kropka_port = ctk.CTkLabel(naglowek, text="●", font=ctk.CTkFont(size=16))
        self.kropka_port.pack(side="right", padx=6)

        ramka = ctk.CTkFrame(self, fg_color=TLO, corner_radius=14, border_width=2, border_color="#1b2d2a")
        ramka.pack(padx=20, pady=6)
        self.vfd = PodgladVFD(ramka)
        self.vfd.pack(padx=6, pady=6)

        self.lbl_audio = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12), text_color="gray70")
        self.lbl_audio.pack(anchor="w", padx=24)

        panel = ctk.CTkFrame(self, corner_radius=12)
        panel.pack(fill="x", padx=20, pady=(8, 10))
        panel.grid_columnconfigure(1, weight=1)
        r = 0

        def etykieta(tekst):
            ctk.CTkLabel(panel, text=tekst, anchor="w").grid(row=r, column=0, sticky="w", padx=(16, 12), pady=8)

        etykieta("Jasność")
        self.jas = ctk.CTkSegmentedButton(panel, values=[f"{p} %" for p in JASNOSCI], command=self.zmien_jasnosc)
        self.jas.set(f"{JASNOSCI[self.s.u['jasnosc']]} %")
        self.jas.grid(row=r, column=1, columnspan=2, sticky="ew", padx=(0, 16))
        r += 1

        etykieta("Czułość")
        self.czul = ctk.CTkSlider(panel, from_=60, to=20, number_of_steps=40, command=self.zmien_czulosc)
        self.czul.set(self.s.u["zakres_db"])
        self.czul.grid(row=r, column=1, sticky="ew")
        self.lbl_czul = ctk.CTkLabel(panel, width=70)
        self.lbl_czul.grid(row=r, column=2, padx=(8, 16))
        r += 1

        etykieta("Opadanie")
        self.spad = ctk.CTkSlider(panel, from_=0.15, to=1.5, number_of_steps=27, command=self.zmien_spadek)
        self.spad.set(self.s.u["spadek"])
        self.spad.grid(row=r, column=1, sticky="ew")
        self.lbl_spad = ctk.CTkLabel(panel, width=70)
        self.lbl_spad.grid(row=r, column=2, padx=(8, 16))
        r += 1

        etykieta("Układ")
        self.lustro = ctk.CTkSwitch(panel, text="Basy w środku (lustro)", command=self.zmien_lustro)
        if self.s.u["lustro"]:
            self.lustro.select()
        self.lustro.grid(row=r, column=1, columnspan=2, sticky="w")
        r += 1

        etykieta("Dźwięk z")
        wiersz = ctk.CTkFrame(panel, fg_color="transparent")
        wiersz.grid(row=r, column=1, columnspan=2, sticky="ew", padx=(0, 16))
        self.audio = ctk.CTkOptionMenu(wiersz, values=[DOMYSLNE], width=330, dynamic_resizing=False,
                                       command=lambda v: self.zmien(audio=audio_z_listy(v)))
        self.audio.set(audio_na_liste(self.s.u["audio"]))
        self.audio.pack(side="left")
        ctk.CTkButton(wiersz, text="Odśwież", width=80, command=self.s.odswiez_audio).pack(side="left", padx=8)
        r += 1

        etykieta("Arduino")
        wiersz = ctk.CTkFrame(panel, fg_color="transparent")
        wiersz.grid(row=r, column=1, columnspan=2, sticky="ew", padx=(0, 16))
        self.port = ctk.CTkOptionMenu(wiersz, values=[AUTO], width=330, dynamic_resizing=False,
                                      command=lambda v: self.zmien(port=v.split(" – ")[0]))
        self.port.pack(side="left")
        ctk.CTkButton(wiersz, text="Odśwież", width=80, command=self.odswiez_porty).pack(side="left", padx=8)
        r += 1

        self.autostart = ctk.CTkCheckBox(panel, text="Uruchamiaj razem z Windows (schowany przy zegarze)",
                                         command=self.zmien_autostart)
        if os.path.exists(AUTOSTART):
            self.autostart.select()
        self.autostart.grid(row=r, column=0, columnspan=3, sticky="w", padx=16, pady=(8, 14))

        ctk.CTkLabel(self, text="Zamknięcie okna chowa program do zasobnika (ikona przy zegarze).",
                     font=ctk.CTkFont(size=11), text_color="gray55").pack(pady=(0, 12))

        self.odswiez_porty()
        self.zmien_czulosc(self.czul.get(), zapisz=False)
        self.zmien_spadek(self.spad.get(), zapisz=False)
        self._urzadzenia = None
        self.zasobnik()
        if schowane:
            self.withdraw()
        self.after(40, self.odswiez)

    # --- ustawienia ---
    def zmien(self, **zmiany):
        self.s.ustaw(**zmiany)
        try:
            with open(PLIK_USTAWIEN, "w", encoding="utf-8") as f:
                json.dump(self.s.u, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def zmien_jasnosc(self, wartosc):
        self.zmien(jasnosc=JASNOSCI.index(int(wartosc.split()[0])))

    def zmien_czulosc(self, v, zapisz=True):
        v = int(round(v))
        self.lbl_czul.configure(text=f"{v} dB")
        if zapisz:
            self.zmien(zakres_db=v)

    def zmien_spadek(self, v, zapisz=True):
        self.lbl_spad.configure(text="wolno" if v < 0.4 else "szybko" if v > 1.0 else "średnio")
        if zapisz:
            self.zmien(spadek=round(v, 2))

    def zmien_lustro(self):
        self.zmien(lustro=bool(self.lustro.get()))

    def odswiez_porty(self):
        porty = [f"{dev} – {opis}" for dev, opis in lista_portow()]
        self.port.configure(values=[AUTO] + porty)
        wybrany = self.s.u["port"]
        self.port.set(next((p for p in porty if p.split(" – ")[0] == wybrany), wybrany))

    def zmien_autostart(self):
        if self.autostart.get():
            pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            skrypt = os.path.abspath(__file__)
            with open(AUTOSTART, "w", encoding="utf-16") as f:
                f.write(f'CreateObject("WScript.Shell").Run """{pythonw}"" ""{skrypt}"" --min", 0\n')
        elif os.path.exists(AUTOSTART):
            os.remove(AUTOSTART)

    # --- podgląd ---
    def odswiez(self):
        gora, dol = kolumny(self.s.wyslane, self.s.vu)
        if self.winfo_viewable():
            self.vfd.pokaz(gora, dol, self.s.u["jasnosc"])
        self.kropka_port.configure(text_color="#3ddc84" if self.s.port_ok else "#e05050")
        self.lbl_port.configure(text=f"Arduino: {self.s.stan_port}")
        self.lbl_audio.configure(text=("Dźwięk z: " if self.s.audio_ok else "Dźwięk: ") + self.s.stan_audio,
                                 text_color="gray70" if self.s.audio_ok else "#e05050")
        self._tik = getattr(self, "_tik", 0) + 1
        if self._tik % 50 == 0:                     # co ~2 s: podpięto/odpięto płytkę?
            porty = lista_portow()
            if porty != getattr(self, "_porty", None):
                self._porty = porty
                self.odswiez_porty()
        lista = [DOMYSLNE] + self.s.urzadzenia + [PREFIKS_APP + a for a in self.s.aplikacje]
        wybrane = audio_na_liste(self.s.u["audio"])
        if wybrane not in lista:                    # zapamiętany program teraz nie działa
            lista.append(wybrane)
        if lista != self._urzadzenia:
            self._urzadzenia = lista
            self.audio.configure(values=lista)
        self.after(40, self.odswiez)

    # --- zasobnik ---
    def zasobnik(self):
        def jasnosc(kod):
            return pystray.MenuItem(f"{JASNOSCI[kod]} %", lambda: self.after(0, self.ustaw_jasnosc, kod),
                                    checked=lambda _: self.s.u["jasnosc"] == kod, radio=True)

        menu = pystray.Menu(
            pystray.MenuItem("Pokaż", lambda: self.after(0, self.pokaz), default=True),
            pystray.MenuItem("Jasność", pystray.Menu(*[jasnosc(k) for k in range(4)])),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Zakończ", lambda: self.after(0, self.zakoncz)),
        )
        self.ikona = pystray.Icon("analizator_vfd", ikona_zasobnika(), "Analizator VFD", menu)
        self.ikona.run_detached()

    def ustaw_jasnosc(self, kod):
        self.jas.set(f"{JASNOSCI[kod]} %")
        self.zmien(jasnosc=kod)

    def pokaz(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def schowaj(self):
        self.withdraw()

    def zakoncz(self):
        self.ikona.stop()
        self.s.stop()
        self.destroy()


def main():
    # tylko jedna kopia programu naraz (obie walczyłyby o port COM)
    blokada = socket.socket()
    try:
        blokada.bind(("127.0.0.1", 47321))
    except OSError:
        sys.exit("Analizator VFD już działa (ikona przy zegarze).")

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")
    silnik = Silnik(wczytaj_ustawienia())
    silnik.start()
    Okno(silnik, "--min" in sys.argv).mainloop()


if __name__ == "__main__":
    main()
