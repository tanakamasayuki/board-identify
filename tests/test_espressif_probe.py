from board_identify.probes.espressif import EspressifProbe


def test_extract_esp32_s3() -> None:
    output = """Detecting chip type... ESP32-S3\nChip is ESP32-S3 (revision v0.2)\nMAC: 7c:df:a1:12:34:56\n"""
    assert EspressifProbe.extract_chip(output) == "ESP32-S3"
    assert EspressifProbe.extract_mac(output) == "7c:df:a1:12:34:56"
