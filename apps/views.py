# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

# Flask modules
from flask   import render_template, request, send_file, send_from_directory, make_response
from jinja2  import TemplateNotFound
import matplotlib



# App modules
from apps import app
from flask_caching import Cache

from io import StringIO

cache = Cache(app,config={'CACHE_TYPE': 'simple','CACHE_DEFAULT_TIMEOUT':3600})

app.config['UPLOAD_FOLDER'] = 'data'

# Import Data
import pandas as pd
import numpy as np
from datetime import datetime
from matplotlib import pyplot as plt
matplotlib.use('agg')
import seaborn as sb
import os

#weather_data = pd.read_csv(os.path.join(app.root_path,'data','gsod_clean_extract.csv'))
weather_data = pd.read_csv(os.path.join(app.root_path,'data','gsod_zip_extract.csv'))



weather_data['DATE'] = pd.to_datetime(dict(year=weather_data.Year, month=weather_data.Mo, day=weather_data.Da))
#weather_data = weather_data.drop('date',axis=1)
weather_data= weather_data.sort_values(by=['Station_ID','DATE'], ascending=[True,True])
station_list = weather_data[['Station_ID','Station_Name']].drop_duplicates(subset=['Station_ID'])
weather_data = pd.merge(weather_data, station_list,how="outer", on=["Station_ID"])
weather_data = weather_data.drop(['Station_Name_x'],axis=1)
weather_data.rename(columns = {"Station_Name_y": "Station_Name",
                               "Year":"year",
                               "Da":"DAY",
                               "Mo":"MONTH",
                                "Temp":"AVG_TEMP",
                                "Max":"MAX_TEMP",
                                "Min":"MIN_TEMP"}, 
          inplace = True)

weather_data['MONTH'] = weather_data['DATE'].dt.strftime('%b')

# Correct Max / Min Temp days
# Where MAX/MIN are both null or 999.9 = Min/Max = Avg
weather_data.loc[ (weather_data['MIN_TEMP']==9999.9) & (weather_data['MAX_TEMP'] == 9999.9),['MIN_TEMP','MAX_TEMP']] = weather_data['AVG_TEMP']
# Where MAX/AVG are known but MIN is not....calculate MIN
weather_data.loc[ (weather_data['MIN_TEMP']==9999.9) & (weather_data['MAX_TEMP'] != 9999.9),['MIN_TEMP']] = (weather_data['AVG_TEMP']*2)-weather_data['MAX_TEMP']
# Where MIN/AVG are known but MAX is not....calculate MAX
weather_data.loc[ (weather_data['MIN_TEMP']!=9999.9) & (weather_data['MAX_TEMP'] == 9999.9),['MAX_TEMP']] = (weather_data['AVG_TEMP']*2)-weather_data['MIN_TEMP']

#weather_data['DATE'] = pd.to_datetime(weather_data['DATE'])
desc_cols = ['Station_ID',
             'Station_Name',
             'DATE',
             'year',
             'MONTH',
             'DAY',
             'Latitude',
             'Longitude',
             'zip_code'
             'city',
             'county']

temp_cols = ['AVG_TEMP',
             'MAX_TEMP',
             'MIN_TEMP']

precip_cols = ['Prcp']


cache.set("weather_data", weather_data)
cache.set('descriptive_columns',desc_cols)
cache.set('precipitation_columns',precip_cols)
cache.set('temperature_columns',temp_cols)



