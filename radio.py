#!/usr/bin/env python3
"""
FM Radio Simulator — RPG prop
Symuluje strojenie radia z szumem i przejściami między stacjami.
Obsługuje wiele zakresów: FM (UKF), AM (SRE), LW (DLU).
Sterowanie: strzałki lewo/prawo (strojenie), Tab (zmiana zakresu), ESC (wyjście).
"""

import json
import math
import os
import sys
import numpy as np
import pygame

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stations.json")

SAMPLE_RATE = 44100
AUDIO_BUFFER = 1024
CHANNELS = 2  # stereo

# How fast we generate noise/mix (chunk size in frames)
CHUNK_FRAMES = 2048

# Visual
WINDOW_W, WINDOW_H = 800, 400
FPS = 30

# Tuning feel
HOLD_INITIAL_DELAY = 300   # ms before repeat starts
HOLD_REPEAT_INTERVAL = 60  # ms between repeats while held


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Noise generator — cached band-limited white noise
# ---------------------------------------------------------------------------
class NoiseGenerator:
    """Generates continuous static noise with optional crackle."""

    def __init__(self, sample_rate, channels):
        self.sr = sample_rate
        self.ch = channels
        # Pre-generate a long noise buffer (2 seconds) and loop through it
        length = sample_rate * 2
        raw = np.random.uniform(-1.0, 1.0, length).astype(np.float32)
        # Slight low-pass for more "radio" feel — simple moving average
        kernel = np.ones(6) / 6
        raw = np.convolve(raw, kernel, mode="same")
        # Add occasional crackle pops
        n_pops = int(length * 0.002)
        pop_positions = np.random.randint(0, length, n_pops)
        raw[pop_positions] += np.random.choice([-1, 1], n_pops) * np.random.uniform(0.4, 0.9, n_pops)
        raw = np.clip(raw, -1.0, 1.0)
        self.buffer = raw
        self.pos = 0

    def get_frames(self, n_frames):
        """Return (n_frames, channels) float32 array of noise."""
        out = np.empty(n_frames, dtype=np.float32)
        remaining = n_frames
        write_pos = 0
        while remaining > 0:
            avail = len(self.buffer) - self.pos
            take = min(avail, remaining)
            out[write_pos:write_pos + take] = self.buffer[self.pos:self.pos + take]
            self.pos += take
            write_pos += take
            remaining -= take
            if self.pos >= len(self.buffer):
                self.pos = 0
        # Stereo: duplicate
        if self.ch == 2:
            return np.column_stack((out, out))
        return out.reshape(-1, 1)


# ---------------------------------------------------------------------------
# Station — wraps a pygame Sound with streaming position
# ---------------------------------------------------------------------------
class Station:
    def __init__(self, name, frequency, filepath, bandwidth=0.3, loop=True, loop_delay=0):
        self.name = name
        self.freq = frequency
        self.bandwidth = bandwidth
        self.filepath = filepath
        self.loop = loop
        self.loop_delay = loop_delay
        self.loaded = False
        self.sound_array = None
        self.play_pos = 0
        self._finished = False
        self._delay_remaining = 0
        self._load()

    def _load(self):
        if not os.path.isfile(self.filepath):
            print(f"[WARN] Brak pliku: {self.filepath} — stacja '{self.name}' wyciszona")
            return
        try:
            snd = pygame.mixer.Sound(self.filepath)
            raw = pygame.sndarray.array(snd)
            if raw.dtype == np.int16:
                arr = raw.astype(np.float32) / 32768.0
            elif raw.dtype == np.int32:
                arr = raw.astype(np.float32) / 2147483648.0
            else:
                arr = raw.astype(np.float32)
            if arr.ndim == 1:
                arr = np.column_stack((arr, arr))
            elif arr.shape[1] == 1:
                arr = np.column_stack((arr[:, 0], arr[:, 0]))
            self.sound_array = arr
            self.play_pos = 0
            self.loaded = True
            print(f"[OK] Zaladowano: {self.name} @ {self.freq} ({len(arr)/SAMPLE_RATE:.1f}s)")
        except Exception as e:
            print(f"[ERR] Nie mozna zaladowac {self.filepath}: {e}")

    def _handle_track_end(self):
        if not self.loop:
            self._finished = True
            self.play_pos = len(self.sound_array)
        elif self.loop_delay > 0:
            self._delay_remaining = int(self.loop_delay * SAMPLE_RATE)
            self.play_pos = 0
        else:
            self.play_pos = 0

    @property
    def is_silent(self):
        return not self.loaded or self._finished or self._delay_remaining > 0

    def advance(self, n_frames):
        if not self.loaded or self._finished:
            return
        if self._delay_remaining > 0:
            self._delay_remaining = max(0, self._delay_remaining - n_frames)
            return
        new_pos = self.play_pos + n_frames
        total = len(self.sound_array)
        if new_pos >= total:
            self._handle_track_end()
            if not self._finished and self._delay_remaining == 0:
                self.play_pos = new_pos % total
        else:
            self.play_pos = new_pos

    def get_frames(self, n_frames):
        if not self.loaded or self._finished:
            return np.zeros((n_frames, 2), dtype=np.float32)
        out = np.zeros((n_frames, 2), dtype=np.float32)
        total = len(self.sound_array)
        remaining = n_frames
        write_pos = 0
        while remaining > 0:
            if self._delay_remaining > 0:
                silence = min(remaining, self._delay_remaining)
                self._delay_remaining -= silence
                write_pos += silence
                remaining -= silence
                continue
            avail = total - self.play_pos
            take = min(avail, remaining)
            out[write_pos:write_pos + take] = self.sound_array[self.play_pos:self.play_pos + take]
            self.play_pos += take
            write_pos += take
            remaining -= take
            if self.play_pos >= total:
                self._handle_track_end()
                if self._finished:
                    break
        return out

    def signal_strength(self, current_freq):
        dist = abs(current_freq - self.freq)
        if dist >= self.bandwidth:
            return 0.0
        t = dist / self.bandwidth
        return 0.5 * (1.0 + math.cos(math.pi * t))


