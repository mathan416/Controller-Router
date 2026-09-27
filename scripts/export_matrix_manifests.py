#!/usr/bin/env python3
"""Export the products' own sketch artwork into shared Router animation assets."""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

HARNESS = r'''#include <cstdint>
#include <cstdio>
#include <cstring>
struct Matrix {
  uint8_t frame[104] = {};
  void draw(uint8_t* pixels) { std::memcpy(frame, pixels, 104); }
  void clear() { std::memset(frame, 0, 104); }
} matrix;
void emit(int duration) {
  std::printf("%d|", duration);
  for (int i=0; i<104; ++i) std::putchar('0'+matrix.frame[i]);
  std::putchar('\n');
}
'''


def render(cpp: str) -> list[dict]:
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "matrix.cpp"
        executable = Path(directory) / "matrix"
        source.write_text(cpp)
        result = subprocess.run(["c++", "-std=c++11", "-Wall", "-Wextra", str(source), "-o", str(executable)],
                                capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr)
        lines = subprocess.check_output([str(executable)], text=True).splitlines()
    frames = []
    for line in lines:
        duration, pixels = line.split("|", 1)
        if len(pixels) != 104 or any(pixel not in "01234567" for pixel in pixels):
            raise ValueError("Sketch produced an invalid Matrix frame")
        frames.append({"ms": int(duration), "rows": [pixels[y:y+13] for y in range(0, 104, 13)]})
    return frames


def virtualglove(source: Path) -> dict:
    sketch = (source / "sketch/sketch.ino").read_text()
    artwork = sketch[sketch.index("// Original 8-bit artwork"):sketch.index("// Router Bridge endpoint: request")]
    prefix = HARNESS + "uint32_t requestedPairingId=0; int requestedPairingPin=0;\n" + artwork
    animations = {}

    def add(name, body, loop=True):
        animations[name] = {"loop": loop, "frames": render(prefix + "int main() {\n" + body + "\n}\n")}

    add("loading", "for(int i=0;i<5;++i){drawRows(loadingFrames[i]);emit(220);}")
    add("idle", "for(unsigned i=0;i<sizeof(idleFrameDurations)/sizeof(uint16_t);++i){drawIdleFrame(i);emit(idleFrameDurations[i]);}")
    add("idle_dim", "for(unsigned i=0;i<sizeof(idleFrameDurations)/sizeof(uint16_t);++i){drawIdleFrame(i,2);emit(idleFrameDurations[i]);}")
    add("ready", "drawRows(readyFrame);emit(1000);")
    add("tracking", "for(int i=0;i<2;++i){drawRows(trackingFrames[i]);emit(360);}")
    add("error", "drawRows(errorFrame);emit(420);matrix.clear();emit(420);")
    add("learning", "for(int i=0;i<8;++i){drawModeLetter(glyphL,i);emit(160);}")
    add("tuning", "for(int i=0;i<8;++i){drawModeLetter(glyphT,i);emit(160);}")
    for profile in range(1, 26):
        add(f"profile_{profile}", f"drawProfile({profile},false);emit(360);drawProfile({profile},true);emit(360);")
    for connection in range(8):
        pixels = ["0"] * 104
        pixels[7 * 13] = "1"
        for bit, x in ((1, 2), (2, 4), (4, 6)):
            if connection & bit:
                pixels[7 * 13 + x] = "1"
        text = "".join(pixels)
        animations[f"idle_off_{connection}"] = {"loop": True, "frames": [{"ms": 1000,
            "rows": [text[y:y+13] for y in range(0, 104, 13)]}]}
    return {"schema": 1, "app": "virtualglove", "animations": animations}


def rob_vision(source: Path) -> dict:
    sketch = (source / "sketch/sketch.ino").read_text()
    artwork = sketch[sketch.index("const char* const loading"):sketch.index("void refreshMatrix()")]
    prefix = HARNESS + "enum RobDisplay { LOADING=0, IDLE=1, GYROMITE=2, STACK_UP=3, TEST=4, TEST_FLASH=5, PAIRING=6, FAULT=7, OFF=8 };\n" + artwork
    animations = {}

    def add(name, body, loop=True):
        animations[name] = {"loop": loop, "frames": render(prefix + "int main() {\n" + body + "\n}\n")}

    add("loading", "for(int i=0;i<3;++i){hourglass(i);emit(240);}")
    for mode, name in ((IDLE := 1, "idle"), (2, "gyromite"), (3, "stack_up")):
        add(name, f"for(int i=0;i<40;++i){{uint8_t pixels[104]={{}};eyes(pixels,i,{mode},0);matrix.draw(pixels);emit(180);}}")
    for hint, name in enumerate(("left", "right", "up", "down", "open", "close"), 1):
        add("hint_" + name, f"uint8_t pixels[104]={{}};eyes(pixels,0,GYROMITE,{hint});matrix.draw(pixels);emit(700);", False)
    add("test", "uint8_t pixels[104]={};glyph(pixels,T,4,4);matrix.draw(pixels);emit(380);")
    add("test_flash", "for(int i=0;i<4;++i){uint8_t pixels[104]={};glyph(pixels,T,4,i<2?7:4);matrix.draw(pixels);emit(380);}")
    add("pairing", "for(int i=0;i<4;++i){uint8_t pixels[104]={};glyph(pixels,P,4,i<2?7:4);matrix.draw(pixels);emit(380);}")
    add("fault", "uint8_t pixels[104]={};glyph(pixels,X,4,7);matrix.draw(pixels);emit(550);matrix.clear();emit(550);")
    return {"schema": 1, "app": "rob_vision", "animations": animations}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--virtualglove", type=Path, required=True)
    parser.add_argument("--rob-vision", type=Path, required=True)
    parser.add_argument("--virtualglove-output", type=Path, required=True)
    options = parser.parse_args()
    outputs = ((options.virtualglove_output, virtualglove(options.virtualglove)),
               (options.rob_vision / "matrix/manifest.json", rob_vision(options.rob_vision)))
    for target, document in outputs:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document, separators=(",", ":")) + "\n")
        print(target, len(document["animations"]), "animations")


if __name__ == "__main__":
    main()
