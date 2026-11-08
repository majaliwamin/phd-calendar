"""Offline Asterisk AMI originate test with a fake AMI socket and fake eSpeak binary."""
import os, tempfile, shutil, socket, threading, wave
from unittest.mock import patch
os.environ["CAL_DATA"] = tempfile.mkdtemp(prefix="mnh-asterisk-test-")
import db, comms

db.init()
sound_dir = tempfile.mkdtemp(prefix="mnh-asterisk-sounds-")
server = socket.socket()
server.settimeout(5)
server.bind(("127.0.0.1", 0))
server.listen(1)
port = server.getsockname()[1]
frames = []

def read_frame(stream):
    lines = []
    while True:
        line = stream.readline()
        if not line: return lines
        if line in (b"\r\n", b"\n"): return lines
        lines.append(line.decode("utf-8", "replace").strip())

def fake_ami():
    conn, _ = server.accept()
    conn.sendall(b"Asterisk Call Manager/5.0.0\r\n")
    stream = conn.makefile("rwb", buffering=0)
    try:
        while True:
            frame = read_frame(stream)
            if not frame: break
            frames.append(frame)
            if any(x.startswith("Action: Login") for x in frame):
                stream.write(b"Response: Success\r\nMessage: Authentication accepted\r\n\r\n")
            elif any(x.startswith("Action: Originate") for x in frame):
                stream.write(b"Response: Success\r\nMessage: Originate successfully queued\r\n\r\n")
            elif any(x.startswith("Action: Logoff") for x in frame):
                break
    finally:
        conn.close()
        server.close()

thread = threading.Thread(target=fake_ami, daemon=True)
thread.start()
comms.save_secrets({"ami_host": "127.0.0.1", "ami_port": str(port), "ami_user": "test", "ami_secret": "test-secret"})
with db.conn() as c:
    comms.init(c)
    comms.set_cfg(c, {"asterisk_sound_dir": sound_dir, "asterisk_channel_prefix": "PJSIP/",
                      "asterisk_channel_suffix": "@test-trunk", "asterisk_context": "mnh-announcement"})
    def fake_tts_run(args, **kwargs):
        wav_path = args[args.index("-w") + 1]
        with wave.open(wav_path, "wb") as audio:
            audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(8000)
            audio.writeframes(b"\x00\x00" * 80)
    with patch.object(comms.shutil, "which", return_value="fake-espeak"), patch.object(comms.subprocess, "run", side_effect=fake_tts_run):
        call_id = comms.PROV.call(c, {"phone": "+265991234567"}, "Academic session reminder", 1)
thread.join(timeout=5)
assert call_id.startswith("mnh-")
assert any(any(x == "Channel: PJSIP/265991234567@test-trunk" for x in frame) for frame in frames)
assert any(any(x == "Context: mnh-announcement" for x in frame) for frame in frames)
prompt_files = [name for name in os.listdir(sound_dir) if name.endswith(".wav") and not name.endswith("_source.wav")]
assert prompt_files
with wave.open(os.path.join(sound_dir, prompt_files[0]), "rb") as prompt:
    assert prompt.getframerate() == 8000 and prompt.getnchannels() == 1 and prompt.getsampwidth() == 2
print("Asterisk mock test passed: 8 kHz mono prompt generated, AMI login accepted, and originate action sent.")
