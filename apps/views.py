# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

# Flask modules
from flask   import render_template, request, send_file, send_from_directory, make_response
from jinja2  import TemplateNotFound



# App modules
from apps import app
from flask_caching import Cache

from io import StringIO

cache = Cache(app,config={'CACHE_TYPE': 'simple'})

app.config['UPLOAD_FOLDER'] = 'data'

# Import Data
import pandas as pd
from datetime import datetime
import os

weather_data = pd.read_csv(os.path.join(app.root_path,'data','gsod_clean_extract.csv'))
weather_data['DATE'] = pd.to_datetime(dict(year=weather_data.year, month=weather_data.MONTH, day=weather_data.DAY))

# Correct Max / Min Temp days
# Where MAX/MIN are both null or 999.9 = Min/Max = Avg
weather_data.loc[ (weather_data['MIN_TEMP']==9999.9) & (weather_data['MAX_TEMP'] == 9999.9),['MIN_TEMP','MAX_TEMP']] = weather_data['AVG_TEMP']
# Where MAX/AVG are known but MIN is not....calculate MIN
weather_data.loc[ (weather_data['MIN_TEMP']==9999.9) & (weather_data['MAX_TEMP'] != 9999.9),['MIN_TEMP']] = (weather_data['AVG_TEMP']*2)-weather_data['MAX_TEMP']
# Where MIN/AVG are known but MAX is not....calculate MAX
weather_data.loc[ (weather_data['MIN_TEMP']!=9999.9) & (weather_data['MAX_TEMP'] == 9999.9),['MAX_TEMP']] = (weather_data['AVG_TEMP']*2)-weather_data['MIN_TEMP']

#weather_data['DATE'] = pd.to_datetime(weather_data['DATE'])
desc_cols = ['stn',
             'name',
             'date',
             'year',
             'MONTH',
             'DAY',
             'country',
             'state',
             'begin',
             'end']

temp_cols = ['AVG_TEMP',
             'MAX_TEMP',
             'MIN_TEMP']

precip_cols = ['prcp']

cache.set("weather_data", weather_data)
cache.set('descriptive_columns',desc_cols)
cache.set('precipitation_columns',precip_cols)
cache.set('temperature_columns',temp_cols)



# App main route + generic routing
@app.route('/temperature_analysis', methods=['GET','POST'])
def display_temp():

     if request.method == 'GET':
        df = cache.get("weather_data")
        df = df.drop(cache.get("precipitation_columns"),axis=1)
        cache.set("view_rain_data",df)
        df_values = df.values
        labels = [row for row in df.columns]
        num_columns = df.shape[1]

        stations = sorted(df['name'].unique())
        max_date = str(df['DATE'].max().strftime("%Y-%m-%d")) 
        min_date = str(df['DATE'].min().strftime("%Y-%m-%d"))
        date_range = df['DATE'].unique()
        date_range = [str(value) for value in date_range]

        temp_data_clean = df.dropna(subset=['AVG_TEMP', 'MAX_TEMP','MIN_TEMP'])
        df_values_avg = temp_data_clean[['DATE','AVG_TEMP',"MAX_TEMP","MIN_TEMP"]].groupby("DATE", as_index=False).mean()
        df_values_max = temp_data_clean[['DATE','AVG_TEMP',"MAX_TEMP","MIN_TEMP"]].groupby("DATE", as_index=False).max()
        df_values_min = temp_data_clean[['DATE','AVG_TEMP',"MAX_TEMP","MIN_TEMP"]].groupby("DATE", as_index=False).min()

        df_values_avg = [value for value in df_values_avg['AVG_TEMP']]
        df_values_max = [value for value in df_values_max['MAX_TEMP']]
        df_values_min = [value for value in df_values_min['MIN_TEMP']]

        temp_max_axis = max(df_values_max) *1.05
        
        return render_template('home/temperature_analysis copy.html',max_date=max_date,min_date=min_date, df_values=df_values, labels=labels,
                               num_columns=num_columns, stations = stations, date_range = date_range, temp_max_axis = temp_max_axis,
                               df_values_avg=df_values_avg,df_values_max=df_values_max,df_values_min=df_values_min)
     
     if request.method == 'POST':

        df = cache.get("weather_data")
        df = df.drop(cache.get("precipitation_columns"),axis=1)

        stations = sorted(df['name'].unique())
        max_date = str(df['DATE'].max().strftime("%Y-%m-%d")) 
        min_date = str(df['DATE'].min().strftime("%Y-%m-%d"))

        location_filter = request.form.getlist('Station_Select2')
        start_date_filter = request.form.get('rain-start2')
        end_date_filter = request.form.get("rain-end2")
        
        
        df = df[df['name'].isin(location_filter)]
        df = df[(df['DATE']<=end_date_filter) & (df['DATE']>=start_date_filter) ]

        cache.set("view_rain_data",df)

        df_values = df.values
        labels = [row for row in df.columns]
        num_columns = df.shape[1]    

        date_range = df['DATE'].unique()
        date_range = [str(value) for value in date_range]

        temp_data_clean = df.dropna(subset=['AVG_TEMP', 'MAX_TEMP','MIN_TEMP'])
        df_values_avg = temp_data_clean[['DATE','AVG_TEMP',"MAX_TEMP","MIN_TEMP"]].groupby("DATE", as_index=False).mean()
        df_values_max = temp_data_clean[['DATE','AVG_TEMP',"MAX_TEMP","MIN_TEMP"]].groupby("DATE", as_index=False).max()
        df_values_min = temp_data_clean[['DATE','AVG_TEMP',"MAX_TEMP","MIN_TEMP"]].groupby("DATE", as_index=False).min()

        df_values_avg = [value for value in df_values_avg['AVG_TEMP']]
        df_values_max = [value for value in df_values_max['MAX_TEMP']]
        df_values_min = [value for value in df_values_min['MIN_TEMP']]

        temp_max_axis = max(df_values_max) *1.05
        
        return render_template('home/temperature_analysis copy.html',max_date=max_date,min_date=min_date, df_values=df_values, labels=labels,
                               num_columns=num_columns, stations = stations, date_range = date_range,temp_max_axis = temp_max_axis,
                               df_values_avg=df_values_avg,df_values_max=df_values_max,df_values_min=df_values_min)
                
        #return render_template('home/temperature_analysis copy.html',max_date=max_date,min_date=min_date, df_values=df_values, labels=labels,num_columns=num_columns, stations = stations, location_filter=location_filter,start_date_filter=start_date_filter)


    

