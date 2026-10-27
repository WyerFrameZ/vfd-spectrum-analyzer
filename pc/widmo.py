"""Widmo dźwięku z głośników komputera -> VFD Noritake na Arduino (USB), wersja konsolowa.
Wersja z oknem: widmo_gui.py

Instalacja:  pip install pyaudiowpatch pyserial numpy
Uruchomienie: python widmo.py [--port COM15] [--jasnosc 50]
W trakcie działania: klawisze 1-4 = jasność 100/75/50/25 %, +/- = jaśniej/ciemniej, q = koniec.
"""
import argparse, msvcrt, sys, time
from silnik import AUTO, JASNOSCI, PASMA, Silnik


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=AUTO)
    ap.add_argument("--jasnosc", type=int, choices=JASNOSCI, default=100, help="jasność VFD w %%")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    s = Silnik({"port": args.port, "jasnosc": JASNOSCI.index(args.jasnosc)})
    s.start()
    print("Klawisze: 1-4 jasność 100/75/50/25 %, +/- jaśniej/ciemniej, q koniec\n")
    lin = lambda w: "".join(" ▁▂▃▄▅▆▇█"[min(v // 2, 8)] for v in w)
    try:
        while True:
            while msvcrt.kbhit():
                k = msvcrt.getwch()
                jas = s.u["jasnosc"]
                if k in "1234":
                    jas = int(k) - 1
                elif k in "+=":
                    jas = max(0, jas - 1)
                elif k in "-_":
                    jas = min(3, jas + 1)
                elif k in "qQ\x1b":
                    raise KeyboardInterrupt
                s.ustaw(jasnosc=jas)
            w, vu = s.wyslane, s.vu
            print(f"\r{lin(w[PASMA - 1::-1])} {'L' if vu[0] else '.'}{'R' if vu[1] else '.'} {lin(w[PASMA:])}"
                  f"  jasność {JASNOSCI[s.u['jasnosc']]:3} %  |  {s.stan_port}  |  {s.stan_audio[:30]}   ",
                  end="", flush=True)
            time.sleep(1 / 25)
    except KeyboardInterrupt:
        pass
    finally:
        s.stop()
        print("\nKoniec.")


if __name__ == "__main__":
    main()
