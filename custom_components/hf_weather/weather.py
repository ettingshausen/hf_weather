"""

"""
import logging, os
from datetime import datetime, timedelta

import asyncio
import async_timeout
import aiohttp

import voluptuous as vol

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from homeassistant.components.weather import (
    WeatherEntity, ATTR_FORECAST_CONDITION, ATTR_FORECAST_TEMP,  
    ATTR_FORECAST_TEMP_LOW, ATTR_FORECAST_PRECIPITATION, ATTR_FORECAST_TIME)
from homeassistant.const import (ATTR_ATTRIBUTION, TEMP_CELSIUS, CONF_NAME)
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

from .const import VERSION, ROOT_PATH

_LOGGER = logging.getLogger(__name__)

TIME_BETWEEN_UPDATES = timedelta(seconds=1800)

DEFAULT_TIME = dt_util.now()

CONF_CITY = "city"
CONF_APPKEY = "appkey"

ATTR_CONDITION_CN = "condition_cn"
ATTR_UPDATE_TIME = "update_time"
ATTR_AQI = "aqi"
ATTR_HOURLY_FORECAST = "hourly_forecast"
ATTR_SUGGESTION = "suggestion"
ATTR_CUSTOM_UI_MORE_INFO = "custom_ui_more_info"
CONDITION_CLASSES = {
    'sunny': ["晴"],
    'cloudy': ["多云"],
    'partlycloudy': ["少云", "晴间多云", "阴"],
    'windy': ["有风", "微风", "和风", "清风"],
    'windy-variant': ["强风", "疾风", "大风", "烈风"],
    'hurricane': ["飓风", "龙卷风", "热带风暴", "狂暴风", "风暴"],
    'rainy': ["雨", "毛毛雨", "小雨", "小到中雨", "中雨", "大雨", "阵雨", "极端降雨"],
    'pouring': ["暴雨", "大暴雨", "特大暴雨", "强阵雨"],
    'lightning-rainy': ["雷阵雨", "强雷阵雨"],
    'fog': ["雾", "薄雾"],
    'hail': ["雷阵雨伴有冰雹"],
    'snowy': ["雪", "小雪", "中雪", "大雪", "暴雪", "阵雪"],
    'snowy-rainy': ["雨夹雪", "雨雪天气", "阵雨夹雪"],
}
TRANSLATE_SUGGESTION = {
    'air': '空气污染扩散条件指数',
    'drsg': '穿衣指数',
    'uv': '紫外线指数',
    'comf': '舒适度指数',
    'flu': '感冒指数',
    'sport': '运动指数',
    'trav': '旅游指数',
    'cw': '洗车指数',
}

ATTRIBUTION = "来自和风天气的天气数据"

ATTR_FORECAST_PROBABLE_PRECIPITATION = 'probable_precipitation'

# 集成安装
async def async_setup_entry(hass, config_entry, async_add_entities):
    hass.http.register_static_path(ROOT_PATH, hass.config.path('custom_components/hf_weather/local'), False)
    hass.components.frontend.add_extra_js_url(hass, ROOT_PATH + '/hf_weather-card/hf_weather-card.js?ver=' + VERSION)
    hass.components.frontend.add_extra_js_url(hass, ROOT_PATH + '/hf_weather-card/hf_weather-more-info.js?ver=' + VERSION)

    _LOGGER.info("setup platform weather.Heweather...")
    config = config_entry.data
    name = config.get(CONF_NAME)
    city = config.get(CONF_CITY)
    appkey = config.get(CONF_APPKEY)

    data = WeatherData(hass, city, appkey)

    await data.async_update(dt_util.now())
    async_track_time_interval(hass, data.async_update, TIME_BETWEEN_UPDATES)

    async_add_entities([HeFengWeather(data, name)], True)

class HeFengWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, data, object_id):
        """Initialize the  weather."""
        self._name = None
        self._object_id = object_id
        self._attr_unique_id = object_id
        self._condition = None
        self._humidity = None
        self._pressure = None
        self._wind_speed = None
        self._wind_bearing = None
        self._forecast = None

        self._data = data
        self._updatetime = None
        self._aqi = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._object_id

    @property
    def registry_name(self):
        """返回实体的friendly_name属性."""
        return '{} {}'.format('和风天气', self._name)

    @property
    def should_poll(self):
        """attention No polling needed for a demo weather condition."""
        return True

    @property
    def humidity(self):
        """Return the humidity."""
        return self._humidity

    @property
    def wind_bearing(self):
        """Return the wind speed."""
        return self._wind_bearing

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self._wind_speed

    @property
    def pressure(self):
        """Return the pressure."""
        return self._pressure

    @property
    def condition(self):
        """Return the weather condition."""
        try:
            # print(self._condition)
            if self._condition:
                return [k for k, v in CONDITION_CLASSES.items() if self._condition in v][0]            
        except Exception as ex:
            pass
        return 'unknown'

    @property
    def attribution(self):
        """Return the attribution."""
        return 'Powered by Home Assistant'

    @property
    def state_attributes(self):
        attributes = super().state_attributes
        """设置其它一些属性值."""
        if self._condition is not None:
            attributes.update({
                "city": self._name,
                ATTR_ATTRIBUTION: ATTRIBUTION,
                ATTR_UPDATE_TIME: self._updatetime,
                ATTR_CONDITION_CN: self._condition,
                ATTR_AQI: self._aqi,
                ATTR_HOURLY_FORECAST: self.hourly_forecast,
                ATTR_SUGGESTION: self._suggestion,
                ATTR_CUSTOM_UI_MORE_INFO: "hf_weather-more-info"
            })
        return attributes

    @property
    def forecast(self):
        """Return the forecast."""
        if self._daily_forecast is None:
            return None
        reftime = datetime.now()

        forecast_data = []
        _LOGGER.debug('daily_forecast: %s', self._daily_forecast)
        for entry in self._daily_forecast:
            data_dict = {
                ATTR_FORECAST_CONDITION: entry[0],
                ATTR_FORECAST_TEMP: entry[1],
                ATTR_FORECAST_TEMP_LOW: entry[2],
                ATTR_FORECAST_TIME: entry[3],
                ATTR_FORECAST_PRECIPITATION: entry[4],
                ATTR_FORECAST_PROBABLE_PRECIPITATION: entry[5]
            }
            reftime = reftime + timedelta(days=1)
            forecast_data.append(data_dict)
        # _LOGGER.debug('forecast_data: %s', forecast_data)
        return forecast_data

    @property
    def hourly_forecast(self):
        """Return the forecast."""
        if self._hourly_forecast is None:
            return None
        forecast_data = []
        _LOGGER.debug('hourly_forecast: %s', self._hourly_forecast)
        for entry in self._hourly_forecast:
            data_dict = {
                ATTR_FORECAST_CONDITION: entry[0],
                ATTR_FORECAST_TEMP: entry[1],
                ATTR_FORECAST_TIME: entry[2],
                ATTR_FORECAST_PROBABLE_PRECIPITATION: entry[3],
                "condition_cn": entry[4]
            }
            forecast_data.append(data_dict)
        # _LOGGER.debug('hourly_forecast_data: %s', forecast_data)
        return forecast_data

    async def async_update(self):
        """update函数变成了async_update."""
        self._updatetime = self._data.updatetime
        self._name = self._data.name
        self._condition = self._data.condition
        self._attr_temperature = self._data.temperature
        self._attr_temperature_unit = self._data.temperature_unit
        self._humidity = self._data.humidity
        self._pressure = self._data.pressure
        self._wind_speed = self._data.wind_speed
        self._wind_bearing = self._data.wind_bearing
        self._daily_forecast = self._data.daily_forecast
        self._hourly_forecast = self._data.hourly_forecast
        self._aqi = self._data.aqi
        self._suggestion = self._data.suggestion
        # _LOGGER.debug("success to update informations")


