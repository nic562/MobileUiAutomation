import logging
from functools import wraps
from os import environ

from airtest.core.settings import Settings
from airtest.core.api import *

from .my_adb import AdbProxy

LOG_DEBUG = environ.get('LOG_DEBUG', False)

if LOG_DEBUG:
    Settings.LOG_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'logs')
else:
    logging.getLogger('airtest.core.android.py_adb').setLevel(logging.WARNING)
    logging.getLogger('airtest.aircv.utils').setLevel(logging.WARNING)
    logging.getLogger('airtest.core.api').setLevel(logging.INFO)
    logging.getLogger('airtest.aircv.template_matching').setLevel(logging.WARNING)
    logging.getLogger('airtest.utils.nbsp').setLevel(logging.WARNING)
    logging.getLogger('airtest.aircv.keypoint_base').setLevel(logging.WARNING)
    logging.getLogger('airtest.core.android.cap_methods.minicap').setLevel(logging.WARNING)
    logging.getLogger('airtest.core.android.rotation').setLevel(logging.WARNING)
    logging.getLogger('airtest.core.android.touch_methods.maxtouch').setLevel(logging.WARNING)

log = logging.getLogger(__name__)


def init_wrapper_for_resource(*paths: str):
    def wrap_func(dir_name: str = None, ext: str = 'png', clear_resources=True):
        def tracer(func):
            @wraps(func)
            def wrapper(*args, **kv):
                obj = args[0]
                if hasattr(obj, 'curr_resources'):
                    if clear_resources:
                        obj.curr_resources.clear()
                    if dir_name:
                        tmp = [x for x in paths]
                        tmp.append(dir_name)
                    else:
                        tmp = paths
                    obj.curr_resources.append(Resource(*tmp, file_ext=ext))
                return func(*args, **kv)

            return wrapper

        return tracer

    return wrap_func


class Resource:
    def __init__(self, *paths: str, file_ext: str = 'png'):
        self.ext = file_ext
        self.paths = paths

    @property
    def dir_path(self):
        k = '_dir_path'
        if not hasattr(self, k):
            setattr(self, k, os.path.join(*self.paths))
        return getattr(self, k)

    def get_img(self, file_name: str, custom_ext=False):
        return os.path.join(self.dir_path, file_name if custom_ext else f'{file_name}.{self.ext}')

    def get_template(self, img_file_name: str, pos: tuple[float, float] = None, threshold=None,
                     custom_ext=False) -> Template:
        """
        获取图片模板
        :param custom_ext: 是否使用文件名中的扩展名
        :param img_file_name: 图片文件名
        :param pos: AirTest 录屏时的位置
        :param threshold: 识别正确的阈值
        :return:
        """
        return Template(self.get_img(img_file_name, custom_ext), record_pos=pos or None, threshold=threshold)

    def touch(self, img_file_name: str, pos: tuple[float, float] = None, threshold=None,
              custom_ext=False) -> (float, float):
        return touch(self.get_template(img_file_name, pos, threshold, custom_ext=custom_ext))

    def exists(self, img_file_name: str, pos: tuple[float, float] = None, threshold=None, custom_ext=False) -> bool:
        return exists(self.get_template(img_file_name, pos, threshold, custom_ext=custom_ext))

    def text(self, img_file_name: str, content: str, pos: tuple[float, float] = None, threshold=None, custom_ext=False):
        if img_file_name:
            self.touch(img_file_name, pos, threshold, custom_ext=custom_ext)
        text(content)

    def touch_on_exists(self, img_file_name: str, pos: tuple[float, float] = None, threshold=None,
                        custom_ext=False) -> bool:
        p = self.exists(img_file_name, pos, threshold, custom_ext=custom_ext)
        if p:
            touch(p)
            return True
        return False

    def wait(self, img_file_name: str, pos: tuple[float, float] = None, threshold=None, custom_ext=False,
             timeout_seconds=120, interval=10) -> (float, float):
        return wait(self.get_template(img_file_name, pos, threshold, custom_ext=custom_ext), timeout=timeout_seconds,
                    interval=interval)


class OsPermission:

    def permission_device_info(self) -> bool:
        raise NotImplementedError

    def permission_screen_record(self) -> bool:
        raise NotImplementedError

    def permission_require(self) -> bool:
        raise NotImplementedError

    def permission_storage(self) -> bool:
        raise NotImplementedError

    def permission_phone(self) -> bool:
        raise NotImplementedError

    def permission_location(self) -> bool:
        raise NotImplementedError


class AndroidBaseUI(OsPermission):

    def __init__(self, adb: AdbProxy):
        self.adb = adb
        self.device_info = self.adb.get_device_info()
        self.device = init_device('Android', self.adb.get_device_serial())
        res = self.device.get_current_resolution()
        self.screen_width = res[0]
        self.screen_height = res[1]

    def close(self):
        self.adb.close()

    def go_back(self):
        self.adb.go_back()

    @property
    def device_brand(self):
        k = '_device_brand'
        if not hasattr(self, k):
            setattr(self, k, self.device_info.brand.lower())
        return getattr(self, k)

    @staticmethod
    def get_location(tmpl: Template) -> (float, float):
        return loop_find(tmpl)

    @staticmethod
    def home():
        home()

    @staticmethod
    def clear(pkg: str):
        """清理App所有数据，需要到开发者选项中开启’禁止权限监控‘"""
        try:
            clear_app(pkg)
        except Exception as e:
            log.warning(f'Clear App Failed: {e}')

    @staticmethod
    def launch_app(pkg: str, activity: str = None):
        start_app(pkg, activity)

    @staticmethod
    def kill_app(pkg: str):
        stop_app(pkg)

    @staticmethod
    def remove_app(pkg: str):
        try:
            uninstall(pkg)
        except Exception as e:
            log.warning(f'Remove App Failed: {e}')

    @staticmethod
    def install_app(file_path: str):
        """直接执行安装过程，安装过程会卡住主进程，不同设备可能会有界面操作上的问题"""
        return install(file_path)

    def exists_app(self, pkg: str) -> str:
        return self.adb.get_app_version(pkg)
