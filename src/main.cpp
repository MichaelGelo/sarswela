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

LiquidCrystal_I2C lcd(0x27,  16, 2);

int lastState = -1;
bool anyPressed = false;
bool foreignGate = false;

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
