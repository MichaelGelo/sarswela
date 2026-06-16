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
  lcd.backlight();
}

void loop() {
  bool pressed = false;

  if (digitalRead(deaf_mode) == LOW) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Deaf Mode");
    Serial.println("Deaf Mode button pressed!");
    pressed = true;
    delay(250);
  }
  else if (digitalRead(blind_mode) == LOW) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Blind Mode");
    Serial.println("PLAY:blind");
    pressed = true;
    delay(250);
  }
  else if (digitalRead(child_mode) == LOW) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Child Mode");
    Serial.println("Child Mode button pressed!");
    pressed = true;
    delay(250);
  }
  else if (digitalRead(forei_mode) == LOW) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Foreign Lang");
    lcd.setCursor(0, 1);
    lcd.print("Mode");
    Serial.println("Foreign Language Mode button pressed!");
    pressed = true;
    delay(250);
  }
  else if (digitalRead(forei_eng) == LOW) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("English");
    Serial.println("PLAY:english");
    pressed = true;
    delay(250);
  }
  else if (digitalRead(forei_span) == LOW) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Spanish");
    Serial.println("PLAY:spanish");
    pressed = true;
    delay(250);
  }
  else if (digitalRead(forei_mand) == LOW) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Mandarin");
    Serial.println("PLAY:mandarin");
    pressed = true;
    delay(250);
  }

  if (!pressed) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Select a mode");
    delay(100);
  }
}