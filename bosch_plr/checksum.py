from crc import CrcCalculator, Configuration

crc8_configuration = Configuration(width=8, polynomial=0xA6, init_value=0xAA, final_xor_value=0x00, reverse_input=False, reverse_output=False)
crc8_calculator = CrcCalculator(crc8_configuration, True)

def crc8(data):
    return crc8_calculator.calculate_checksum(data)

crc32_configuration = Configuration(width=32, polynomial=0x04C11DB7, init_value=0xAAAAAAAA, final_xor_value=0x00, reverse_input=False, reverse_output=False)
crc32_calculator = CrcCalculator(crc32_configuration, True)

def crc32(data):
    return crc32_calculator.calculate_checksum(data)