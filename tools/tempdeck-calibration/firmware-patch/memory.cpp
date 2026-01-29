/*
 * memory.cpp - EEPROM storage implementation for Temperature Module
 *
 * MODIFIED: Added calibration offset storage at EEPROM address 0x80
 *
 * New methods:
 *   - read_calibration_offset()  - Get stored offset (returns 0.0 if none)
 *   - write_calibration_offset() - Store offset with CRC validation
 *   - has_valid_calibration()    - Check if valid calibration exists
 *   - clear_calibration()        - Invalidate stored calibration
 */

#include "memory.h"

Memory::Memory() {
    error_flag = MEMORY_OK;
}

// ============================================================================
// Address helpers
// ============================================================================

int Memory::_get_address(IdentifierType type) {
    return (type == ID_SERIAL) ? ADDRESS_SERIAL : ADDRESS_MODEL;
}

int Memory::_get_crc_address(IdentifierType type) {
    return (type == ID_SERIAL) ? ADDRESS_SERIAL_CRC : ADDRESS_MODEL_CRC;
}

// ============================================================================
// CRC calculation
// ============================================================================

uint8_t Memory::_calculate_crc(String &data) {
    uint8_t crc = 0;
    for (unsigned int i = 0; i < data.length(); i++) {
        uint8_t b = data.charAt(i);
        crc = CRC_TABLE[(crc ^ (b >> 4)) & 0x0F] ^ (crc << 4);
        crc = CRC_TABLE[(crc ^ (b & 0x0F)) & 0x0F] ^ (crc << 4);
    }
    return crc;
}

uint8_t Memory::_calculate_calibration_crc(float offset) {
    uint8_t* bytes = (uint8_t*)&offset;
    uint8_t crc = 0;
    for (unsigned int i = 0; i < sizeof(float); i++) {
        crc = CRC_TABLE[(crc ^ (bytes[i] >> 4)) & 0x0F] ^ (crc << 4);
        crc = CRC_TABLE[(crc ^ (bytes[i] & 0x0F)) & 0x0F] ^ (crc << 4);
    }
    return crc;
}

// ============================================================================
// EEPROM validation
// ============================================================================

bool Memory::_validate_eeprom(IdentifierType type) {
    String data;
    int addr = _get_address(type);
    int crc_addr = _get_crc_address(type);

    for (int i = 0; i < MAX_SERIAL_MODEL_LENGTH; i++) {
        char c = EEPROM.read(addr + i);
        if (c == 0 || c == 0xFF) break;
        data += c;
    }

    if (data.length() == 0) {
        return false;
    }

    uint8_t stored_crc = EEPROM.read(crc_addr);
    uint8_t calculated_crc = _calculate_crc(data);

    return (stored_crc == calculated_crc);
}

// ============================================================================
// Serial/Model read/write (existing functionality)
// ============================================================================

uint8_t Memory::_write_data(IdentifierType type, String &data) {
    if (data.length() > MAX_SERIAL_MODEL_LENGTH) {
        return MEMORY_ERROR_LENGTH;
    }

    int addr = _get_address(type);
    int crc_addr = _get_crc_address(type);

    for (unsigned int i = 0; i < data.length(); i++) {
        EEPROM.write(addr + i, data.charAt(i));
    }
    EEPROM.write(addr + data.length(), 0);

    uint8_t crc = _calculate_crc(data);
    EEPROM.write(crc_addr, crc);

    return MEMORY_OK;
}

uint8_t Memory::_read_data(IdentifierType type, String &data) {
    if (!_validate_eeprom(type)) {
        return MEMORY_ERROR_INVALID;
    }

    data = "";
    int addr = _get_address(type);

    for (int i = 0; i < MAX_SERIAL_MODEL_LENGTH; i++) {
        char c = EEPROM.read(addr + i);
        if (c == 0 || c == 0xFF) break;
        data += c;
    }

    return MEMORY_OK;
}

uint8_t Memory::write_serial(String &serial) {
    return _write_data(ID_SERIAL, serial);
}

uint8_t Memory::write_model(String &model) {
    return _write_data(ID_MODEL, model);
}

uint8_t Memory::read_serial(String &serial) {
    return _read_data(ID_SERIAL, serial);
}

uint8_t Memory::read_model(String &model) {
    return _read_data(ID_MODEL, model);
}

// ============================================================================
// CALIBRATION OFFSET METHODS (NEW)
// ============================================================================

/*
 * Check if valid calibration data exists in EEPROM
 *
 * Validation:
 *   1. Flag byte must be CALIBRATION_VALID_FLAG (0xCA)
 *   2. CRC must match stored offset value
 *   3. Offset must be in reasonable range (-10 to +10)
 */
bool Memory::has_valid_calibration() {
    uint8_t flag = EEPROM.read(ADDRESS_CALIBRATION_FLAG);
    if (flag != CALIBRATION_VALID_FLAG) {
        return false;
    }

    float stored_offset;
    EEPROM.get(ADDRESS_CALIBRATION_OFFSET, stored_offset);

    // Check CRC
    uint8_t stored_crc = EEPROM.read(ADDRESS_CALIBRATION_CRC);
    uint8_t calculated_crc = _calculate_calibration_crc(stored_offset);
    if (stored_crc != calculated_crc) {
        return false;
    }

    // Sanity check range
    if (stored_offset < -10.0 || stored_offset > 10.0) {
        return false;
    }

    return true;
}

/*
 * Read calibration offset from EEPROM
 *
 * Returns:
 *   Stored offset if valid calibration exists
 *   0.0 if no valid calibration (no correction applied)
 */
float Memory::read_calibration_offset() {
    if (!has_valid_calibration()) {
        return 0.0;
    }

    float offset;
    EEPROM.get(ADDRESS_CALIBRATION_OFFSET, offset);
    return offset;
}

/*
 * Write calibration offset to EEPROM
 *
 * Writes:
 *   - Float value at ADDRESS_CALIBRATION_OFFSET (0x80)
 *   - CRC at ADDRESS_CALIBRATION_CRC (0x85)
 *   - Validity flag at ADDRESS_CALIBRATION_FLAG (0x84) - written last!
 *
 * Parameters:
 *   offset - Temperature offset in °C (must be -10.0 to +10.0)
 *
 * Returns:
 *   true  - Write successful
 *   false - Offset out of valid range
 */
bool Memory::write_calibration_offset(float offset) {
    // Validate range
    if (offset < -10.0 || offset > 10.0) {
        return false;
    }

    // Write offset value (4 bytes)
    EEPROM.put(ADDRESS_CALIBRATION_OFFSET, offset);

    // Write CRC
    uint8_t crc = _calculate_calibration_crc(offset);
    EEPROM.write(ADDRESS_CALIBRATION_CRC, crc);

    // Write validity flag LAST (marks data as complete)
    EEPROM.write(ADDRESS_CALIBRATION_FLAG, CALIBRATION_VALID_FLAG);

    return true;
}

/*
 * Clear/invalidate calibration data
 *
 * Sets flag to invalid (0xFF). Offset value remains but is ignored.
 * Module will report uncorrected temperatures after this.
 */
void Memory::clear_calibration() {
    EEPROM.write(ADDRESS_CALIBRATION_FLAG, CALIBRATION_INVALID);
}
