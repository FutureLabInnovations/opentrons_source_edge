/*
 * gcode.h - G-code parser for Temperature Module
 *
 * MODIFIED: Added M303 calibration offset command
 *
 * Changes from original:
 *   - Added GCODE_CALIBRATION (6) for M303 command
 *   - Increased TOTAL_GCODE_COMMAND_CODES to 7
 *   - Added print_calibration_offset() method
 */

#ifndef Gcode_h
#define Gcode_h

#include "Arduino.h"

#define NO_TARGET_TEMP_SET 32766

#define MAX_SERIAL_BUFFER_LENGTH 100
#define MAX_SERIAL_DIGITS_IN_NUMBER 7
#define SERIAL_DIGITS_IN_RESPONSE 3

// G-code command codes
#define GCODE_NO_CODE               -1
#define GCODE_GET_TEMP              0   // M105 - Get temperature
#define GCODE_SET_TEMP              1   // M104 - Set temperature
#define GCODE_DISENGAGE             2   // M18  - Deactivate
#define GCODE_DEVICE_INFO           3   // M115 - Device info
#define GCODE_DFU                   4   // dfu  - Enter bootloader
#define GCODE_RESET_REASON          5   // M114 - Reset reason
#define GCODE_CALIBRATION           6   // M303 - Calibration offset  [NEW]
#define TOTAL_GCODE_COMMAND_CODES   7   // Updated from 6 to 7

class Gcode {

    public:

        Gcode();
        void setup(int baudrate);
        bool received_newline();
        bool pop_command();
        void send_ack();
        int code;
        float parsed_number = 0;

        // Response methods
        void print_device_info(String serial, String model, String version);
        void print_targetting_temperature(float target_temp, float current_temp);
        void print_stablizing_temperature(float current_temp);
        void print_warning(String msg);
        void print_generic_response(String msg);

        // [NEW] Calibration offset response
        void print_calibration_offset(float offset);

        // Parameter parsing
        bool read_number(char key);

    private:

        String COMMAND_CODES[TOTAL_GCODE_COMMAND_CODES];
        String GCODE_BUFFER_STRING;
        String SERIAL_BUFFER_STRING;
        char CHARACTERS_TO_STRIP[3] = {' ', '\r', '\n'};
        bool SEND_ACK_NEXT_UPDATE = false;

        void _strip_serial_buffer();
        void _parse_gcode_commands();
};

#endif