class WeatherData(object):
    """天气相关的数据，存储在这个类中."""

    def __init__(self, hass, city, appkey):
        """初始化函数."""
        self._hass = hass

        self._params = {"location": city,
                        "key": appkey}


        self._name = None
        self._condition = None
        self._temperature = None
        self._temperature_unit = None
        self._humidity = None
        self._pressure = None
        self._wind_speed = None
        self._wind_bearing = None
        self._forecast = None
        self._updatetime = None
        self._daily_forecast = None
        self._hourly_forecast = None
        self._aqi = None
        self._suggestion = None

    @property
    def name(self):
        """地点."""
        return self._name

    @property
    def condition(self):
        """天气情况."""
        return self._condition

    @property
    def temperature(self):
        """温度."""
        return self._temperature

    @property
    def temperature_unit(self):
        """温度单位."""
        return TEMP_CELSIUS

    @property
    def humidity(self):
        """湿度."""
        return self._humidity

    @property
    def pressure(self):
        """气压."""
        return self._pressure

    @property
    def wind_speed(self):
        """风速."""
        return self._wind_speed
    
    @property
    def wind_bearing(self):
        """风向."""
        return self._wind_bearing

    @property
    def daily_forecast(self):
        """预报."""
        return self._daily_forecast

    @property
    def hourly_forecast(self):
        """小时预报."""
        return self._hourly_forecast

    @property
    def updatetime(self):
        """更新时间."""
        return self._updatetime
 
    @property
    def aqi(self):
        """空气质量."""
        return self._aqi

    @property
    def suggestion(self):
        """生活建议."""
        return self._suggestion
    
    def format_datetime(self, input_time):
        parsed_time = datetime.fromisoformat(input_time)
        return parsed_time.strftime("%Y-%m-%d %H:%M")


    async def fetch_url(self, session, url, params):
        async with session.get(url, params=params) as response:
            return await response.json()
        
    def parse_condition(self, text):
        match_list = [k for k, v in CONDITION_CLASSES.items() if text in v]
        return match_list[0] if match_list else 'unknown'

    async def async_update(self, now):
        """从远程更新信息."""
        _LOGGER.info("Update from JingdongWangxiang's OpenAPI...")

        endpoits = ['basic', 'aqi', 'now', '7d', '24h', 'suggestion']
        urls = [
        'https://geoapi.qweather.com/v2/city/lookup',
        'https://devapi.qweather.com/v7/air/now',
        'https://devapi.qweather.com/v7/weather/now',
        'https://devapi.qweather.com/v7/weather/7d',
        'https://devapi.qweather.com/v7/weather/24h',
        'https://devapi.qweather.com/v7/indices/1d?type=1,2,3,5,6,8,9,10']

        params = self._params

        session = async_get_clientsession(self._hass)
        tasks = [self.fetch_url(session, url, params) for url in urls]
        results = await asyncio.gather(*tasks)
        for endpoint, result in zip(endpoits, results):
            _LOGGER.warn(f'Response from {endpoint}: {str(result)}...')
            if result is not None and result["code"] == '200':
                
                 if endpoint == 'aqi':
                     self._aqi = {
                    "aqi": result["now"]["aqi"],
					"qlty": result["now"]["category"],
					"pm25": result["now"]["pm2p5"],
					"pm10": result["now"]["pm10"],
					"no2": result["now"]["no2"],
					"so2": result["now"]["so2"],
					"co": result["now"]["co"],
					"o3": result["now"]["o3"],}
                 elif endpoint == 'basic':
                     self._name = result["location"][0]["name"]
                 elif endpoint == 'now':
                     self._temperature = float(result["now"]["temp"])
                     self._humidity = int(result["now"]["humidity"])
                     self._pressure = int(result["now"]["pressure"])
                     self._wind_speed = float(result["now"]["windSpeed"])
                     self._wind_bearing = float(result["now"]["wind360"])
                     self._updatetime = self.format_datetime(result["updateTime"])
                     self._condition = result["now"]["text"]
                 elif endpoint == 'suggestion':
                     self._suggestion = [{'title': TRANSLATE_SUGGESTION.get(suggestion["type"], suggestion["type"]), 'title_cn': suggestion["name"], 'brf': suggestion["category"], 'txt': suggestion["text"] } for suggestion in result["daily"]]
                 elif endpoint == '7d':
                     self._daily_forecast = [[self.parse_condition(forecast["textDay"]), int(forecast["tempMax"]), int(forecast["tempMin"]), forecast["fxDate"], forecast["precip"], "0"] for forecast in result["daily"]]
                 elif endpoint == '24h':
                     latest7h = result["hourly"][:7]
                     self._hourly_forecast = [[hour["text"], int(hour["temp"]), self.format_datetime(hour["fxTime"]), hour["pop"], hour['precip']] for hour in latest7h]
            else: 
                return

