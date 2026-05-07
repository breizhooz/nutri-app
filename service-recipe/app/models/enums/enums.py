from enum import Enum as PyEnum


class Seasonality(str, PyEnum):
    SPRING = "enums.seasonality.spring"
    SUMMER = "enums.seasonality.summer"
    AUTuMN = "enums.seasonality.autumn"
    WINTER = "enums.seasonality.winter"
