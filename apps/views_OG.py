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
from google.cloud import bigquery
from google.oauth2 import service_account

#weather_data = pd.read_csv(os.path.join(app.root_path,'data','gsod_clean_extract.csv'))
#weather_data = pd.read_csv(os.path.join(app.root_path,'data','gsod_zip_extract.csv'))

# GCP?
refresh_data=False

'''if refresh_data:
    credentials = service_account.Credentials.from_service_account_file(
            os.path.join(app.root_path,'config','gmu-capstone-2023-7bc5f5f29d06.json'))
    client = bigquery.Client(credentials=credentials, project='gmu-capstone-2023')
    
    # compose the SQL query
    sql = """
    SELECT  *
    FROM `gmu-capstone-2023.VA_NOAA_SORTED_ZIPS.VA_NOAA_SORTED_ZIPS1`
    WHERE Year >= '2022' AND Station_ID != '999999'
    
    """
    weather_data = client.query(sql).to_dataframe()
    weather_data.to_csv(os.path.join(app.root_path,'data','gsod_zip_extract_gcp.csv'),index=False)
    '''

if refresh_data:
    credentials = service_account.Credentials.from_service_account_file(
            os.path.join(app.root_path,'config','va-climate-change-ccd123ee3fbe.json'))
    client = bigquery.Client(credentials=credentials, project='va-climate-change')
    
    # compose the SQL query
    sql = """
    SELECT  Station_ID, Station_Name, date, Year, Mo, Da, Temp, Min, Max,Prcp,
      Latitude, Longitude, county
    FROM `va-climate-change.gsod_dataset.gsod_data_clean_zip`
    WHERE Year >= '2000' AND Station_ID != '999999'
    
    """
    weather_data = client.query(sql).to_dataframe()
    weather_data.to_csv(os.path.join(app.root_path,'data','gsod_zip_extract_gcp.csv'),index=False)

weather_data = pd.read_csv(os.path.join(app.root_path,'data','gsod_zip_extract_gcp.csv'))



##### Data Cleansing

weather_data['DATE'] = pd.to_datetime(dict(year=weather_data.Year, month=weather_data.Mo, day=weather_data.Da))
#weather_data = weather_data.drop('date',axis=1)
#weather_data= weather_data.sort_values(by=['Station_ID','DATE'], ascending=[True,True])
weather_data= weather_data.sort_values(by=['DATE'], ascending=[True])
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

weather_data['MONTH_Name'] = weather_data['DATE'].dt.strftime('%b')

# Correct Max / Min Temp days
# Where MAX/MIN are both null or 999.9 = Min/Max = Avg
weather_data.loc[ (weather_data['MIN_TEMP']==9999.9) & (weather_data['MAX_TEMP'] == 9999.9),['MIN_TEMP','MAX_TEMP']] = weather_data['AVG_TEMP']
# Where MAX/AVG are known but MIN is not....calculate MIN
weather_data.loc[ (weather_data['MIN_TEMP']==9999.9) & (weather_data['MAX_TEMP'] != 9999.9),['MIN_TEMP']] = (weather_data['AVG_TEMP']*2)-weather_data['MAX_TEMP']
# Where MIN/AVG are known but MAX is not....calculate MAX
weather_data.loc[ (weather_data['MIN_TEMP']!=9999.9) & (weather_data['MAX_TEMP'] == 9999.9),['MAX_TEMP']] = (weather_data['AVG_TEMP']*2)-weather_data['MIN_TEMP']

