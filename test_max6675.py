import spidev
import time

# Initialisation SPI
spi = spidev.SpiDev()
spi.open(0, 0)          # bus 0, CE0
spi.max_speed_hz = 500000
spi.mode = 0b00

def read_max6675():
    # Lecture de 2 octets
    data = spi.readbytes(2)

    value = (data[0] << 8) | data[1]

    # Bit D2 = thermocouple débranché
    if value & 0x4:
        return None

    # Les 12 bits de poids fort contiennent la température
    temp_c = (value >> 3) * 0.25
    return temp_c


try:
    while True:
        temp = read_max6675()
        if temp is None:
            print("⚠️ Thermocouple non détecté")
        else:
            print(f"Température : {temp:.2f} °C")
        time.sleep(1)

except KeyboardInterrupt:
    spi.close()
    print("\nTest terminé")
