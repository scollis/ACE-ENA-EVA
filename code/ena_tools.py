import urllib3
from matplotlib import use
use('agg')
#fetch GFS data and plot at ENA
import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import netCDF4
from cartopy.mpl.ticker import LongitudeFormatter, LatitudeFormatter
import numpy as np
from siphon.catalog import TDSCatalog
from siphon.ncss import NCSS
from datetime import datetime, timedelta
from netCDF4 import num2date, Dataset
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import tempfile
import boto3
from siphon.catalog import get_latest_access_url


def gen_s3_key(fig_datetime, pref, sfx=''):
    fmt_str = '%Y/%m/%d/' + pref + '%Y%m%d_%H%M' + sfx + '.png'
    o_str = datetime.strftime(fig_datetime, fmt_str)
    return o_str


def format_minnis(my_datetime):
    base = 'https://www-pm.larc.nasa.gov/cgi-bin/site/'
    useless_text = '/showdoc?docid=22&c=binary-download&domain=amf_azores&type=P&'
    fmt_str = 'year=%Y&month=%m&day=%d&fn=MT10V03.0.AMFAZRS.%Y%j.%H00.PX.03K.NC'
    last_str = datetime.strftime(my_datetime, fmt_str)
    fqdn = base + useless_text + last_str
    return fqdn


def fetch_minnis(url):
    localfile = tempfile.NamedTemporaryFile()
    connection_pool = urllib3.PoolManager()
    resp = connection_pool.request('GET',url )
    f = open(localfile.name, 'wb')
    f.write(resp.data)
    f.close()
    resp.release_conn()
    mydata = Dataset(localfile.name)
    return mydata

def fetch_latest_minnis():
    now = datetime.utcnow()
    try:
        url = format_minnis(now)
        data = fetch_minnis(url)
    except OSError: #get last hours
        print('Fetching last hours')
        url = format_minnis(now - timedelta(minutes=60))
        data =  fetch_minnis(url)

    return data

def ir_plot(mydata, ofile):
    lat_2d = mydata.variables['latitude'][:]
    lon_2d = mydata.variables['longitude'][:]
    temp_vals = mydata.variables['temperature_ir'][:] -273.15
    time_val = num2date(mydata.variables['time_offset'][:], mydata.variables['time_offset'].units)
    ter_lat = 38.7216
    ter_lon = -27.2206
    gra_lat = 39.0525
    gra_lon = -28.0069


    # Create a new figure
    fig = plt.figure(figsize=(15, 12))

    # Add the map and set the extent
    ax = plt.axes(projection=ccrs.PlateCarree())
    ax.set_xticks([-23, -24, -26, -28 ], crs=ccrs.PlateCarree())
    ax.set_yticks([37,39,41], crs=ccrs.PlateCarree())
    lon_formatter = LongitudeFormatter(zero_direction_label=True)
    lat_formatter = LatitudeFormatter()
    ax.xaxis.set_major_formatter(lon_formatter)
    ax.yaxis.set_major_formatter(lat_formatter)

    ax.set_extent([-23., -31., 35, 43])

    # Add state boundaries to plot
    coast = cfeature.NaturalEarthFeature(category='physical', scale='10m',
                                facecolor='none', name='coastline')
    _ = ax.add_feature(coast, edgecolor='black')

    #ax.add_feature(cfeature.NaturalEarthFeature, edgecolor='black', linewidth=2)

    # Contour temperature at each lat/long
    cf = ax.pcolormesh(lon_2d, lat_2d, temp_vals, transform=ccrs.PlateCarree(), zorder=0,
                     cmap='coolwarm', vmin = -55, vmax = 25)

    # Plot a colorbar to show temperature and reduce the size of it
    plt.colorbar(cf, ax=ax, fraction=0.032)


    # Make a title with the time value
    ax.set_title(u'Minnis IR Brightness Temperature (\u00b0C) for {0:%d %B %Y %H:%MZ}'.format(time_val),
                 fontsize=20)


    ax.plot([ter_lon, gra_lon], [ter_lat, gra_lat],
           'ro', transform=ccrs.PlateCarree())

    ax.text(ter_lon+.2, ter_lat+.2,
            'Tericia', transform=ccrs.PlateCarree(), fontsize = 16)

    ax.text(gra_lon+.2, gra_lat+.2,
            'Graciosa', transform=ccrs.PlateCarree(), fontsize = 16)

    plt.savefig(ofile)
    plt.close(fig)
    return time_val


def save_latest_minnis_png_s3():
    my_data = fetch_latest_minnis()
    local_fig =  tempfile.NamedTemporaryFile(suffix='.png')
    fn = local_fig.name
    fig_datetime = ir_plot(my_data, fn)
    my_data.close()
    s3_key = 'minnis_ir/' + gen_s3_key(fig_datetime, 'minnis_ir_')
    s3 = boto3.resource('s3')
    data = open(fn, 'rb')
    s3.Bucket('aceena').put_object(Key=s3_key, Body=data, ACL='public-read')
    data.close()
    data2 = open(fn, 'rb')
    s3.Bucket('aceena').put_object(Key='latest_minnis_ir.png', Body=data2, ACL='public-read')
    data2.close()
    return s3_key, fn

def give_me_latest_gfs():
    best_gfs = 'http://thredds.ucar.edu/thredds/catalog/grib/NCEP/GFS/Global_0p5deg/catalog.xml'
    latest_gfs = get_latest_access_url(best_gfs, "NetcdfSubset")
    ncss = NCSS(latest_gfs)
    return ncss

def get_me_grw_ts(ncss, varss):
    query = ncss.query()
    now = datetime.utcnow()
    gra_lat = 39.0525
    gra_lon = -28.0069
    query.lonlat_point(gra_lon, gra_lat).vertical_level(0).all_times()
    query.variables(*varss).accept('netcdf')
    data = ncss.get_data(query)
    return data


def plot_ttd_gra(my_ts, ofile):
    temp = my_ts.variables['Temperature_height_above_ground']
    dp = my_ts.variables['Dewpoint_temperature_height_above_ground']
    time = my_ts.variables['time']
    datetimes = num2date(time[:].squeeze(), time.units)
    fig = plt.figure(figsize = [15,5])
    plt.plot(datetimes, temp[:].squeeze()-273.15, 'r-', label='Temperatue (c)')
    plt.plot(datetimes, dp[:].squeeze()-273.15, 'b-', label=r't$_{dp}$ (c)')
    plt.legend()
    plt.title('Time Series for Graciosa')
    plt.savefig(ofile)
    plt.close(fig)
    return datetimes[0]


def save_latest_gfs_grw_ttd():
    my_ncss = give_me_latest_gfs()
    my_ts = get_me_grw_ts(my_ncss, ['Temperature_height_above_ground',
               'Dewpoint_temperature_height_above_ground'])
    local_fig =  tempfile.NamedTemporaryFile(suffix='.png')
    fn = local_fig.name
    fig_datetime = plot_ttd_gra(my_ts, fn)
    s3_key = 'time_series_gfs/' + gen_s3_key(fig_datetime, 'T_ts_timeseries_GFS_GRW')
    s3 = boto3.resource('s3')
    data = open(fn, 'rb')
    s3.Bucket('aceena').put_object(Key=s3_key, Body=data, ACL='public-read')
    data.close()





