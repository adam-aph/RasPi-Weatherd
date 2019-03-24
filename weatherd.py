#!/usr/bin/python

import subprocess
import os
import signal
import time
import sys
import re
import urllib
import argparse
import datetime
import math
import logging
import ConfigParser

from decimal import Decimal

config = ConfigParser.ConfigParser()
config.read('/home/pi/RasPi-Weatherd/weather.ini')

logger = logging.getLogger("weatherd")
logging.basicConfig(filename = '/var/log/weatherd.log', level=logging.INFO)


wu_uri = 'http://rtupdate.wunderground.com/weatherstation/updateweatherstation.php'

a = 17.271
b = 237.7

def dewpApp(T,RH):
    return (b * gamma(T,RH)) / (a - gamma(T,RH))

def gamma(T,RH):
    return (a * T / (b + T)) + math.log(RH/100.0)

def C2F(C):
    return 9.0/5.0 * C + 32.0

def kmh2mph(KMH):
    return KMH / 1.609

def mm2in(MM):
    return MM / 25.4


class Sensor:
        wind_mph = 0.0
        temp_f = 0.0
        rh_pct = 0.0
        winddir_deg = 0.0
        rain_in = 0.0 #hourly rain
        rain_daily_in = 0.0 #daily rain
        timestamp = ''
        soiltempf = 0.0
        def reset(self):
                self.wind_mph = 0.0
                self.temp_f = 0.0
                self.rh_pct = 0.0
                self.winddir_deg = 0.0
                self.rain_in = 0.0
                self.rain_daily_in = 0.0
                self.timestamp = ''

def update_wu(readings):
        logger.debug("update_wu [in]")
        try:
                params = urllib.urlencode({
                        'action':'updateraw',
                        'ID':config.get('station','id'),
                        'PASSWORD':config.get('station','pw'),
                        'dateutc':readings.timestamp,
                        'winddir':readings.winddir_deg,
                        'windspeedmph':kmh2mph(readings.wind_mph),
                        'humidity':readings.rh_pct,
                        'tempf':C2F(readings.temp_f),
                        'rainin':mm2in(readings.rain_in), #rain in last hour
                        'dailyrainin':mm2in(readings.rain_daily_in), #rain in last day
                        'dewptf':C2F(dewpApp(readings.temp_f,readings.rh_pct)),
                        'soiltempf':C2F(readings.soiltempf),
                        #dewpt eq from http://andrew.rsmas.miami.edu/bmcnoldy/Humidity.html
                        #'dewptf':243.04*(math.log(readings.rh_pct/100)+((17.625*readings.temp_f)/(243.04+readings.temp_f)))/(17.625-math.log(readings.rh_pct/100)-((17.625*readings.temp_f)/(243.04+readings.temp_f))),
                        'softwaretype':'rtl-433',
                        'realtime':'1',
                        'rtfreq':'60.0'})

                logger.debug(params)
                if (not config.has_option('station','test') or config.getboolean('station', 'test') == False):
                        try:
                            result = urllib.urlopen(wu_uri + "?%s" % params)
                            logger.debug(result.read())
                        except Exception as e:
                                logger.error("IO Error: %s", str(e))
                else:
                        logger.debug("Skipping GET of URL for test mode")
                        logger.debug(wu_uri + "?%s" % params)
        except ConfigParser.NoSectionError:
                logger.error("Missing config section")
        except Exception as e:
                logger.error(str(e))


