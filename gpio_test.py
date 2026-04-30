#!/usr/bin/env python3
"""
Test GPIO — sprawdza czy enkoder w ogole generuje sygnaly.
Czyta surowy stan pinow A i B i wypisuje zmiany.
"""

import time
import sys

try:
    from gpiozero import DigitalInputDevice
except ImportError:
    print("BLAD: brak biblioteki gpiozero. Zainstaluj: sudo apt install python3-gpiozero")
    sys.exit(1)

PIN_A = 17
PIN_B = 27

print(f"Test enkodera na pinach GPIO{PIN_A} (A) i GPIO{PIN_B} (B)")
print("Pull-up aktywny — bez sygnalu pin czyta '1', uziemienie czyta '0'")
print("Krec enkoderem — powinienes widziec zmiany 0/1 na obu pinach")
print("Ctrl+C zeby zakonczyc\n")

a = DigitalInputDevice(PIN_A, pull_up=True)
b = DigitalInputDevice(PIN_B, pull_up=True)

last_a = a.value
last_b = b.value
print(f"Stan poczatkowy:  A={last_a}  B={last_b}")
print(f"  (jesli widzisz A=1 B=1 — pull-up dziala, ale srodkowy pin moze nie byc na GND)")
print(f"  (jesli A=0 B=0 stale — sprawdz polaczenia)\n")

events = 0
try:
    while True:
        ca = a.value
        cb = b.value
        if ca != last_a or cb != last_b:
            events += 1
            arrow_a = "v" if ca < last_a else "^" if ca > last_a else "."
            arrow_b = "v" if cb < last_b else "^" if cb > last_b else "."
            print(f"[{events:>4}]  A={ca}{arrow_a}  B={cb}{arrow_b}")
            last_a = ca
            last_b = cb
        time.sleep(0.005)
except KeyboardInterrupt:
    print(f"\nZakonczono. Lacznie zdarzen: {events}")
    if events == 0:
        print("\nUWAGA: zero zdarzen — enkoder nie generuje sygnalu.")
        print("Sprawdz:")
        print("  1. Pin A podlaczony do pinu fizycznego 11 (GPIO17)")
        print("  2. Pin B podlaczony do pinu fizycznego 13 (GPIO27)")
        print("  3. SRODKOWY pin enkodera podlaczony do GND (np. pin fizyczny 9)")
        print("  4. Polaczenia mocno wpiete, kable nie przerwane")