# Where Prcp = 99.99 set to 0
weather_data.loc[ (weather_data['Prcp']==99.99) ,['Prcp']] = 0

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
     temp_threshold = list(range(70,110))

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
        counties = sorted(df['county'].unique())
        max_date = str(df['DATE'].max().strftime("%Y-%m-%d")) 
        min_date = str(df['DATE'].min().strftime("%Y-%m-%d"))

        num_stations = len(stations)
        

        # Daily Line Chart Data
        date_range = [np.datetime64(date) for date in sorted(df['DATE'].unique())]
        date_range = pd.to_datetime(date_range)
        date_range = [str(value.date()) for value in date_range]

        temp_data_clean = df.dropna(subset=['AVG_TEMP', 'MAX_TEMP','MIN_TEMP'])
        df_values_avg = temp_data_clean[['DATE','AVG_TEMP']].groupby("DATE", as_index=False).mean()
        df_values_max = temp_data_clean[['DATE',"MAX_TEMP"]].groupby("DATE", as_index=False).max()
        df_values_min = temp_data_clean[['DATE',"MIN_TEMP"]].groupby("DATE", as_index=False).min()

        df_values_avg = df_values_avg.sort_values(by=['DATE'], ascending=[True])
        df_values_max = df_values_max.sort_values(by=['DATE'], ascending=[True])
        df_values_min = df_values_min.sort_values(by=['DATE'], ascending=[True])

        max_heat_threshold_filter = 88
        min_heat_threshold_filter = 88
        start_date_filter = min_date
        end_date_filter = max_date

        # Get takeaway metrics for extreme heat

        df_values_max_threshold = df_values_max.loc[df_values_max['MAX_TEMP']>=int(max_heat_threshold_filter)]
        num_days_max_heat_threshold = len(df_values_max_threshold['DATE'])
        pct_days_max_heat_threshold = np.round((num_days_max_heat_threshold/len(df_values_max['MAX_TEMP']))*100,0)

        df_values_min_threshold=df_values_min.loc[df_values_min['MIN_TEMP']>=int(min_heat_threshold_filter)]
        num_days_min_heat_threshold = len(df_values_min_threshold['DATE'])
        pct_days_min_heat_threshold = np.round((num_days_min_heat_threshold/len(df_values_min['MIN_TEMP']))*100,0)

        num_days_minmax_heat_threshold= len(df_values_min_threshold.merge(df_values_max_threshold, on=['DATE'], how='inner')['DATE'])
        pct_days_minmax_heat_threshold = np.round((num_days_minmax_heat_threshold/len(df_values_min['MIN_TEMP']))*100,0)
        

        df_values_avg = [value for value in df_values_avg['AVG_TEMP']]
        df_values_max = [value for value in df_values_max['MAX_TEMP']]
        df_values_min = [value for value in df_values_min['MIN_TEMP']]

        temp_max_axis = np.round(max(df_values_max) *1.1,0)
        temp_min_axis =  0 if  min(df_values_min)>0 else np.round(min(df_values_min)* 1.1,0)


        ##### Create Monthly Line Chart Data
        df_values_avg_monthly = temp_data_clean[['MONTH','year','DATE','AVG_TEMP']].groupby(['MONTH','year'], as_index=False).mean()
        df_values_max_monthly = temp_data_clean[['MONTH','year','DATE',"MAX_TEMP"]].groupby(['MONTH','year'], as_index=False).max()
        df_values_min_monthly = temp_data_clean[['MONTH','year','DATE',"MIN_TEMP"]].groupby(['MONTH','year'], as_index=False).min()

        df_values_avg_monthly = df_values_avg_monthly.sort_values(by=['year','MONTH'], ascending=[True,True])
        df_values_max_monthly = df_values_max_monthly.sort_values(by=['year','MONTH'], ascending=[True,True])
        df_values_min_monthly = df_values_min_monthly.sort_values(by=['year','MONTH'], ascending=[True,True])

        # Pull out data for overtime
        df_values_avg_monthly_decades = df_values_avg_monthly.loc[df_values_avg_monthly['year'] % 10 == 0 ]


        df_values_avg_monthly = [value for value in df_values_avg_monthly['AVG_TEMP']]
        df_values_max_monthly = [value for value in df_values_max_monthly['MAX_TEMP']]
        df_values_min_monthly = [value for value in df_values_min_monthly['MIN_TEMP']]

        date_range_monthly = df['DATE'].dt.strftime("%m/%y").unique().tolist()
       # date_range_monthly = df['DATE'].dt.unique().tolist()


       ###### Create BoxPlot
        dfl = pd.melt(df, id_vars='MONTH_Name', value_vars=["MAX_TEMP","MIN_TEMP"])
        plt.clf()
        colors = ["#FF0000", "#0275D8"]
        sb.set_palette(sb.color_palette(colors))
        plot = sb.boxplot(x='MONTH_Name', y='value', data=dfl, showfliers=False, hue='variable')
        #plt.legend(bbox_to_anchor=(1.04,0.5), loc="center left", borderaxespad=0)
        plt.legend([],[], frameon=False)
              
        #set axis names
        plot.set(xlabel='Month',
                 ylabel='Temperature')
        
        #boxplot_url = str(os.path.join(app.root_path,'static','assets','img','temp_box.png'))
        plt.savefig(os.path.join(app.root_path, 'static','assets','img','temp_box.png'))
        #plt.savefig(boxplot_url)
        boxplot_url = '/static/assets/img/temp_box.png'

        # Create Yearly Data
        sb.reset_defaults()
        plt.figure(figsize=(10, 6))
        years = sorted(df_values_avg_monthly_decades['year'].unique())
        for year in years:
            df_year = df_values_avg_monthly_decades[df_values_avg_monthly_decades['year'] == year]
            months = df_year['MONTH'].sort_values().tolist()
            avg_prcp = df_year.sort_values(by='MONTH')['AVG_TEMP'].tolist()
            plt.plot(months, avg_prcp, label=year, marker='o')
            
        # Customize the plot
        plt.xlabel('Month')
        plt.ylabel('Average Precipitation (inches)')
        plt.title(f'Monthly Average Precipitation Across {years}'.format(years))
        plt.xticks(range(1, 13), ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
        plt.legend()
        plt.grid()
        plt.tight_layout()

        #boxplot_url = str(os.path.join(app.root_path,'static','assets','img','temp_box.png'))
        plt.savefig(os.path.join(app.root_path, 'static','assets','img','decade_lines.png'))
        #plt.savefig(boxplot_url)
        decades_url = '/static/assets/img/decade_lines.png'

        

           


        ##### Render Template
        
        return render_template('home/temperature_analysis copy.html',max_date=max_date,min_date=min_date, df_values=df_values, labels=labels,
                               num_columns=num_columns, stations = stations, counties = counties,date_range = date_range, temp_max_axis = temp_max_axis,temp_min_axis = temp_min_axis,
                               df_values_avg=df_values_avg,df_values_max=df_values_max,df_values_min=df_values_min,
                               df_values_avg_monthly = df_values_avg_monthly, df_values_max_monthly=df_values_max_monthly,df_values_min_monthly=df_values_min_monthly,
                               date_range_monthly=date_range_monthly,temp_threshold=temp_threshold, boxplot_name = boxplot_url ,boxplot_url = boxplot_url,
                               num_days_max_heat_threshold=num_days_max_heat_threshold,num_days_min_heat_threshold=num_days_min_heat_threshold,
                               pct_days_max_heat_threshold=pct_days_max_heat_threshold,pct_days_min_heat_threshold=pct_days_min_heat_threshold,max_heat_threshold_filter=max_heat_threshold_filter,
                               min_heat_threshold_filter=min_heat_threshold_filter,num_days_minmax_heat_threshold=num_days_minmax_heat_threshold,
                               pct_days_minmax_heat_threshold=pct_days_minmax_heat_threshold,start_date_filter=start_date_filter,end_date_filter=end_date_filter,
                               num_stations=num_stations,decades_url=decades_url)
     
     if request.method == 'POST':

        df = cache.get("weather_data")
        if all(col in df.columns for col in cache.get("precipitation_columns")):
            df = df.drop(cache.get("precipitation_columns"),axis=1)
        else:
            df = df

        stations = sorted(df['Station_Name'].unique())
        counties = sorted(df['county'].unique())
        max_date = str(df['DATE'].max().strftime("%Y-%m-%d")) 
        min_date = str(df['DATE'].min().strftime("%Y-%m-%d"))

        #location_filter = request.form.getlist('Station_Select2')
        county_filter = request.form.getlist('County_Select')
        start_date_filter = request.form.get('temp-start2')
        end_date_filter = request.form.get("temp-end2")
        max_heat_threshold_filter = request.form.get("max-heat-options")
        min_heat_threshold_filter = request.form.get("min-heat-options")
        

        
        
        #df = df[df['Station_Name'].isin(location_filter)]
        df = df[df['county'].isin(county_filter)]

        num_stations = len(df['Station_Name'].unique())

        if len(df[df["DATE"]<=pd.to_datetime(end_date_filter)]) == 0:
            df = df.append(df.head(1),ignore_index=True)
            df.loc[len(df)-1,['DATE','year','MONTH','DAY','AVG_TEMP','MAX_TEMP','MIN_TEMP']] = [pd.to_datetime(end_date_filter),np.NaN,np.NaN,np.NaN,np.Nan,np.Nan,np.Nan]

        # Store Truncated Data for 30 year average
        thirty_year_avg = df[(df['DATE']<=pd.to_datetime('12/31/2020')) & (df['DATE']>=pd.to_datetime('01/01/1991') ) ]
        thirty_year_avg_monthly = thirty_year_avg[['MONTH','AVG_TEMP']].groupby("MONTH", as_index=False).mean()

        # Limit Data
        df = df[(df['DATE']<=end_date_filter) & (df['DATE']>=start_date_filter) ]

        cache.set("view_rain_data",df)

        df_values = df.values
        labels = [row for row in df.columns]
        num_columns = df.shape[1]    

        date_range = [np.datetime64(date) for date in sorted(df['DATE'].unique())]
        date_range = pd.to_datetime(date_range)
        date_range = [str(value.date()) for value in date_range]

        temp_data_clean = df.dropna(subset=['AVG_TEMP', 'MAX_TEMP','MIN_TEMP'])
        df_values_avg = temp_data_clean[['DATE','AVG_TEMP',"MAX_TEMP","MIN_TEMP"]].groupby("DATE", as_index=False).mean()
        df_values_max = temp_data_clean[['DATE','AVG_TEMP',"MAX_TEMP","MIN_TEMP"]].groupby("DATE", as_index=False).max()
        df_values_min = temp_data_clean[['DATE','AVG_TEMP',"MAX_TEMP","MIN_TEMP"]].groupby("DATE", as_index=False).min()

        df_values_avg = df_values_avg.sort_values(by=['DATE'], ascending=[True])
        df_values_max = df_values_max.sort_values(by=['DATE'], ascending=[True])
        df_values_min = df_values_min.sort_values(by=['DATE'], ascending=[True])

        # Get takeaway metrics for extreme heat

        df_values_max_threshold = df_values_max.loc[df_values_max['MAX_TEMP']>=int(max_heat_threshold_filter)]
        num_days_max_heat_threshold = len(df_values_max_threshold['DATE'])
        pct_days_max_heat_threshold = np.round((num_days_max_heat_threshold/len(df_values_max['MAX_TEMP']))*100,0)

        df_values_min_threshold=df_values_min.loc[df_values_min['MIN_TEMP']>=int(min_heat_threshold_filter)]
        num_days_min_heat_threshold = len(df_values_min_threshold['DATE'])
        pct_days_min_heat_threshold = np.round((num_days_min_heat_threshold/len(df_values_min['MIN_TEMP']))*100,0)

        num_days_minmax_heat_threshold= len(df_values_min_threshold.merge(df_values_max_threshold, on=['DATE'], how='inner')['DATE'])
        pct_days_minmax_heat_threshold = np.round((num_days_minmax_heat_threshold/len(df_values_min['MIN_TEMP']))*100,0)

        

        df_values_avg = [value for value in df_values_avg['AVG_TEMP']]
        df_values_max = [value for value in df_values_max['MAX_TEMP']]
        df_values_min = [value for value in df_values_min['MIN_TEMP']]

        temp_max_axis = np.round(max(df_values_max) *1.1,0)
        temp_min_axis =  0 if  min(df_values_min)>0 else np.round(min(df_values_min)* 1.1,0)
        
        

        ##### Create Monthly Line Chart Data
        df_values_avg_monthly = temp_data_clean[['MONTH','year','DATE','AVG_TEMP']].groupby(['MONTH','year'], as_index=False).mean()
        df_values_max_monthly = temp_data_clean[['MONTH','year','DATE',"MAX_TEMP"]].groupby(['MONTH','year'], as_index=False).max()
        df_values_min_monthly = temp_data_clean[['MONTH','year','DATE',"MIN_TEMP"]].groupby(['MONTH','year'], as_index=False).min()

        df_values_avg_monthly = df_values_avg_monthly.sort_values(by=['year','MONTH'], ascending=[True,True])
        df_values_max_monthly = df_values_max_monthly.sort_values(by=['year','MONTH'], ascending=[True,True])
        df_values_min_monthly = df_values_min_monthly.sort_values(by=['year','MONTH'], ascending=[True,True])

        df_values_avg_monthly_decades = df_values_avg_monthly.loc[df_values_avg_monthly['year'] % 10 == 0 ]

        df_values_avg_monthly = [value for value in df_values_avg_monthly['AVG_TEMP']]
        df_values_max_monthly = [value for value in df_values_max_monthly['MAX_TEMP']]
        df_values_min_monthly = [value for value in df_values_min_monthly['MIN_TEMP']]

        date_range_monthly = df['DATE'].dt.strftime("%m/%y").unique().tolist()

        ###### Create BoxPlot
        dfl = pd.melt(df, id_vars='MONTH_Name', value_vars=["MAX_TEMP","MIN_TEMP"])
        plt.clf()
        colors = ["#FF0000", "#0275D8"]
        sb.set_palette(sb.color_palette(colors))
        plot = sb.boxplot(x='MONTH_Name', y='value', data=dfl, showfliers=False,hue="variable")
        
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


        # Create Yearly Data
        sb.reset_defaults()
        plt.clf()
        plt.figure(figsize=(10, 6))
        years = sorted(df_values_avg_monthly_decades['year'].unique())
        for year in years:
            df_year = df_values_avg_monthly_decades[df_values_avg_monthly_decades['year'] == year]
            months = df_year['MONTH'].sort_values().tolist()
            avg_prcp = df_year.sort_values(by='MONTH')['AVG_TEMP'].tolist()
            plt.plot(months, avg_prcp, label=year, marker='o')
            
        # Customize the plot
        
        plt.plot(months, thirty_year_avg_monthly['AVG_TEMP'], label='30-Year Avg (1991 - 2020)', color='black', linestyle=':', linewidth=3)
        plt.xlabel('Month', fontsize=14)
        plt.ylabel('Average Precipitation (inches)', fontsize=14)
        plt.title(f'Monthly Average Precipitation Across {years}'.format(years), fontsize=16)
        plt.xticks(range(1, 13), ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], fontsize=12)
        plt.yticks(fontsize=12)
        plt.legend()
        plt.grid()
        plt.tight_layout()

        #boxplot_url = str(os.path.join(app.root_path,'static','assets','img','temp_box.png'))
        plt.savefig(os.path.join(app.root_path, 'static','assets','img','decade_lines.png'))
        #plt.savefig(boxplot_url)
        decades_url = '/static/assets/img/decade_lines.png'


        ##### Render Template
        
        return render_template('home/temperature_analysis copy.html',max_date=max_date,min_date=min_date, df_values=df_values, labels=labels,
                               num_columns=num_columns, stations = stations, counties = counties,date_range = date_range, temp_max_axis = temp_max_axis,temp_min_axis = temp_min_axis,
                               df_values_avg=df_values_avg,df_values_max=df_values_max,df_values_min=df_values_min,
                               df_values_avg_monthly = df_values_avg_monthly, df_values_max_monthly=df_values_max_monthly,df_values_min_monthly=df_values_min_monthly,
                               date_range_monthly=date_range_monthly,temp_threshold=temp_threshold, boxplot_name = boxplot_url ,boxplot_url = boxplot_url,
                               num_days_max_heat_threshold=num_days_max_heat_threshold,num_days_min_heat_threshold=num_days_min_heat_threshold,
                               pct_days_max_heat_threshold=pct_days_max_heat_threshold,pct_days_min_heat_threshold=pct_days_min_heat_threshold,max_heat_threshold_filter=max_heat_threshold_filter,
                               min_heat_threshold_filter=min_heat_threshold_filter,num_days_minmax_heat_threshold=num_days_minmax_heat_threshold,
                               pct_days_minmax_heat_threshold=pct_days_minmax_heat_threshold,start_date_filter=start_date_filter,end_date_filter=end_date_filter,
                               num_stations=num_stations,decades_url=decades_url)
                


    

