from utils import update_alert_messages
from utils import clear_expired_alerts

# TODO:
# when alert expires, delete from db
# when a device updates location - update it's FIPS automatically (IFTTT)
# what happens if a device moves, and it still has the old alert_id?
# 

print "running..."

# monitor length of script runtime
from datetime import datetime
startTime = datetime.now()

update_alert_messages()
clear_expired_alerts()

print "How long did this script run? : "
print datetime.now() - startTime
