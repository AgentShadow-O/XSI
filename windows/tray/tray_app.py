import os
import sys
import json
import time
import threading
import webbrowser
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

import win32serviceutil
import win32service


class XSITrayApp:

    def __init__(self):
        self.exe_path = (
            sys.executable
            if getattr(sys, "frozen", False)
            else __file__
        )

        self.exe_dir = Path(os.path.dirname(self.exe_path))

        self.config_path = self.exe_dir / "config.json"

        self.service_name = "XSI Agent"

        self._status_text = "Checking..."
        self._server_text = "Unknown"

        self.icon = self.create_icon()

        self.menu = pystray.Menu(
            pystray.MenuItem(
                "Open Dashboard",
                self.open_dashboard
            ),

            pystray.MenuItem(
                lambda item: f"Status: {self._status_text}",
                self.none,
                enabled=False
            ),

            pystray.MenuItem(
                lambda item: f"Server: {self._server_text}",
                self.none,
                enabled=False
            ),

            pystray.Menu.SEPARATOR,

            pystray.MenuItem(
                "Restart Agent Service",
                self.restart_agent
            ),

            pystray.MenuItem(
                "Advanced Settings",
                self.open_settings
            ),

            pystray.Menu.SEPARATOR,

            pystray.MenuItem(
                "Exit Tray App",
                self.on_exit
            )
        )


        self.tray = pystray.Icon(
            "XSI Agent",
            self.icon,
            "XSI Security Agent",
            self.menu
        )


    def create_icon(self):

        icon_path = self.exe_dir / "assets" / "icon.png"

        if icon_path.exists():
            try:
                return Image.open(icon_path)
            except Exception:
                pass


        # fallback icon
        img = Image.new(
            "RGBA",
            (64, 64),
            (0, 0, 0, 0)
        )

        draw = ImageDraw.Draw(img)

        draw.polygon(
            [
                (32, 5),
                (55, 15),
                (55, 45),
                (32, 60),
                (9, 45),
                (9, 15)
            ],
            fill=(31, 107, 79),
            outline=(61, 214, 153)
        )

        return img


    def none(self, icon, item):
        return


    def load_config(self):

        if not self.config_path.exists():
            return {}

        try:
            return json.loads(
                self.config_path.read_text(
                    encoding="utf-8"
                )
            )

        except Exception:
            return {}


    def open_dashboard(self, icon, item):

        config = self.load_config()

        url = config.get("dashboard_url") or config.get("server")

        if url:
            webbrowser.open(url)



    def restart_agent(self, icon, item):

        try:

            win32serviceutil.RestartService(
                self.service_name
            )

            self._status_text = "Restarting..."

        except Exception as e:

            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0,
                f"Failed restarting service:\n\n{e}",
                "XSI Agent",
                0x10
            )



    def open_settings(self, icon, item):

        if self.config_path.exists():

            os.startfile(
                self.config_path
            )

        else:

            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0,
                "config.json not found",
                "XSI Agent",
                0x10
            )



    def update_status(self):

        while True:

            try:

                status = win32serviceutil.QueryServiceStatus(
                    self.service_name
                )[1]


                if status == win32service.SERVICE_RUNNING:

                    self._status_text = "Running"


                elif status == win32service.SERVICE_STOPPED:

                    self._status_text = "Stopped"


                elif status == win32service.SERVICE_START_PENDING:

                    self._status_text = "Starting"


                else:

                    self._status_text = "Busy"



                config = self.load_config()

                self._server_text = config.get(
                    "server",
                    "Not Configured"
                )


                self.tray.title = (
                    f"XSI Security Agent - "
                    f"{self._status_text}"
                )


            except Exception:

                self._status_text = "Service Offline"

                self.tray.title = (
                    "XSI Security Agent - Offline"
                )


            time.sleep(5)



    def on_exit(self, icon, item):

        self.tray.stop()



    def run(self):

        threading.Thread(
            target=self.update_status,
            daemon=True
        ).start()

        self.tray.run()



if __name__ == "__main__":

    XSITrayApp().run()