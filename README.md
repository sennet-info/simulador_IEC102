# IEC 60870-5-102 Meter Simulator

Aplicación Python/PySide6 para Windows 10 orientada a laboratorio, pensada para simular un contador eléctrico IEC 60870-5-102 mediante TCP o puerto serie.

## Requisitos

- Windows 10 x64
- Python 3.9.9
- Entorno virtual `.venv`
- Compatibilidad mínima del código: Python 3.9
- Dependencias instaladas desde `requirements.txt`

## Estado actual

Primera versión funcional con:

- GUI nativa con PySide6
- selección TCP server o Serial COM
- valores configurables de tensión, intensidad, potencia y energía
- persistencia de configuración en `config.json`
- monitor de protocolo con HEX RX/TX y resumen decodificado
- logs guardables en `logs/iec102_YYYYMMDD_HHMMSS.log`
- arquitectura modular `transport/`, `protocol/iec102/`, `meter/`, `ui/`
- utilidad CLI `python tools/decode_frame.py "68 ..."`

## Arquitectura

```text
src/
├── main.py
├── app_controller.py
├── protocol/iec102/
├── transport/
├── meter/
├── ui/
└── logging/
```

## Instalación en Windows CMD

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Arranque

```bat
python src\main.py
```

## Uso básico

1. Selecciona modo **Serial** o **TCP Server**.
2. Configura puerto COM o `IP:port`.
3. Ajusta direcciones IEC-102 y valores eléctricos/energías.
4. Pulsa **Apply values**.
5. Pulsa **START SERVER / CONNECT**.
6. Observa RX/TX en **PROTOCOL MONITOR**.

## Comunicación COM

- detección automática de COM disponibles
- parámetros configurables: baudrate, data bits, paridad, stop bits y timeout
- implementación basada en `pyserial`

## Comunicación TCP

- servidor TCP local configurable
- un cliente simultáneo en esta versión
- desconexión manual disponible desde la GUI

## IEC-102 implementado

Subconjunto conservador documentado en [`docs/IEC102_IMPLEMENTATION_STATUS.md`](docs/IEC102_IMPLEMENTATION_STATUS.md):

- FT1.2 fixed/variable frames
- reset y estado de enlace
- cola de respuesta para polling clase 2
- lectura de identificación genérica, hora, energías absolutas e instantáneos

## No implementado todavía

- cobertura completa del estándar IEC-102
- todas las tarifas/eventos/históricos
- fault injection avanzado
- importación/comparación de capturas reales
- validación contra fabricantes concretos

## Generar EXE para Windows

```bat
build_windows.bat
```

Genera `dist/IEC102MeterSimulator.exe` con PyInstaller.

El script usa explícitamente `.venv\Scripts\python.exe`, muestra la versión de ese intérprete al inicio y construye el ejecutable con ese mismo Python del entorno virtual.
Para mantener compatibilidad con Python 3.9.9, el propio script limita la actualización de `pip` a una versión compatible antes de instalar dependencias y ejecutar PyInstaller.

## Logs

Cada línea de log incluye:

- timestamp
- dirección RX/TX
- transporte
- HEX bruto
- resumen decodificado

## Diagrama

```text
                +----------------------+
                |    Windows 10 PC     |
                |                      |
                | IEC102 Meter         |
                | Simulator            |
                +----------+-----------+
                           |
                +----------+-----------+
                |                      |
             SERIAL                   TCP
             COMx               IP:port
                |                      |
                +----------+-----------+
                           |
                           v
                +----------------------+
                | Datalogger /         |
                | Data Logger / BMS    |
                +----------------------+
```
