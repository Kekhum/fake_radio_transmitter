#!/usr/bin/env python3
"""
FM Radio Simulator — RPG prop
Symuluje strojenie radia FM z szumem i przejściami między stacjami.
Sterowanie: strzałki lewo/prawo (strojenie), ESC (wyjście).
"""

import json
import math
import os
import sys
import struct
import array
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

# Signal shape: how signal strength falls off from station center
# signal = max(0, 1 - (distance / bandwidth)^2)
# bandwidth is per-station (in MHz), default 0.3


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
        self.loop = loop                # False = play once then go silent
        self.loop_delay = loop_delay    # seconds of silence between loops
        self.loaded = False
        self.sound_array = None  # numpy float32 array (frames, channels)
        self.play_pos = 0
        self._finished = False          # True when loop=False and track ended
        self._delay_remaining = 0       # frames of silence left before next loop
        self._load()

    def _load(self):
        if not os.path.isfile(self.filepath):
            print(f"[WARN] Brak pliku: {self.filepath} — stacja '{self.name}' wyciszona")
            return
        try:
            snd = pygame.mixer.Sound(self.filepath)
            raw = pygame.sndarray.array(snd)  # shape (frames,) or (frames, ch)
            # Normalize to float32 -1..1
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
            print(f"[OK] Zaladowano: {self.name} @ {self.freq} MHz ({len(arr)/SAMPLE_RATE:.1f}s)")
        except Exception as e:
            print(f"[ERR] Nie mozna zaladowac {self.filepath}: {e}")

    def _handle_track_end(self):
        """Handle what happens when playback reaches the end of the track."""
        if not self.loop:
            self._finished = True
            self.play_pos = len(self.sound_array)  # park at end
        elif self.loop_delay > 0:
            self._delay_remaining = int(self.loop_delay * SAMPLE_RATE)
            self.play_pos = 0
        else:
            self.play_pos = 0

    @property
    def is_silent(self):
        return not self.loaded or self._finished or self._delay_remaining > 0

    def advance(self, n_frames):
        """Advance playback position without returning audio (background playback)."""
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
        """Return (n_frames, 2) float32. Respects loop/delay settings."""
        if not self.loaded or self._finished:
            return np.zeros((n_frames, 2), dtype=np.float32)

        out = np.zeros((n_frames, 2), dtype=np.float32)
        total = len(self.sound_array)
        remaining = n_frames
        write_pos = 0

        while remaining > 0:
            # If in delay gap, fill with silence
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
                    break  # remaining frames stay silent (zeros)

        return out

    def signal_strength(self, current_freq):
        """0.0 .. 1.0 based on distance from station center."""
        dist = abs(current_freq - self.freq)
        if dist >= self.bandwidth:
            return 0.0
        # Smooth falloff (cosine-based for nice radio feel)
        t = dist / self.bandwidth
        return 0.5 * (1.0 + math.cos(math.pi * t))


