import sys

import librosa
import numpy as np

path = sys.argv[1]
y, sr = librosa.load(path, sr=22050)
yt, _ = librosa.effects.trim(y, top_db=25)
print("duration_sec", round(len(y) / sr, 2), "trimmed", round(len(yt) / sr, 2))
if len(yt) < sr * 0.5:
    print("too short")
    sys.exit(1)
f0, voiced, _ = librosa.pyin(
    yt, fmin=librosa.note_to_hz("C3"), fmax=librosa.note_to_hz("C6"), sr=sr
)
f0v = f0[voiced]
print("voiced_frames", len(f0v))
if len(f0v) < 5:
    print("not enough pitch")
    sys.exit(1)
try:
    tempo = float(librosa.feature.tempo(y=yt, sr=sr)[0])
except AttributeError:
    tempo = float(librosa.beat.tempo(y=yt, sr=sr)[0])
print("tempo_bpm", round(tempo, 1))
mids = np.round(librosa.hz_to_midi(f0v)).astype(int)
seq = []
last = None
for m in mids:
    n = librosa.midi_to_note(m)
    if n != last:
        seq.append(n)
        last = n
print("melody_notes", " ".join(seq))
