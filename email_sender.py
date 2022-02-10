import os
import json
import smtplib
import os.path
import logging
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from pathlib import Path
from subprocess import check_output

import jinja2
import boto3

KEYSTORE_S3_BUCKET = "scylla-qa-keystore"

LOGGER = logging.getLogger(__name__)


class KeyStore:
    def __init__(self):
        self.s3 = boto3.resource("s3")

    def get_file_contents(self, file_name):
        obj = self.s3.Object(KEYSTORE_S3_BUCKET, file_name)
        return obj.get()["Body"].read()

    def get_json(self, json_file):
        # deepcode ignore replace~read~decode~json.loads: is done automatically
        return json.loads(self.get_file_contents(json_file))

    def download_file(self, filename, dest_filename):
        with open(dest_filename, 'wb') as file_obj:
            file_obj.write(self.get_file_contents(filename))

    def get_email_credentials(self):
        return self.get_json("email_config.json")


class AttachementSizeExceeded(Exception):
    def __init__(self, current_size, limit):
        self.current_size = current_size
        self.limit = limit
        super().__init__()


class BodySizeExceeded(Exception):
    def __init__(self, current_size, limit):
        self.current_size = current_size
        self.limit = limit
        super().__init__()


class Email:
    #  pylint: disable=too-many-instance-attributes
    """
    Responsible for sending emails
    """
    _attachments_size_limit = 10485760  # 10Mb = 20 * 1024 * 1024
    _body_size_limit = 26214400  # 25Mb = 20 * 1024 * 1024

    def __init__(self):
        self.sender = "qa@scylladb.com"
        self._password = ""
        self._user = ""
        self._server_host = "smtp.gmail.com"
        self._server_port = "587"
        self._conn = None
        self._retrieve_credentials()
        self._connect()

    def _retrieve_credentials(self):
        keystore = KeyStore()
        creds = keystore.get_email_credentials()
        self._user = creds["user"]
        self._password = creds["password"]

    def _connect(self):
        self.conn = smtplib.SMTP(host=self._server_host, port=self._server_port)
        self.conn.ehlo()
        self.conn.starttls()
        self.conn.login(user=self._user, password=self._password)

    def prepare_email(self, subject, content, recipients, html=True, files=()):  # pylint: disable=too-many-arguments
        msg = MIMEMultipart()
        msg['subject'] = subject
        msg['from'] = self.sender
        assert recipients, "No recipients provided"
        msg['to'] = ','.join(recipients)
        if html:
            text_part = MIMEText(content, "html")
        else:
            text_part = MIMEText(content, "plain")
        msg.attach(text_part)
        attachment_size = 0
        for path in files:
            attachment_size += os.path.getsize(path)
            with open(path, "rb") as fil:
                part = MIMEApplication(
                    fil.read(),
                    Name=os.path.basename(path)
                )
            part['Content-Disposition'] = 'attachment; filename="%s"' % os.path.basename(path)
            msg.attach(part)
        if attachment_size >= self._attachments_size_limit:
            raise AttachementSizeExceeded(current_size=attachment_size, limit=self._attachments_size_limit)
        email = msg.as_string()
        if len(email) >= self._body_size_limit:
            raise BodySizeExceeded(current_size=len(email), limit=self._body_size_limit)
        return email

    def send(self, subject, content, recipients, html=True, files=()):  # pylint: disable=too-many-arguments
        """
        :param subject: text
        :param content: text/html
        :param recipients: iterable, list of recipients
        :param html: True/False
        :param files: paths of the files that will be attached to the email
        :return:
        """
        email = self.prepare_email(subject, content, recipients, html, files)
        self.send_email(recipients, email)

    def send_email(self, recipients, email):
        self.conn.sendmail(self.sender, recipients, email)

    def __del__(self):
        self.conn.quit()


def send_mail(recipients, report):
    loader = jinja2.FileSystemLoader(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'report_templates'))
    env = jinja2.Environment(loader=loader, autoescape=True, extensions=['jinja2.ext.loopcontrols'])
    template = env.get_template("report.html")
    html = template.render(report)
    LOGGER.info("Results has been rendered to html")

    email_client = Email()
    LOGGER.info("Sending email to '%s'", recipients)
    subject = f"{report['status']}: {report['job_name']} {report['build_id']} - {datetime.now()}"

    email_client.send(subject=subject,
                      content=html,
                      recipients=recipients)


def get_scylla_build_info():
    for build_info in Path(os.getenv("WORKSPACE", ".")).glob("**/00-Build.txt"):
        return dict([l.split(': ', maxsplit=1) for l in build_info.read_text().splitlines()])


def get_ci_info():
    return dict(
        build_url=os.getenv("BUILD_URL", "N/A"),
        build_id=os.getenv("BUILD_DISPLAY_NAME", "N/A"),
        job_name=os.getenv("JOB_NAME", "N/A"),
    )


def get_driver_origin_remote(java_driver_path):
    return check_output(["bash", "-c", "git config --get remote.origin.url"], cwd=java_driver_path, text=True).strip()


def create_report(results, **kwargs):
    build_info = get_scylla_build_info()
    scylla_version = f"{build_info.get('scylla-version')}-{build_info.get('scylla-release')}"
    return dict(results=results, scylla_version=scylla_version, **get_ci_info(), **kwargs)
