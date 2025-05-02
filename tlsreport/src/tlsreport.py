import email
import gzip
import os
import time
import imaplib
import json
import logging
import signal
import mysql.connector
import dateutil.parser

class ReportParser:
    def __init__(self,
                 imapserver: str, imapuser: str, imappass: str, imapfolder: str,
                 dbserver: str, dbuser: str, dbpass: str, db: str):
        self.server = imapserver
        self.username = imapuser
        self.password = imappass
        self.folder = imapfolder
        self.dbserver = dbserver
        self.dbuser = dbuser
        self.dbpass = dbpass
        self.db = db

        # connect to database
        db_tries = 10
        while db_tries > 0:
            db_tries -= 1
            try:
                self.db = mysql.connector.connect(
                    host=self.dbserver,
                    user=self.dbuser,
                    password=self.dbpass,
                    database=self.db,
                    connect_timeout=1,
                    buffered=True,
                )
            except mysql.connector.Error as err:
                logging.error(err)
                time.sleep(5)
            else:
                logging.debug(f'Connected to database: {self.db.database}')
                self.cursor = self.db.cursor()
                # self.init_db()
                break
        if not self.db.database:
            exit(1)

    def get_mails(self):
        # Connecting to server
        mailbox = imaplib.IMAP4_SSL(self.server)
        # logging in
        mailbox.login(self.username, self.password)
        # Opening mailbox
        mailbox.select(self.folder)
        # Search for messages
        status, messages = mailbox.search(
            None,
            'ALL' if int(os.environ.get("READ_ALL_MAILS")) else 'UNSEEN')
        # Get available IDs
        mail_ids = messages[0].split()
        logging.debug(f'Status: {status}, Mail ids: {mail_ids}')
        logging.info(f'Found {len(mail_ids)} mail(s)')

        # iterare through available mails
        for mail_id in mail_ids:
            # fetch mail and decode it
            status, data = mailbox.fetch(mail_id, '(RFC822)')
            for response in data:
                if isinstance(response, tuple):
                    message = email.message_from_bytes(response[1])
                    self.parse_mail(message)
        # closing the mailbox and logging out
        mailbox.close()
        mailbox.logout()

    def parse_mail(self, message):
        # get TLS-Report specific headers - if those aren't there, we can ignore the mail
        sender_domain = message.get("TLS-Report-Submitter")
        receiver_domain = message.get("TLS-Report-Domain")
        logging.debug(f'Sender: {sender_domain}, Receiver: {receiver_domain}')

        # We got a report mail! Let's fetch the IDs from the database
        if sender_domain and receiver_domain:
            sender_id = self.get_domain_id(sender_domain)
            receiver_id = self.get_domain_id(receiver_domain)

            # go through all available parts and check if it's a tls report
            for part in message.walk():
                content_type = part.get_content_type()
                logging.debug(f'Content type: {content_type}')

                # check if this part is a report
                if content_type in ('application/tlsrpt+json', 'application/tlsrpt+gzip'):
                    content = part.get_payload(decode=True)

                    # if it's compressed, we need to unzip it first
                    if content_type == 'application/tlsrpt+gzip':
                        logging.debug("Decompressing data...")
                        content = gzip.decompress(content)

                    # read report json into dictionary
                    report = json.loads(content)

                    # get the organization id from the database
                    org_id = self.get_org_id(report.get('organization-name'))

                    # extract the datetimes for the report
                    date_range = report.get('date-range')
                    start_datetime = dateutil.parser.parse(date_range.get('start-datetime'))
                    end_datetime = dateutil.parser.parse(date_range.get('end-datetime'))
                    logging.debug(f'Start datetime: {start_datetime}, End datetime: {end_datetime}')

                    # get the report id and check if it's already there to avoid double entries
                    report_id = report.get('report-id')
                    self.cursor.execute(
                        "SELECT id FROM reports WHERE "
                        "`reportid` = %s AND `receiverdomain` = %s AND `senderdomain` = %s",
                        (report_id, receiver_id, sender_id))
                    found_ids = self.cursor.fetchall()
                    logging.debug(f'Found ids: {found_ids}')
                    if not found_ids:
                        # go through the policy entries in the report and store the data in our db
                        for policy in report.get("policies", {}):
                            summary = policy.get('summary')
                            failure_details = policy.get("failure-details", [])
                            cols = ("(reportid, starttime ,endtime ,organization,"
                                    "senderdomain, receiverdomain, "
                                    "successful, failure, failuredetails)")
                            params = (
                                report_id,
                                start_datetime,
                                end_datetime,
                                org_id,
                                sender_id,
                                receiver_id,
                                summary.get('total-successful-session-count', 0),
                                summary.get('total-failure-session-count', 0),
                                json.dumps(policy.get('failure-details', []))
                            )
                            operation = f"INSERT INTO reports {cols} VALUES (%s{', %s' * (len(params) - 1)})"
                            logging.debug(operation)
                            logging.debug(params)
                            self.cursor.execute(operation, params)
                            self.db.commit()
                            logging.info(f"Added report from {report.get('organization-name')}")
                            if failure_details:
                                logging.warning(f"Failure details: {failure_details}")
                            else:
                                logging.debug(f"No failure details")

    def get_org_id(self, org_name: str) -> int:
        logging.debug(f"Getting org id for {org_name}")
        self.cursor.execute("SELECT id FROM organizations WHERE name = %s", (org_name,))
        result = self.cursor.fetchall()
        if not result:
            logging.debug(f"Adding {org_name} to db")
            self.cursor.execute("INSERT INTO organizations (name) VALUES (%s)", (org_name,))
            self.db.commit()
            result = self.cursor.lastrowid
        else:
            result = result[0]
        logging.debug(f"Result: {result}")
        return result

    def get_domain_id(self, domain_name: str) -> int:
        logging.debug(f"Getting domain id for {domain_name}")
        self.cursor.execute("SELECT id FROM domains WHERE domain = %s", (domain_name,))
        result = self.cursor.fetchall()
        if not result:
            logging.debug(f"Adding {domain_name} to db")
            self.cursor.execute("INSERT INTO domains (domain) VALUES (%s)", (domain_name,))
            self.db.commit()
            result = self.cursor.lastrowid
        else:
            result = result[0]
        logging.debug(f"Result: {result}")
        return result

    def close(self):
        self.db.close()

class ProcessKiller:
    def __init__(self):
        self.killme = False
        signal.signal(signal.SIGINT, self.kill)
        signal.signal(signal.SIGTERM, self.kill)

    def kill(self, signum, frame):
        logging.info(f'Caught signal {signum}, terminating')
        self.killme = True

def main():
    logging.basicConfig(level=os.environ.get('LOG_LEVEL', 'INFO'))

    parser = ReportParser(
        os.environ.get('IMAP_SERVER'),
        os.environ.get('IMAP_USERNAME'),
        os.environ.get('IMAP_PASSWORD'),
        os.environ.get('IMAP_FOLDER'),
        os.environ.get('MYSQL_SERVER'),
        os.environ.get('MYSQL_USER'),
        os.environ.get('MYSQL_PASSWORD'),
        os.environ.get('MYSQL_DATABASE'),
    )

    killer = ProcessKiller()

    try:
        while not killer.killme:
            parser.get_mails()
            # make sure we only sleep a second at a time to be able to gracefully die
            sleeptime = int(os.environ.get('IMAP_INTERVAL', 15)) * 60
            while not killer.killme and sleeptime > 0:
                sleeptime -= 1
                time.sleep(1)
    except KeyboardInterrupt:
        logging.info('Caught keyboard interrupt, terminating')
    parser.close()


if __name__ == '__main__':
    main()
