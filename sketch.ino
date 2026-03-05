#include <LiquidCrystal.h>

//                RS  EN  D4 D5 D6 D7
LiquidCrystal lcd(12, 11, 5, 4, 3, 2);
void setup() {
  Serial.begin(1000000);
  lcd.begin(16, 2);
  lcd.setCursor(0, 0);
  lcd.print("____LCD1602A");
  lcd.setCursor(0, 0);
  lcd.write(byte(0));
  lcd.write(byte(1));
  lcd.write(byte(2));
  lcd.write(byte(3));
  lcd.setCursor(0, 1);
  lcd.print("____20x16Display");
  lcd.setCursor(0, 1);
  lcd.write(byte(4));
  lcd.write(byte(5));
  lcd.write(byte(6));
  lcd.write(byte(7));
}

void loop() {
  if (Serial.available() >= 8) { 
    uint8_t customData[8][8];     

    for (int i = 0; i < 8; i++) {
      while (Serial.available() < 8) {}
      for (int row = 0; row < 8; row++) {
        customData[i][row] = Serial.read();
      }
    }

    // Update custom characters data
    for (int i = 0; i < 8; i++) {
      lcd.createChar(i, customData[i]);
    }
  }
}