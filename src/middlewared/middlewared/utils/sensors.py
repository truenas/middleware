#!/usr/bin/env python3
"""
Python ctypes wrapper for libsensors (lm-sensors) library on Linux.
Provides access to hardware monitoring sensors (temperature, voltage, fan speed, etc.)
"""

from __future__ import annotations

import ctypes
import ctypes.util
import enum
from types import TracebackType


class SensorsFeatureType(enum.IntEnum):
    """Sensor feature types from sensors.h"""

    SENSORS_FEATURE_IN = 0x00
    SENSORS_FEATURE_FAN = 0x01
    SENSORS_FEATURE_TEMP = 0x02
    SENSORS_FEATURE_POWER = 0x03
    SENSORS_FEATURE_ENERGY = 0x04
    SENSORS_FEATURE_CURR = 0x05
    SENSORS_FEATURE_HUMIDITY = 0x06
    SENSORS_FEATURE_MAX_MAIN = 0x7F
    SENSORS_FEATURE_VID = 0x10
    SENSORS_FEATURE_INTRUSION = 0x11
    SENSORS_FEATURE_MAX_OTHER = 0x12
    SENSORS_FEATURE_BEEP_ENABLE = 0x18
    SENSORS_FEATURE_MAX = 0x1F
    SENSORS_FEATURE_UNKNOWN = 0x7F


class SensorsSubfeatureType(enum.IntEnum):
    """Sensor subfeature types from sensors.h"""

    SENSORS_SUBFEATURE_IN_INPUT = 0
    SENSORS_SUBFEATURE_IN_MIN = 1
    SENSORS_SUBFEATURE_IN_MAX = 2
    SENSORS_SUBFEATURE_IN_LCRIT = 3
    SENSORS_SUBFEATURE_IN_CRIT = 4
    SENSORS_SUBFEATURE_IN_AVERAGE = 5
    SENSORS_SUBFEATURE_IN_LOWEST = 6
    SENSORS_SUBFEATURE_IN_HIGHEST = 7
    SENSORS_SUBFEATURE_IN_ALARM = 0x80
    SENSORS_SUBFEATURE_IN_MIN_ALARM = 0x81
    SENSORS_SUBFEATURE_IN_MAX_ALARM = 0x82
    SENSORS_SUBFEATURE_IN_BEEP = 0x83
    SENSORS_SUBFEATURE_IN_LCRIT_ALARM = 0x84
    SENSORS_SUBFEATURE_IN_CRIT_ALARM = 0x85

    SENSORS_SUBFEATURE_FAN_INPUT = 0x100
    SENSORS_SUBFEATURE_FAN_MIN = 0x101
    SENSORS_SUBFEATURE_FAN_MAX = 0x102
    SENSORS_SUBFEATURE_FAN_ALARM = 0x180
    SENSORS_SUBFEATURE_FAN_FAULT = 0x181
    SENSORS_SUBFEATURE_FAN_DIV = 0x182
    SENSORS_SUBFEATURE_FAN_BEEP = 0x183
    SENSORS_SUBFEATURE_FAN_PULSES = 0x184
    SENSORS_SUBFEATURE_FAN_MIN_ALARM = 0x185
    SENSORS_SUBFEATURE_FAN_MAX_ALARM = 0x186

    SENSORS_SUBFEATURE_TEMP_INPUT = 0x200
    SENSORS_SUBFEATURE_TEMP_MAX = 0x201
    SENSORS_SUBFEATURE_TEMP_MAX_HYST = 0x202
    SENSORS_SUBFEATURE_TEMP_MIN = 0x203
    SENSORS_SUBFEATURE_TEMP_CRIT = 0x204
    SENSORS_SUBFEATURE_TEMP_CRIT_HYST = 0x205
    SENSORS_SUBFEATURE_TEMP_LCRIT = 0x206
    SENSORS_SUBFEATURE_TEMP_EMERGENCY = 0x207
    SENSORS_SUBFEATURE_TEMP_EMERGENCY_HYST = 0x208
    SENSORS_SUBFEATURE_TEMP_LOWEST = 0x209
    SENSORS_SUBFEATURE_TEMP_HIGHEST = 0x20A
    SENSORS_SUBFEATURE_TEMP_MIN_HYST = 0x20B
    SENSORS_SUBFEATURE_TEMP_LCRIT_HYST = 0x20C
    SENSORS_SUBFEATURE_TEMP_ALARM = 0x280
    SENSORS_SUBFEATURE_TEMP_MAX_ALARM = 0x281
    SENSORS_SUBFEATURE_TEMP_MIN_ALARM = 0x282
    SENSORS_SUBFEATURE_TEMP_CRIT_ALARM = 0x283
    SENSORS_SUBFEATURE_TEMP_FAULT = 0x284
    SENSORS_SUBFEATURE_TEMP_TYPE = 0x285
    SENSORS_SUBFEATURE_TEMP_OFFSET = 0x286
    SENSORS_SUBFEATURE_TEMP_BEEP = 0x287
    SENSORS_SUBFEATURE_TEMP_EMERGENCY_ALARM = 0x288
    SENSORS_SUBFEATURE_TEMP_LCRIT_ALARM = 0x289


