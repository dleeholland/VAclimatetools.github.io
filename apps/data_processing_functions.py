# Data Ingestion Scripts

# important packages
import pandas as pd
from apps import app
from datetime import datetime
import os
from google.cloud import bigquery
from google.oauth2 import service_account
from flask_caching import Cache





def data_refresh(cache):
    if datetime.today().day == 3:
         refresh_data=True
    else:
         refresh_data = False

    if refresh_data:
        credentials = service_account.Credentials.from_service_account_file(
                        os.path.join(app.root_path,'config','va-climate-change-ccd123ee3fbe.json'))
        client = bigquery.Client(credentials=credentials, project='va-climate-change')
        
        # compose the SQL query
        sql = """
            SELECT  Station_ID, Station_Name, date, Year, Mo, Da, Temp, Min, Max,Prcp,
             Latitude, Longitude, county
                     FROM `va-climate-change.gsod_dataset.gsod_data_clean_zip`
                             WHERE Year >= '1960' AND Station_ID != '999999'
                               """
        weather_data = client.query(sql).to_dataframe()
        weather_data.to_csv(os.path.join(app.root_path,'data','gsod_zip_extract_gcp.csv'),index=False)



def get_clean_data(cache):
    weather_data = pd.read_csv(os.path.join(app.root_path,'data','gsod_zip_extract_gcp.csv'))
    
    ##### Data Cleansing
    weather_data['DATE'] = pd.to_datetime(dict(year=weather_data.Year, month=weather_data.Mo, day=weather_data.Da))
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
    # # Where MAX/MIN are both null or 999.9 = Min/Max = Avg
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
