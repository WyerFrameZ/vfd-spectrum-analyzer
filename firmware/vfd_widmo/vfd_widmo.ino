// Analizator widma stereo na VFD Noritake CU20029ECPB-W1J (20x2).
// Dane przychodzą z komputera po USB (widmo.py):
//   0xFF, 9 pasm L, 9 pasm R (0..16), VU L, VU R (0..8), jasność (0..3)
// Układ: [9 pasm L] L R [9 pasm R], literki w dolnej linii (kropka = cisza w kanale).
#include <LiquidCrystal.h>
// RS, E, D0..D7
LiquidCrystal vfd(12, 11, 10, 9, 8, 7, 5, 4, 3, 2);

const byte W = 20;
const byte PASMA = 9;          // pasm na kanał
const bool LUSTRO = true;      // true = bas obu kanałów przy środku, false = bas po lewej w obu
const byte RAMKA = 2 * PASMA + 3;

byte poziom[2 * PASMA];        // [0..8] = L, [9..17] = R, indeks 0 = bas
byte vu[2];
byte jas = 0, jasTeraz = 255;
bool nowe = false;
unsigned long ostatnieDane = 0;

void jasnosc(byte p) {         // 0 = 100%, 1 = 75%, 2 = 50%, 3 = 25%
  vfd.command(0x38);
  vfd.write(p & 3);
  jasTeraz = p;
}

// znaki 0..7 = słupek wypełniony od dołu na 1..8 wierszy
void znakiSlupkow() {
  for (byte n = 0; n < 8; n++) {
    byte c[8];
    for (byte r = 0; r < 8; r++) c[r] = (r >= 7 - n) ? 0x1F : 0;
    vfd.createChar(n, c);
  }
}

byte kolumna(byte kanal, byte i) {   // i = 0 (bas) .. 8 (wysokie)
  if (kanal == 0) return LUSTRO ? PASMA - 1 - i : i;
  return PASMA + 2 + i;
}

void odbierz() {
  static byte idx = RAMKA, buf[RAMKA];
  while (Serial.available()) {
    byte b = Serial.read();
    if (b == 0xFF) { idx = 0; continue; }
    if (idx >= RAMKA) continue;
    buf[idx++] = b;
    if (idx == RAMKA) {
      for (byte i = 0; i < 2 * PASMA; i++) poziom[i] = min(buf[i], 16);
      vu[0] = min(buf[2 * PASMA], 8);
      vu[1] = min(buf[2 * PASMA + 1], 8);
      jas = buf[2 * PASMA + 2] & 3;
      nowe = true;
      ostatnieDane = millis();
    }
  }
}

void rysujWidmo() {
  byte gora[W], dol[W];
  memset(gora, ' ', W);
  memset(dol, ' ', W);
  for (byte k = 0; k < 2; k++) {
    for (byte i = 0; i < PASMA; i++) {
      byte h = poziom[k * PASMA + i], x = kolumna(k, i);
      if (h >= 8) dol[x] = 7; else if (h) dol[x] = h - 1;
      if (h > 8) gora[x] = h - 9;
    }
    // środek: literka kanału, w ciszy kropka
    dol[PASMA + k] = vu[k] ? (k ? 'R' : 'L') : '.';
  }
  if (jas != jasTeraz) jasnosc(jas);
  vfd.setCursor(0, 0);
  for (byte x = 0; x < W; x++) vfd.write(gora[x]);
  vfd.setCursor(0, 1);
  for (byte x = 0; x < W; x++) vfd.write(dol[x]);
}

void rysujCzekanie(unsigned long t) {
  static unsigned long ostatnio = 0;
  if (t - ostatnio < 70) return;
  ostatnio = t;
  vfd.setCursor(0, 0);
  vfd.print("  Waiting for USB...");
  byte k = (t / 70) % 38;
  byte p = k < 19 ? k : 38 - k;        // skaner odbija się od brzegów
  vfd.setCursor(0, 1);
  for (byte i = 0; i < W; i++)
    vfd.write(i == p ? byte(7) : (abs(i - p) == 1 ? byte(2) : byte(' ')));
}

void setup() {
  Serial.begin(115200);
  delay(500);
  vfd.begin(W, 2);
  jasnosc(0);
  znakiSlupkow();
  vfd.clear();
}

void loop() {
  odbierz();
  unsigned long t = millis();
  if (t - ostatnieDane > 2000 || ostatnieDane == 0) {
    rysujCzekanie(t);
  } else if (nowe) {
    nowe = false;
    rysujWidmo();
  }
}
