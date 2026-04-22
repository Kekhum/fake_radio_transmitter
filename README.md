# Radio Simulator

Symulator radia stworzony jako prop do sesji RPG. Program odtwarza pliki audio (MP3/WAV) przypisane do konkretnych częstotliwości radiowych, a między stacjami generuje realistyczny szum z trzaskami — jak prawdziwe radio analogowe.

Obsługuje wiele zakresów: **FM (UKF)**, **AM (SRE)**, **LW (DLU)**.

## Funkcje

- **Wiele zakresów** — FM, AM, fale długie — przełączanie klawiszem `Tab`
- **Strojenie** strzałkami `<` / `>` (przytrzymaj = szybciej)
- **Szum radiowy** z trzaskami i crackle między stacjami
- **Płynne przejścia** — sygnał narasta/opada kosinusoidalnie w obrębie bandwidth stacji
- **Dropouty** — na krawędzi zasięgu sygnał chwilowo zanika, imitując słaby odbiór
- **Ciągłe odtwarzanie** — wszystkie stacje na wszystkich zakresach "grają" od startu programu
- **Loopowanie** — utwory zapętlają się bezszwowo, z opcjonalnym opóźnieniem lub jednorazowym odtworzeniem
- **Interfejs graficzny** z wizualizacją skali, igłą strojenia, miernikiem sygnału i nazwą stacji
- **Tryb headless** — automatyczny na Raspberry Pi bez monitora (lub `--headless`)

## Wymagania

- Python 3.8+
- pygame
- numpy

### Instalacja zależności

```bash
pip install pygame numpy
```

## Uruchomienie

```bash
python radio.py
```

### Szybki test (bez własnych plików audio)

Wygeneruj testowe pliki dźwiękowe (tony sinusoidalne):

```bash
python generate_test_tones.py
```

Następnie uruchom `radio.py` — stacje testowe na wszystkich zakresach będą gotowe do odsłuchu.

## Sterowanie

| Klawisz          | Akcja                                      |
| ---------------- | ------------------------------------------ |
| `<` (strzałka)   | Strojenie w dół (przytrzymaj = szybciej)   |
| `>` (strzałka)   | Strojenie w górę (przytrzymaj = szybciej)  |
| `^` (strzałka)   | Głośność w górę (krok 5%)                  |
| `v` (strzałka)   | Głośność w dół (krok 5%)                   |
| `Tab`            | Przełączanie zakresu (FM / AM / LW)        |
| `ESC`            | Wyjście z programu                         |

## Konfiguracja

Plik `stations.json` definiuje zakresy i stacje. Każdy zakres (`band`) ma własne parametry strojenia i listę stacji:

```json
{
    "bands": [
        {
            "name": "UKF (FM)",
            "key": "FM",
            "unit": "MHz",
            "min_freq": 87.5,
            "max_freq": 108.0,
            "step": 0.1,
            "start_freq": 87.5,
            "stations": [
                {
                    "name": "Radio Wolnosc",
                    "frequency": 91.2,
                    "file": "music/radio_wolnosc.wav",
                    "bandwidth": 0.3,
                    "loop": true,
                    "loop_delay": 0
                }
            ]
        }
    ]
}
```

### Parametry zakresu

| Pole              | Opis                                              |
| ----------------- | ------------------------------------------------- |
| `name`            | Pełna nazwa zakresu                               |
| `key`             | Skrót wyświetlany w UI (FM, AM, LW)               |
| `unit`            | Jednostka częstotliwości (MHz, kHz)                |
| `min_freq`        | Dolna granica zakresu                              |
| `max_freq`        | Górna granica zakresu                              |
| `step`            | Krok strojenia                                     |
| `start_freq`      | Częstotliwość startowa po uruchomieniu             |
| `freq_format`     | Format wyświetlania (.1f dla MHz, .0f dla kHz)     |
| `dial_major_step` | Co ile jednostek rysować główne znaczniki na skali |
| `dial_minor_step` | Co ile jednostek rysować drobne znaczniki          |

### Parametry stacji

| Pole         | Opis                                                                 | Domyślnie |
| ------------ | -------------------------------------------------------------------- | --------- |
| `name`       | Nazwa wyświetlana w UI po złapaniu sygnału                          | —         |
| `frequency`  | Częstotliwość stacji (w jednostce zakresu)                           | —         |
| `file`       | Ścieżka do pojedynczego pliku audio                                 | —         |
| `playlist`   | Lista plików audio odtwarzanych kolejno (zamiast `file`)             | —         |
| `bandwidth`  | Szerokość pasma — im większa, tym łatwiej złapać stację             | `0.3`     |
| `loop`       | `true` = zapętla, `false` = gra raz i milknie                       | `true`    |
| `loop_delay` | Przerwa w sekundach ciszy między powtórzeniami playlisty             | `0`       |

Użyj `file` dla pojedynczego pliku albo `playlist` dla kolejki utworów:

```json
{
    "name": "Radio Wolnosc",
    "frequency": 91.2,
    "playlist": [
        "music/jingle.wav",
        "music/piosenka1.mp3",
        "music/reklamy.wav",
        "music/piosenka2.mp3"
    ],
    "bandwidth": 0.3,
    "loop": true,
    "loop_delay": 5
}

## Struktura projektu

```
Radio/
├── radio.py                 # Główna aplikacja
├── stations.json            # Konfiguracja zakresów i stacji
├── generate_test_tones.py   # Generator testowych plików audio
├── requirements.txt         # Zależności Pythona
└── music/                   # Katalog z plikami audio stacji
    ├── radio_wolnosc.wav    # FM 91.2 MHz
    ├── audycja_nocna.wav    # FM 97.5 MHz
    ├── wiadomosci.wav       # FM 103.8 MHz
    ├── polskie_radio.wav    # AM 756 kHz
    ├── radio_moskwa.wav     # AM 1143 kHz
    └── program_1.wav        # LW 225 kHz
```

## Przygotowanie audycji

- Przygotuj pliki audio tak, by koniec płynnie przechodził w początek (loopowalne)
- Stacje grają ciągle w tle od momentu uruchomienia — dłuższe nagrania dają większą różnorodność
- Użyj `loop_delay` żeby symulować przerwy w nadawaniu
- Użyj `"loop": false` dla jednorazowych komunikatów (np. specjalne wiadomości)
- Obsługiwane formaty: WAV, MP3, OGG

## Raspberry Pi

Program automatycznie przechodzi w tryb headless gdy nie wykryje wyświetlacza. Można też wymusić: `python radio.py --headless`. Przygotowany pod podpięcie enkodera obrotowego na GPIO.
