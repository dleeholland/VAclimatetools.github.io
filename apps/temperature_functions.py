# Temperature Functions

# important packages
import pandas as pd
from apps import app
from datetime import datetime
import os
from flask   import render_template, request

def get_daily_line_data(df,min_date,max_date,request_type):

    # First Check if this is a POST Request (i.e. filters need to be applied)
    if request_type == 'POST':
        county_filter = request.form.getlist('County_Select')
        start_date_filter = request.form.get('temp-start2')
        end_date_filter = request.form.get("temp-end2")
        max_heat_threshold_filter = request.form.get("max-heat-options")
        min_heat_threshold_filter = request.form.get("min-heat-options")
    else:
        max_heat_threshold_filter = 90
        min_heat_threshold_filter = 80
        start_date_filter = min_date
        end_date_filter = max_date

    