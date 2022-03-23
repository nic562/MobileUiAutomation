# coding=utf8
import re
import types
from logging import getLogger

logging = getLogger(__name__)


class AndroidDevice(object):
    os_version = None
    sdk_version = None
    model = None
    brand = None
    account_password = None  # 设置权限、安装app时可能要较验设备账号密码

    def __str__(self):
        return f'品牌:{self.brand} 型号:{self.model} Android {self.os_version} (SDK {self.sdk_version})'


class CPUBase:
    def __init__(self, user: int, kernel: int):
        """
        :param user: 用户态时间
        :param kernel: 内核态时间
        """
        self.user = user
        self.kernel = kernel

    def __str__(self):
        return f'CPU User: {self.user}, Kernel: {self.kernel}'


class AppCPU(CPUBase):
    def __str__(self):
        return f'[App]{super().__str__()}'


class SysCPU(CPUBase):
    def __init__(self, user: int, kernel: int, total: int, freq: float):
        """
        :param total: 总的CPU时间
        :param freq: CPU 当前频率占最大频率比例
        """
        super().__init__(user, kernel)
        self.total = total
        self.freq = freq

    def __str__(self):
        return f'[Sys]{super().__str__()}'


class AdbInterface:
    # 基础ADB通讯接口
    def run_shell(self, cmd: str, clean_wrap=False) -> str:
        """
        执行命令
        :param cmd: 命令内容
        :param clean_wrap: 是否清理结果换行
        :return:
        """
        raise NotImplementedError

    def stream_shell(self, cmd: str) -> types.GeneratorType:
        """
        执行命令，返回输出流的迭代器，每次返回一行输出结果
        :param cmd: 命令内容
        :return: 每行输出结果迭代
        """
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def add_app(self, apk_path):
        raise NotImplementedError

    def remove_app(self, app_bundle: str):
        raise NotImplementedError

    def push_file(self, local_path: str, device_path: str):
        raise NotImplementedError

    def pull_file(self, device_path: str, local_path: str):
        raise NotImplementedError

    def get_device_serial(self) -> str:
        raise NotImplementedError


