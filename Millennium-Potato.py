"""
Millennium Potato
Say "potato" 1500 times and the box unlocks.

Secret commands:
    "gizmo unlock" - unlock immediately
    "gizmo reset"  - set the count back to 0 and re-lock

Usage:
    python Millennium-Potato.py                 # listen on the default mic
    python Millennium-Potato.py --list-devices  # show available mics
    python Millennium-Potato.py --device 1      # use a specific mic
    python Millennium-Potato.py --type          # type words instead of speaking (testing)
"""

import argparse
import json
import os
import queue
import sys

TARGET = 1500
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "potato_state.json")
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model")

# Restricting the vocabulary means Vosk can only ever hear these phrases.
# Anything else ("tomato", talking, TV) falls into [unk] and is ignored.
GRAMMAR = ["potato", "gizmo unlock", "gizmo reset", "[unk]"]


# ---------- state ----------

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"count": 0, "unlocked": False}


def save_state(state):
    # Write to a temp file then swap it in, so a power cut mid-save
    # can't leave a half-written (corrupt) file behind.
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, STATE_FILE)


# ---------- hardware (placeholders for now) ----------

def unlock_box():
    # TODO: drive the S51 servos here once the mechanism is designed.
    print("\n*** UNLOCKING THE BOX ***\n")


def lock_box():
    # TODO: drive the S51 servos back to the locked position.
    print("\n*** LOCKING THE BOX ***\n")


def show_count(state):
    # TODO: send this to the display once it arrives.
    if state["unlocked"]:
        print(f"Potatoes: {state['count']} / {TARGET}  (UNLOCKED)")
    else:
        print(f"Potatoes: {state['count']} / {TARGET}")


# ---------- core logic ----------

def handle_text(text, state):
    """Process one recognized phrase like 'potato potato gizmo reset'."""
    text = text.replace("[unk]", "").strip()
    if not text:
        return

    if "gizmo reset" in text:
        state["count"] = 0
        state["unlocked"] = False
        save_state(state)
        lock_box()
        show_count(state)
        return

    if "gizmo unlock" in text:
        state["unlocked"] = True
        save_state(state)
        unlock_box()
        show_count(state)
        return

    if state["unlocked"]:
        return

    heard = text.split().count("potato")
    if heard == 0:
        return

    state["count"] = min(state["count"] + heard, TARGET)
    if state["count"] >= TARGET:
        state["unlocked"] = True
        save_state(state)
        show_count(state)
        unlock_box()
    else:
        save_state(state)
        show_count(state)


# ---------- input modes ----------

def run_typed(state):
    print("Type mode: enter words as if you said them (Ctrl+C to quit).")
    while True:
        handle_text(input("> ").lower(), state)


def run_mic(state, device):
    import sounddevice as sd
    from vosk import KaldiRecognizer, Model, SetLogLevel

    SetLogLevel(-1)  # keep Vosk's internal logging quiet

    if not os.path.isdir(MODEL_DIR):
        sys.exit(f"Vosk model not found at {MODEL_DIR}. Download one and unzip it there.")

    samplerate = int(sd.query_devices(device, "input")["default_samplerate"])
    model = Model(MODEL_DIR)
    rec = KaldiRecognizer(model, samplerate, json.dumps(GRAMMAR))

    audio = queue.Queue()

    def callback(indata, frames, time, status):
        audio.put(bytes(indata))

    with sd.RawInputStream(samplerate=samplerate, blocksize=8000, device=device,
                           dtype="int16", channels=1, callback=callback):
        print(f"Listening at {samplerate} Hz... say 'potato'! (Ctrl+C to quit)")
        while True:
            # Only count finished phrases; partial results get revised
            # as Vosk hears more, so counting them would double-count.
            if rec.AcceptWaveform(audio.get()):
                handle_text(json.loads(rec.Result())["text"], state)


def main():
    parser = argparse.ArgumentParser(description="Millennium Potato")
    parser.add_argument("--list-devices", action="store_true", help="list audio devices and exit")
    parser.add_argument("--device", type=int, default=None, help="input device number")
    parser.add_argument("--type", action="store_true", help="type words instead of using the mic")
    args = parser.parse_args()

    if args.list_devices:
        import sounddevice as sd
        print(sd.query_devices())
        return

    state = load_state()
    show_count(state)

    try:
        if args.type:
            run_typed(state)
        else:
            run_mic(state, args.device)
    except (KeyboardInterrupt, EOFError):
        print("\nBye. Progress is saved.")


if __name__ == "__main__":
    main()
