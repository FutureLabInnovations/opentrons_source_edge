/*
 * gcode.cpp - G-code parser implementation for Temperature Module
 *
 * MODIFIED: Added M303 calibration offset command
 *
 * Changes from original:
 *   - Added "M303" to COMMAND_CODES array in setup()
 *   - Added print_calibration_offset() method
 */

#include "gcode.h"

Gcode::Gcode() {
    code = GCODE_NO_CODE;
}

void Gcode::setup(int baudrate) {
    Serial.begin(baudrate);
    while (!Serial) {
        ;  // Wait for serial port to connect
    }

    // Command code mapping
    COMMAND_CODES[GCODE_GET_TEMP] = "M105";
    COMMAND_CODES[GCODE_SET_TEMP] = "M104";
    COMMAND_CODES[GCODE_DISENGAGE] = "M18";
    COMMAND_CODES[GCODE_DEVICE_INFO] = "M115";
    COMMAND_CODES[GCODE_DFU] = "dfu";
    COMMAND_CODES[GCODE_RESET_REASON] = "M114";
    COMMAND_CODES[GCODE_CALIBRATION] = "M303";  // [NEW] Calibration command

    GCODE_BUFFER_STRING = "";
    SERIAL_BUFFER_STRING = "";
}

bool Gcode::received_newline() {
    while (Serial.available()) {
        delay(2);  // Small delay for stable character capture
        char c = Serial.read();
        SERIAL_BUFFER_STRING += c;
        if (c == '\n') {
            _strip_serial_buffer();
            if (SERIAL_BUFFER_STRING.length() > 0) {
                if (GCODE_BUFFER_STRING.length() > 0) {
                    GCODE_BUFFER_STRING += ' ';
                }
                GCODE_BUFFER_STRING += SERIAL_BUFFER_STRING;
            }
            SERIAL_BUFFER_STRING = "";
            return true;
        }
    }
    return false;
}

void Gcode::_strip_serial_buffer() {
    for (int i = 0; i < 3; i++) {
        SERIAL_BUFFER_STRING.replace(String(CHARACTERS_TO_STRIP[i]), "");
    }
}

bool Gcode::pop_command() {
    if (GCODE_BUFFER_STRING.length() == 0) {
        return false;
    }

    _parse_gcode_commands();

    if (code == GCODE_NO_CODE) {
        GCODE_BUFFER_STRING = "";
        return false;
    }
    return true;
}

void Gcode::_parse_gcode_commands() {
    code = GCODE_NO_CODE;

    for (int i = 0; i < TOTAL_GCODE_COMMAND_CODES; i++) {
        int index = GCODE_BUFFER_STRING.indexOf(COMMAND_CODES[i]);
        if (index >= 0) {
            code = i;
            // Remove the command from the buffer, keep parameters
            int cmd_end = index + COMMAND_CODES[i].length();
            GCODE_BUFFER_STRING = GCODE_BUFFER_STRING.substring(cmd_end);
            GCODE_BUFFER_STRING.trim();
            return;
        }
    }
}

bool Gcode::read_number(char key) {
    int key_index = GCODE_BUFFER_STRING.indexOf(key);
    if (key_index < 0) {
        return false;
    }

    String number_string = "";
    bool found_decimal = false;
    bool found_negative = false;

    for (int i = key_index + 1; i < GCODE_BUFFER_STRING.length(); i++) {
        char c = GCODE_BUFFER_STRING.charAt(i);

        if (c == '-' && number_string.length() == 0) {
            found_negative = true;
            number_string += c;
        }
        else if (c == '.' && !found_decimal) {
            found_decimal = true;
            number_string += c;
        }
        else if (c >= '0' && c <= '9') {
            if (number_string.length() < MAX_SERIAL_DIGITS_IN_NUMBER) {
                number_string += c;
            }
        }
        else {
            break;  // End of number
        }
    }

    if (number_string.length() > 0 && number_string != "-" && number_string != ".") {
        parsed_number = number_string.toFloat();
        return true;
    }
    return false;
}

void Gcode::send_ack() {
    Serial.print("ok\r\nok\r\n");
}

void Gcode::print_device_info(String serial, String model, String version) {
    Serial.print("serial:");
    Serial.print(serial);
    Serial.print(" model:");
    Serial.print(model);
    Serial.print(" version:");
    Serial.print(version);
    Serial.print(" ");
}

void Gcode::print_targetting_temperature(float target_temp, float current_temp) {
    Serial.print("T:");
    Serial.print(target_temp, SERIAL_DIGITS_IN_RESPONSE);
    Serial.print(" C:");
    Serial.print(current_temp, SERIAL_DIGITS_IN_RESPONSE);
    Serial.print(" ");
}

void Gcode::print_stablizing_temperature(float current_temp) {
    Serial.print("T:none");
    Serial.print(" C:");
    Serial.print(current_temp, SERIAL_DIGITS_IN_RESPONSE);
    Serial.print(" ");
}

void Gcode::print_warning(String msg) {
    Serial.print("Warning:");
    Serial.print(msg);
    Serial.print(" ");
}

void Gcode::print_generic_response(String msg) {
    Serial.print(msg);
    Serial.print(" ");
}

/*
 * [NEW] Print calibration offset response
 *
 * Format: "O:1.50 " (offset with 2 decimal places)
 *
 * Examples:
 *   O:0.00   - No offset
 *   O:1.50   - Positive offset (module reads low)
 *   O:-0.75  - Negative offset (module reads high)
 */
void Gcode::print_calibration_offset(float offset) {
    Serial.print("O:");
    Serial.print(offset, 2);  // 2 decimal places
    Serial.print(" ");
}