# App main route + generic routing
@app.route('/temperature_analysis', methods=['GET','POST'])
def display_temp():
     temp_threshold = list(range(88,110))

     if request.method == 'GET':
        df = cache.get("weather_data")

        if all(col in df.columns for col in cache.get("precipitation_columns")):
            df = df.drop(cache.get("precipitation_columns"),axis=1)
        else:
            df = df
        
        cache.set("view_rain_data",df)
        df_values = df.values
        labels = [row for row in df.columns]
        num_columns = df.shape[1]

        stations = sorted(df['Station_Name'].unique())
        max_date = str(df['DATE'].max().strftime("%Y-%m-%d")) 
        min_date = str(df['DATE'].min().strftime("%Y-%m-%d"))

        # Daily Line Chart Data
        date_range = [np.datetime64(date) for date in df['DATE'].unique()]
        date_range = pd.to_datetime(date_range)
        date_range = [str(value.date()) for value in date_range]

        temp_data_clean = df.dropna(subset=['AVG_TEMP', 'MAX_TEMP','MIN_TEMP'])
        df_values_avg = temp_data_clean[['DATE','AVG_TEMP',"MAX_TEMP","MIN_TEMP"]].groupby("DATE", as_index=False).mean()
        df_values_max = temp_data_clean[['DATE','AVG_TEMP',"MAX_TEMP","MIN_TEMP"]].groupby("DATE", as_index=False).max()
        df_values_min = temp_data_clean[['DATE','AVG_TEMP',"MAX_TEMP","MIN_TEMP"]].groupby("DATE", as_index=False).min()

        df_values_avg = [value for value in df_values_avg['AVG_TEMP']]
        df_values_max = [value for value in df_values_max['MAX_TEMP']]
        df_values_min = [value for value in df_values_min['MIN_TEMP']]

        temp_max_axis = np.round(max(df_values_max) *1.05,0)
        temp_min_axis =  0 if  min(df_values_min)>0 else np.round(min(df_values_min)* 1.05,0)


        ##### Create Monthly Line Chart Data
        df_values_avg_monthly = temp_data_clean[['MONTH','year','DATE','AVG_TEMP',"MAX_TEMP","MIN_TEMP"]].groupby(['MONTH','year'], as_index=False).mean()
        df_values_max_monthly = temp_data_clean[['MONTH','year','DATE','AVG_TEMP',"MAX_TEMP","MIN_TEMP"]].groupby(['MONTH','year'], as_index=False).max()
        df_values_min_monthly = temp_data_clean[['MONTH','year','DATE','AVG_TEMP',"MAX_TEMP","MIN_TEMP"]].groupby(['MONTH','year'], as_index=False).min()

        df_values_avg_monthly = [value for value in df_values_avg_monthly['AVG_TEMP']]
        df_values_max_monthly = [value for value in df_values_max_monthly['MAX_TEMP']]
        df_values_min_monthly = [value for value in df_values_min_monthly['MIN_TEMP']]

        date_range_monthly = df['DATE'].dt.strftime("%m/%y").unique().tolist()
       # date_range_monthly = df['DATE'].dt.unique().tolist()


       ###### Create BoxPlot
        dfl = pd.melt(df, id_vars='MONTH', value_vars=["MAX_TEMP","MIN_TEMP"])
        plt.clf()
        colors = ["#FF0000", "#0275D8"]
        sb.set_palette(sb.color_palette(colors))
        plot = sb.boxplot(x='MONTH', y='value', data=dfl, showfliers=False, hue='variable')
        #plt.legend(bbox_to_anchor=(1.04,0.5), loc="center left", borderaxespad=0)
        plt.legend([],[], frameon=False)
              
        #set axis names
        plot.set(xlabel='Month',
                 ylabel='Temperature')
        
        #boxplot_url = str(os.path.join(app.root_path,'static','assets','img','temp_box.png'))
        plt.savefig(os.path.join(app.root_path, 'static','assets','img','temp_box.png'))
        #plt.savefig(boxplot_url)
        boxplot_url = '/static/assets/img/temp_box.png'
        


        ##### Render Template
        
        return render_template('home/temperature_analysis copy.html',max_date=max_date,min_date=min_date, df_values=df_values, labels=labels,
                               num_columns=num_columns, stations = stations, date_range = date_range, temp_max_axis = temp_max_axis,temp_min_axis = temp_min_axis,
                               df_values_avg=df_values_avg,df_values_max=df_values_max,df_values_min=df_values_min,
                               df_values_avg_monthly = df_values_avg_monthly, df_values_max_monthly=df_values_max_monthly,df_values_min_monthly=df_values_min_monthly,
                               date_range_monthly=date_range_monthly,temp_threshold=temp_threshold, boxplot_name = boxplot_url ,boxplot_url = boxplot_url)
     
     if request.method == 'POST':

        df = cache.get("weather_data")
        if all(col in df.columns for col in cache.get("precipitation_columns")):
            df = df.drop(cache.get("precipitation_columns"),axis=1)
        else:
            df = df

        stations = sorted(df['Station_Name'].unique())
        max_date = str(df['DATE'].max().strftime("%Y-%m-%d")) 
        min_date = str(df['DATE'].min().strftime("%Y-%m-%d"))

        location_filter = request.form.getlist('Station_Select2')
        start_date_filter = request.form.get('temp-start2')
        end_date_filter = request.form.get("temp-end2")
        
        
        df = df[df['Station_Name'].isin(location_filter)]

        if len(df[df["DATE"]<=pd.to_datetime(end_date_filter)]) == 0:
            df = df.append(df.head(1),ignore_index=True)
            df.loc[len(df)-1,['DATE','year','MONTH','DAY','AVG_TEMP','MAX_TEMP','MIN_TEMP']] = [pd.to_datetime(end_date_filter),np.NaN,np.NaN,np.NaN,0,0,0]

        df = df[(df['DATE']<=end_date_filter) & (df['DATE']>=start_date_filter) ]

        cache.set("view_rain_data",df)

        df_values = df.values
        labels = [row for row in df.columns]
        num_columns = df.shape[1]    

        date_range = [np.datetime64(date) for date in df['DATE'].unique()]
        date_range = pd.to_datetime(date_range)
        date_range = [str(value.date()) for value in date_range]

        temp_data_clean = df.dropna(subset=['AVG_TEMP', 'MAX_TEMP','MIN_TEMP'])
        df_values_avg = temp_data_clean[['DATE','AVG_TEMP',"MAX_TEMP","MIN_TEMP"]].groupby("DATE", as_index=False).mean()
        df_values_max = temp_data_clean[['DATE','AVG_TEMP',"MAX_TEMP","MIN_TEMP"]].groupby("DATE", as_index=False).max()
        df_values_min = temp_data_clean[['DATE','AVG_TEMP',"MAX_TEMP","MIN_TEMP"]].groupby("DATE", as_index=False).min()

        df_values_avg = [value for value in df_values_avg['AVG_TEMP']]
        df_values_max = [value for value in df_values_max['MAX_TEMP']]
        df_values_min = [value for value in df_values_min['MIN_TEMP']]

        temp_max_axis = max(df_values_max) * 1.05
        temp_min_axis =  0 if  min(df_values_min)>0 else min(df_values_min)* 1.05
        
        

        ##### Create Monthly Line Chart Data
        df_values_avg_monthly = temp_data_clean[['MONTH','year','DATE','AVG_TEMP',"MAX_TEMP","MIN_TEMP"]].groupby(['MONTH','year'], as_index=False).mean()
        df_values_max_monthly = temp_data_clean[['MONTH','year','DATE','AVG_TEMP',"MAX_TEMP","MIN_TEMP"]].groupby(['MONTH','year'], as_index=False).max()
        df_values_min_monthly = temp_data_clean[['MONTH','year','DATE','AVG_TEMP',"MAX_TEMP","MIN_TEMP"]].groupby(['MONTH','year'], as_index=False).min()

        df_values_avg_monthly = [value for value in df_values_avg_monthly['AVG_TEMP']]
        df_values_max_monthly = [value for value in df_values_max_monthly['MAX_TEMP']]
        df_values_min_monthly = [value for value in df_values_min_monthly['MIN_TEMP']]

        date_range_monthly = df['DATE'].dt.strftime("%m/%y").unique().tolist()

        ###### Create BoxPlot
        dfl = pd.melt(df, id_vars='MONTH', value_vars=["MAX_TEMP","MIN_TEMP"])
        plt.clf()
        colors = ["#FF0000", "#0275D8"]
        sb.set_palette(sb.color_palette(colors))
        plot = sb.boxplot(x='MONTH', y='value', data=dfl, showfliers=False,hue="variable")
        
        #plot = sb.boxplot(x='MONTH', y='value', data=dfl, showfliers=False, hue='variable')
        #plt.legend(bbox_to_anchor=(1.04,0.5), loc="center left", borderaxespad=0)
        plt.legend([],[], frameon=False)
              
        #set axis names
        plot.set(xlabel='Month',
                 ylabel='Temperature')
        #boxplot_url = str(os.path.join(app.root_path,'static','assets','img','temp_box.png'))
        plt.savefig(os.path.join(app.root_path, 'static','assets','img','temp_box.png'))
        #plt.savefig(boxplot_url)
        boxplot_url = '/static/assets/img/temp_box.png'

        ##### Render Template
        
        return render_template('home/temperature_analysis copy.html',max_date=max_date,min_date=min_date, df_values=df_values, labels=labels,
                               num_columns=num_columns, stations = stations, date_range = date_range, temp_max_axis = temp_max_axis,temp_min_axis = temp_min_axis,
                               df_values_avg=df_values_avg,df_values_max=df_values_max,df_values_min=df_values_min,
                               df_values_avg_monthly = df_values_avg_monthly, df_values_max_monthly=df_values_max_monthly,df_values_min_monthly=df_values_min_monthly,
                               date_range_monthly=date_range_monthly,temp_threshold=temp_threshold, boxplot_name = boxplot_url ,boxplot_url = boxplot_url)
                
        #return render_template('home/temperature_analysis copy.html',max_date=max_date,min_date=min_date, df_values=df_values, labels=labels,num_columns=num_columns, stations = stations, location_filter=location_filter,start_date_filter=start_date_filter)


    

