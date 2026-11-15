import math
import random
import struct
import io
import wave
import pyglet

SAMPLE_RATE = 22050
NOTES_FREQ = [
    32.70, 34.65, 36.71, 38.89, 41.20, 43.65,
    46.25, 49.00, 51.91, 55.00, 58.27, 61.74
]  # C-1 a B-1


class TICAudio:

    def __init__(self, memory):
        self.memory = memory
        self.players = {ch: pyglet.media.Player() for ch in range(4)}
        self.playing = {}
        self.master_volume = 1.0
        self._sfx_cache = {}
        self._music_state = None

    def _get_waveform(self, wave_idx):
        wave_idx = int(wave_idx) & 15
        raw = self.memory.waveforms.get(wave_idx)
        if raw:
            raw = raw.ljust(16, b"\x00")
            samples = []
            for b in raw[:16]:
                samples.append(((b & 0x0F) / 7.5) - 1.0)
                samples.append((((b >> 4) & 0x0F) / 7.5) - 1.0)
            return samples

        # Ondas por defecto si el cartucho no define WAVEFORMS
        if wave_idx == 0:    # Cuadrada
            return [1.0 if i < 16 else -1.0 for i in range(32)]
        elif wave_idx == 1:  # Triángulo
            return [(i / 8.0 - 1.0) if i < 16 else (3.0 - i / 8.0) for i in range(32)]
        elif wave_idx == 2:  # Sierra
            return [(i / 15.5) - 1.0 for i in range(32)]
        else:                # Pulso estrecho / Ruido
            return [1.0 if i < 8 else -1.0 for i in range(32)]

    def _decode_sfx(self, sfx_id):
        raw = self.memory.sfx_data.get(sfx_id)
        if not raw:
            return None
        raw = raw.ljust(66, b"\x00")

        ticks = []
        for i in range(30):
            b0 = raw[i * 2]
            b1 = raw[i * 2 + 1]
            val = b0 | (b1 << 8)

            vol = val & 0x0F
            wave = (val >> 4) & 0x0F
            chord = (val >> 8) & 0x0F
            pitch = (val >> 12) & 0x0F
            if pitch >= 8:
                pitch -= 16

            # En formato TIC-80 v1+, nota y octava van codificadas en los bits superiores o segundo byte
            note = b0 & 0x0F
            octave = (b0 >> 4) & 0x07
            vol = 15 - ((b1 >> 4) & 0x0F)
            wave = b1 & 0x0F

            ticks.append({
                "note": note % 12,
                "octave": octave,
                "vol": max(0, min(15, vol)),
                "wave": wave,
                "pitch": pitch,
                "chord": chord
            })

        speed = raw[60] & 0x07
        return {"ticks": ticks, "speed": speed}

    def _render_sfx_source(self, sfx_id, base_note=-1, volume=-1, speed=-1):
        key = (sfx_id, base_note, volume, speed)
        if key in self._sfx_cache:
            return self._sfx_cache[key]

        sfx = self._decode_sfx(sfx_id)
        if not sfx:
            return None

        spd = speed if speed >= 0 else sfx["speed"]
        tick_duration = (1.0 / 60.0) * (1 + spd)
        samples_per_tick = max(1, int(SAMPLE_RATE * tick_duration))

        pcm = bytearray()
        phase = 0.0

        for tk in sfx["ticks"]:
            vol_norm = (volume if volume >= 0 else tk["vol"]) / 15.0
            if vol_norm <= 0.01:
                pcm.extend(b"\x00\x00" * samples_per_tick)
                continue

            if base_note >= 0:
                note_idx = base_note % 12
                octave = base_note // 12
            else:
                note_idx = tk["note"]
                octave = tk["octave"]

            freq = NOTES_FREQ[note_idx] * (2 ** max(0, min(7, octave)))
            wave_table = self._get_waveform(tk["wave"])
            is_noise = (tk["wave"] >= 12 and not self.memory.waveforms)

            step = (freq * 32.0) / SAMPLE_RATE
            amp = int(12000 * vol_norm * self.master_volume)

            for _ in range(samples_per_tick):
                if is_noise:
                    sample_val = random.uniform(-1.0, 1.0)
                else:
                    sample_val = wave_table[int(phase) & 31]
                    phase = (phase + step) % 32.0

                pcm.extend(struct.pack("<h", int(sample_val * amp)))

        if not pcm:
            return None

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(bytes(pcm))
        buf.seek(0)

        source = pyglet.media.load("sfx.wav", file=buf, streaming=False)
        self._sfx_cache[key] = source
        return source

    def sfx(self, id, note=-1, volume=-1,
            speed=-1, channel=0, loops=0, pan=0):

        channel = int(channel) & 3
        id = int(id)

        if id < 0:
            self.stop(channel)
            return

        source = self._render_sfx_source(id, int(note), int(volume), int(speed))
        if source is None:
            return

        player = self.players[channel]
        player.pause()
        player.next_source()
        player.loop = bool(loops)
        player.queue(source)
        player.play()
        self.playing[channel] = id

    def music(self, track=-1, frame=-1, row=-1,
              loop=True, sustain=False,
              tempo=-1, speed=-1):

        track = int(track)
        if track < 0:
            self.stop_all()
            return

        if track not in self.memory.music_data:
            return

        self._music_state = {
            "track": track,
            "frame": max(0, int(frame)),
            "row": max(0, int(row)),
            "loop": bool(loop),
            "sustain": bool(sustain),
            "tempo": int(tempo) if tempo > 0 else 150,
            "speed": int(speed) if speed > 0 else 6,
            "tick": 0
        }

    def update(self):
        if not self._music_state:
            return

        st = self._music_state
        st["tick"] += 1
        if st["tick"] < st["speed"]:
            return
        st["tick"] = 0

        track_data = self.memory.music_data.get(st["track"])
        if not track_data or st["frame"] * 3 >= len(track_data):
            if st["loop"]:
                st["frame"] = 0
                st["row"] = 0
            else:
                self._music_state = None
            return

        base = st["frame"] * 3
        pat_ids = [
            track_data[base] & 0x3F,
            ((track_data[base] >> 6) | ((track_data[base + 1] & 0x0F) << 2)) & 0x3F,
            ((track_data[base + 1] >> 4) | ((track_data[base + 2] & 0x03) << 4)) & 0x3F,
            (track_data[base + 2] >> 2) & 0x3F
        ]

        for ch, pat_id in enumerate(pat_ids):
            if pat_id == 0:
                continue
            pat_data = self.memory.patterns.get(pat_id - 1)
            if not pat_data or st["row"] * 3 + 2 >= len(pat_data):
                continue

            r_off = st["row"] * 3
            b0, b1, b2 = pat_data[r_off], pat_data[r_off + 1], pat_data[r_off + 2]
            note = b0 & 0x0F
            sfx_id = ((b0 >> 4) & 0x0F) | ((b1 & 0x03) << 4)
            octave = (b2 >> 5) & 0x07

            if note > 0:
                if note == 1:  # Note cut
                    self.stop(ch)
                else:
                    midi_note = octave * 12 + (note - 4)
                    self.sfx(sfx_id, note=midi_note, channel=ch)

        st["row"] += 1
        if st["row"] >= 64:
            st["row"] = 0
            st["frame"] += 1

    def stop(self, channel):
        channel = int(channel) & 3
        player = self.players.get(channel)
        if player:
            player.pause()
            player.next_source()
        self.playing.pop(channel, None)

    def stop_all(self):
        self._music_state = None
        for ch in range(4):
            self.stop(ch)

    def set_volume(self, volume):
        self.master_volume = max(0.0, min(1.0, float(volume)))
        self._sfx_cache.clear()
