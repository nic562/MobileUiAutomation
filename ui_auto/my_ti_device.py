# coding=utf8
import logging
import time
from typing import Optional
from requests.exceptions import HTTPError

import tidevice
from tidevice._proto import MODELS
from tidevice._perf import DataType, CallbackType


class IOSDevice(object):
    os_version = None
    model = None
    device_id = None

    def __str__(self):
        return f'型号:{self.model} iOS {self.os_version} 设备ID:{self.device_id}'


class TiDevice(object):
    PERFORMANCE_DATA = DataType
    PERFORMANCE_ALL = [DataType.CPU, DataType.MEMORY, DataType.NETWORK, DataType.FPS, DataType.PAGE,
                       DataType.SCREENSHOT, DataType.GPU]
    PERFORMANCE_DEFAULT = [DataType.CPU, DataType.MEMORY, DataType.NETWORK]

    def __init__(self):
        try:
            self.device = tidevice.Device()
        except Exception as e:
            logging.error(f'连接设备失败，可现尝试使用iTunes连接: {e}')

    def check_auth(self) -> bool:
        try:
            self.device.pair()
            return True
        except Exception as e:
            logging.error(e)
            return False

    def get_device_info(self, dev: IOSDevice = None) -> IOSDevice:
        info = self.device.device_info()
        d = dev or IOSDevice()
        d.device_id = self.device.udid
        d.model = MODELS.get(info['ProductType'])
        d.os_version = info['ProductVersion']
        return d

    def install_ipa(self, ipa_path: str):
        self.device.app_install(ipa_path)

    def uninstall_app(self, bundle_id: str):
        self.device.app_uninstall(bundle_id=bundle_id)

    def launch_app(self, bundle_id: str, args: Optional[list] = [],
                   kill_running: bool = False) -> int:
        try:
            return self.device.app_start(bundle_id, args, kill_running)
        except HTTPError as e:
            raise EnvironmentError(f'''{str(e)}
Please find it in xCode[/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/DeviceSupport] 
and copy it into `$HOME/.tidevice/device-support`''')

    def kill_app(self, bundle_id: str):
        return self.device.app_stop(bundle_id)

    def get_app_version(self, bundle_id: str) -> str:
        for info in self.device.installation.iter_installed():
            if bundle_id == info['CFBundleIdentifier']:
                return info.get('CFBundleShortVersionString', '')

    def performance(self, bundle_id: str, callback: CallbackType, *targets: PERFORMANCE_DATA) -> tidevice.Performance:
        """
        异步获取性能数据
        其中回调函数中，CPU/内存的结果有`pid`，可按进程进行区分
        注意：关于返回的数据值，会带有时间戳`timestamp`,经实测可能后半段数据（将近stop之前部分）的时间戳并不连续，因此建议延迟目标监听时长，以便获取足够的数据
        :param bundle_id: 包名
        :param callback: 异步回调函数，函数被回调时返回2个参数，type：返回数据类型 参考 tidevice.DataType. value: Dict
                        内存单位MB,流量单位KB
        :param targets: 指定获取目标性能类型
        :return: tidevice.Performance 实例, 请手动调用其stop 方法以停止监听
        """
        if not targets:
            targets = self.PERFORMANCE_ALL
        perf = tidevice.Performance(self.device, targets)
        perf.start(bundle_id=bundle_id, callback=callback)
        return perf

    def sync_performance(self, bundle_id: str, listen_seconds: int, *targets: PERFORMANCE_DATA) -> dict:
        """
        同步获取性能数据
        :param bundle_id: 包名
        :param listen_seconds: 监听的秒数
        :param targets: 指定获取目标性能类型
        :return: 返回数据字典
        """
        dm = {}

        def callback(data_type, value):
            # 将各类数据按每1秒进行聚合
            dm.setdefault(data_type, {})
            xd = dm.get(data_type)
            if data_type == self.PERFORMANCE_DATA.NETWORK:
                t = int(value['timestamp'] / 1000)
                xd.setdefault(t, dict(downFlow=0, upFlow=0))
                v = xd[t]
                vt = value['downFlow']
                if vt / 1024 < 10:  # 有一些诡异大波动, 忽略大于10M的
                    v['downFlow'] += vt
                vt = value['upFlow']
                if vt / 1024 < 10:
                    v['upFlow'] += vt
            elif data_type == self.PERFORMANCE_DATA.CPU:
                t = int(value['timestamp'] / 1000)
                xd.setdefault(t, dict(value=0, sys=0))
                v = xd[t]
                v['value'] += value['value']
                v['sys'] += value['sys_value']
            elif data_type == self.PERFORMANCE_DATA.MEMORY:
                t = int(value['timestamp'] / 1000)
                xd.setdefault(t, 0)
                xd[t] += value['value']
            else:
                logging.warning(f'Unhandled dataType:{data_type}')

        perf = self.performance(bundle_id, callback, *targets)
        self.launch_app(bundle_id, kill_running=True)
        time.sleep(listen_seconds)
        perf.stop()
        self.kill_app(bundle_id)
        rs = {}
        for k, _v in dm.items():
            if k == self.PERFORMANCE_DATA.NETWORK:
                du = dict(timestamp=[], value=[])
                dd = dict(timestamp=[], value=[])
                rs['network_up'] = du
                rs['network_down'] = dd
                for _t, j in _v.items():
                    du['timestamp'].append(_t)
                    dd['timestamp'].append(_t)
                    du['value'].append(j['upFlow'])
                    dd['value'].append(j['downFlow'])
            elif k == self.PERFORMANCE_DATA.CPU:
                du = dict(timestamp=[], value=[])
                ds = dict(timestamp=[], value=[])
                rs['cpu'] = du
                rs['cpu_sys'] = ds
                for _t, j in _v.items():
                    du['timestamp'].append(_t)
                    ds['timestamp'].append(_t)
                    du['value'].append(j['value'])
                    ds['value'].append(j['sys'])
                # 第一个值较异常，忽略掉
                du['timestamp'] = du['timestamp'][1:]
                ds['timestamp'] = ds['timestamp'][1:]
                du['value'] = du['value'][1:]
                ds['value'] = ds['value'][1:]
            elif k == self.PERFORMANCE_DATA.MEMORY:
                du = dict(timestamp=[], value=[])
                rs['memory'] = du
                for _t, j in _v.items():
                    du['timestamp'].append(_t)
                    du['value'].append(j)
            else:
                logging.warning(f'Unhandled Format dataType:{k}')
        return rs

    def close(self):
        pass
