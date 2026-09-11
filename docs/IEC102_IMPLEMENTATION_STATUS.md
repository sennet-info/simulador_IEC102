# IEC102 implementation status

## Verified public-implementation subset used here

This simulator implements a conservative subset based on publicly inspectable implementations and tests from IEC 60870-5-102 ecosystems:

- FT1.2 fixed and variable frames (`10 ... 16` and `68 L L 68 ... CS 16`)
- checksum by modulo-256 byte sum
- 2-byte link address, 2-byte measurement-point address, 1-byte record address
- request/response queueing model where user-data requests are ACKed and later returned on class-2 polling
- ASDU 100 -> 71 (manufacturer/equipment, laboratory subset)
- ASDU 103 -> 72 (current meter time)
- ASDU 122 -> 8 (absolute integrated totals)
- ASDU 162 -> 163 (instantaneous values subset)

## Implemented in this first version

- Link reset / link status / class-2 polling
- TCP server and serial transport abstraction
- Configurable electrical magnitudes and energies from the GUI
- Persistent configuration in `config.json`
- Protocol monitor with raw hex + decoded summary
- CLI decoder: `python tools/decode_frame.py "68 ..."`

## TODO IEC102 STANDARD VERIFICATION

The following areas are intentionally marked pending because the official standard text was not available in this environment and they should not be invented:

- byte-exact manufacturer/equipment payload semantics for ASDU 71 beyond the laboratory generic profile
- complete authentication/session workflow coverage for all vendor variants
- full tariff-information ASDUs
- full billing-period, historical blocks, and event logs
- exhaustive cause-of-transmission matrix for every command family
- comparison/import tooling for captured real-meter traces
- fault-injection IEC-aware behavior beyond transport-level extension points

## Current limitations

- single active TCP client at a time
- serial transport requires `pyserial` and an available COM port on Windows
- the manufacturer-identification payload is a generic lab profile response and may need refinement against a target datalogger
- no automatic EXE is shipped from this repository; `build_windows.bat` builds it locally with PyInstaller
