#!/usr/bin/env python3
"""Shared PGD formula and station-aggregation vocabulary."""

from __future__ import annotations


STATION_AGGREGATION_METHOD = "median"
STATION_AGGREGATION_METHODS = (STATION_AGGREGATION_METHOD,)
METHOD_CONTRACT = "one_station_aggregation_method"
FORMULA_COMPARISON_SCOPE = "formula_only"
FORMULA_NAMES = ("melgar_2015", "crowell_2016_gfast", "ruhl_2019")


def is_median_station_aggregation(value: object) -> bool:
    return str(value or "").strip() == STATION_AGGREGATION_METHOD
