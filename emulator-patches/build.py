#!/usr/bin/env python3
"""Build pinned emulator source in a new isolated directory; never install it."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
PROFILES = {
    'arcem': ('SDL/DispKbd.c', 'cbb3e6e30a17706b2ff4af9aa2b6ae2bcdfc985df7f7f283e71a2044209aa180'),
    'gsplus': ('gsplus/src/sdl_driver.c', '452a005a80d527840deee3ec1ef1127e203aa3e4df8c223749f35a5c2ba6846b'),
}


def build(profile, source, destination, jobs=2, cmake_args=()):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists():
        raise ValueError('Build destination already exists')
    if destination == source or source in destination.parents:
        raise ValueError('Build destination must be outside the source tree')
    filename, expected = PROFILES[profile]
    if hashlib.sha256((source / filename).read_bytes()).hexdigest() != expected:
        raise ValueError('Source does not match the supported upstream revision')
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns('.git', 'build', '__pycache__'))
    subprocess.run(['patch', '-p1', '--batch', '--forward', '-i', str(ROOT / profile / 'router-input.patch')], cwd=destination, check=True)
    if profile == 'arcem':
        subprocess.run(['make', 'SYSTEM=SDL2', '-j' + str(jobs)], cwd=destination, check=True)
        binary = destination / 'arcem'
    else:
        subprocess.run(['cmake', '-S', str(destination / 'gsplus/src'), '-B', str(destination / 'router-build'), '-DCMAKE_BUILD_TYPE=Release'] + list(cmake_args), check=True)
        subprocess.run(['cmake', '--build', str(destination / 'router-build'), '--target', 'gsplus-sdl', '-j', str(jobs)], check=True)
        binary = destination / 'router-build/gsplus'
    if not binary.is_file():
        raise RuntimeError('Build did not produce the expected executable')
    return binary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', choices=sorted(PROFILES))
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--cmake-arg', action='append', default=[], help='Additional CMake option for GSplus')
    args = parser.parse_args()
    if not 1 <= args.jobs <= 64:
        parser.error('--jobs must be between 1 and 64')
    print(build(args.profile, args.source, args.destination, args.jobs, args.cmake_arg))


if __name__ == '__main__':
    main()