# App main route + generic routing
@app.route('/temperature_table', methods = ['GET','POST'])
def display_temperature():

    if request.method == 'GET':
        df = cache.get("weather_data")
        if all(col in df.columns for col in cache.get("precipitation_columns")):
            df = df.drop(cache.get("precipitation_columns"),axis=1)
        else:
            df = df

        cache.set("view_temp_data",df)

        df_values = df.values
        labels = [row for row in df.columns]
        num_columns = df.shape[1]

        stations = sorted(df['Station_Name'].unique())
        counties = sorted(df['county'].unique())
        max_date = str(df['DATE'].max().strftime("%Y-%m-%d")) 
        min_date = str(df['DATE'].min().strftime("%Y-%m-%d"))
        
        
        
        return render_template('home/temperature_table.html',max_date=max_date,min_date=min_date, df_values=df_values, 
                               labels=labels,num_columns=num_columns, stations = stations, counties = counties)
    if request.method == 'POST':

        df = cache.get("weather_data")
        if all(col in df.columns for col in cache.get("precipitation_columns")):
            df = df.drop(cache.get("precipitation_columns"),axis=1)
        else:
            df = df

        stations = sorted(df['Station_Name'].unique())
        counties = sorted(df['county'].unique())
        max_date = str(df['DATE'].max().strftime("%Y-%m-%d")) 
        min_date = str(df['DATE'].min().strftime("%Y-%m-%d"))

        #location_filter = request.form.getlist('Station_Select')
        county_filter = request.form.getlist('County_Select')
        start_date_filter = request.form.get('temp-start')
        end_date_filter = request.form.get("temp-end")
        
        
        #df = df[df['Station_Name'].isin(location_filter)]
        df = df[df['county'].isin(county_filter)]
        
        if len(df[df["DATE"]<=end_date_filter]) == 0:
            df = df.append(df.head(1),ignore_index=True)
            df.loc[len(df)-1,['DATE','year','MONTH','DAY','AVG_TEMP','MAX_TEMP','MIN_TEMP']] = [pd.to_datetime(end_date_filter),np.NaN,np.NaN,np.NaN,np.NaN,np.NaN,np.NaN]

        df = df[(df['DATE']<=end_date_filter) & (df['DATE']>=start_date_filter) ]

        cache.set("view_temp_data",df)

        df_values = df.values
        labels = [row for row in df.columns]
        num_columns = df.shape[1]

       
        
        
        return render_template('home/temperature_table.html',max_date=max_date,min_date=min_date, df_values=df_values, 
                               labels=labels,num_columns=num_columns, stations = stations,counties = counties, start_date_filter=start_date_filter)


