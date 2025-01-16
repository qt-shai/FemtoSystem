/*
  Title: Precise Analog Measurement with Identification
  Author: Boaz Raz
  Description:
    - Implements *IDN? for device identification.
    - Handles "start measure:<num_points>,<time_us>" commands.
    - Uses precise timing with micros() for accurate delays.
*/

#include <Arduino.h>

static const unsigned int MAX_POINTS = 200; 
static const unsigned long MAX_DELAY_MICROSEC = 5000;
const int PULSE_PIN = 9; // Digital pin for pulse output
volatile bool pulseActive = false; // Flag to control pulse generation

unsigned long pulseWidth = 1000;  // Pulse duration in microseconds (updated dynamically)
unsigned long pulseSpacing = 5000; // Time between pulses in microseconds (updated dynamically)

void setup() {
  Serial.begin(9600);
  while (!Serial) {
    // Wait for Serial to be ready (especially useful on Leonardo/Micro).
  }
  pinMode(A0, INPUT);
  pinMode(PULSE_PIN, OUTPUT);
  digitalWrite(PULSE_PIN, LOW);
}

void loop() {
  // Continuously check if there's incoming serial data
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    // IDN Query Response
    if (command == "*IDN?") {
      Serial.println("Arduino,BoazRaz,001,1.0");  // Manufacturer, Model, Serial, Firmware Version
      return;
    }

    // Process only "start measure" commands
    if (command.startsWith("start measure:")) {
      String params = command.substring(strlen("start measure:"));
      params.trim();

      int commaIndex = params.indexOf(',');
      if (commaIndex == -1) {
        Serial.println("ERROR: Malformed parameters. Expected <num_points>,<time_us>.");
        return;
      }

      unsigned int numPoints = params.substring(0, commaIndex).toInt();
      unsigned long timeUs = params.substring(commaIndex + 1).toInt();

      if (numPoints == 0 || numPoints > MAX_POINTS) {
        Serial.println("ERROR: Invalid number of points.");
        return;
      }
      if (timeUs == 0 || timeUs > MAX_DELAY_MICROSEC) {
        Serial.println("ERROR: Invalid time delay.");
        return;
      }

      // Acquire measurements with precise timing
      int measurements[MAX_POINTS];
      unsigned long startTime, elapsedTime, waitTime;

      for (unsigned int i = 0; i < numPoints; i++) {
        startTime = micros();
        measurements[i] = analogRead(A0);

        if (i < numPoints - 1) {
          elapsedTime = micros() - startTime;
          waitTime = (timeUs > elapsedTime) ? (timeUs - elapsedTime) : 0;
          delayMicroseconds(waitTime);
        }
      }

      // Send result
      String result = "MEASURE:";
      for (unsigned int i = 0; i < numPoints; i++) {
        result += String(measurements[i]);
        if (i < numPoints - 1) {
          result += ",";
        }
      }
      Serial.println(result);
    } else {
      Serial.println("ERROR: Unknown command.");
    }

     // Handle continuous pulse mode
    if (command.startsWith("set pulse:")) {
      handle_pulse(command);
      return;
    }

    // Stop pulse generation
    if (command == "stop pulse") {
      pulseActive = false;
      digitalWrite(PULSE_PIN, LOW);
      Serial.println("Pulse generation stopped.");
      return;
    }
  }

  // If pulse mode is active, keep generating pulses
  if (pulseActive) {
    generate_pulse();
  }

}


/**
 * Handles continuous pulse command.
 */
void handle_pulse(String command) {
  String params = command.substring(strlen("set pulse:"));
  params.trim();

  int commaIndex = params.indexOf(',');
  if (commaIndex == -1) {
    Serial.println("ERROR: Malformed parameters. Expected <pulse_width_us>,<spacing_us>.");
    return;
  }

  unsigned long newPulseWidth = params.substring(0, commaIndex).toInt();
  unsigned long newSpacing = params.substring(commaIndex + 1).toInt();

  if (newPulseWidth == 0 || newSpacing == 0) {
    Serial.println("ERROR: Invalid pulse parameters.");
    return;
  }

  pulseWidth = newPulseWidth; // Update global variables
  pulseSpacing = newSpacing; 

  Serial.print("Starting pulse mode: width=");
  Serial.print(pulseWidth);
  Serial.print(" us, spacing=");
  Serial.print(pulseSpacing);
  Serial.println(" us");

  pulseActive = true;
}

/**
 * Generates pulses continuously.
 */
void generate_pulse() {
  static unsigned long lastPulseTime = 0;
  static bool pulseState = false;

  unsigned long now = micros();
  
  if (!pulseState && (now - lastPulseTime >= pulseSpacing)) {
    digitalWrite(PULSE_PIN, HIGH);
    lastPulseTime = now;
    pulseState = true;
  } 
  
  if (pulseState && (now - lastPulseTime >= pulseWidth)) {
    digitalWrite(PULSE_PIN, LOW);
    lastPulseTime = now;
    pulseState = false;
  }
}