# ---------------------------------------------------------------------------
# Band — a frequency range with its own stations
# ---------------------------------------------------------------------------
class Band:
    def __init__(self, band_config, base_dir):
        self.name = band_config["name"]
        self.key = band_config["key"]
        self.unit = band_config["unit"]
        self.min_freq = band_config["min_freq"]
        self.max_freq = band_config["max_freq"]
        self.step = band_config["step"]
        self.start_freq = band_config.get("start_freq", self.min_freq)
        self.freq_format = band_config.get("freq_format", ".1f")
        self.dial_major_step = band_config.get("dial_major_step", 2)
        self.dial_minor_step = band_config.get("dial_minor_step", 1)
        self.dial_range_start = band_config.get("dial_range_start", int(self.min_freq))
        self.dial_range_end = band_config.get("dial_range_end", int(self.max_freq))
        self.current_freq = self.start_freq
        self.stations_config = band_config.get("stations", [])

        self.stations = []
        for s in self.stations_config:
            filepath = os.path.join(base_dir, s["file"])
            st = Station(
                s["name"], s["frequency"], filepath,
                bandwidth=s.get("bandwidth", 0.3),
                loop=s.get("loop", True),
                loop_delay=s.get("loop_delay", 0),
            )
            self.stations.append(st)

    def format_freq(self):
        return f"{self.current_freq:{self.freq_format}}"