# App main route + generic routing
@app.route('/temperature_table', methods = ['GET','POST'])
def display_temperature():

    if request.method == 'GET':
        df = cache.get("weather_data")
        if all(col in df.columns for col in cache.get("precipitation_columns")):
            df = df.drop(cache.get("precipitation_columns"),axis=1)
        else:
            df = df

        cache.set("view_rain_data",df)

        df_values = df.values
        labels = [row for row in df.columns]
        num_columns = df.shape[1]

        stations = sorted(df['Station_Name'].unique())
        max_date = str(df['DATE'].max().strftime("%Y-%m-%d")) 
        min_date = str(df['DATE'].min().strftime("%Y-%m-%d"))
        
        
        
        return render_template('home/temperature_table.html',max_date=max_date,min_date=min_date, df_values=df_values, 
                               labels=labels,num_columns=num_columns, stations = stations)
    if request.method == 'POST':

        df = cache.get("weather_data")
        if all(col in df.columns for col in cache.get("precipitation_columns")):
            df = df.drop(cache.get("precipitation_columns"),axis=1)
        else:
            df = df

        stations = sorted(df['Station_Name'].unique())
        max_date = str(df['DATE'].max().strftime("%Y-%m-%d")) 
        min_date = str(df['DATE'].min().strftime("%Y-%m-%d"))

        location_filter = request.form.getlist('Station_Select')
        start_date_filter = request.form.get('temp-start')
        end_date_filter = request.form.get("temp-end")
        
        
        df = df[df['Station_Name'].isin(location_filter)]
        
        if len(df[df["DATE"]<=end_date_filter]) == 0:
            df = df.append(df.head(1),ignore_index=True)
            df.loc[len(df)-1,['DATE','year','MONTH','DAY','AVG_TEMP','MAX_TEMP','MIN_TEMP']] = [pd.to_datetime(end_date_filter),np.NaN,np.NaN,np.NaN,np.NaN,np.NaN,np.NaN]

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
        
