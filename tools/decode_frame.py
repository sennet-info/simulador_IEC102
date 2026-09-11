from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.protocol.iec102.decoder import FrameDecoder
from src.protocol.iec102.frame import format_hex
from src.protocol.iec102.parser import FrameParseError, FrameParser


def normalize_hex(value: str) -> bytes:
    cleaned = value.replace("0x", "").replace(",", " ").strip()
    cleaned = " ".join(cleaned.split())
    return bytes(int(part, 16) for part in cleaned.split())


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print('Usage: python tools/decode_frame.py "68 ..."')
        return 1
    raw = normalize_hex(argv[1])
    parser = FrameParser()
    decoder = FrameDecoder()
    try:
        parsed = parser.parse(raw)
    except FrameParseError as exc:
        print(f"Raw frame: {format_hex(raw)}")
        print(f"Checksum OK/FAIL: FAIL ({exc})")
        return 2
    print(f"Raw frame: {format_hex(raw)}")
    print(f"Frame type: {parsed.frame.kind.value}")
    print(f"Link address: {parsed.frame.address}")
    print(f"Function: {parsed.frame.function_code}")
    if parsed.asdu:
        decoded = decoder.decode_frame(parsed)
        print(json.dumps(decoded, indent=2))
    print("Checksum OK/FAIL: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
