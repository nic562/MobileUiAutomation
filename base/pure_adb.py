import types

from airtest.core.android.py_adb import ADB

from .my_adb import AdbInterface


class PureAdb(ADB, AdbInterface):
    """
    基于pure-python-adb的封装
    """

    def __init__(self, serial=None):
        if not serial:
            super().__init__()
            dvs = self.devices()
            if dvs:
                serial = dvs[0][0]
            self.connect(serial)
        else:
            super().__init__(serial)

    def get_device_serial(self) -> str:
        return self.serial

    def stream_shell(self, cmd: str) -> types.GeneratorType:
        def handler(connection):
            try:
                while True:
                    d = connection.read(1024)
                    if not d:
                        break
                    yield d.decode('utf-8')
            finally:
                connection.close()

        return self.shell(cmd, handler=handler)

    def run_shell(self, cmd: str, clean_wrap=False) -> str:
        return self.shell(cmd, clean_wrap=clean_wrap)

    def close(self):
        return self.disconnect()

    def add_app(self, apk_path):
        return self.install_app(apk_path, replace=True)

    def remove_app(self, app_bundle: str):
        return self.uninstall_app(app_bundle)

    def push_file(self, local_path: str, device_path: str):
        return self.push(local_path, device_path)

    def pull_file(self, device_path: str, local_path: str):
        return self.pull(device_path, local_path)
