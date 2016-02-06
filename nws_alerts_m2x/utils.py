import os
import requests
import time
import json

from models import Alert
from m2x.client import M2XClient
from xml.etree import ElementTree

# M2X config
m2x_client = M2XClient(key=os.environ["M2X_API_KEY"])

# The namespace of the XML returned by NWS
nws_url = 'http://alerts.weather.gov/cap/us.php?x=0'
nws_alerts_namespace = '{http://www.w3.org/2005/Atom}'
nws_entry_namespace = '{urn:oasis:names:tc:emergency:cap:1.1}'

def update_alert_messages():
    """
    Get all current weather alerts from NWS, if the alert is not expired:
    check if alert is new/updated against local datastore, and if so update 
    affected M2X devices.
    """
    print 'Checking for new alerts & updating affected devices'

    try:
        alerts = requests.get(nws_url).text

        root = ElementTree.fromstring(alerts)
        for child in root:
            if child.tag == nws_alerts_namespace + "entry":
                alert_id = child.find(nws_alerts_namespace + 'id').text
                updated = child.find(nws_alerts_namespace + 'updated').text
                message = child.find(nws_alerts_namespace + 'title').text
                geocode = child.find(nws_entry_namespace + 'geocode')

                alert = Alert().create_or_update(alert_id=alert_id, updated=updated)
                if alert == "created" or alert == "updated":
                    if not is_expired(alert_id):
                        fips = get_fips(geocode)
                        ugc = get_ugc(geocode)
                        affected_devices = get_devices(fips, ugc)
                        
                        for device in affected_devices:
                            update_device(device, alert_id, message, "active")
                        
                        send_command(command_name="UPDATE_WEATHER_ALERT", command_data={ 'message': message }, affected_devices=affected_devices)
                    else:
                        Alert().delete(alert_id)
    except Exception as e:
        print e

def get_fips(geocode):
    """
    Return and array of FIPS6 codes which identify the county regions 
    effected by the weather alert.

    FIPS6 is a code which uniquely identifies counties in the United States. 
    For more info: https://en.wikipedia.org/wiki/FIPS_county_code

    FIPS returned by NWS alerts can be formatted two ways:
    
    Multiple FIPS per <value> block delimited by space:
    <value>066010 069100 069110 069120</value>
    
    Single FIPS:
    <value>066010</value>
    
    Note: the leading zero will be removed, as FIPS should be 5 digits
    """
    fips = []

    i = 0

    value = geocode[1].text
    if value is not None:
        for item in value.split():
            fips.append(item[1:])
    return fips

def get_ugc(geocode):
    """
    Return and array of UGC codes which identify the UGC regions 
    effected by the weather alert.

    More info on UGC code format: http://www.nws.noaa.gov/emwin/winugc.htm

    UGC returned by NWS alerts can be formatted two ways:
    
    Multiple UGC per <value> block delimited by space:
    <value>NJZ009 NJZ010 NJZ012 NJZ013 NJZ015 NJZ016 NJZ017 NJZ018 NJZ019</value>
    
    Single UGC:
    <value>NJZ009</value>
    """
    ugc = []

    value = geocode[3].text
    if value is not None:
        for item in value.split():
            if item[2] == 'Z':
                # only add UGC codes in format 'Z'
                # those with format 'C' are duplicates of FIPS6
                ugc.append(item)
    return ugc

def get_devices(fips, ugc): 
    """
    Gets devices from M2X which have a matching FIPS6 county code
    or a matching UGC code stored in the device metadata with keys
    'fips6' or 'ugc' respectively.
    """
    devices = []

    for code in fips:  
        try:      
            returned_devices = m2x_client.devices_search(metadata={ 'fips6': { 'match': code } })
            time.sleep(1)
            devices.extend(returned_devices)
        except Exception as e:
            print e

    for code in ugc:        
        try:
            returned_devices = m2x_client.devices_search(metadata={ 'ugc': { 'match': code } })
            time.sleep(1)
            devices.extend(returned_devices)
        except Exception as e:
            print e

    return devices

def update_device(device, alert_url, message, alert_status):  
    """
    Updates weather alert url, message & status streams for a given device.
    """
    print "Updating device streams"
    get_stream(device, 'weather_alert_url').add_value(alert_url)
    time.sleep(1)
    get_stream(device, 'weather_alert_message').add_value(message)
    time.sleep(1)
    get_stream(device, 'weather_alert_status').add_value(alert_status)
    time.sleep(1)

def send_command(command_name, command_data, affected_devices):
    """
    Send a command via M2X to target_devices.
    """
    target_devices = []  
    
    for device in affected_devices:
        target_devices.append(device.id)

    if len(target_devices) > 0:
        try:
            m2x_client.send_command(name=command_name, data=command_data, targets={ 'devices': target_devices })
        except Exception as e:
            print e

def clear_expired_alerts():
    """
    Iterate over all devices with active alerts and check if the alert is expired,
    if so the device is updated to clear the alert.
    """
    print 'Checking for expired alerts & update affected devices'

    try:
        devices = m2x_client.devices_search(streams={'weather_alert_status': { 'match': 'active' } })
        affected_devices = []

        time.sleep(1)

        for device in devices:
            try:
                m2x_response = device.values(streams='weather_alert_url', limit=1)
                alert_url = m2x_response['values'][0]['values']['weather_alert_url']
            except KeyError:
                continue

            if is_expired(alert_url):
                get_stream(device, 'weather_alert_status').add_value('expired')
                affected_devices.append(device)
                Alert().delete(alert_url)

        send_command(command_name="CLEAR_WEATHER_ALERT", command_data={}, affected_devices=affected_devices)
    except Exception as e:
        print e

def is_expired(alert_url):
    """
    Return true if the given alert has expired.
    """
    try:
        alert_content = requests.get(alert_url).text
        time.sleep(1)
        root = ElementTree.fromstring(alert_content)       
        info = root.find(nws_entry_namespace + 'info')
        description = info.find(nws_entry_namespace + 'description').text
        if description.strip() == 'This alert has expired':
            return True
    except Exception as e:
        print "Error checking expiry status, assuming not expired. Alert URL:"
        print alert_url
        print "Error output:"
        print e

    return False

def get_stream(device, stream_name):
    """
    Return an M2X stream
    
    Gets the stream for the given device / stream_name if it exists,
    if not creates the device.
    """
    try:
        stream = device.stream(stream_name)
    except HTTPError:
        stream = device.create_stream(stream_name)

    return stream
