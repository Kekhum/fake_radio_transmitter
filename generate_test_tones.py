#!/usr/bin/env python3
"""Generuje testowe pliki WAV z tonami, żeby przetestować radio bez prawdziwej muzyki."""

import os
import wave
import struct
import math

SAMPLE_RATE = 44100
DURATION = 30  # seconds
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music")


def generate_tone_wav(filename, freq_hz, duration=DURATION):
    """Generate a simple sine wave WAV file."""
    filepath = os.path.join(BASE_DIR, filename)
    n_frames = SAMPLE_RATE * duration

    with wave.open(filepath, "w") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)

        for i in range(n_frames):
            t = i / SAMPLE_RATE
            # Main tone + harmonics for richer sound
            val = 0.5 * math.sin(2 * math.pi * freq_hz * t)
            val += 0.2 * math.sin(2 * math.pi * freq_hz * 2 * t)
            val += 0.1 * math.sin(2 * math.pi * freq_hz * 3 * t)
            # Slight tremolo
            val *= 0.8 + 0.2 * math.sin(2 * math.pi * 0.5 * t)
            sample = int(val * 24000)
            sample = max(-32768, min(32767, sample))
            wf.writeframes(struct.pack("<hh", sample, sample))

    print(f"Wygenerowano: {filepath}")


if __name__ == "__main__":
    os.makedirs(BASE_DIR, exist_ok=True)
    generate_tone_wav("radio_wolnosc.wav", 440)      # A4 — 91.2 MHz
    generate_tone_wav("audycja_nocna.wav", 330)       # E4 — 97.5 MHz
    generate_tone_wav("wiadomosci.wav", 523)          # C5 — 103.8 MHz
    print("Gotowe! Zmien rozszerzenia w stations.json na .wav lub podmien na prawdziwe MP3.")
