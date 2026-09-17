---
title: 'Breadboard Hardware: I2C Environmental Sensor Shield'
schematic_cas: urn:breadboard:cas:018f62f8-9a3b-7d23-bf72-5b9c03bfba43
pcb_revision: Rev C
gpio_pinout_map:
  GPIO21: SDA
  GPIO22: SCL
operating_voltage_vdc: 3.3
$pkm:
  id: urn:uuid:01a0adb6-d2f6-7e7a-9ab9-ede8214f1a91
  realm: breadboard
  created_at: '2026-09-16T12:00:00Z'
  updated_at: '2026-09-16T12:00:00Z'
  relations:
    purchasedViaTx: urn:qtm:tx:0191fa30-1046-7000-8000-000000000046
---

# Breadboard Hardware: I2C Environmental Sensor Shield

Electronics engineering dossier indexing schematic CAS, PCB revision, and I2C pinout.

## Electrical Specifications
Revision: `Rev C` | Voltage: `3.3 VDC` | Bus: `I2C` (GPIO21: SDA, GPIO22: SCL)

## Transcluded Schematic Diagram
![[breadboard/circuits/esp32-sensor#pinout-diagram]]

## PCB Layout Verification
Decoupling 100nF ceramic capacitors placed within 2mm of the BME280 sensor VDD pin.
^breadboard-sensor-shield