class AdbBase(AdbInterface):
    # 基于ADB的常用功能扩展实现
    exp_version = re.compile(r'versionName=([\w\.]+)')

    def go_back(self):
        return self.run_shell('input keyevent BACK')

    def set_http_proxy(self, host_port: str):
        """
        设置 wifi 代理
        :param host_port: ip:端口 的格式
        :return:
        """
        rs = self.run_shell(f'settings put global http_proxy {host_port}')
        if rs.find('Permission denial') == -1:
            return rs
        raise RuntimeError('Wifi 代理因权限问题而设置失败，请尝试授权：'
                           '\n小米: 在开发者选项里，把“USB调试（安全设置）"打开即可; 或允许USB调试修改权限或模拟点击'
                           '\noppo：在开发者选项里，把"禁止权限监控"打开')

    def close_http_proxy(self):
        return self.set_http_proxy(':0')

    def get_device_resolution(self) -> (int, int):
        k = '_resolution'
        if not hasattr(self, k):
            rs = re.split(r'\s+', self.run_shell('wm size').strip())
            rs = rs[-1].split('x')
            setattr(self, k, (int(rs[0]), int(rs[1])))
        return getattr(self, k)

    def get_device_info(self, dev: AndroidDevice = None) -> AndroidDevice:
        d = dev or AndroidDevice()
        d.os_version = self.run_shell('getprop ro.build.version.release', True)
        d.sdk_version = self.run_shell('getprop ro.build.version.sdk', True)
        d.model = self.run_shell('getprop ro.product.model', True)
        d.brand = self.run_shell('getprop ro.product.brand', True)
        return d

    def launch_app(self, app_pkg: str, app_activity: str = None):
        m = app_activity and f'am start {app_pkg}/{app_activity}' or \
            f'monkey -p {app_pkg} -c android.intent.category.LAUNCHER 1'
        return self.run_shell(m)

    def get_app_version(self, app_bundle: str) -> str:
        rs = self.run_shell(f'pm dump {app_bundle} | grep "version"', True)
        v = self.exp_version.findall(rs)
        v = v and v[0] or None
        return v

    def clear_app(self, app_bundle: str):
        """
        清理缓存和数据
        :param app_bundle:
        :return:
        """
        return self.run_shell(f'pm clear {app_bundle}')

    def kill_app(self, app_bundle: str):
        return self.run_shell(f'am force-stop {app_bundle}', True)

    def find_processes(self, app_bundle: str) -> list:
        """
        每个app可能会有多个进程
        :param app_bundle:
        :return: list: [(进程ID，父进程ID，进程名)]
        """
        rs = self.run_shell(f'ps -A | grep {app_bundle}')
        ll = []
        for x in rs.split('\n'):
            d = re.split(r'\s+', x)
            if not d or not d[0]:
                continue
            ll.append((d[1], d[2], d[-1]))
        return ll

    def find_process_ids(self, app_bundle: str) -> list:
        return [p[0] for p in self.find_processes(app_bundle)]

    def find_main_process_id(self, app_bundle: str) -> str:
        for p in self.find_processes(app_bundle):
            if p[-1].find(':') == -1:
                return p[0]
        raise ValueError('No Process Found!')

    def get_memory_details(self, app_bundle_or_pid: str):
        return self.run_shell(f'dumpsys meminfo {app_bundle_or_pid}')

    def get_memory(self, app_bundle_or_pid: str) -> float:
        """
        :param app_bundle_or_pid:
        :return: 当前内存占用 MB
        """
        logging.debug(f'Getting Memory usage on {app_bundle_or_pid} ...')
        rs = self.get_memory_details(app_bundle_or_pid)
        # logging.warning(f'{app_bundle_or_pid}  details:::{rs}')
        m = re.findall(r'TOTAL PSS:\s+(\d+)', rs)
        if m:
            return int(m[0]) / 1024.0
        if rs.find('No process') != -1:
            # 进程被销毁
            logging.warning(f'process miss:{app_bundle_or_pid}')
            return 0
        if rs.find('MEMINFO in pid') != -1:
            logging.warning('try to get MemoryInfo again!')
            return self.get_memory(app_bundle_or_pid)
        raise ValueError(f'Matching `TOTAL PSS` failed!\n{rs}')

    def get_memory_by_app_processes(self, process_id_list: list) -> float:
        total = 0.0
        for pi in process_id_list:
            total += self.get_memory(pi)
        return total

    def get_cpu_count(self) -> int:
        c = self.run_shell('cat /proc/cpuinfo | grep ^processor | wc -l')
        return int(c)

    def get_cpu_x_curr_freq(self, idx: int) -> int:
        """获取某个CPU核的当前频率
        :param idx: CPU核的下标
        """
        f = self.run_shell(f'cat /sys/devices/system/cpu/cpu{idx}/cpufreq/scaling_cur_freq')
        return int(f)

    def get_cpu_x_max_freq(self, idx: int) -> int:
        """获取某个CPU核的最大频率
        注意：如果提示文件 提示 Permission denied 权限不足，则关闭手机的 USB 调试，和开发者模式，重启手机，再重新开启开发者以及USB调试
        :param idx: CPU核的下标
        """
        f = self.run_shell(f'cat /sys/devices/system/cpu/cpu{idx}/cpufreq/scaling_max_freq')
        try:
            return int(f)
        except ValueError:
            raise RuntimeError(f'文件读取遇到错误: {f}\n请关闭手机的开发者模式，重启手机后再尝试重新开启开发者模式并开启USB调试后进行测试.')

    def get_cpu_freq(self) -> float:
        """计算CPU当前频率占比
        :return 当前时刻所有CPU频率之和/所有CPU频率最大值之和
        """
        c = self.get_cpu_count()
        ct = 0
        mt = 0
        for i in range(c):
            ct += self.get_cpu_x_curr_freq(i)
            mt += self.get_cpu_x_max_freq(i)
        return ct * 1.0 / mt

    def get_cpu_global(self) -> SysCPU:
        """
        # 从/proc/stat读取CPU运行信息, 该文件中的所有值都是从系统启动开始累计到当前时刻
        时间数据单位：jiffies。  1jiffies=0.01秒
        # 参考 https://www.cnblogs.com/wangfengju/p/6172440.html
        :return: 返回系统启动以来(总的用户态时间，总的内核态时间)
        """
        #
        # 1: 总的用户态时间
        # 3: 总的内核态时间
        t = re.split(r'\s+', self.run_shell('cat /proc/stat|head -n 1'))
        total = 0
        for x in t[1:8]:
            if not x:
                continue
            total += int(x)
        return SysCPU(int(t[1]), int(t[3]), total, self.get_cpu_freq())

    def get_cpu_details(self, pid: str, for_all=False):
        """
        从/proc/{pid}/stat 读取目标进程的CPU运行信息，该文件的所有值都是从进程创建开始累计到当前时间
        时间数据单位：jiffies。  1jiffies=0.01秒
        # 参考 https://blog.csdn.net/houzhizhen/article/details/79474427
        """
        rs = self.run_shell(f'cat /proc/{pid}/stat')
        if rs.find('No such') != -1:
            # 进程有可能被销毁
            raise KeyError(f'Bad return: {rs}')
        if rs.find('error') != -1:
            raise ValueError(f'Error return: {rs}')
        if for_all:
            return rs
        m = re.split(r'\s+', rs)
        if m:
            return m
        raise ValueError(f'Format error: {rs}')

    def get_cpu_usage(self, pid) -> AppCPU:
        """
        获取指定进程CPU占用时间
        :param pid: 进程ID
        :return: (进程用户态所占CPU时间, 系统内核态所占CPU时间)
        """
        logging.debug(f'Getting CPU usage on {pid} ...')
        p = self.get_cpu_details(pid)
        # 13：utime 该进程用户态时间
        # 14：stime 该进程内核态时间
        return AppCPU(int(p[13]), int(p[14]))

    def get_cpu_usage_by_app_processes(self, process_id_list: list[int], auto_remove_miss_process=True) -> AppCPU:
        """
        每个App可能会有多个进程
        获取目标Apps进程id列表的最新CPU占用时间汇总
        :param process_id_list: App的进程列表
        :param auto_remove_miss_process: 是否从process_id_list中清理不存在进程ID
        :return: 当前总的目标AppCPU时间
        """
        total_u, total_s = 0, 0
        miss_pid_list = []
        for pi in process_id_list:
            try:
                cpu_use = self.get_cpu_usage(pi)
            except KeyError as e:
                if str(e).find('No such') != -1:
                    logging.warning(f'process miss:{pi}')
                    miss_pid_list.append(pi)
                    continue
                raise e
            total_u += cpu_use.user
            total_s += cpu_use.kernel
        if auto_remove_miss_process:
            for xp in miss_pid_list:
                process_id_list.remove(xp)
        return AppCPU(total_s, total_s)

    @staticmethod
    def compute_cpu_rate(
            start_sys_cpu: SysCPU,
            end_sys_cpu: SysCPU,
            start_app_cpu: AppCPU,
            end_app_cpu: AppCPU,
            is_normalized=True
    ) -> (float, float):
        """
        计算一个周期内的App的CPU占用率
        注意：区分规范化和非规范化  https://bbs.perfdog.qq.com/detail-146.html
        :param start_sys_cpu: 周期开始时系统占用CPU时间
        :param end_sys_cpu: 周期结束时系统占用CPU时间
        :param start_app_cpu: 周期开始时应用占用CPU时间
        :param end_app_cpu: 周期结束时应用占用CPU时间
        :param is_normalized: 是否规范化
        :return: (App用户态+内核态占用率，系统总用户态+内核态占用率)
        """
        sys_u = end_sys_cpu.user - start_sys_cpu.user
        sys_s = end_sys_cpu.kernel - start_sys_cpu.kernel
        app_u = end_app_cpu.user - start_app_cpu.user
        app_s = end_app_cpu.kernel - start_app_cpu.kernel
        total_cpu = end_sys_cpu.total - start_sys_cpu.total
        rs = (app_u + app_s) * 1.0 / total_cpu, (sys_u + sys_s) * 1.0 / total_cpu
        if is_normalized:
            rs = rs[0] * end_sys_cpu.freq, rs[1] * end_sys_cpu.freq
            logging.debug('CPU Normalized: %.2f%% on Freq: %.2f%%', rs[0] * 100, end_sys_cpu.freq * 100)
        else:
            logging.debug('CPU: %.2f%%', rs[0] * 100)
        return rs

    def get_app_user_id(self, app_bundle: str):
        """
        获取某个应用在系统中分配的用户ID，通常一个应用(不论有多少进程)有全局唯一的用户ID
        :param app_bundle:
        :return:
        """
        rs = self.run_shell(f'dumpsys package {app_bundle} | grep userId=')
        u = re.findall(r'userId=(\d+)', rs)
        if u:
            return u[0]
        raise ValueError(f'Matching userId error: {rs}')

    def _get_net_flow_raw(self, uid: str, target_net_file: str):
        # 状态字参考:https://users.cs.northwestern.edu/~agupta/cs340/project2/TCPIP_State_Transition_Diagram.pdf
        # https://guanjunjian.github.io/2017/11/09/study-8-proc-net-tcp-analysis/
        # https://zhuanlan.zhihu.com/p/49981590
        rs = self.run_shell(f'cat /proc/net/{target_net_file} | grep {uid}')
        if rs:
            ll = []
            for r in rs.split('\n'):
                if not r:
                    continue
                m = re.split(r'\s+', r.strip())
                if m and m[7] == uid:
                    ll.append(m)
            return ll

    _net_files = ['tcp', 'tcp6', 'udp', 'udp6']

    def cat_file(self, file_path):
        return self.run_shell(f'cat {file_path}')

    def del_file(self, file_path):
        return self.run_shell(f'rm {file_path}')

    def send_broadcast(self, broadcast_action: str, *args: str, **kv: str):
        vv = map(lambda x: f"-e {x[0]} {x[1]}", kv.items())
        return self.run_shell(
            f'am broadcast -a {broadcast_action} {" ".join(args)} {" ".join(vv)}')

    def ping(self, h: str) -> bool:
        rs = self.run_shell(f'ping -c 1 -W 1 {h}')
        return rs.rfind('1 received') != -1


class AdbProxy(AdbBase):
    # ADB 代理，用于衔接adb协议的不同底层实现

    def __init__(self, adb_implement: AdbInterface):
        self._impl = adb_implement

    def get_device_serial(self) -> str:
        return self._impl.get_device_serial()

    def run_shell(self, cmd: str, clean_wrap=False) -> str:
        return self._impl.run_shell(cmd, clean_wrap=clean_wrap)

    def stream_shell(self, cmd: str) -> types.GeneratorType:
        return self._impl.stream_shell(cmd)

    def close(self):
        return self._impl.close()

    def add_app(self, apk_path):
        return self._impl.add_app(apk_path)

    def remove_app(self, app_bundle: str):
        return self._impl.remove_app(app_bundle)

    def push_file(self, local_path: str, device_path: str):
        return self._impl.push_file(local_path, device_path)

    def pull_file(self, device_path: str, local_path: str):
        return self._impl.pull_file(device_path, local_path)
