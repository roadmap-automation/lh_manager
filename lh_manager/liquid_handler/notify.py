"""Utility for sending email notifications. Requires a settings file"""

import json
import pathlib
import smtplib

from dataclasses import dataclass, field

@dataclass
class NotifierConfig:
    sender: str = 'no_reply@nist.gov'
    sender_name: str = 'ROADMAP Instrument Control'
    receivers: dict = field(default_factory=dict)
    host: str = 'localhost'
    port: int = 25

class EmailNotifier:
    
    def __init__(self, config: NotifierConfig = NotifierConfig()):
        self.config: NotifierConfig = config
        self._smtp: smtplib.SMTP | None = None
        self._connected: bool = False

    def connect(self):
        try:
            self._smtp = smtplib.SMTP(host=self.config.host, port=self.config.port)
            self._connected = True
        except smtplib.SMTPException:
            print(f"Error: unable to connect to {self.config.host}:{self.config.port}")

    def disconnect(self):
        if self._smtp is not None:
            self._smtp.close()
            self._connected = False

    def notify(self, subject: str, msg: str):
        #print(self._connected, len(self.config.receivers), self.config.receivers)
        self.connect()
        if self._connected & (len(self.config.receivers) > 0):
            receiver_text = '; '.join(f'{k} <{v}>' for k, v in self.config.receivers.items())
            
            message = f"From: {self.config.sender_name} <{self.config.sender}>\nTo: {receiver_text}\nSubject: {subject}\n\n{msg}\n"
            try:
                self._smtp.sendmail(self.config.sender, list(self.config.receivers.values()), message)
                print(f'Sent message {message}')
            except smtplib.SMTPException:
                print(f"Error: unable to send email")
            finally:
                self.disconnect()
    
    def load_config(self, fn: pathlib.Path):

        if fn.exists():
            with open(fn, 'r') as f:
                self.config = NotifierConfig(**json.load(f))
        else:
            print(f'Warning loading config for EmailNotifier: {fn} does not exist')

    @property
    def receivers(self):
        return self.config.receivers

# set global notifier. 
notifier = EmailNotifier()