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

weather_data = pd.read_csv(os.path.join(app.root_path,'data','VA GHCND 2019_06_01_2023.csv'))
weather_data['DATE'] = pd.to_datetime(weather_data['DATE'])
desc_cols = ['STATION',
             'NAME',
             'LATITUDE',
             'LONGITUDE',
             'ELEVATION',
             'DATE']

temp_cols = ['TAVG',
             'TAVG_ATTRIBUTES',
             'TMAX',
             'TMAX_ATTRIBUTES',
             'TMIN',
             'TMIN_ATTRIBUTES',
             'TOBS',
             'TOBS_ATTRIBUTES']

precip_cols = ['DAPR',
             'DAPR_ATTRIBUTES',
             'MDPR',
             'MDPR_ATTRIBUTES',
             'PRCP',
             'PRCP_ATTRIBUTES',
             'SNOW',
             'SNOW_ATTRIBUTES',
            'SNWD',
            'SNWD_ATTRIBUTES']

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

        stations = sorted(df['NAME'].unique())
        max_date = str(df['DATE'].max().strftime("%Y-%m-%d")) 
        min_date = str(df['DATE'].min().strftime("%Y-%m-%d"))
        date_range = df['DATE'].unique()
        date_range = [str(value) for value in date_range]

        temp_data_clean = df.dropna(subset=['TAVG', 'TMAX','TMIN'])
        df_values_avg = temp_data_clean[['DATE','TAVG',"TMAX","TMIN"]].groupby("DATE", as_index=False).mean()
        df_values_max = temp_data_clean[['DATE','TAVG',"TMAX","TMIN"]].groupby("DATE", as_index=False).max()
        df_values_min = temp_data_clean[['DATE','TAVG',"TMAX","TMIN"]].groupby("DATE", as_index=False).min()

        df_values_avg = [value for value in df_values_avg['TAVG']]
        df_values_max = [value for value in df_values_max['TMAX']]
        df_values_min = [value for value in df_values_min['TMIN']]

        temp_max_axis = max(df_values_max) *1.05
        
        return render_template('home/temperature_analysis copy.html',max_date=max_date,min_date=min_date, df_values=df_values, labels=labels,
                               num_columns=num_columns, stations = stations, date_range = date_range, temp_max_axis = temp_max_axis,
                               df_values_avg=df_values_avg,df_values_max=df_values_max,df_values_min=df_values_min)
     
     if request.method == 'POST':

        df = cache.get("weather_data")
        df = df.drop(cache.get("precipitation_columns"),axis=1)

        stations = sorted(df['NAME'].unique())
        max_date = str(df['DATE'].max().strftime("%Y-%m-%d")) 
        min_date = str(df['DATE'].min().strftime("%Y-%m-%d"))

        location_filter = request.form.getlist('Station_Select2')
        start_date_filter = request.form.get('rain-start2')
        end_date_filter = request.form.get("rain-end2")
        
        
        df = df[df['NAME'].isin(location_filter)]
        df = df[(df['DATE']<=end_date_filter) & (df['DATE']>=start_date_filter) ]

        cache.set("view_rain_data",df)

        df_values = df.values
        labels = [row for row in df.columns]
        num_columns = df.shape[1]    

        date_range = df['DATE'].unique()
        date_range = [str(value) for value in date_range]

        temp_data_clean = df.dropna(subset=['TAVG', 'TMAX','TMIN'])
        df_values_avg = temp_data_clean[['DATE','TAVG',"TMAX","TMIN"]].groupby("DATE", as_index=False).mean()
        df_values_max = temp_data_clean[['DATE','TAVG',"TMAX","TMIN"]].groupby("DATE", as_index=False).max()
        df_values_min = temp_data_clean[['DATE','TAVG',"TMAX","TMIN"]].groupby("DATE", as_index=False).min()

        df_values_avg = [value for value in df_values_avg['TAVG']]
        df_values_max = [value for value in df_values_max['TMAX']]
        df_values_min = [value for value in df_values_min['TMIN']]

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

        stations = sorted(df['NAME'].unique())
        max_date = str(df['DATE'].max().strftime("%Y-%m-%d")) 
        min_date = str(df['DATE'].min().strftime("%Y-%m-%d"))
        
        
        
        return render_template('home/temperature_table.html',max_date=max_date,min_date=min_date, df_values=df_values, 
                               labels=labels,num_columns=num_columns, stations = stations)
    if request.method == 'POST':

        df = cache.get("weather_data")
        df = df.drop(cache.get("precipitation_columns"),axis=1)

        stations = sorted(df['NAME'].unique())
        max_date = str(df['DATE'].max().strftime("%Y-%m-%d")) 
        min_date = str(df['DATE'].min().strftime("%Y-%m-%d"))

        location_filter = request.form.getlist('Station_Select')
        start_date_filter = request.form.get('rain-start')
        end_date_filter = request.form.get("rain-end")
        
        
        df = df[df['NAME'].isin(location_filter)]
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
        