class WeatherD:

        def run(self):
                logger.info("Starting weatherd")
                proc = subprocess.Popen(['rtl_433','-R','40'], stdout=subprocess.PIPE)

                msgid_re = re.compile('.*Acurite-5n1.*message_type\" : (\d\d).*')
                msg56_re = re.compile('.*wind_speed.* : (\d+\.?\d*).*temperature.* : (\d+\.?\d*).*humidity.* : (\d+\.?\d*).*')
                msg49_re = re.compile('.*wind_speed.* : (\d+\.?\d*).*wind_dir.* : (\d+\.?\d*).*rain.* : (\d+\.?\d*).*')
                msgLight_re = re.compile('.*Acurite-Lightning.*temperature.* : (\d+\.?\d*).*humidity.* : (\d+\.?\d*).*strike_count.* : (\d+\.?\d*).*storm_dist.* : (\d+\.?\d*).*')
                msgTower_re = re.compile('.*Acurite-Tower.*temperature.* : (\d+\.?\d*).*humidity.* : (\d+\.?\d*).*')

                got_msg49 = False
                got_msg56 = False

                rain_total = Decimal(0.0)
                rain_hour = Decimal(0.0)
                rain_day = Decimal(0.0)
                weather = Sensor()
                cur_hour = datetime.datetime.today().hour
                cur_day = datetime.datetime.today().day
                times = 0
                cur_rain = Decimal(0.0)
                timestamp = ''
                lastUpdate = 0.0

                while(1):
                        line = proc.stdout.readline()

                        msgLight = msgLight_re.match(line)
                        if(msgLight):
                                logger.debug("%s Msg-Lightning", datetime.datetime.now())
                                weather.soiltempf = float(msgLight.group(1))

                        msgTower = msgTower_re.match(line)
                        if(msgTower):
                                logger.debug("%s Msg-Tower", datetime.datetime.now())
                                weather.soiltempf = float(msgTower.group(1))

                        msgobj = msgid_re.match(line)
                        if(msgobj):
                                timestamp = datetime.datetime.now()
                                msgNo = int(msgobj.group(1))
                                logger.debug("%s MsgId %s", timestamp, msgNo)

                                if msgNo == 56:
                                        msg56mo = msg56_re.match(line)
                                        if (msg56mo != None):
                                                got_msg56 = True
                                                weather.timestamp = timestamp
                                                weather.wind_mph = float(msg56mo.group(1))
                                                weather.temp_f = float(msg56mo.group(2))
                                                weather.rh_pct = float(msg56mo.group(3))

                                elif msgNo == 49:
                                        msg49mo = msg49_re.match(line)
                                        if (msg49mo != None):
                                                got_msg49 = True
                                                weather.timestamp = timestamp
                                                weather.wind_mph = float(msg49mo.group(1))
                                                weather.winddir_deg = float(msg49mo.group(2))
                                                weather.cur_rain = Decimal(msg49mo.group(3)) - rain_total #inches rain since last message

                                                #handle hourly rain
                                                if (cur_hour != datetime.datetime.today().hour):
                                                        logger.info("%s Resetting hourly rain total, was %1.1f", weather.timestamp, rain_hour)
                                                        cur_hour = datetime.datetime.today().hour
                                                        rain_hour = Decimal(0.0)

                                                rain_hour += cur_rain
                                                rain_in = rain_hour

                                                #handle daily rain
                                                if (cur_day != datetime.datetime.today().day):
                                                        logger.info("%s Resetting daily rain total, was %1.1f",  weather.timestamp, rain_day)
                                                        cur_day = datetime.datetime.today().day
                                                        rain_day = Decimal(0.0)

                                                rain_day = rain_day + cur_rain
                                                rain_daily_in = rain_day

                                                #total rain
                                                rain_total += cur_rain

                        if (got_msg56 and got_msg49):
                                logger.debug("%s Wind %1.1f mph, dir %03.1f deg, %1.3f F, RH %1.1f%%, Rain (last) %1.2f in, (1hr) %1.2f in, (1day) %1.2f in", weather.timestamp, weather.wind_mph, weather.winddir_deg, weather.temp_f, weather.rh_pct, cur_rain, weather.rain_in, weather.rain_daily_in)
                                got_msg49 = False
                                got_msg56 = False

                                if (time.time() - lastUpdate > 60.0):
                                    logger.debug("Updating weather")
                                    update_wu(weather)
                                    logger.debug("Weather updated")
                                    weather.reset()
                                    cur_rain = Decimal(0.0)
                                    lastUpdate = time.time();

if __name__ == "__main__":
        daemon = WeatherD()
        if len(sys.argv) == 2:
                if 'start' == sys.argv[1]:
                    daemon.run()
                elif 'stop' == sys.argv[1]:
                    print "ok"
                elif 'restart' == sys.argv[1]:
                    print "ok"
                else:
                        print "Unknown command"
                        sys.exit(2)
                sys.exit(0)
        else:
                print "usage: %s start|stop|restart" % sys.argv[0]
                sys.exit(2)
 
