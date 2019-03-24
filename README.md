RasPi-Weatherd
==============

Service to use rtl_433 output to read Acurite sensors and update Weather Underground.

Currently it supports following sensors:
- Acuritt 5n1
- Acurite Lightning
- Acurite Tower

It runs as a service on your Raspberry Pi and updates your PWS account on Weather Underground with 1 minute interval.

This software is inspired by excellent work done here: https://github.com/nordoff/rtl_433_to_wu

Requirements
------------
*Hardware*
* Acurite weather sensors
* USB RTL-SDR dongle
* Raspberry Pi with Raspbian OS

*Software*
* [rtl_433](https://github.com/merbanan/rtl_433) to be installed.

Installation
------------
0. make sure rtl_433 is working fine and showing your sensors:
```
rtl_r433 -R 40
```

1. get all the software to your local folder in RasPi:
```
cd ~
git clone https://github.com/adam-aph/RasPi-Weatherd.git
cd RasPi-Weatherd
sudo chmod 777 *
```

2. edit weather.ini with your PWS credentials

3. move service setup files into system directory:
```
sudo mv weatherd /etc/systemd/system/
sudo mv weatherd.service /lib/systemd/system/
```	
4. start your service and make it permanent:
```
sudo systemctl start weatherd
sudo systemctl enable weatherd
```
5. make sure it is starting after reboot:
```
sudo reboot
```	
Thats it!

Note
----
This software translates metric values (Celsius, kmph etc) to imperial before sending data to WU. If your sensors send Fahnrenhait, inches etc then remove all translation functions from lines 73-80 of weatherd.py