@app.route('/download_temp_data')
def download_temp():
    
    df = cache.get("view_temp_data")

    resp = make_response(df.to_csv())
    resp.headers["Content-Disposition"] = "attachment; filename= VCC_Temperature_Data_Export_on_{}.csv".format(datetime.today().strftime('%Y-%m-%d %I:%M:%S:%p'))
    resp.headers["Content-Type"] = "text/csv"

    return resp
    

# App main route + generic routing
@app.route('/precipitation_analysis', methods=['GET','POST'])
def display_precip():
    prcp_threshold = list(range(0,20))
    
    if request.method == 'GET':
        df = cache.get("weather_data")

        if all(col in df.columns for col in cache.get("temperature_columns")):
            df = df.drop(cache.get("temperature_columns"),axis=1)
        else:
            df = df
        
        cache.set("view_rain_data",df)
        df_values = df.values
        labels = [row for row in df.columns]
        num_columns = df.shape[1]

        stations = sorted(df['Station_Name'].unique())
        counties = sorted(df['county'].unique())
        max_date = str(df['DATE'].max().strftime("%Y-%m-%d")) 
        min_date = str(df['DATE'].min().strftime("%Y-%m-%d"))

        num_stations = len(stations)
        

        # Daily Line Chart Data
        date_range = [np.datetime64(date) for date in sorted(df['DATE'].unique())]
        date_range = pd.to_datetime(date_range)
        date_range = [str(value.date()) for value in date_range]

        temp_data_clean = df.dropna(subset=['Prcp'])
        df_values_avg = temp_data_clean[['DATE','Prcp']].groupby("DATE", as_index=False).mean()
        df_values_max = temp_data_clean[['DATE',"Prcp"]].groupby("DATE", as_index=False).max()
        df_values_min = temp_data_clean[['DATE',"Prcp"]].groupby("DATE", as_index=False).min()

        df_values_avg = df_values_avg.sort_values(by=['DATE'], ascending=[True])
        df_values_max = df_values_max.sort_values(by=['DATE'], ascending=[True])
        df_values_min = df_values_min.sort_values(by=['DATE'], ascending=[True])

        max_prcp_threshold_filter = 10
        min_prcp_threshold_filter = 0
        start_date_filter = min_date
        end_date_filter = max_date

        # Get takeaway metrics for precipitation

        df_values_max_threshold = df_values_max.loc[df_values_max['Prcp']>=int(max_prcp_threshold_filter)]
        num_days_max_prcp_threshold = len(df_values_max_threshold['DATE'])
        pct_days_max_prcp_threshold = np.round((num_days_max_prcp_threshold/len(df_values_max['Prcp']))*100,0)

        df_values_min_threshold=df_values_min.loc[df_values_min['Prcp']>=int(min_prcp_threshold_filter)]
        num_days_min_prcp_threshold = len(df_values_min_threshold['DATE'])
        pct_days_min_prcp_threshold = np.round((num_days_min_prcp_threshold/len(df_values_min['Prcp']))*100,0)

        num_days_minmax_prcp_threshold= len(df_values_min_threshold.merge(df_values_max_threshold, on=['DATE'], how='inner')['DATE'])
        pct_days_minmax_prcp_threshold = np.round((num_days_minmax_prcp_threshold/len(df_values_min['Prcp']))*100,0)
        

        df_values_avg = [value for value in df_values_avg['Prcp']]
        df_values_max = [value for value in df_values_max['Prcp']]
        df_values_min = [value for value in df_values_min['Prcp']]

        prcp_max_axis = np.round(max(df_values_max) *1.1,0)
        prcp_min_axis =  0 if  min(df_values_min)>0 else np.round(min(df_values_min)* 1.1,0)


        ##### Create Monthly Line Chart Data
        df_values_avg_monthly = temp_data_clean[['MONTH','year','DATE','Prcp']].groupby(['MONTH','year'], as_index=False).mean()
        df_values_max_monthly = temp_data_clean[['MONTH','year','DATE',"Prcp"]].groupby(['MONTH','year'], as_index=False).max()
        df_values_min_monthly = temp_data_clean[['MONTH','year','DATE',"Prcp"]].groupby(['MONTH','year'], as_index=False).min()

        df_values_avg_monthly = df_values_avg_monthly.sort_values(by=['year','MONTH'], ascending=[True,True])
        df_values_max_monthly = df_values_max_monthly.sort_values(by=['year','MONTH'], ascending=[True,True])
        df_values_min_monthly = df_values_min_monthly.sort_values(by=['year','MONTH'], ascending=[True,True])

        df_values_avg_monthly = [value for value in df_values_avg_monthly['Prcp']]
        df_values_max_monthly = [value for value in df_values_max_monthly['Prcp']]
        df_values_min_monthly = [value for value in df_values_min_monthly['Prcp']]

        date_range_monthly = df['DATE'].dt.strftime("%m/%y").unique().tolist()
       # date_range_monthly = df['DATE'].dt.unique().tolist()


       ###### Create BoxPlot
        dfl = pd.melt(df, id_vars='MONTH_Name', value_vars=["Prcp"])
        plt.clf()
        colors = ["#0275D8"]
        sb.set_palette(sb.color_palette(colors))
        plot = sb.boxplot(x='MONTH_Name', y='value', data=dfl, showfliers=False, hue='variable')
        #plt.legend(bbox_to_anchor=(1.04,0.5), loc="center left", borderaxespad=0)
        plt.legend([], frameon=False)
              
        #set axis names
        plot.set(xlabel='Month',
                 ylabel='Precipitation')
        
        #boxplot_url = str(os.path.join(app.root_path,'static','assets','img','temp_box.png'))
        plt.savefig(os.path.join(app.root_path, 'static','assets','img','prcp_box.png'))
        #plt.savefig(boxplot_url)
        boxplot_url = '/static/assets/img/prcp_box.png'

        # Create Map Data

           


        ##### Render Template
        
        return render_template('home/precipitation_analysis.html',max_date=max_date,min_date=min_date, df_values=df_values, labels=labels,
                               num_columns=num_columns, stations = stations, counties = counties,date_range = date_range, prcp_max_axis = prcp_max_axis,prcp_min_axis = prcp_min_axis,
                               df_values_avg=df_values_avg,df_values_max=df_values_max,df_values_min=df_values_min,
                               df_values_avg_monthly = df_values_avg_monthly, df_values_max_monthly=df_values_max_monthly,df_values_min_monthly=df_values_min_monthly,
                               date_range_monthly=date_range_monthly,prcp_threshold=prcp_threshold, boxplot_name = boxplot_url ,boxplot_url = boxplot_url,
                               num_days_max_prcp_threshold=num_days_max_prcp_threshold,num_days_min_prcp_threshold=num_days_min_prcp_threshold,
                               pct_days_max_prcp_threshold=pct_days_max_prcp_threshold,pct_days_min_prcp_threshold=pct_days_min_prcp_threshold,max_prcp_threshold_filter=max_prcp_threshold_filter,
                               min_prcp_threshold_filter=min_prcp_threshold_filter,num_days_minmax_prcp_threshold=num_days_minmax_prcp_threshold,
                               pct_days_minmax_prcp_threshold=pct_days_minmax_prcp_threshold,start_date_filter=start_date_filter,end_date_filter=end_date_filter,
                               num_stations=num_stations)
     
    if request.method == 'POST':

        df = cache.get("weather_data")
        if all(col in df.columns for col in cache.get("temperature_columns")):
            df = df.drop(cache.get("temperature_columns"),axis=1)
        else:
            df = df

        stations = sorted(df['Station_Name'].unique())
        counties = sorted(df['county'].unique())
        max_date = str(df['DATE'].max().strftime("%Y-%m-%d")) 
        min_date = str(df['DATE'].min().strftime("%Y-%m-%d"))

        #location_filter = request.form.getlist('Station_Select2')
        county_filter = request.form.getlist('County_Select')
        start_date_filter = request.form.get('prcp-start2')
        end_date_filter = request.form.get("prcp-end2")
        max_prcp_threshold_filter = request.form.get("max-prcp-options")
        min_prcp_threshold_filter = request.form.get("min-prcp-options")
        
        
        #df = df[df['Station_Name'].isin(location_filter)]
        df = df[df['county'].isin(county_filter)]

        num_stations = len(df['Station_Name'].unique())

        if len(df[df["DATE"]<=pd.to_datetime(end_date_filter)]) == 0:
            df = df.append(df.head(1),ignore_index=True)
            df.loc[len(df)-1,['DATE','year','MONTH','DAY','Prcp']] = [pd.to_datetime(end_date_filter),np.NaN,np.NaN,np.NaN,np.Nan]

        df = df[(df['DATE']<=end_date_filter) & (df['DATE']>=start_date_filter) ]

        cache.set("view_rain_data",df)

        df_values = df.values
        labels = [row for row in df.columns]
        num_columns = df.shape[1]    

        date_range = [np.datetime64(date) for date in sorted(df['DATE'].unique())]
        date_range = pd.to_datetime(date_range)
        date_range = [str(value.date()) for value in date_range]

        prcp_data_clean = df.dropna(subset=['Prcp'])
        df_values_avg = prcp_data_clean[['DATE','Prcp']].groupby("DATE", as_index=False).mean()
        df_values_max = prcp_data_clean[['DATE','Prcp']].groupby("DATE", as_index=False).max()
        df_values_min = prcp_data_clean[['DATE','Prcp']].groupby("DATE", as_index=False).min()

        df_values_avg = df_values_avg.sort_values(by=['DATE'], ascending=[True])
        df_values_max = df_values_max.sort_values(by=['DATE'], ascending=[True])
        df_values_min = df_values_min.sort_values(by=['DATE'], ascending=[True])

        # Get takeaway metrics for precipitation

        df_values_max_threshold = df_values_max.loc[df_values_max['Prcp']>=int(max_prcp_threshold_filter)]
        num_days_max_prcp_threshold = len(df_values_max_threshold['DATE'])
        pct_days_max_prcp_threshold = np.round((num_days_max_prcp_threshold/len(df_values_max['Prcp']))*100,0)

        df_values_min_threshold=df_values_min.loc[df_values_min['Prcp']>=int(min_prcp_threshold_filter)]
        num_days_min_prcp_threshold = len(df_values_min_threshold['DATE'])
        pct_days_min_prcp_threshold = np.round((num_days_min_prcp_threshold/len(df_values_min['Prcp']))*100,0)

        num_days_minmax_prcp_threshold= len(df_values_min_threshold.merge(df_values_max_threshold, on=['DATE'], how='inner')['DATE'])
        pct_days_minmax_prcp_threshold = np.round((num_days_minmax_prcp_threshold/len(df_values_min['Prcp']))*100,0)

        

        df_values_avg = [value for value in df_values_avg['Prcp']]
        df_values_max = [value for value in df_values_max['Prcp']]
        df_values_min = [value for value in df_values_min['Prcp']]

        prcp_max_axis = np.round(max(df_values_max) *1.1,0)
        prcp_min_axis =  0 if  min(df_values_min)>0 else np.round(min(df_values_min)* 1.1,0)
        
        

        ##### Create Monthly Line Chart Data
        df_values_avg_monthly = prcp_data_clean[['MONTH','year','DATE','Prcp']].groupby(['MONTH','year'], as_index=False).mean()
        df_values_max_monthly = prcp_data_clean[['MONTH','year','DATE',"Prcp"]].groupby(['MONTH','year'], as_index=False).max()
        df_values_min_monthly = prcp_data_clean[['MONTH','year','DATE',"Prcp"]].groupby(['MONTH','year'], as_index=False).min()

        df_values_avg_monthly = df_values_avg_monthly.sort_values(by=['year','MONTH'], ascending=[True,True])
        df_values_max_monthly = df_values_max_monthly.sort_values(by=['year','MONTH'], ascending=[True,True])
        df_values_min_monthly = df_values_min_monthly.sort_values(by=['year','MONTH'], ascending=[True,True])

        df_values_avg_monthly = [value for value in df_values_avg_monthly['Prcp']]
        df_values_max_monthly = [value for value in df_values_max_monthly['Prcp']]
        df_values_min_monthly = [value for value in df_values_min_monthly['Prcp']]

        date_range_monthly = df['DATE'].dt.strftime("%m/%y").unique().tolist()

        ###### Create BoxPlot
        dfl = pd.melt(df, id_vars='MONTH_Name', value_vars=["Prcp"])
        plt.clf()
        colors = ["#0275D8"]
        sb.set_palette(sb.color_palette(colors))
        plot = sb.boxplot(x='MONTH_Name', y='value', data=dfl, showfliers=False,hue="variable")
        
        #plot = sb.boxplot(x='MONTH', y='value', data=dfl, showfliers=False, hue='variable')
        #plt.legend(bbox_to_anchor=(1.04,0.5), loc="center left", borderaxespad=0)
        plt.legend([], frameon=False)
              
        #set axis names
        plot.set(xlabel='Month',
                 ylabel='Precipitation')
        #boxplot_url = str(os.path.join(app.root_path,'static','assets','img','temp_box.png'))
        plt.savefig(os.path.join(app.root_path, 'static','assets','img','prcp_box.png'))
        #plt.savefig(boxplot_url)
        boxplot_url = '/static/assets/img/prcp_box.png'

        ##### Render Template
        
        return render_template('home/precipitation_analysis.html',max_date=max_date,min_date=min_date, df_values=df_values, labels=labels,
                               num_columns=num_columns, stations = stations, counties = counties,date_range = date_range, prcp_max_axis = prcp_max_axis,prcp_min_axis = prcp_min_axis,
                               df_values_avg=df_values_avg,df_values_max=df_values_max,df_values_min=df_values_min,
                               df_values_avg_monthly = df_values_avg_monthly, df_values_max_monthly=df_values_max_monthly,df_values_min_monthly=df_values_min_monthly,
                               date_range_monthly=date_range_monthly,prcp_threshold=prcp_threshold, boxplot_name = boxplot_url ,boxplot_url = boxplot_url,
                               num_days_max_prcp_threshold=num_days_max_prcp_threshold,num_days_min_prcp_threshold=num_days_min_prcp_threshold,
                               pct_days_max_prcp_threshold=pct_days_max_prcp_threshold,pct_days_min_prcp_threshold=pct_days_min_prcp_threshold,max_prcp_threshold_filter=max_prcp_threshold_filter,
                               min_prcp_threshold_filter=min_prcp_threshold_filter,num_days_minmax_prcp_threshold=num_days_minmax_prcp_threshold,
                               pct_days_minmax_prcp_threshold=pct_days_minmax_prcp_threshold,start_date_filter=start_date_filter,end_date_filter=end_date_filter,
                               num_stations=num_stations)
    

    #return render_template('home/precipitation_analysis.html')

