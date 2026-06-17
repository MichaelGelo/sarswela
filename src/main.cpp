#include <Arduino.h>
#include <LiquidCrystal_I2C.h>

#include  <Wire.h>
#define deaf_mode 2
#define blind_mode 3
#define child_mode 4
#define forei_mode 5

#define forei_eng 8
#define forei_span 9
#define forei_mand 10

#define relay_pin 7

LiquidCrystal_I2C lcd(0x27,  16, 2);

#define UNIT 150

const char* morseTable[] = {
  ".-",   // A
  "-...", // B
  "-.-.", // C
  "-..",  // D
  ".",    // E
  "..-.", // F
  "--.",  // G
  "....", // H
  "..",   // I
  ".---", // J
  "-.-",  // K
  ".-..", // L
  "--",   // M
  "-.",   // N
  "---",  // O
  ".--.", // P
  "--.-", // Q
  ".-.",  // R
  "...",  // S
  "-",    // T
  "..-",  // U
  "...-", // V
  ".--",  // W
  "-..-", // X
  "-.--", // Y
  "--.."  // Z
};

int lastState = -1;
bool anyPressed = false;
bool foreignGate = false;

bool otherButtonPressed() {
  return digitalRead(blind_mode) == LOW ||
         digitalRead(child_mode) == LOW ||
         digitalRead(forei_mode) == LOW ||
         digitalRead(forei_eng)  == LOW ||
         digitalRead(forei_span) == LOW ||
         digitalRead(forei_mand) == LOW;
}

// Returns true if another button was pressed during the wait
bool interruptibleDelay(unsigned long ms) {
  unsigned long start = millis();
  while (millis() - start < ms) {
    if (otherButtonPressed()) return true;
  }
  return false;
}

bool dot() {
  digitalWrite(relay_pin, LOW);
  if (interruptibleDelay(UNIT))       { digitalWrite(relay_pin, HIGH); return true; }
  digitalWrite(relay_pin, HIGH);
  return interruptibleDelay(UNIT);
}

bool dash() {
  digitalWrite(relay_pin, LOW);
  if (interruptibleDelay(UNIT * 3))   { digitalWrite(relay_pin, HIGH); return true; }
  digitalWrite(relay_pin, HIGH);
  return interruptibleDelay(UNIT);
}

bool playMorse(const char* text) {
  for (int i = 0; text[i] != '\0'; i++) {
    char c = toupper(text[i]);
    if (c == ' ') {
      if (interruptibleDelay(UNIT * 7)) return true;
      continue;
    }
    if (c < 'A' || c > 'Z') continue;

    const char* pattern = morseTable[c - 'A'];
    for (int j = 0; pattern[j] != '\0'; j++) {
      if (pattern[j] == '.') { if (dot())  return true; }
      else                   { if (dash()) return true; }
    }
    if (interruptibleDelay(UNIT * 3)) return true;
  }
  return false;
}

void displayMessage(int state) {
  if (state == lastState) return;
  lastState = state;

  lcd.clear();
  lcd.setCursor(0, 0);

  switch (state) {
    case 0: lcd.print("Deaf Mode"); break;
    case 1: lcd.print("Blind Mode"); break;
    case 2: lcd.print("Child Mode"); break;
    case 3:
      lcd.print("Foreign Lang");
      lcd.setCursor(0, 1);
      lcd.print("Mode");
      break;
    case 4: lcd.print("English"); break;
    case 5: lcd.print("Spanish"); break;
    case 6: lcd.print("Mandarin"); break;
    case 7: lcd.print("Select a mode"); break;
  }
}

void setup() {
  Serial.begin(9600);

  pinMode(deaf_mode, INPUT_PULLUP);
  pinMode(blind_mode, INPUT_PULLUP);
  pinMode(child_mode, INPUT_PULLUP);
  pinMode(forei_mode, INPUT_PULLUP);

  pinMode(forei_eng, INPUT_PULLUP);
  pinMode(forei_span, INPUT_PULLUP);
  pinMode(forei_mand, INPUT_PULLUP);

  pinMode(relay_pin, OUTPUT);
  digitalWrite(relay_pin, HIGH);

  lcd.init();
  lcd.clear();
  lcd.backlight();
  displayMessage(7);
}

void loop() {
  if (digitalRead(deaf_mode) == LOW) {
    foreignGate = false;
    displayMessage(0);
    Serial.println("STOP");
    anyPressed = true;
    playMorse("Sarswela");
    digitalWrite(relay_pin, HIGH); // ensure relay is off whether interrupted or finished
    delay(250);
  }
  else if (digitalRead(blind_mode) == LOW) {
    foreignGate = false;
    displayMessage(1);
    Serial.println("PLAY:blind");
    anyPressed = true;
    delay(250);
  }
  else if (digitalRead(child_mode) == LOW) {
    foreignGate = false;
    displayMessage(2);
    Serial.println("STOP");
    anyPressed = true;
    delay(250);
  }
  else if (digitalRead(forei_mode) == LOW) {
    foreignGate = true;
    displayMessage(3);
    Serial.println("STOP");
    anyPressed = true;
    delay(250);
  }
  else if (digitalRead(forei_eng) == LOW && foreignGate) {
    displayMessage(4);
    Serial.println("PLAY:english");
    anyPressed = true;
    delay(250);
  }
  else if (digitalRead(forei_span) == LOW && foreignGate) {
    displayMessage(5);
    Serial.println("PLAY:spanish");
    anyPressed = true;
    delay(250);
  }
  else if (digitalRead(forei_mand) == LOW && foreignGate) {
    displayMessage(6);
    Serial.println("PLAY:mandarin");
    anyPressed = true;
    delay(250);
  }
  else if (!anyPressed) {
    displayMessage(7);
  }
}