# ---------------------------------------------------------------------------
# Audio callback via pygame.mixer custom channel streaming
# ---------------------------------------------------------------------------
class RadioMixer:
    """Mixes station audio with noise based on current tuning."""

    def __init__(self, stations, noise, sample_rate, channels):
        self.stations = stations
        self.noise = noise
        self.sr = sample_rate
        self.ch = channels
        self.current_freq = 87.5
        self._volume = 0.8

    def render_chunk(self, n_frames):
        """Return pygame-compatible Sound from mixed audio."""
        # Get noise base
        noise = self.noise.get_frames(n_frames)

        # Find strongest station signal
        best_signal = 0.0
        mixed_station = np.zeros((n_frames, 2), dtype=np.float32)

        for st in self.stations:
            sig = st.signal_strength(self.current_freq)
            if sig > 0:
                frames = st.get_frames(n_frames)
                if sig > best_signal:
                    # Blend: when multiple overlap, strongest wins but others bleed
                    mixed_station = mixed_station * 0.3 + frames * sig
                    best_signal = sig
                else:
                    mixed_station += frames * sig * 0.3
            else:
                # Station plays in background — advance position to stay in sync
                st.advance(n_frames)

        # Clamp station signal
        best_signal = min(best_signal, 1.0)

        # Mix: crossfade between noise and station
        # Add subtle noise even on strong signal (radio atmosphere)
        noise_level = (1.0 - best_signal) * 0.85 + 0.02
        station_level = best_signal

        mixed = noise * noise_level + mixed_station * station_level
        mixed *= self._volume

        # Simulate slight distortion at edges of reception
        if 0.1 < best_signal < 0.6:
            # Intermittent dropouts
            dropout_chance = (0.6 - best_signal) * 0.15
            dropout_mask = (np.random.random(n_frames) > dropout_chance).astype(np.float32)
            # Smooth the mask to avoid harsh clicks
            kernel = np.ones(32) / 32
            dropout_mask = np.convolve(dropout_mask, kernel, mode="same")
            mixed[:, 0] *= dropout_mask
            mixed[:, 1] *= dropout_mask

        # Clip and convert to int16
        mixed = np.clip(mixed, -1.0, 1.0)
        int_data = (mixed * 32767).astype(np.int16)
        return int_data


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
class RadioDisplay:
    """Draws the radio tuner UI."""

    def __init__(self, screen, config):
        self.screen = screen
        self.min_freq = config["tuning"]["min_freq"]
        self.max_freq = config["tuning"]["max_freq"]
        pygame.font.init()
        self.font_big = pygame.font.SysFont("consolas", 48, bold=True)
        self.font_med = pygame.font.SysFont("consolas", 22)
        self.font_sm = pygame.font.SysFont("consolas", 16)
        self.stations = config["stations"]

        # Colors
        self.BG = (30, 25, 20)
        self.DIAL_BG = (45, 40, 32)
        self.FREQ_COLOR = (255, 200, 80)
        self.NEEDLE_COLOR = (255, 80, 50)
        self.STATION_COLOR = (120, 200, 120)
        self.TEXT_DIM = (140, 130, 110)
        self.SIGNAL_ON = (80, 255, 80)
        self.SIGNAL_OFF = (60, 55, 45)
        self.GLOW = (255, 220, 100)

    def draw(self, freq, signal_strength, station_name):
        self.screen.fill(self.BG)

        # --- Dial background ---
        dial_rect = pygame.Rect(40, 60, WINDOW_W - 80, 100)
        pygame.draw.rect(self.screen, self.DIAL_BG, dial_rect, border_radius=8)
        pygame.draw.rect(self.screen, (70, 65, 55), dial_rect, 2, border_radius=8)

        # --- Frequency markers on dial ---
        for mhz in range(88, 109):
            x = self._freq_to_x(float(mhz), dial_rect)
            is_major = mhz % 2 == 0
            h = 20 if is_major else 10
            color = self.TEXT_DIM if is_major else (80, 75, 65)
            pygame.draw.line(self.screen, color, (x, dial_rect.bottom - h), (x, dial_rect.bottom - 2))
            if is_major:
                label = self.font_sm.render(str(mhz), True, self.TEXT_DIM)
                self.screen.blit(label, (x - label.get_width() // 2, dial_rect.y + 8))

        # --- Station markers ---
        for st in self.stations:
            sx = self._freq_to_x(st["frequency"], dial_rect)
            pygame.draw.line(self.screen, self.STATION_COLOR, (sx, dial_rect.y + 30), (sx, dial_rect.y + 45), 2)

        # --- Needle (current frequency) ---
        nx = self._freq_to_x(freq, dial_rect)
        pygame.draw.line(self.screen, self.NEEDLE_COLOR, (nx, dial_rect.y + 5), (nx, dial_rect.bottom - 5), 3)
        # Glow effect
        glow_surf = pygame.Surface((20, dial_rect.height - 10), pygame.SRCALPHA)
        glow_surf.fill((255, 80, 50, 40))
        self.screen.blit(glow_surf, (nx - 10, dial_rect.y + 5))

        # --- Frequency display ---
        freq_text = f"{freq:>6.1f} MHz"
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
            # Flicker effect at low signal
            alpha = min(255, int(signal_strength * 400))
            name_color = (
                min(255, int(self.GLOW[0] * signal_strength)),
                min(255, int(self.GLOW[1] * signal_strength)),
                min(255, int(self.GLOW[2] * signal_strength)),
            )
            name_surf = self.font_med.render(station_name, True, name_color)
            self.screen.blit(name_surf, (WINDOW_W // 2 - name_surf.get_width() // 2, 260))

        # --- Controls hint ---
        hint = self.font_sm.render("[<] [>] strojenie    [ESC] wyjscie", True, (80, 75, 65))
        self.screen.blit(hint, (WINDOW_W // 2 - hint.get_width() // 2, WINDOW_H - 30))

        pygame.display.flip()

    def _freq_to_x(self, freq, rect):
        t = (freq - self.min_freq) / (self.max_freq - self.min_freq)
        return int(rect.x + t * rect.width)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def detect_headless():
    """Check if we should run without display (no screen available or --headless flag)."""
    if "--headless" in sys.argv:
        return True
    # Try to detect missing display (typical on headless Raspberry Pi)
    os.environ.setdefault("SDL_AUDIODRIVER", "alsa")
    if not os.environ.get("DISPLAY") and sys.platform != "win32":
        return True
    return False


def main():
    config = load_config()
    tuning = config["tuning"]
    min_freq = tuning["min_freq"]
    max_freq = tuning["max_freq"]
    step = tuning["step"]
    current_freq = tuning.get("start_freq", min_freq)
    headless = detect_headless()

    # Init pygame
    if headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        pygame.init()
        screen = None
        print("=== FM Radio Simulator (headless) ===")
        print("Sterowanie: strzalki <> = strojenie, ESC/Ctrl+C = wyjscie")
        print(f"Zakres: {min_freq} - {max_freq} MHz")
    else:
        pygame.init()
        screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        pygame.display.set_caption("FM Radio Simulator")

    pygame.mixer.quit()
    pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=CHANNELS, buffer=AUDIO_BUFFER)

    # Load stations
    base_dir = os.path.dirname(os.path.abspath(__file__))
    stations = []
    for s in config["stations"]:
        filepath = os.path.join(base_dir, s["file"])
        st = Station(
            s["name"], s["frequency"], filepath,
            bandwidth=s.get("bandwidth", 0.3),
            loop=s.get("loop", True),
            loop_delay=s.get("loop_delay", 0),
        )
        stations.append(st)

    noise = NoiseGenerator(SAMPLE_RATE, CHANNELS)
    mixer = RadioMixer(stations, noise, SAMPLE_RATE, CHANNELS)
    mixer.current_freq = current_freq
    display = RadioDisplay(screen, config) if not headless else None

    clock = pygame.time.Clock()

    # We'll use pygame.mixer.Channel with queued Sounds for gapless playback
    channel = pygame.mixer.Channel(0)

    def make_sound(int16_array):
        """Create pygame.Sound from numpy int16 array."""
        return pygame.sndarray.make_sound(int16_array)

    # Pre-render first chunk
    chunk = mixer.render_chunk(CHUNK_FRAMES)
    snd = make_sound(chunk)
    channel.play(snd)

    # Key repeat state
    tuning_direction = 0  # -1 left, +1 right, 0 none
    hold_timer = 0
    hold_started = False

    # Headless: track last printed freq to avoid spam
    last_printed_freq = None

    running = True
    try:
        while running:
            dt = clock.tick(FPS)

            # --- Events ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_LEFT:
                        tuning_direction = -1
                        current_freq = max(min_freq, round(current_freq - step, 1))
                        hold_timer = 0
                        hold_started = False
                    elif event.key == pygame.K_RIGHT:
                        tuning_direction = 1
                        current_freq = min(max_freq, round(current_freq + step, 1))
                        hold_timer = 0
                        hold_started = False
                elif event.type == pygame.KEYUP:
                    if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                        tuning_direction = 0
                        hold_timer = 0
                        hold_started = False

            # --- Hold-to-tune ---
            if tuning_direction != 0:
                hold_timer += dt
                if not hold_started and hold_timer >= HOLD_INITIAL_DELAY:
                    hold_started = True
                    hold_timer = 0
                if hold_started:
                    # Continuous tuning
                    steps_this_frame = max(1, int(hold_timer / HOLD_REPEAT_INTERVAL))
                    hold_timer -= steps_this_frame * HOLD_REPEAT_INTERVAL
                    for _ in range(steps_this_frame):
                        current_freq += tuning_direction * step
                    current_freq = round(max(min_freq, min(max_freq, current_freq)), 1)

            mixer.current_freq = current_freq

            # --- Audio: queue next chunk when current finishes ---
            if not channel.get_queue():
                chunk = mixer.render_chunk(CHUNK_FRAMES)
                snd = make_sound(chunk)
                channel.queue(snd)

            # --- Find current station info for display ---
            best_signal = 0.0
            best_name = ""
            for st in stations:
                sig = st.signal_strength(current_freq)
                if sig > best_signal:
                    best_signal = sig
                    best_name = st.name

            # --- Draw ---
            if display:
                display.draw(current_freq, best_signal, best_name)
            elif current_freq != last_printed_freq:
                sig_bar = "#" * int(best_signal * 15)
                station_info = f"  [{best_name}]" if best_signal > 0.3 else ""
                print(f"\r  {current_freq:>5.1f} MHz  |{sig_bar:<15}|{station_info}     ", end="", flush=True)
                last_printed_freq = current_freq

    except KeyboardInterrupt:
        print("\nZamykanie...")

    pygame.quit()


if __name__ == "__main__":
    main()