# C structure definitions
class SensorsBusId(ctypes.Structure):
    """sensors_bus_id structure"""

    _fields_ = [
        ("type", ctypes.c_short),
        ("nr", ctypes.c_short),
    ]


class SensorsChipName(ctypes.Structure):
    """sensors_chip_name structure"""

    _fields_ = [
        ("prefix", ctypes.c_char_p),
        ("bus", SensorsBusId),
        ("addr", ctypes.c_int),
        ("path", ctypes.c_char_p),
    ]


class SensorsFeature(ctypes.Structure):
    """sensors_feature structure"""

    _fields_ = [
        ("name", ctypes.c_char_p),
        ("number", ctypes.c_int),
        ("type", ctypes.c_int),  # SensorsFeatureType
        ("first_subfeature", ctypes.c_int),
        ("padding1", ctypes.c_int),
    ]


class SensorsSubfeature(ctypes.Structure):
    """sensors_subfeature structure"""

    _fields_ = [
        ("name", ctypes.c_char_p),
        ("number", ctypes.c_int),
        ("type", ctypes.c_int),  # SensorsSubfeatureType
        ("mapping", ctypes.c_int),
        ("flags", ctypes.c_uint),
    ]


class SensorsWrapper:
    """
    Python wrapper for libsensors library.

    Usage:
        # Method 1: Manual init/cleanup
        sensors = SensorsWrapper()
        sensors.init()
        readings = sensors.get_all_readings()
        sensors.cleanup()

        # Method 2: Context manager (recommended for resource management)
        with SensorsWrapper() as sensors:
            readings = sensors.get_all_readings()

        # Method 3: Long-running process with periodic refresh
        sensors = SensorsWrapper()
        sensors.init()
        while True:
            readings = sensors.get_all_readings()
            time.sleep(60)
            # Optionally refresh chip detection
            sensors.refresh()
        sensors.cleanup()
    """

    def __init__(self, config_file: str | None = None) -> None:
        """
        Initialize the sensors wrapper.

        Args:
            config_file: Optional path to sensors configuration file
        """
        self.config_file: str | None = config_file
        self.lib: ctypes.CDLL | None = None
        self._initialized: bool = False
        self._load_library()
        self._setup_functions()

    def __enter__(self) -> SensorsWrapper:
        """Context manager entry"""
        self.init()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit - ensures cleanup"""
        self.cleanup()

    def _load_library(self) -> None:
        """Load the libsensors library"""
        # Try to find libsensors
        lib_path: str | None = ctypes.util.find_library("sensors")
        if not lib_path:
            # Try common paths
            for path in [
                "/usr/lib/libsensors.so",
                "/usr/lib/x86_64-linux-gnu/libsensors.so",
            ]:
                try:
                    self.lib = ctypes.CDLL(path)
                    break
                except OSError:
                    continue
            if not self.lib:
                raise OSError("Could not find libsensors. Install lm-sensors package.")
        else:
            self.lib = ctypes.CDLL(lib_path)

    def _setup_functions(self) -> None:
        """Setup function signatures for libsensors functions"""
        assert self.lib is not None
        # sensors_init
        self.lib.sensors_init.argtypes = [ctypes.c_void_p]
        self.lib.sensors_init.restype = ctypes.c_int

        # sensors_cleanup
        self.lib.sensors_cleanup.argtypes = []
        self.lib.sensors_cleanup.restype = None

        # sensors_get_detected_chips
        self.lib.sensors_get_detected_chips.argtypes = [
            ctypes.POINTER(SensorsChipName),
            ctypes.POINTER(ctypes.c_int),
        ]
        self.lib.sensors_get_detected_chips.restype = ctypes.POINTER(SensorsChipName)

        # sensors_get_features
        self.lib.sensors_get_features.argtypes = [
            ctypes.POINTER(SensorsChipName),
            ctypes.POINTER(ctypes.c_int),
        ]
        self.lib.sensors_get_features.restype = ctypes.POINTER(SensorsFeature)

        # sensors_get_all_subfeatures
        self.lib.sensors_get_all_subfeatures.argtypes = [
            ctypes.POINTER(SensorsChipName),
            ctypes.POINTER(SensorsFeature),
            ctypes.POINTER(ctypes.c_int),
        ]
        self.lib.sensors_get_all_subfeatures.restype = ctypes.POINTER(SensorsSubfeature)

        # sensors_get_value
        self.lib.sensors_get_value.argtypes = [
            ctypes.POINTER(SensorsChipName),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_double),
        ]
        self.lib.sensors_get_value.restype = ctypes.c_int

        # sensors_get_label
        self.lib.sensors_get_label.argtypes = [
            ctypes.POINTER(SensorsChipName),
            ctypes.POINTER(SensorsFeature),
        ]
        self.lib.sensors_get_label.restype = ctypes.c_char_p

        # sensors_snprintf_chip_name
        self.lib.sensors_snprintf_chip_name.argtypes = [
            ctypes.c_char_p,
            ctypes.c_size_t,
            ctypes.POINTER(SensorsChipName),
        ]
        self.lib.sensors_snprintf_chip_name.restype = ctypes.c_int

    def init(self) -> None:
        """
        Initialize the sensors library.
        Must be called before using other methods.
        """
        if self._initialized:
            return  # Already initialized

        assert self.lib is not None
        config: ctypes.c_char_p | None = None
        if self.config_file:
            config = ctypes.c_char_p(self.config_file.encode("utf-8"))

        result: int = self.lib.sensors_init(config)
        if result != 0:
            raise RuntimeError(f"Failed to initialize sensors library: {result}")
        self._initialized = True

    def cleanup(self) -> None:
        """Clean up the sensors library resources"""
        if not self._initialized:
            return  # Not initialized, nothing to cleanup

        assert self.lib is not None
        self.lib.sensors_cleanup()
        self._initialized = False

    def refresh(self) -> None:
        """
        Refresh sensor detection. Useful for long-running processes
        to detect newly added/removed sensors.
        """
        if self._initialized:
            self.cleanup()
        self.init()

    def get_detected_chips(self) -> list[SensorsChipName]:
        """
        Get list of all detected sensor chips.

        Returns:
            List of SensorsChipName structures
        """
        assert self.lib is not None
        chips: list[SensorsChipName] = []
        nr = ctypes.c_int(0)

        while True:
            chip = self.lib.sensors_get_detected_chips(None, ctypes.byref(nr))
            if not chip:
                break
            chips.append(chip.contents)

        return chips

    def get_chip_name(self, chip: SensorsChipName) -> str:
        """
        Get human-readable name for a chip.

        Args:
            chip: SensorsChipName structure

        Returns:
            Chip name as string
        """
        assert self.lib is not None
        buf = ctypes.create_string_buffer(200)
        self.lib.sensors_snprintf_chip_name(buf, 200, ctypes.byref(chip))
        return buf.value.decode("utf-8")

    def get_features(self, chip: SensorsChipName) -> list[SensorsFeature]:
        """
        Get all features for a chip.

        Args:
            chip: SensorsChipName structure

        Returns:
            List of SensorsFeature structures
        """
        assert self.lib is not None
        features: list[SensorsFeature] = []
        nr = ctypes.c_int(0)

        while True:
            feature = self.lib.sensors_get_features(
                ctypes.byref(chip), ctypes.byref(nr)
            )
            if not feature:
                break
            features.append(feature.contents)

        return features

    def get_subfeatures(
        self, chip: SensorsChipName, feature: SensorsFeature
    ) -> list[SensorsSubfeature]:
        """
        Get all subfeatures for a feature.

        Args:
            chip: SensorsChipName structure
            feature: SensorsFeature structure

        Returns:
            List of SensorsSubfeature structures
        """
        assert self.lib is not None
        subfeatures: list[SensorsSubfeature] = []
        nr = ctypes.c_int(0)

        while True:
            subfeature = self.lib.sensors_get_all_subfeatures(
                ctypes.byref(chip), ctypes.byref(feature), ctypes.byref(nr)
            )
            if not subfeature:
                break
            subfeatures.append(subfeature.contents)

        return subfeatures

    def get_value(self, chip: SensorsChipName, subfeature_nr: int) -> float:
        """
        Get sensor value for a subfeature.

        Args:
            chip: SensorsChipName structure
            subfeature_nr: Subfeature number

        Returns:
            Sensor value as float
        """
        assert self.lib is not None
        value = ctypes.c_double()
        result: int = self.lib.sensors_get_value(
            ctypes.byref(chip), subfeature_nr, ctypes.byref(value)
        )
        if result != 0:
            raise RuntimeError(f"Failed to get sensor value: {result}")
        return value.value

    def get_label(self, chip: SensorsChipName, feature: SensorsFeature) -> str:
        """
        Get human-readable label for a feature.

        Args:
            chip: SensorsChipName structure
            feature: SensorsFeature structure

        Returns:
            Feature label as string
        """
        assert self.lib is not None
        label = self.lib.sensors_get_label(ctypes.byref(chip), ctypes.byref(feature))
        if label:
            result: str = label.decode("utf-8")
            # Note: libsensors documentation says to free the label, but this can cause
            # crashes depending on the libsensors version and build configuration.
            # In practice, the memory leak is minimal for most use cases.
            # If you need to free memory in a long-running process, you can try:
            # 1. Use sensors.cleanup() and sensors.init() periodically to reset
            # 2. Check your libsensors version compatibility
            return result
        return ""

    def get_cpu_temperatures(self) -> dict[str, dict[str, float]]:
        """
        Get only CPU temperature readings in a nested format.

        Note: AMD EPYC processors typically only expose Tctl (overall CPU temperature)
        through k10temp, not per-core temperatures. Intel processors with coretemp
        usually provide per-core temperatures. The availability of temperature sensors
        depends on the CPU model and kernel driver support.

        Returns:
            Dictionary with chip names as keys and temperature readings as nested dicts
            Example: {'coretemp-isa-0000': {'Core 0': 48.0}, 'k10temp-pci-00c3': {'Tctl': 67.0}}
        """
        cpu_temps: dict[str, dict[str, float]] = {}

        # CPU sensor chip patterns - various vendors
        cpu_chip_patterns = [
            "coretemp",  # Intel
            "k10temp",  # AMD Family 10h+
            "k8temp",  # AMD Family 8
            "via_cputemp",  # VIA
            "cpu_thermal",  # ARM/embedded
        ]

        for chip in self.get_detected_chips():
            chip_name = self.get_chip_name(chip)

            # Check if this is a CPU sensor chip
            if any(pattern in chip_name.lower() for pattern in cpu_chip_patterns):
                for feature in self.get_features(chip):
                    if feature.type == SensorsFeatureType.SENSORS_FEATURE_TEMP:
                        label = self.get_label(chip, feature)

                        # Get the input temperature value
                        for subfeature in self.get_subfeatures(chip, feature):
                            if subfeature.flags & 0x01:  # SENSORS_MODE_R
                                subfeature_name = (
                                    subfeature.name.decode("utf-8")
                                    if subfeature.name
                                    else ""
                                )
                                if "input" in subfeature_name:
                                    try:
                                        value = self.get_value(chip, subfeature.number)
                                        if chip_name not in cpu_temps:
                                            cpu_temps[chip_name] = {}
                                        cpu_temps[chip_name][label] = value
                                    except RuntimeError:
                                        pass
                                    break

        return cpu_temps
