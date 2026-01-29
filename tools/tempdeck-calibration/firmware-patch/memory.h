/*
 * memory.h - EEPROM storage for Temperature Module
 *
 * MODIFIED: Added calibration offset storage
 *
 * Changes from original:
 *   - Added EEPROM addresses for calibration data (0x80-0x88)
 *   - Added calibration read/write/clear methods
 *   - Added CALIBRATION_VALID_FLAG constant
 *
 * EEPROM Memory Map:
 *   0x00 - 0x1F : Serial number (32 bytes)
 *   0x20 - 0x3F : Model number (32 bytes)
 *   0x40 - 0x5F : Serial CRC
 *   0x60 - 0x7F : Model CRC
 *   0x80 - 0x83 : Calibration offset (float, 4 bytes)  [NEW]
 *   0x84        : Calibration valid flag (1 byte)      [NEW]
 *   0x85 - 0x88 : Calibration CRC (4 bytes)            [NEW]
 */

#ifndef Memory_h
#define Memory_h

#include "Arduino.h"
#include <EEPROM.h>

// Existing EEPROM addresses
#define ADDRESS_SERIAL          0x00
#define ADDRESS_MODEL           0x20
#define ADDRESS_SERIAL_CRC      0x40
#define ADDRESS_MODEL_CRC       0x60

// [NEW] Calibration EEPROM addresses
#define ADDRESS_CALIBRATION_OFFSET  0x80   // float (4 bytes)
#define ADDRESS_CALIBRATION_FLAG    0x84   // validity flag (1 byte)
#define ADDRESS_CALIBRATION_CRC     0x85   // CRC (4 bytes)

// Constants
#define MAX_SERIAL_MODEL_LENGTH 32
#define MEMORY_OK               0
#define MEMORY_ERROR_LENGTH     1
#define MEMORY_ERROR_INVALID    2

// [NEW] Calibration validity flag
#define CALIBRATION_VALID_FLAG  0xCA   // Magic number indicating valid calibration
#define CALIBRATION_INVALID     0xFF   // Uninitialized EEPROM value

class Memory {

    public:

        Memory();

        // Existing methods for serial/model
        uint8_t write_serial(String &serial);
        uint8_t write_model(String &model);
        uint8_t read_serial(String &serial);
        uint8_t read_model(String &model);

        // [NEW] Calibration methods
        float read_calibration_offset();
        bool write_calibration_offset(float offset);
        bool has_valid_calibration();
        void clear_calibration();

    private:

        // CRC lookup table
        const uint8_t CRC_TABLE[16] = {
            0x00, 0x07, 0x0E, 0x09, 0x1C, 0x1B, 0x12, 0x15,
            0x38, 0x3F, 0x36, 0x31, 0x24, 0x23, 0x2A, 0x2D
        };

        // Internal types
        enum IdentifierType { ID_SERIAL, ID_MODEL };

        // Internal helper methods
        uint8_t _calculate_crc(String &data);
        bool _validate_eeprom(IdentifierType type);
        uint8_t _write_data(IdentifierType type, String &data);
        uint8_t _read_data(IdentifierType type, String &data);
        int _get_address(IdentifierType type);
        int _get_crc_address(IdentifierType type);

        // [NEW] Calibration CRC helper
        uint8_t _calculate_calibration_crc(float offset);

        // Error tracking
        uint8_t error_flag;
};

#endif