# App main route + generic routing
@app.route('/precipitation_table', methods = ['GET','POST'])
def display_precipitation():

    if request.method == 'GET':
        df = cache.get("weather_data")
        if all(col in df.columns for col in cache.get("temperature_columns")):
            df = df.drop(cache.get("temperature_columns"),axis=1)
        else:
            df = df

        cache.set("view_prcp_data",df)

        df_values = df.values
        labels = [row for row in df.columns]
        num_columns = df.shape[1]

        stations = sorted(df['Station_Name'].unique())
        counties = sorted(df['county'].unique())
        max_date = str(df['DATE'].max().strftime("%Y-%m-%d")) 
        min_date = str(df['DATE'].min().strftime("%Y-%m-%d"))
        
        
        
        return render_template('home/precipitation_table.html',max_date=max_date,min_date=min_date, df_values=df_values, 
                               labels=labels,num_columns=num_columns, stations = stations, counties = counties)
    if request.method == 'POST':

        df = cache.get("weather_data")
        if all(col in df.columns for col in cache.get("temperature_columns")):
            df = df.drop(cache.get("temperature_columns"),axis=1)
        else:
            df = df

        stations = sorted(df['Station_Name'].unique())
        counties = sorted(df['county'].unique())
        max_date = str(df['DATE'].max().strftime("%Y-%m-%d")) 
        min_date = str(df['DATE'].min().strftime("%Y-%m-%d"))

        #location_filter = request.form.getlist('Station_Select')
        county_filter = request.form.getlist('County_Select')
        start_date_filter = request.form.get('prcp-start')
        end_date_filter = request.form.get("prcp-end")
        
        
        #df = df[df['Station_Name'].isin(location_filter)]
        df = df[df['county'].isin(county_filter)]
        
        if len(df[df["DATE"]<=end_date_filter]) == 0:
            df = df.append(df.head(1),ignore_index=True)
            df.loc[len(df)-1,['DATE','year','Prcp']] = [pd.to_datetime(end_date_filter),np.NaN,np.NaN,np.NaN]

        df = df[(df['DATE']<=end_date_filter) & (df['DATE']>=start_date_filter) ]

        cache.set("view_prcp_data",df)

        df_values = df.values
        labels = [row for row in df.columns]
        num_columns = df.shape[1]

       
        
        
        return render_template('home/precipitation_table.html',max_date=max_date,min_date=min_date, df_values=df_values, 
                               labels=labels,num_columns=num_columns, stations = stations,counties = counties, start_date_filter=start_date_filter)
    
@app.route('/download_precp_data')
def download_rain():
    
    df = cache.get("view_rain_data")

    resp = make_response(df.to_csv())
    resp.headers["Content-Disposition"] = "attachment; filename= VCC_Precipitation_Data_Export_on_{}.csv".format(datetime.today().strftime('%Y-%m-%d %I:%M:%S:%p'))
    resp.headers["Content-Type"] = "text/csv"

    return resp



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
        