# App main route + generic routing
@app.route('/temperature_table', methods = ['GET','POST'])
def display_temperature():

    if request.method == 'GET':
        df = cache.get("weather_data")
        df = df.drop(cache.get("precipitation_columns"),axis=1)

        cache.set("view_rain_data",df)

        df_values = df.values
        labels = [row for row in df.columns]
        num_columns = df.shape[1]

        stations = sorted(df['name'].unique())
        max_date = str(df['DATE'].max().strftime("%Y-%m-%d")) 
        min_date = str(df['DATE'].min().strftime("%Y-%m-%d"))
        
        
        
        return render_template('home/temperature_table.html',max_date=max_date,min_date=min_date, df_values=df_values, 
                               labels=labels,num_columns=num_columns, stations = stations)
    if request.method == 'POST':

        df = cache.get("weather_data")
        df = df.drop(cache.get("precipitation_columns"),axis=1)

        stations = sorted(df['name'].unique())
        max_date = str(df['DATE'].max().strftime("%Y-%m-%d")) 
        min_date = str(df['DATE'].min().strftime("%Y-%m-%d"))

        location_filter = request.form.getlist('Station_Select')
        start_date_filter = request.form.get('rain-start')
        end_date_filter = request.form.get("rain-end")
        
        
        df = df[df['name'].isin(location_filter)]
        df = df[(df['DATE']<=end_date_filter) & (df['DATE']>=start_date_filter) ]

        cache.set("view_rain_data",df)

        df_values = df.values
        labels = [row for row in df.columns]
        num_columns = df.shape[1]

       
        
        
        return render_template('home/temperature_table.html',max_date=max_date,min_date=min_date, df_values=df_values, labels=labels,num_columns=num_columns, stations = stations, location_filter=location_filter,start_date_filter=start_date_filter)


@app.route('/download_rain_data')
def download_rain():
    
    df = cache.get("view_rain_data")

    resp = make_response(df.to_csv())
    resp.headers["Content-Disposition"] = "attachment; filename= VCC_Temperature_Data_Export_on_{}.csv".format(datetime.today().strftime('%Y-%m-%d %I:%M:%S:%p'))
    resp.headers["Content-Type"] = "text/csv"

    return resp
    

# App main route + generic routing
@app.route('/precipitation_analysis', methods=['GET','POST'])
def display_precip():

    return render_template('home/precipitation_analysis.html')

# App main route + generic routing
@app.route('/precipitation_table', methods = ['GET','POST'])
def display_precipitation():

    if request.method == 'POST' or request.method == 'GET':
        df = cache.get("weather_data")
        df = df.drop(cache.get("temperature_columns"),axis=1)
        df_values = df.values
        labels = [row for row in df.columns]
        num_columns = df.shape[1]
        
        return render_template('home/precipitation_table.html', df_values=df_values, labels=labels,num_columns=num_columns)


@app.route('/', defaults={'path': 'index.html'})
@app.route('/<path>')
def index(path):
        

    try:

        # Detect the current page
        segment = get_segment( request )

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template( 'home/' + path, segment=segment )
    
    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

def get_segment( request ): 

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'index'

        return segment    

    except:
        return None  
        