# ---------------------------------------------------------------------------
# Audio mixer
# ---------------------------------------------------------------------------
class RadioMixer:
    """Mixes station audio with noise based on current tuning."""

    def __init__(self, noise, sample_rate, channels):
        self.noise = noise
        self.sr = sample_rate
        self.ch = channels
        self.all_bands = []   # all bands — for background advance
        self.active_band = None
        self._volume = 0.8

    def render_chunk(self, n_frames):
        noise = self.noise.get_frames(n_frames)
        best_signal = 0.0
        mixed_station = np.zeros((n_frames, 2), dtype=np.float32)

        # Advance all stations on all bands
        for band in self.all_bands:
            for st in band.stations:
                if band is self.active_band:
                    sig = st.signal_strength(band.current_freq)
                    if sig > 0:
                        frames = st.get_frames(n_frames)
                        if sig > best_signal:
                            mixed_station = mixed_station * 0.3 + frames * sig
                            best_signal = sig
                        else:
                            mixed_station += frames * sig * 0.3
                    else:
                        st.advance(n_frames)
                else:
                    st.advance(n_frames)

        best_signal = min(best_signal, 1.0)
        noise_level = (1.0 - best_signal) * 0.85 + 0.02
        station_level = best_signal

        mixed = noise * noise_level + mixed_station * station_level
        mixed *= self._volume

        if 0.1 < best_signal < 0.6:
            dropout_chance = (0.6 - best_signal) * 0.15
            dropout_mask = (np.random.random(n_frames) > dropout_chance).astype(np.float32)
            kernel = np.ones(32) / 32
            dropout_mask = np.convolve(dropout_mask, kernel, mode="same")
            mixed[:, 0] *= dropout_mask
            mixed[:, 1] *= dropout_mask

        mixed = np.clip(mixed, -1.0, 1.0)
        return (mixed * 32767).astype(np.int16)


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
class RadioDisplay:
    """Draws the radio tuner UI with multi-band support."""

    def __init__(self, screen):
        self.screen = screen
        pygame.font.init()
        self.font_big = pygame.font.SysFont("consolas", 48, bold=True)
        self.font_med = pygame.font.SysFont("consolas", 22)
        self.font_sm = pygame.font.SysFont("consolas", 16)

        self.BG = (30, 25, 20)
        self.DIAL_BG = (45, 40, 32)
        self.FREQ_COLOR = (255, 200, 80)
        self.NEEDLE_COLOR = (255, 80, 50)
        self.STATION_COLOR = (120, 200, 120)
        self.TEXT_DIM = (140, 130, 110)
        self.SIGNAL_ON = (80, 255, 80)
        self.SIGNAL_OFF = (60, 55, 45)
        self.GLOW = (255, 220, 100)
        self.BAND_ACTIVE = (255, 200, 80)
        self.BAND_INACTIVE = (80, 75, 65)

    def draw(self, band, bands, signal_strength, station_name):
        self.screen.fill(self.BG)

        # --- Band selector ---
        bx = 40
        for b in bands:
            is_active = b is band
            color = self.BAND_ACTIVE if is_active else self.BAND_INACTIVE
            label = self.font_med.render(b.key, True, color)
            if is_active:
                # Underline
                lw = label.get_width()
                pygame.draw.line(self.screen, color, (bx, 38), (bx + lw, 38), 2)
            self.screen.blit(label, (bx, 15))
            bx += label.get_width() + 25

        # --- Dial background ---
        dial_rect = pygame.Rect(40, 60, WINDOW_W - 80, 100)
        pygame.draw.rect(self.screen, self.DIAL_BG, dial_rect, border_radius=8)
        pygame.draw.rect(self.screen, (70, 65, 55), dial_rect, 2, border_radius=8)

        # --- Frequency markers on dial ---
        f = band.dial_range_start
        while f <= band.dial_range_end:
            x = self._freq_to_x(float(f), dial_rect, band)
            is_major = (f - band.dial_range_start) % band.dial_major_step == 0
            h = 20 if is_major else 10
            color = self.TEXT_DIM if is_major else (80, 75, 65)
            pygame.draw.line(self.screen, color, (x, dial_rect.bottom - h), (x, dial_rect.bottom - 2))
            if is_major:
                label_text = str(int(f)) if f == int(f) else f"{f:{band.freq_format}}"
                label = self.font_sm.render(label_text, True, self.TEXT_DIM)
                self.screen.blit(label, (x - label.get_width() // 2, dial_rect.y + 8))
            f += band.dial_minor_step

        # --- Station markers ---
        for st in band.stations:
            sx = self._freq_to_x(st.freq, dial_rect, band)
            pygame.draw.line(self.screen, self.STATION_COLOR, (sx, dial_rect.y + 30), (sx, dial_rect.y + 45), 2)

        # --- Needle ---
        nx = self._freq_to_x(band.current_freq, dial_rect, band)
        pygame.draw.line(self.screen, self.NEEDLE_COLOR, (nx, dial_rect.y + 5), (nx, dial_rect.bottom - 5), 3)
        glow_surf = pygame.Surface((20, dial_rect.height - 10), pygame.SRCALPHA)
        glow_surf.fill((255, 80, 50, 40))
        self.screen.blit(glow_surf, (nx - 10, dial_rect.y + 5))

        # --- Frequency display ---
        freq_text = f"{band.format_freq()} {band.unit}"
        freq_surf = self.font_big.render(freq_text, True, self.FREQ_COLOR)
        self.screen.blit(freq_surf, (WINDOW_W // 2 - freq_surf.get_width() // 2, 200))

        # --- Signal strength meter ---
        meter_x, meter_y = 50, 290
        meter_label = self.font_sm.render("SIGNAL", True, self.TEXT_DIM)
        self.screen.blit(meter_label, (meter_x, meter_y - 20))
        n_bars = 15
        for i in range(n_bars):
            bar_on = (i / n_bars) < signal_strength
            color = self.SIGNAL_ON if bar_on else self.SIGNAL_OFF
            bx = meter_x + i * 18
            bar_h = 12 + i * 1.5
            pygame.draw.rect(self.screen, color, (bx, meter_y + 30 - bar_h, 12, bar_h), border_radius=2)

        # --- Station name ---
        if signal_strength > 0.3 and station_name:
            name_color = (
                min(255, int(self.GLOW[0] * signal_strength)),
                min(255, int(self.GLOW[1] * signal_strength)),
                min(255, int(self.GLOW[2] * signal_strength)),
            )
            name_surf = self.font_med.render(station_name, True, name_color)
            self.screen.blit(name_surf, (WINDOW_W // 2 - name_surf.get_width() // 2, 260))

        # --- Controls hint ---
        hint = self.font_sm.render("[<] [>] strojenie    [Tab] zakres    [ESC] wyjscie", True, (80, 75, 65))
        self.screen.blit(hint, (WINDOW_W // 2 - hint.get_width() // 2, WINDOW_H - 30))

        pygame.display.flip()

    def _freq_to_x(self, freq, rect, band):
        pad = 20
        t = (freq - band.min_freq) / (band.max_freq - band.min_freq)
        return int(rect.x + pad + t * (rect.width - 2 * pad))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def detect_headless():
    if "--headless" in sys.argv:
        return True
    if sys.platform.startswith("linux"):
        os.environ.setdefault("SDL_AUDIODRIVER", "alsa")
    if not os.environ.get("DISPLAY") and sys.platform != "win32":
        return True
    return False


def main():
    config = load_config()
    headless = detect_headless()

    # Init pygame
    if headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        pygame.init()
        screen = None
        print("=== Radio Simulator (headless) ===")
        print("Sterowanie: <> strojenie, Tab zakres, ESC/Ctrl+C wyjscie")
    else:
        pygame.init()
        screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        pygame.display.set_caption("Radio Simulator")

    pygame.mixer.quit()
    pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=CHANNELS, buffer=AUDIO_BUFFER)

    # Load bands
    base_dir = os.path.dirname(os.path.abspath(__file__))
    bands = [Band(b, base_dir) for b in config["bands"]]
    band_idx = 0
    active_band = bands[band_idx]

    noise = NoiseGenerator(SAMPLE_RATE, CHANNELS)
    mixer = RadioMixer(noise, SAMPLE_RATE, CHANNELS)
    mixer.all_bands = bands
    mixer.active_band = active_band
    display = RadioDisplay(screen) if not headless else None

    clock = pygame.time.Clock()
    channel = pygame.mixer.Channel(0)

    def make_sound(int16_array):
        return pygame.sndarray.make_sound(int16_array)

    chunk = mixer.render_chunk(CHUNK_FRAMES)
    snd = make_sound(chunk)
    channel.play(snd)

    tuning_direction = 0
    hold_timer = 0
    hold_started = False
    last_printed_state = None

    running = True
    try:
        while running:
            dt = clock.tick(FPS)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_TAB:
                        band_idx = (band_idx + 1) % len(bands)
                        active_band = bands[band_idx]
                        mixer.active_band = active_band
                        tuning_direction = 0
                        hold_started = False
                    elif event.key == pygame.K_LEFT:
                        tuning_direction = -1
                        active_band.current_freq = max(
                            active_band.min_freq,
                            round(active_band.current_freq - active_band.step, 1),
                        )
                        hold_timer = 0
                        hold_started = False
                    elif event.key == pygame.K_RIGHT:
                        tuning_direction = 1
                        active_band.current_freq = min(
                            active_band.max_freq,
                            round(active_band.current_freq + active_band.step, 1),
                        )
                        hold_timer = 0
                        hold_started = False
                elif event.type == pygame.KEYUP:
                    if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                        tuning_direction = 0
                        hold_timer = 0
                        hold_started = False

            # Hold-to-tune
            if tuning_direction != 0:
                hold_timer += dt
                if not hold_started and hold_timer >= HOLD_INITIAL_DELAY:
                    hold_started = True
                    hold_timer = 0
                if hold_started:
                    steps_this_frame = max(1, int(hold_timer / HOLD_REPEAT_INTERVAL))
                    hold_timer -= steps_this_frame * HOLD_REPEAT_INTERVAL
                    for _ in range(steps_this_frame):
                        active_band.current_freq += tuning_direction * active_band.step
                    active_band.current_freq = round(
                        max(active_band.min_freq, min(active_band.max_freq, active_band.current_freq)), 1
                    )

            # Audio
            if not channel.get_queue():
                chunk = mixer.render_chunk(CHUNK_FRAMES)
                snd = make_sound(chunk)
                channel.queue(snd)

            # Find current station
            best_signal = 0.0
            best_name = ""
            for st in active_band.stations:
                sig = st.signal_strength(active_band.current_freq)
                if sig > best_signal:
                    best_signal = sig
                    best_name = st.name

            # Draw
            if display:
                display.draw(active_band, bands, best_signal, best_name)
            else:
                state = (active_band.key, active_band.current_freq)
                if state != last_printed_state:
                    sig_bar = "#" * int(best_signal * 15)
                    station_info = f"  [{best_name}]" if best_signal > 0.3 else ""
                    freq_str = f"{active_band.format_freq()} {active_band.unit}"
                    print(f"\r  [{active_band.key}] {freq_str:>12}  |{sig_bar:<15}|{station_info}     ", end="", flush=True)
                    last_printed_state = state

    except KeyboardInterrupt:
        print("\nZamykanie...")

    pygame.quit()


if __name__ == "__main__":
    main()
