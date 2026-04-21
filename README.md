# FM Radio Simulator

Symulator radia FM stworzony jako prop do sesji RPG. Program odtwarza pliki audio (MP3/WAV) przypisane do konkretnych częstotliwości radiowych, a między stacjami generuje realistyczny szum z trzaskami — tak jak prawdziwe radio analogowe.

## Funkcje

- **Strojenie** strzałkami `<` / `>` w zakresie 87.5–108.0 MHz (krok 0.1 MHz)
- **Szum radiowy** z trzaskami i crackle między stacjami
- **Płynne przejścia** — sygnał narasta/opada kosinusoidalnie w obrębie bandwidth stacji
- **Dropouty** — na krawędzi zasięgu sygnał chwilowo zanika, imitując słaby odbiór
- **Ciągłe odtwarzanie** — wszystkie stacje "grają" od startu programu; po przełączeniu i powrocie audycja jest w miejscu, w jakim byłaby gdyby leciała cały czas
- **Loopowanie** — utwory zapętlają się bezszwowo
- **Interfejs graficzny** z wizualizacją skali, igłą strojenia, miernikiem siły sygnału i nazwą stacji

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

Następnie uruchom `radio.py` — trzy stacje testowe będą gotowe do odsłuchu.

## Sterowanie

| Klawisz          | Akcja                                      |
| ---------------- | ------------------------------------------ |
| `<` (strzałka)   | Strojenie w dół (przytrzymaj = szybciej)   |
| `>` (strzałka)   | Strojenie w górę (przytrzymaj = szybciej)  |
| `ESC`            | Wyjście z programu                         |

## Konfiguracja stacji

Plik `stations.json` definiuje stacje i parametry strojenia:

```json
{
    "stations": [
        {
            "name": "Radio Wolnosc",
            "frequency": 91.2,
            "file": "music/radio_wolnosc.wav",
            "bandwidth": 0.3
        }
    ],
    "tuning": {
        "min_freq": 87.5,
        "max_freq": 108.0,
        "step": 0.1,
        "start_freq": 87.5
    }
}
```

### Parametry stacji

| Pole        | Opis                                                                 |
| ----------- | -------------------------------------------------------------------- |
| `name`      | Nazwa wyświetlana w UI po złapaniu sygnału                          |
| `frequency` | Częstotliwość stacji w MHz                                           |
| `file`      | Ścieżka do pliku audio (MP3 lub WAV) względem katalogu projektu     |
| `bandwidth` | Szerokość pasma w MHz — im większa, tym łatwiej złapać stację (domyślnie 0.3) |

### Parametry strojenia

| Pole         | Opis                                |
| ------------ | ----------------------------------- |
| `min_freq`   | Dolna granica zakresu FM (MHz)      |
| `max_freq`   | Górna granica zakresu FM (MHz)      |
| `step`       | Krok strojenia (MHz)                |
| `start_freq` | Częstotliwość startowa po uruchomieniu |

## Struktura projektu

```
Radio/
├── radio.py                 # Główna aplikacja
├── stations.json            # Konfiguracja stacji i strojenia
├── generate_test_tones.py   # Generator testowych plików audio
├── requirements.txt         # Zależności Pythona
└── music/                   # Katalog z plikami audio stacji
    ├── radio_wolnosc.wav
    ├── audycja_nocna.wav
    └── wiadomosci.wav
```

## Przygotowanie audycji

Aby uzyskać najlepszy efekt:

- Przygotuj pliki audio tak, by koniec płynnie przechodził w początek (loopowalne)
- Stacje grają ciągle w tle od momentu uruchomienia — dłuższe nagrania dają większą różnorodność
- Obsługiwane formaty: WAV, MP3, OGG

## Raspberry Pi

Program jest przygotowany pod docelowe uruchomienie na Raspberry Pi z fizycznym pokrętłem (enkoder obrotowy). Wymaga jedynie podmiany obsługi klawiszy na odczyty GPIO.
