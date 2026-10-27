"""VFD spectrum analyzer - console version (GUI version: widmo_gui.py).

Install: pip install pyaudiowpatch pyserial numpy
Run:     python widmo.py [--port COM15] [--jasnosc 50]
Keys:    1-4 = brightness 100/75/50/25 %, +/- = brighter/dimmer, q = quit
"""
import argparse, msvcrt, sys, time
from silnik import AUTO, JASNOSCI, PASMA, Silnik


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=AUTO)
    ap.add_argument("--jasnosc", type=int, choices=JASNOSCI, default=100, help="VFD brightness in %%")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    s = Silnik({"port": args.port, "jasnosc": JASNOSCI.index(args.jasnosc)})
    s.start()
    print("Keys: 1-4 brightness 100/75/50/25 %, +/- brighter/dimmer, q quit\n")
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
                  f"  brightness {JASNOSCI[s.u['jasnosc']]:3} %  |  {s.stan_port}  |  {s.stan_audio[:30]}   ",
                  end="", flush=True)
            time.sleep(1 / 25)
    except KeyboardInterrupt:
        pass
    finally:
        s.stop()
        print("\nBye.")


if __name__ == "__main__":
    main()
