# Radio Simulator

A radio simulator built as a prop for tabletop RPG sessions. The program plays audio files (MP3/WAV) assigned to specific radio frequencies, generating realistic static noise with crackle between stations — just like a real analog radio.

Supports multiple bands: **FM**, **AM (MW)**, **LW**.

## Features

- **Multiple bands** — FM, AM, Long Wave — switch with `Tab`
- **Tuning** with `<` / `>` arrow keys (hold for faster tuning)
- **Radio static** with crackle and pops between stations
- **Smooth transitions** — signal fades in/out with cosine falloff within station bandwidth
- **Signal dropouts** — intermittent audio loss at the edge of reception range
- **Continuous playback** — all stations on all bands play from program start; switching back finds them where they would be
- **Looping** — tracks loop seamlessly, with optional delay or one-shot playback
- **GUI** — dial visualization, tuning needle, signal strength meter, and station name display
- **Headless mode** — automatic on Raspberry Pi without a display (or `--headless` flag)

## Requirements

- Python 3.8+
- pygame
- numpy

### Install dependencies

```bash
pip install pygame numpy
```

## Running

```bash
python radio.py
```

### Quick test (without your own audio files)

Generate test audio files (sine wave tones):

```bash
python generate_test_tones.py
```

Then run `radio.py` — test stations on all bands will be ready to listen to.

## Controls

| Key              | Action                                     |
| ---------------- | ------------------------------------------ |
| `<` (arrow)      | Tune down (hold for faster)                |
| `>` (arrow)      | Tune up (hold for faster)                  |
| `^` (arrow)      | Volume up (5% step)                        |
| `v` (arrow)      | Volume down (5% step)                      |
| `Tab`            | Switch band (FM / AM / LW)                 |
| `ESC`            | Exit                                       |

## Configuration

The `stations.json` file defines bands and stations. Each band has its own tuning parameters and station list:

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

### Band parameters

| Field             | Description                                       |
| ----------------- | ------------------------------------------------- |
| `name`            | Full band name                                    |
| `key`             | Short label shown in UI (FM, AM, LW)              |
| `unit`            | Frequency unit (MHz, kHz)                         |
| `min_freq`        | Lower frequency limit                             |
| `max_freq`        | Upper frequency limit                             |
| `step`            | Tuning step size                                  |
| `start_freq`      | Starting frequency on launch                      |
| `freq_format`     | Display format (.1f for MHz, .0f for kHz)         |
| `dial_major_step` | Major tick interval on the dial scale             |
| `dial_minor_step` | Minor tick interval on the dial scale             |

### Station parameters

| Field        | Description                                                          | Default   |
| ------------ | -------------------------------------------------------------------- | --------- |
| `name`       | Station name displayed when signal is locked                         | —         |
| `frequency`  | Station frequency (in the band's unit)                               | —         |
| `file`       | Path to a single audio file                                          | —         |
| `playlist`   | List of audio files played in sequence (instead of `file`)           | —         |
| `bandwidth`  | Signal width — larger value = easier to find the station             | `0.3`     |
| `loop`       | `true` = loop, `false` = play once then go silent                    | `true`    |
| `loop_delay` | Silence gap in seconds between playlist repeats                      | `0`       |

Use `file` for a single track or `playlist` for a queue:

```json
{
    "name": "Radio Wolnosc",
    "frequency": 91.2,
    "playlist": [
        "music/jingle.wav",
        "music/song1.mp3",
        "music/commercials.wav",
        "music/song2.mp3"
    ],
    "bandwidth": 0.3,
    "loop": true,
    "loop_delay": 5
}

## Project structure

```
Radio/
├── radio.py                 # Main application
├── stations.json            # Band and station configuration
├── generate_test_tones.py   # Test audio file generator
├── requirements.txt         # Python dependencies
└── music/                   # Station audio files
    ├── radio_wolnosc.wav    # FM 91.2 MHz
    ├── audycja_nocna.wav    # FM 97.5 MHz
    ├── wiadomosci.wav       # FM 103.8 MHz
    ├── polskie_radio.wav    # AM 756 kHz
    ├── radio_moskwa.wav     # AM 1143 kHz
    └── program_1.wav        # LW 225 kHz
```

## Preparing audio content

- Prepare audio files so the end transitions smoothly into the beginning (loopable)
- Stations play continuously in the background from launch — longer recordings give more variety
- Use `loop_delay` to simulate broadcast pauses
- Use `"loop": false` for one-time messages (e.g. special news bulletins)
- Supported formats: WAV, MP3, OGG

## Raspberry Pi

The program automatically switches to headless mode when no display is detected. Can also be forced with: `python radio.py --headless`. Ready for rotary encoder input via GPIO.
