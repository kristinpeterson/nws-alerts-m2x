from db import DB

class Alert:

    def __init__(self):
        """
        Creates alerts table if not exists.

        id is the unique URL where alert info is served.
        updated is the updated timestamp as string. e.g. "2016-02-02T15:08:00-05:00"
        """
        self.db = DB()
        try:
            self.db.execute("CREATE TABLE alerts (id varchar PRIMARY KEY, updated varchar);")
            self.db.commit()
            print "This is the initial run of the script, this will take longer than usual. Building alerts database"
        except Exception as e:
            self.db.rollback()

    def get(self, alert_id):
        """
        Return alert with the given id.
        """
        alert = None
        try:
            self.db.execute("SELECT * FROM alerts WHERE id = '%s';" % (alert_id))
            alert = self.db.cur.fetchone()
            self.db.commit()
        except Exception as e:
            print e
            self.db.rollback()
        return alert
 
    def create_or_update(self, alert_id, updated):
        """
        Create alert if not exists, or if exists update the updated timestamp for the given alert.
        """
        alert = self.get(alert_id)

        try:
            if alert is None:
                self.db.execute("INSERT INTO alerts (id, updated) VALUES ('%s', '%s', '%s');" % (alert_id, updated))
                self.db.commit()
                return 'created'
            else:
                current_updated_value = alert[1]
                if current_updated_value != updated:
                    self.db.execute("UPDATE alerts SET updated = '%s' WHERE id = '%s';" % (updated, alert_id))
                    self.db.commit()
                    return 'updated'
        except Exception as e:
            print e
            self.db.rollback()

    def delete(self, alert_id):
        """
        Delete the given alert from the database.
        """
        try:
            self.db.execute("DELETE FROM alerts WHERE id = '%s';" % (alert_id))
            self.db.commit()
        except Exception as e:
            self.db.rollback()
