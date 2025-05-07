import asyncio
import pathlib
import datetime
import requests
import time
import traceback

from pywinauto import keyboard
from pywinauto.application import Application
from pywinauto.findwindows import find_elements, find_window
from urllib.parse import urljoin

from lh_manager.liquid_handler.notify import notifier, EmailNotifier

TRILUTION_ERRORS = ['Critical Error', '*** ERROR', 'Error condition']
INJECTION_URL = 'http://localhost:5003'
LH_URL = 'http://localhost:5001'

class TrilutionMonitor:

    def __init__(self, path: str = 'LH.exe', poll_interval: float = 300, notifier: EmailNotifier = notifier):
        self.path = path
        self.poll_interval = poll_interval
        self.connected = False
        self.app = None
        self.clear_error: asyncio.Event = asyncio.Event()
        self.notifier = notifier

    def connect(self):
        try:
            self.app = Application(backend='uia').connect(path=self.path)
            self.connected = True
        except:
            print(f'Could not connect to {self.path}')
            self.connected = False

    async def find_error_async(self) -> str | None:

        error = await asyncio.to_thread(self.find_error)
        print(datetime.datetime.now().isoformat(), error)
        return error
        
    def find_error(self) -> list[str] | None:
        
        if self.app.is_process_running():
            self.connected = True
            application_window = self.app.window(auto_id='ApplicationRun')
            bottom_panel = application_window.child_window(auto_id="PanBotton")
            log = bottom_panel.child_window(auto_id="txtProgress")
            if log.exists():
                txts = log.wrapper_object().texts()
                error_idx = None
                for idx, txt in enumerate(txts):
                    if any(error in txt[0] for error in TRILUTION_ERRORS):
                        error_idx = idx
                        break
                
                if error_idx is not None:
                    # grab all log entries 10 before the error to the end
                    error_txt = [t[0] for t in txts[min(0, error_idx - 10):]]
                else:
                    error_txt = None

                return error_txt
            else:
                self.connected = False
                return None
        else:
            self.connected = False
            return None

        """Alternative: button will read Stopped
        button_panel = bottom_panel.child_window(auto_id="PanManualRunBtn")
        run_button = bottom_panel.child_window(auto_id='btnApplicationRun')
        if 'Stopped' in run_button.wrapper_object().texts():
            return True
        """

    def notify(self, error: list[str]):
        self.notifier.connect()
        print('Sending notification with config ', self.notifier.config)
        self.notifier.notify('Critical Error in Trilution', 'Critical error found: ' + '\n'.join(error))
        self.notifier.disconnect()

    async def handle_error(self, error: list[str]):

        # handle known errors
        if any("Incorrect Instrument or Unit ID/Serial Number 63 not connected." in e for e in error):
            """this error arises when Trilution attempts to initialize GSIOC but there is a GSIOC error.
                to retry, 1. reset GSIOC, 2. restart Trilution auto run, 3. resubmit LH task with incremented ID
            """
            print('Found incorrect instrument error')
            # step 1. reset GSIOC
            response = requests.post(urljoin(INJECTION_URL, '/GSIOC/Reset'))
            print('Resetting GSIOC', response.json())

            # step 2. restart Trilution auto run
            exc = await asyncio.to_thread(self._restart_trilution_collection)
            if exc is not None:
                self.notify(error + ['Attempt to restart trilution failed with error:\n' + exc])

            # step 3. resubmit LH task with incremented ID
            response = requests.post(urljoin(LH_URL, '/LH/ResubmitActiveJob/'))
            print('Resubmitting active job', response.json())
            response = requests.post(urljoin(LH_URL, '/LH/ResetErrorState/'))
            print('Resetting error state', response.json())
        else:
            self.notify(error)

    def _restart_trilution_collection(self) -> str | None:
        try:
            application_window = self.app.window(auto_id='ApplicationRun')
            run_button = application_window.child_window(auto_id='btnApplicationRun')
            application_window.wrapper_object().set_focus()
            time.sleep(1)
            run_button.wrapper_object().click_input()

            dlg = application_window.child_window(auto_id="GilsonMessageBoxForm")
            dlg.wait('visible', timeout=10)
            dlgtext = dlg.child_window(auto_id="messageLbl")
            yesbtn = dlg.child_window(auto_id='btnYes')

            dlg.wrapper_object().set_focus()
            time.sleep(1)
            yesbtn.wrapper_object().click_input()
        except Exception:
            return traceback.format_exc()
    
    async def _prevent_screen_lock(self, interval=60):
        """
        Prevents the screen from locking by sending keystrokes at regular intervals.
        
        :param interval: Time in seconds between each keystroke. Default is 60 seconds.
        """
        try:
            while True:
                # Simulate pressing the Shift key
                keyboard.send_keys('{VK_SHIFT}')
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            print("Screen lock prevention stopped.")

    async def poll(self):

        try:
            keep_alive_task = asyncio.create_task(self._prevent_screen_lock())
            while True:
                error_txt = await self.find_error_async()
                if error_txt is not None:
                    await self.handle_error(error_txt)
                    # wait for error to clear
                    while await self.find_error_async() is not None:
                        await asyncio.sleep(self.poll_interval)    
                else:
                    await asyncio.sleep(self.poll_interval)

        except asyncio.CancelledError:
            pass
        finally:
            print('Shutting down Trilution monitor...')
            keep_alive_task.cancel()


async def monitor():

    notifier.load_config(pathlib.Path('persistent_state') / 'notification_settings.json')
    monitor = TrilutionMonitor(poll_interval=120, notifier=notifier)
    monitor.connect()
    if monitor.connected:
        await monitor.poll()


if __name__ == '__main__':

    asyncio.run(monitor(), debug=True)
