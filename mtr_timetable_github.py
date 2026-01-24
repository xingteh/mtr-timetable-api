'''
Minecraft Transit Railway 时刻表生成程序，生成车站发车和列车时刻表
Generate station departures and train timetables for Minecraft Transit Railway.
'''

# 导入必要的模块
from datetime import datetime, timedelta, timezone  # 用于处理日期和时间
from difflib import SequenceMatcher  # 用于字符串相似度比较
from statistics import mode  # 用于计算众数
import json  # 用于处理JSON数据
import pickle  # 用于序列化和反序列化Python对象
import random  # 用于生成随机数

from opencc import OpenCC  # 用于中文简繁转换

# 创建OpenCC实例，用于不同方向的中文转换
tt_opencc1 = OpenCC('s2t')  # 简体转繁体
tt_opencc2 = OpenCC('t2jp')  # 繁体转日语汉字
tt_opencc3 = OpenCC('t2s')  # 繁体转简体
tt_opencc4 = OpenCC('jp2t')  # 日语汉字转繁体

# 列车类型注释
# 区间快速 - 西武池袋快速 #00CCFF
# 快速 - 京王调布快速 #0F4E8C
# 区间急行 - 京王调布区间急行 #D3C427
# 急行 - 京王调布急行 #05B08D
# 特急 - JR八王子特急 #CB3550
# 卧铺列车 - JR八王子特急 #CB3550
# 快特 - 小田急小田原快急 #FF8F0C

# 列车类型映射表：键为线路标识，值为列车类型
EXPRESS_TABLE = {...: ...,
                 'CFR||MED': '快速',  # CFR中等速度列车
                 'CFR||FAST': '急行',  # CFR快速列车
                 'CFR||NIGHT': '卧铺车',  # CFR夜间卧铺车
                 'CrossCountry': '特急',  # 跨国列车
                #  'CrossCountry||Portsmouth - Carmine 02': '急行',
                #  'CrossCountry||Portsmouth-Kirkenkessie 05': '急行',
                 'CrossCountry||Mimatsu->Portsmouth 11': '急行',  # 特定路线急行
                 'CrossCountry||Portsmouth->Mimatsu 11': '急行',  # 特定路线急行
                 'CrossCountry||Seowonju - Airport 12': '快速',  # 机场线快速
                 'CrossCountry||Airport - Seowonju 12': '快速',  # 机场线快速
                 'CrossCountry||Liskeard Intl - Portsmouth Express 01': '快速特急',  # 国际线快速特急
                 'CrossCountry||Portsmouth - Liskeard Intl Express 01': '快速特急',  # 国际线快速特急
                 '大立綫': '特急',  # 大立线特急
                 '歐洲之星|Eurostar': '特急',  # 欧洲之星特急
                 'KTT': '特急',  # KTT特急
                 ...: ...}

# 列车类型颜色映射表：键为列车类型，值为颜色代码
COLOR_TABLE = {'区间快速': '#00CCFF',  # 区间快速的颜色
               '快速': '#0F4E8C',  # 快速的颜色
               '区间急行': '#D3C427',  # 区间急行的颜色
               '急行': '#05B08D',  # 急行的颜色
               '特急': '#CB3550',  # 特急的颜色
               '快速特急': '#FF8F0C',  # 快速特急的颜色
               '卧铺车': '#CB3550'}  # 卧铺车的颜色


def route_name_to_id(data: dict, route_name: str) -> list[str]:
    '''
    将线路名称转换为线路ID
    
    Args:
        data: 包含线路信息的数据字典
        route_name: 线路名称
        
    Returns:
        包含线路ID的列表
    '''
    # 首先检查线路名称是否直接匹配线路ID
    for route in data[0]['routes']:
        if route_name == route['id']:
            return [route_name]

    # 将线路名称转换为小写，用于不区分大小写的比较
    route_name = route_name.lower()
    result = []
    
    # 遍历所有线路
    for route in data[0]['routes']:
        output: str = route['id']  # 线路ID
        n: str = route['name']  # 线路名称
        number: str = route['number']  # 线路编号
        
        # 构建可能的线路名称列表
        route_names = [n, n.split('|')[0]]  # 完整名称和第一个部分
        
        # 处理包含英文名称的情况
        if ('||' in n and n.count('|') > 2) or \
                ('||' not in n and n.count('|') > 0):
            eng_name = n.split('|')[1].split('|')[0]  # 提取英文名称
            if eng_name != '':
                route_names.append(eng_name)

        # 如果有线路编号，添加带编号的名称
        if number not in ['', ' ']:
            for tmp_name in route_names[1:]:
                route_names.append(tmp_name + ' ' + number)

        # 检查每个可能的名称是否匹配
        for x in route_names:
            x = x.lower().strip()  # 转换为小写并去除空格
            if x == route_name:
                result.append(output)
                continue

            # 跳过纯ASCII字符的名称（可能是英文）
            if x.isascii():
                continue

            # 尝试将繁体转换为简体进行匹配
            simp1 = tt_opencc3.convert(x)  # 繁体转简体
            if simp1 == route_name:
                result.append(output)
                continue

            # 尝试将日语汉字转换为繁体再转简体进行匹配
            simp2 = tt_opencc3.convert(tt_opencc4.convert(x))  # 日语汉字转繁体再转简体
            if simp2 == route_name:
                result.append(output)
                continue

    return result


def get_close_matches(words, possibilities, cutoff=0.2):
    '''
    查找与给定单词最相似的匹配项
    
    Args:
        words: 要匹配的单词列表
        possibilities: 可能的匹配项列表，每个元素是(名称, ID)的元组
        cutoff: 相似度阈值，默认为0.2
        
    Returns:
        最相似的匹配项的ID
    '''
    # 初始化结果列表，包含一个默认值(-1, None)
    result = [(-1, None)]
    s = SequenceMatcher()  # 创建SequenceMatcher实例用于计算字符串相似度
    
    # 遍历每个要匹配的单词
    for word in words:
        s.set_seq2(word)  # 设置第二个序列为当前单词
        
        # 遍历每个可能的匹配项
        for x, y in possibilities:
            s.set_seq1(x)  # 设置第一个序列为当前可能的匹配项
            
            # 快速检查相似度，提高性能
            if s.real_quick_ratio() >= cutoff and \
                    s.quick_ratio() >= cutoff:
                # 计算实际相似度
                ratio = s.ratio()
                if ratio >= cutoff:
                    # 添加到结果列表
                    result.append((ratio, y))

    # 返回相似度最高的匹配项的ID
    return max(result)[1]


def station_name_to_id(data: dict, sta: str,
                       fuzzy_compare=True) -> str:
    '''
    将车站名称转换为车站ID
    
    Args:
        data: 包含车站信息的数据字典
        sta: 车站名称
        fuzzy_compare: 是否使用模糊匹配，默认为True
        
    Returns:
        车站ID，如果未找到则返回None
    '''
    # 将车站名称转换为小写，用于不区分大小写的比较
    sta = sta.lower()
    # 尝试不同的中文转换形式
    tra1 = tt_opencc1.convert(sta)  # 简体转繁体
    sta_try = [sta, tra1, tt_opencc2.convert(tra1)]  # 原始、繁体、日语汉字形式

    all_names = []  # 用于模糊匹配的所有车站名称列表
    stations = data['stations']  # 获取所有车站
    output = None  # 输出结果
    has_station = False  # 是否找到车站
    
    # 遍历所有车站
    for station_id, station_dict in stations.items():
        s_1 = station_dict['name']  # 车站全名
        # 如果车站有坐标信息，添加到模糊匹配列表
        if 'x' in station_dict and 'z' in station_dict:
            all_names.append((s_1, station_id))

        # 提取车站名称的不同部分
        s_split = station_dict['name'].split('|')
        s_2_2 = s_split[-1]  # 最后一个部分
        s_2 = s_2_2.split('/')[-1]  # 最后一个部分的最后一个子部分
        s_3 = s_split[0]  # 第一个部分
        
        # 检查是否匹配任何形式的车站名称
        for st in sta_try:
            if st in (s_1.lower(), s_2.lower(), s_2_2.lower(), s_3.lower()):
                has_station = True
                output = station_id
                break

    # 如果未找到车站且启用模糊匹配，尝试模糊匹配
    if has_station is False and fuzzy_compare is True:
        output = get_close_matches(sta_try, all_names)

    return output


def station_short_id_to_id(data: dict, short_id: int) -> str:
    '''
    将车站短ID转换为车站ID
    
    Args:
        data: 包含车站信息的数据字典
        short_id: 车站短ID（整数形式）
        
    Returns:
        车站ID，如果未找到则返回None
    '''
    # 将短ID转换为十六进制字符串（去除'0x'前缀）
    short_id = hex(short_id)[2:]
    stations = data['stations']  # 获取所有车站
    output = None  # 输出结果
    
    # 遍历所有车站，查找匹配的短ID
    for station_id, station_dict in stations.items():
        if short_id == station_dict['station']:
            output = station_id
            break

    return output


def convert_time(t, use_second=False):
    '''
    将秒数转换为时间字符串
    
    Args:
        t: 时间（秒）
        use_second: 是否包含秒，默认为False
        
    Returns:
        格式化的时间字符串
    '''
    if use_second is True:
        # 计算小时、分钟和秒
        hour = str(t // (60 * 60)).rjust(2, '0')  # 小时，补零到2位
        minute = str((t % 3600) // 60).rjust(2, '0')  # 分钟，补零到2位
        second = str(t % 60).rjust(2, '0')  # 秒，补零到2位
        result = ':'.join([hour, minute, second])  # 组合成时间字符串
    else:
        # 计算小时、分钟
        hour = t // (60 * 60)  # 小时
        minute = (t % 3600) // 60  # 分钟
        second = t % 60  # 秒
        
        # 处理秒数超过60的情况
        if second >= 60:
            minute += 1
        
        # 处理分钟超过60的情况
        if minute >= 60:
            minute -= 60
            hour += 1
        
        # 处理小时为24的情况（转换为0）
        if hour == 24:
            hour = 0
        
        # 转换为字符串并补零
        hour = str(hour).rjust(2, '0')  # 小时，补零到2位
        minute = str(minute).rjust(2, '0')  # 分钟，补零到2位
        result = ':'.join([hour, minute])  # 组合成时间字符串

    return result


def get_timetable(data, dep_data, station_name, route_name, use_second=False):
    '''
    获取指定车站和线路的时刻表
    
    Args:
        data: 包含车站信息的数据字典
        dep_data: 发车数据
        station_name: 车站名称
        route_name: 线路名称
        use_second: 是否包含秒，默认为False
        
    Returns:
        包含(线路ID, 时间)元组的列表
    '''
    # 将车站名称转换为车站ID
    station_id = station_name_to_id(data, station_name)
    # 获取该车站该线路的发车数据
    data = dep_data[station_id][route_name]
    # 按时间排序
    data.sort(key=lambda x: x[1])
    output = []
    
    # 遍历发车数据，转换时间格式并去重
    for d in data:
        result = convert_time(d[1], use_second)  # 转换时间格式
        if result not in output:  # 去重
            output.append((d[0], result))  # 添加到输出列表

    return output


def get_train(data, station, train_id: int,
              station_tt: dict[str, dict[str, tuple]],
              train_tt: dict[str, list[tuple]]):
    '''
    获取指定列车的详细信息
    
    Args:
        data: 包含车站和线路信息的数据字典
        station: 车站名称或短ID
        train_id: 列车ID
        station_tt: 车站时刻表数据
        train_tt: 列车时刻表数据
        
    Returns:
        包含线路名称、车站列表和状态信息的元组，或None/False表示失败
    '''
    station_id = None
    try:
        # 尝试将station转换为整数，作为短ID处理
        sta_short_id = int(station)
        station_id = station_short_id_to_id(data, sta_short_id)
    except ValueError:
        # 否则作为车站名称处理
        station_id = station_name_to_id(data, station)

    # 如果未找到车站，返回None
    if station_id is None:
        return None

    try:
        # 获取列车的线路ID、索引和发车时间
        route_id, i, dep = station_tt[station_id][train_id]
    except KeyError:
        # 如果未找到列车信息，返回False
        return False

    # 获取列车的详细时刻表
    train: list = train_tt[route_id][i]
    all_stations = data['stations']  # 所有车站信息
    route_data = data['routes'][route_id]  # 线路信息
    route_name: str = route_data['name']  # 线路名称
    route_name = route_name.replace('||', ' ').replace('|', ' ')  # 格式化线路名称
    route_stations = route_data['stations']  # 线路经过的车站

    # 转换时间格式
    timetable = [convert_time(x % 86400, use_second=True) for x in train]
    output = []  # 输出列表
    msg = tuple()  # 状态信息
    _t2 = 2 ** 32  # 初始值
    
    # 遍历线路上的每个车站
    for i, x in enumerate(route_stations):
        if i == 0:
            # 第一个车站，没有到达时间
            t1 = None
        else:
            try:
                # 获取到达时间并从列表中移除
                t1 = timetable.pop(0)
                train.pop(0)
            except IndexError:
                # 如果列表为空，继续下一个车站
                continue

        if i == len(route_stations) - 1:
            # 最后一个车站，没有发车时间
            t2 = None
            _t2 = None
        else:
            try:
                # 获取发车时间并从列表中移除
                t2 = timetable.pop(0)
                _t2 = train.pop(0)
            except IndexError:
                # 如果列表为空，继续下一个车站
                continue

        # 检查是否为当前列车的停站
        if _t2 is not None and _t2 % 86400 == dep % 86400:
            # 停站
            msg = (all_stations[x['id']]['name'].split('|')[0], )

        # 获取车站名称并添加到输出列表
        station_name = all_stations[x['id']]['name']
        output.append((station_name.split('|')[0], t1, t2, x['id']))

    # 返回线路名称、车站列表和状态信息
    return route_name, output, msg


def route_random_train(data_v3, data, route, trains: dict[str, list],
                       departure_time: int = None):
    '''
    获取指定线路的随机列车信息
    
    Args:
        data_v3: 包含线路信息的数据字典（v3格式）
        data: 包含车站和线路信息的数据字典
        route: 线路名称
        trains: 列车时刻表数据
        departure_time: 发车时间（秒），默认为当前时间
        
    Returns:
        包含线路名称、车站列表和状态信息的元组，或None表示失败
    '''
    # 将线路名称转换为线路ID
    route_id = route_name_to_id(data_v3, route)
    if route_id == []:
        return None

    all_stations = data['stations']  # 所有车站信息
    tz = 8  # 时区（+8）
    
    # 如果未指定发车时间，使用当前时间
    if departure_time is None:
        dtz = timezone(timedelta(hours=tz))  # 创建时区对象
        t1 = datetime.now().replace(year=1970, month=1, day=1)  # 创建当前时间对象（1970年基准）
        try:
            t1 = t1.astimezone(dtz).replace(tzinfo=timezone.utc)  # 转换时区
        except OSError:
            t1 = t1.replace(tzinfo=timezone.utc)  # 处理时区转换失败的情况

        departure_time = round(t1.timestamp())  # 转换为时间戳

    departure_time %= 86400  # 取模24小时

    # 构建线路和列车的列表
    all_trains = [(x, trains[x]) for x in route_id if x in trains]
    train = [-1]  # 初始列车值
    tries = 3000  # 尝试次数
    
    # 尝试找到符合时间条件的列车
    while (departure_time < min(train) or departure_time > max(train)) and \
            (departure_time + 86400 < min(train) or
             departure_time + 86400 > max(train)):
        route = random.choice(all_trains)  # 随机选择线路
        if len(route[1]) == 0:
            continue  # 跳过无列车的线路

        train = random.choice(route[1])  # 随机选择列车
        route_data = data['routes'][route[0]]  # 线路信息
        tries -= 1
        if tries == 0:
            break  # 达到最大尝试次数

        if len(train) == 0:
            continue  # 跳过无时刻表的列车

    # 如果未找到符合条件的列车，随机选择一个
    if train == [-1]:
        route = [0, 0]
        tries = 1000
        while len(route[1]) == 0 or len(train) == 0:
            route = random.choice(all_trains)
            train = random.choice(route)
            route_data = data['routes'][route[0]]
            tries -= 1
            if tries == 0:
                break

    # 处理线路名称和车站
    route_name: str = route_data['name']
    route_name = route_name.replace('||', ' ').replace('|', ' ')  # 格式化线路名称
    route_stations = route_data['stations']  # 线路经过的车站

    # 转换时间格式
    timetable = [convert_time(x % 86400, use_second=True) for x in train]
    output = []  # 输出列表
    msg = tuple()  # 状态信息
    _t2 = 2 ** 32  # 初始值
    
    # 遍历线路上的每个车站
    for i, x in enumerate(route_stations):
        if i == 0:
            # 第一个车站，没有到达时间
            t1 = None
            _t1 = None
        else:
            # 获取到达时间
            t1 = timetable.pop(0)
            _t1 = train.pop(0)

        # 检查列车是否在运行中
        if _t1 is not None and _t2 is not None and \
                (_t2 <= departure_time <= _t1 or
                 _t2 <= departure_time + 86400 <= _t1):
            # 运行中
            last_id = all_stations[route_stations[i - 1]['id']]
            msg = ((last_id['name'].split('|')[0],
                    all_stations[x['id']]['name'].split('|')[0]))

        if i == len(route_stations) - 1:
            # 最后一个车站，没有发车时间
            t2 = None
            _t2 = None
        else:
            # 获取发车时间
            t2 = timetable.pop(0)
            _t2 = train.pop(0)

        # 检查列车是否在站内
        if _t1 is not None and _t2 is not None and \
                (_t1 < departure_time < _t2 or
                 _t1 < departure_time + 86400 < _t2):
            # 停站
            msg = (all_stations[x['id']]['name'].split('|')[0], )

        # 添加车站信息到输出列表
        station_name = all_stations[x['id']]['name']
        output.append((station_name.split('|')[0], t1, t2, x['id']))

    # 返回线路名称、车站列表和状态信息
    return route_name, output, msg


def random_train(data, trains: dict[str, list], departure_time: int = None):
    '''
    随机获取一辆列车的信息
    
    Args:
        data: 包含车站和线路信息的数据字典
        trains: 列车时刻表数据
        departure_time: 发车时间（秒），默认为当前时间
        
    Returns:
        包含线路名称、车站列表和状态信息的元组
    '''
    all_stations = data['stations']  # 所有车站信息
    tz = 8  # 时区（+8）
    
    # 如果未指定发车时间，使用当前时间
    if departure_time is None:
        dtz = timezone(timedelta(hours=tz))  # 创建时区对象
        t1 = datetime.now().replace(year=1970, month=1, day=1)  # 创建当前时间对象（1970年基准）
        try:
            t1 = t1.astimezone(dtz).replace(tzinfo=timezone.utc)  # 转换时区
        except OSError:
            t1 = t1.replace(tzinfo=timezone.utc)  # 处理时区转换失败的情况

        departure_time = round(t1.timestamp())  # 转换为时间戳

    departure_time %= 86400  # 取模24小时

    # 构建列车列表
    all_trains = list(trains.items())
    train = [-1]  # 初始列车值
    tries = 3000  # 尝试次数
    
    # 尝试找到符合时间条件的列车
    while (departure_time < min(train) or departure_time > max(train)) and \
            (departure_time + 86400 < min(train) or
             departure_time + 86400 > max(train)):
        route = random.choice(all_trains)  # 随机选择线路
        if len(route[1]) == 0:
            continue  # 跳过无列车的线路

        route_data = data['routes'][route[0]]  # 线路信息
        if route_data['hidden'] is True:
            continue  # 跳过隐藏的线路

        train = random.choice(route[1])  # 随机选择列车
        tries -= 1
        if tries == 0:
            break  # 达到最大尝试次数

    # 处理线路名称和车站
    route_name: str = route_data['name']
    route_name = route_name.replace('||', ' ').replace('|', ' ')  # 格式化线路名称
    route_stations = route_data['stations']  # 线路经过的车站

    # 转换时间格式
    timetable = [convert_time(x % 86400, use_second=True) for x in train]
    output = []  # 输出列表
    msg = tuple()  # 状态信息
    _t2 = 2 ** 32  # 初始值
    
    # 遍历线路上的每个车站
    for i, x in enumerate(route_stations):
        if i == 0:
            # 第一个车站，没有到达时间
            t1 = None
            _t1 = None
        else:
            # 获取到达时间
            t1 = timetable.pop(0)
            _t1 = train.pop(0)

        # 检查列车是否在运行中
        if _t1 is not None and _t2 is not None and \
                (_t2 <= departure_time <= _t1 or
                 _t2 <= departure_time + 86400 <= _t1):
            # 运行中
            last_id = all_stations[route_stations[i - 1]['id']]
            msg = ((last_id['name'].split('|')[0],
                    all_stations[x['id']]['name'].split('|')[0]))

        if i == len(route_stations) - 1:
            # 最后一个车站，没有发车时间
            t2 = None
            _t2 = None
        else:
            # 获取发车时间
            t2 = timetable.pop(0)
            _t2 = train.pop(0)

        # 检查列车是否在站内
        if _t1 is not None and _t2 is not None and \
                (_t1 < departure_time < _t2 or
                 _t1 < departure_time + 86400 < _t2):
            # 停站
            msg = (all_stations[x['id']]['name'].split('|')[0], )

        # 添加车站信息到输出列表
        station_name = all_stations[x['id']]['name']
        output.append((station_name.split('|')[0], t1, t2, x['id']))

    # 返回线路名称、车站列表和状态信息
    return route_name, output, msg


def get_text_timetable(data, station, departure_time: int,
                       station_tt: dict[str, dict[str, tuple]]):
    '''
    获取指定车站的文本格式时刻表
    
    Args:
        data: 包含车站和线路信息的数据字典
        station: 车站名称或短ID
        departure_time: 发车时间（秒）
        station_tt: 车站时刻表数据
        
    Returns:
        文本格式的时刻表字符串，或None表示失败
    '''
    station_id = None
    try:
        # 尝试将station转换为整数，作为短ID处理
        sta_short_id = int(station)
        station_id = station_short_id_to_id(data, sta_short_id)
    except ValueError:
        # 否则作为车站名称处理
        station_id = station_name_to_id(data, station)

    # 如果未找到车站，返回None
    if station_id is None:
        return None

    output = ''  # 输出字符串
    dep_dict: dict[str, list] = {}  # 发车数据字典
    
    # 遍历车站的所有列车
    for train_id, (route_id, i, dep) in station_tt[station_id].items():
        if route_id not in dep_dict:
            dep_dict[route_id] = []

        dep_dict[route_id].append((dep, train_id, i))  # 添加当前发车时间
        dep_dict[route_id].append((dep + 86400, train_id, i))  # 添加次日发车时间

    # 按线路名称排序
    k = list(dep_dict.items())
    k.sort(key=lambda x: data['routes'][x[0]]['name'])
    
    # 遍历每条线路
    for route_id, x in k:
        x.sort()  # 按发车时间排序
        route_data = data['routes'][route_id]  # 线路信息
        route_name: str = route_data['name']  # 线路名称
        route_name = route_name.replace('||', ' ').replace('|', ' ')  # 格式化线路名称
        count = 1  # 计数
        template = f'{route_name}: '  # 模板字符串
        
        # 遍历发车时间
        for y in x:
            dep = y[0]  # 发车时间
            train_id = y[1]  # 列车ID
            if dep > departure_time:
                # 转换时间格式并添加到模板
                dep_time = convert_time(dep % 86400, use_second=True)
                template += f'{dep_time}({train_id}), '
                count += 1
                if count == 3:
                    # 每条线路只显示3个发车时间
                    template = template[:-2] + '\n'
                    output += template
                    break

    # 获取车站信息
    station_data = data['stations'][station_id]
    original_station_name = station_data['name'].split('|')[0]  # 车站名称
    short_id = station_data['station']  # 车站短ID
    short_id = int('0x' + str(short_id), 16)  # 转换为整数
    
    # 构建结果字符串
    result = f'{original_station_name}站 - ID: {short_id}\n{output}'
    # 转换为简体中文
    return tt_opencc3.convert(tt_opencc4.convert(result))


def get_sta_timetable(data_v3, data, station, routes, template_file,
                      station_tt: dict[str, dict[str, tuple]]):
    '''
    获取指定车站和线路的HTML格式时刻表
    
    Args:
        data_v3: 包含线路信息的数据字典（v3格式）
        data: 包含车站和线路信息的数据字典
        station: 车站名称或短ID
        routes: 线路名称或线路名称列表
        template_file: HTML模板文件路径
        station_tt: 车站时刻表数据
        
    Returns:
        HTML格式的时刻表字符串，或None/False表示失败
    '''
    # 如果routes是字符串，转换为列表
    if isinstance(routes, str):
        routes = [routes]

    station_id = None
    try:
        # 尝试将station转换为整数，作为短ID处理
        sta_short_id = int(station)
        station_id = station_short_id_to_id(data, sta_short_id)
    except ValueError:
        # 否则作为车站名称处理
        station_id = station_name_to_id(data, station)

    # 如果未找到车站，返回None
    if station_id is None:
        return None

    # 获取线路ID列表
    route_ids = []
    for r in routes:
        route_ids += route_name_to_id(data_v3, r)

    # 如果未找到线路，返回None
    if route_ids == []:
        return None

    all_stations = data['stations']  # 所有车站信息
    all_routes = data['routes']  # 所有线路信息
    short_id = all_stations[station_id]['station']  # 车站短ID
    short_id = int('0x' + str(short_id), 16)  # 转换为整数

    # 读取HTML模板
    with open(template_file, 'r', encoding='utf-8') as f:
        html = f.read()

    # 获取车站名称和英文名称
    n: str = all_stations[station_id]['name']
    station_name = n.split('|')[0]  # 车站名称
    if '|' in n:
        eng_name = n.split('|')[1].split('|')[0]  # 英文名称
    else:
        eng_name = ''

    # 获取线路颜色和名称
    route_colors = [hex(all_routes[x]['color'])[2:].rjust(6, '0')
                    for x in route_ids]  # 线路颜色
    route_names = [all_routes[x]['name'].split('|')[0] for x in route_ids]  # 线路名称
    route_names = list(set(route_names))  # 去重
    
    next_stations = []  # 下一站列表
    last_stations = {}  # 终点站映射
    
    # 遍历每条线路
    for x in route_ids:
        station_ids: list[str] = [y['id'] for y in all_routes[x]['stations']]  # 线路经过的车站ID
        stations_names: list[str] = [all_stations[y]['name']
                                     for y in station_ids]  # 线路经过的车站名称
        
        if station_id in station_ids:
            i = station_ids.index(station_id)  # 当前车站在线路中的索引
            if i != len(station_ids) - 1:
                next_station = stations_names[i + 1].split('|')[0]  # 下一站
                last_station = stations_names[-1].split('|')[0]  # 终点站
                tmp_sta = last_station
                
                # 处理包含WIP的终点站
                if 'WIP' in last_station:
                    last_station = last_station.split('WIP')[1]
                    last_station = last_station.strip('])').strip()

                # 处理终点站名称
                final_last_sta = last_station[:4]  # 取前4个字符
                if len(last_station) > 4 and \
                        final_last_sta in list(last_stations.values()):
                    # 如果前4个字符已存在，使用前2个和后2个字符
                    k = len(last_station)
                    final_last_sta = last_station[:2] + last_station[k - 2:k]

                last_stations[tmp_sta] = final_last_sta  # 添加到终点站映射
                
                # 添加到下一站列表
                if next_station not in next_stations and \
                        next_station != station_name:
                    next_stations.append(next_station)

                # if last_station not in next_stations:
                #     next_stations.append(last_station)

    # 处理终点站映射
    last_count = 0
    last_sta_table = ''
    for x, y in last_stations.items():
        if x != y:
            last_sta_table += f'...{y}={x}...\n'
            last_count += 1

    # 构建输出列表
    output = []
    height = 220 + last_count * 39  # 计算高度
    count = 0
    
    # 遍历车站的所有列车
    for train_id, train in station_tt[station_id].items():
        if train[0] not in route_ids:
            continue  # 跳过不在指定线路的列车

        route_id = train[0]
        t = convert_time(train[2])  # 转换时间格式
        output.append((route_id, t, train_id))

    # 如果没有列车，返回False
    if output == []:
        return False

    # 按时间排序
    output.sort(key=lambda x: x[1])
    last_hour = ''
    
    # 处理列车类型
    express_table = list(EXPRESS_TABLE.items())
    express_table.sort(key=lambda x: len(x[0]), reverse=True)  # 按长度排序，优先匹配长的
    template = ''
    
    # 遍历列车
    for route_id, t, train_id in output:
        route_name = all_routes[route_id]['name']  # 线路名称
        
        # 匹配列车类型
        for name, level in express_table:
            if name in route_name:
                color = COLOR_TABLE[level]  # 列车颜色
                # 处理列车类型缩写
                if len(level) == 2:
                    level = level[0]
                elif len(level) == 3:
                    level = level[0] + level[1]
                elif len(level) == 4:
                    level = level[0] + level[2]
                break
        else:
            # 未匹配到列车类型
            color = '#000000'
            level = ''

        level += ' ' + str(train_id)  # 添加列车ID
        destination_id = all_routes[route_id]['stations'][-1]['id']  # 终点站ID
        destination: str = all_stations[destination_id]['name']  # 终点站名称
        dest = last_stations[destination.split('|')[0]]  # 终点站缩写
        
        # 处理环线
        if all_routes[route_id]['circularState'] == 'CLOCKWISE':
            dest = '顺时针'
        elif all_routes[route_id]['circularState'] == 'ANTICLOCKWISE':
            dest = '逆时针'

        count += 1
        if count % 13 == 0:
            height += 64  # 每13个列车增加高度
        
        hour = t[:2]  # 当前小时
        if hour != last_hour:
            # 新的小时，添加小时标题
            if count % 13 != 0:
                height += 64
            height += 12 * 2
            count = 0
            last_hour = hour
            template += f'''...{hour}...'''

        dest, color, level, ...


def get_sta_directions(data, station, template_file):
    '''
    获取指定车站的线路方向信息
    
    Args:
        data: 包含车站和线路信息的数据字典
        station: 车站名称或短ID
        template_file: HTML模板文件路径
        
    Returns:
        包含HTML字符串、尺寸和方向表的元组，或None表示失败
    '''
    MAX_DIST = 30  # 最大距离阈值

    def min_dist(tuple1, tuples):
        '''
        计算两点之间的最小距离
        
        Args:
            tuple1: 第一个点的坐标
            tuples: 点的列表
            
        Returns:
            最小距离和对应的索引
        '''
        dists = []
        for tuple2 in tuples:
            dist = 0
            for i in range(3):
                dist += abs(tuple1[i] - tuple2[i])  # 计算曼哈顿距离

            dists.append(dist)
            # dists.append(abs(tuple1[0] - tuple2[0]))
            # dists.append(abs(tuple1[2] - tuple2[2]))

        return min(dists), dists.index(min(dists))

    def find_connected_components(graph: dict[str]):
        '''
        查找图中的连通组件
        
        Args:
            graph: 图的字典表示
            
        Returns:
            连通组件的列表
        '''
        visited = set()
        components = []

        def dfs(node, component: set):
            '''深度优先搜索''' 
            visited.add(node)
            component.add(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, component)

        for node in graph:
            if node not in visited:
                component = set()
                dfs(node, component)
                components.append(tuple(sorted(component)))

        return components

    station_id = None
    try:
        # 尝试将station转换为整数，作为短ID处理
        sta_short_id = int(station)
        station_id = station_short_id_to_id(data, sta_short_id)
    except ValueError:
        # 否则作为车站名称处理
        station_id = station_name_to_id(data, station)

    # 如果未找到车站，返回None
    if station_id is None:
        return None

    routes: list[str] = data['station_routes'][station_id]  # 车站所属的线路
    same_direction: dict[str, list] = {}  # 同方向线路映射
    
    # 遍历每条线路
    for route_id1 in routes:
        route_data1 = data['routes'][route_id1]  # 线路信息
        if route_data1['hidden'] is True:
            continue  # 跳过隐藏的线路

        stations1 = route_data1['stations']  # 线路经过的车站
        station_ids1 = [x['id'] for x in route_data1['stations']]  # 车站ID列表
        i1 = station_ids1.index(station_id)  # 当前车站在线路中的索引
        if i1 == len(station_ids1) - 1:
            continue  # 跳过终点站

        if route_id1 not in same_direction:
            same_direction[route_id1] = []

        # 遍历其他线路
        for route_id2 in routes:
            if route_id1 == route_id2:
                continue  # 跳过自身

            route_data2 = data['routes'][route_id2]  # 线路信息
            if route_data2['hidden'] is True:
                continue  # 跳过隐藏的线路

            # 检查线路类型是否兼容
            if route_data1['type'] != route_data2['type']:
                if not ('train_normal' in [route_data1['type'],
                                           route_data2['type']] and
                        'train_high_speed' in [route_data1['type'],
                                               route_data2['type']]):
                    continue

            stations2 = route_data2['stations']  # 线路经过的车站
            station_ids2 = [x['id'] for x in route_data2['stations']]  # 车站ID列表
            i2 = station_ids2.index(station_id)  # 当前车站在线路中的索引
            if i2 == len(station_ids2) - 1:
                continue  # 跳过终点站

            if route_id2 not in same_direction:
                same_direction[route_id2] = []

            if route_id2 in same_direction[route_id1]:
                continue  # 跳过已处理的线路

            # 获取站台坐标
            plat1 = (stations1[i1]['x'], stations1[i1]['y'],
                     stations1[i1]['z'])
            plat2 = (stations2[i2]['x'], stations2[i2]['y'],
                     stations2[i2]['z'])
            if plat1 == plat2:
                same_direction[route_id1].append(route_id2)
                continue

            # 获取后续车站的坐标
            plats1 = [(sta['x'], sta['y'], sta['z'])
                      for sta in stations1[i1 + 1:-1]]
            plats2 = [(sta['x'], sta['y'], sta['z'])
                      for sta in stations2[i2 + 1:-1]]
            
            # 处理只有终点站的情况
            if plats1 == []:
                plats1 = [(sta['x'], sta['y'], sta['z'])
                          for sta in [stations1[-1]]]
                plats2 = [(sta['x'], sta['y'], sta['z'])
                          for sta in stations2[i2 + 1:]]

            if plats2 == []:
                plats1 = [(sta['x'], sta['y'], sta['z'])
                          for sta in stations1[i1 + 1:]]
                plats2 = [(sta['x'], sta['y'], sta['z'])
                          for sta in [stations2[-1]]]

            if plats1 == [] or plats2 == []:
                continue

            # 检查距离是否在阈值内
            if min_dist(plats1[0], plats2)[0] > MAX_DIST and \
                    min_dist(plats2[0], plats1)[0] > MAX_DIST:
                continue

            # 检查是否有车站在距离阈值内
            for x in plats1:
                min_distance = min_dist(x, plats2)
                if min_distance[0] <= MAX_DIST:
                    same_direction[route_id1].append(route_id2)
                    break

    # 查找连通组件
    components = find_connected_components(same_direction)
    result = []
    result_2 = []
    for x in components:
        t: tuple[str] = tuple(data['routes'][y]['name'] for y in x)
        t2 = tuple(x.split('|')[0] for x in t)
        result.append(t)
        result_2.append(t2)

    # 构建图
    graph: dict[str, list] = {}
    graph_2: dict[str, list] = {}
    graph_3: dict[str, list] = {}
    for i1, x1 in enumerate(result_2):
        item1_1 = result[i1]
        if item1_1 not in graph:
            graph[item1_1] = []

        item1_2 = result_2[i1]
        if item1_2 not in graph_2:
            graph_2[item1_2] = []

        item1_3 = components[i1]
        if item1_3 not in graph_3:
            graph_3[item1_3] = []

        if i1 == len(result_2) - 1:
            break

        for i2, x2 in enumerate(result_2[i1 + 1:]):
            i2 += i1 + 1
            have_same = len([x for x in x1 if x in x2]) > 0  # 检查是否有相同的线路

            item2_1 = result[i2]
            if item2_1 not in graph:
                graph[item2_1] = []

            if have_same is True:
                graph[item1_1].append(item2_1)
                graph[item2_1].append(item1_1)

            item2_2 = result_2[i2]
            if item2_2 not in graph_2:
                graph_2[item2_2] = []

            if have_same is True:
                graph_2[item1_2].append(item2_2)
                graph_2[item2_2].append(item1_2)

            item2_3 = components[i2]
            if item2_3 not in graph_3:
                graph_3[item2_3] = []

            if have_same is True:
                graph_3[item1_3].append(item2_3)
                graph_3[item2_3].append(item1_3)

    # 查找连通组件
    same_ids = find_connected_components(graph)
    same_ids_2 = find_connected_components(graph_2)
    same_ids_3 = find_connected_components(graph_3)
    
    # 获取车站信息
    sta_data = data['stations'][station_id]
    sta_name = sta_data['name'].split('|')[0]  # 车站名称
    short_id = int('0x' + sta_data['station'], 16)  # 车站短ID

    # 读取HTML模板
    with open(template_file, 'r', encoding='utf-8') as f:
        html = f.read()

    sta_directions_table = {}  # 方向表
    template = ''  # 模板字符串
    template1 = '...({{id}}) {{sta}}方向...\n'  # 方向模板
    count = 1  # 计数
    height = 87  # 高度
    
    # 遍历连通组件
    for index, routes in enumerate(same_ids):
        all_routes = set(y for x in same_ids_2[index] for y in x)  # 所有线路
        all_names = '/<br>&nbsp;'.join(sorted(all_routes))  # 线路名称
        template += f'''...{all_names}...\n'''
        all_route_ids = same_ids_3[index]  # 所有线路ID
        
        for x in all_route_ids:
            next_stations = []  # 下一站列表
            last_stations = []  # 终点站列表
            
            for z in x:
                route_data = data['routes'][z]  # 线路信息
                
                # 处理环线
                if route_data['circularState'] == 'CLOCKWISE':
                    dest = '顺时针'
                    last_stations.append(dest)
                    continue
                elif route_data['circularState'] == 'ANTICLOCKWISE':
                    dest = '逆时针'
                    last_stations.append(dest)
                    continue

                station_ids: list[str] = [
                    y['id'] for y in route_data['stations']]  # 车站ID列表
                stations_names: list[str] = [data['stations'][y]['name']
                                             for y in station_ids]  # 车站名称列表
                if station_id not in station_ids:
                    continue

                i = station_ids.index(station_id)  # 当前车站在线路中的索引
                if i != len(station_ids) - 1:
                    next_station = stations_names[i + 1].split('|')[0]  # 下一站
                    last_station = stations_names[-1].split('|')[0]  # 终点站
                    
                    # 处理包含WIP的终点站
                    if 'WIP' in last_station:
                        last_station = last_station.split('WIP')[1]
                        last_station = last_station.strip('])').strip()

                    # 添加到终点站列表
                    if last_station not in last_stations and \
                            last_station != sta_name:
                        last_stations.append(last_station)

                    # 添加到下一站列表
                    if next_station not in next_stations and \
                            next_station != sta_name:
                        next_stations.append(next_station)

            last_stations.sort()  # 排序
            if last_stations == []:
                continue

            # 构建方向模板
            template2 = template1.replace('{{sta}}', '/'.join(last_stations))
            template2 = template2.replace('{{id}}', str(count))
            template += template2
            sta_directions_table[count] = x  # 添加到方向表
            count += 1

        template += '</ul></dd></dl>\n'
        height += 120  # 增加高度

    # 替换模板变量
    html = html.replace('{{template}}', template)
    html = html.replace('{{station}}', f'{sta_name} ({short_id})')
    return html, (800, height), sta_directions_table


def main_route_random_train(LOCAL_FILE_PATH, LOCAL_FILE_PATH_V3,
                            DATABASE_PATH, route_name,
                            departure_time=None) -> tuple[str, tuple]:
    '''
    主函数：获取指定线路的随机列车信息
    
    Args:
        LOCAL_FILE_PATH: 本地数据文件路径
        LOCAL_FILE_PATH_V3: v3格式的本地数据文件路径
        DATABASE_PATH: 数据库文件路径
        route_name: 线路名称
        departure_time: 发车时间（秒），默认为当前时间
        
    Returns:
        包含HTML字符串和尺寸的元组，或None表示失败
    '''
    # 加载列车时刻表数据
    with open(DATABASE_PATH + 'train_timetable_data.dat', 'rb') as f:
        database = pickle.load(f)

    # 加载车站和线路信息
    with open(LOCAL_FILE_PATH, encoding='utf-8') as f:
        data = json.load(f)

    # 加载v3格式的线路信息
    with open(LOCAL_FILE_PATH_V3, encoding='utf-8') as f:
        data_v3 = json.load(f)

    # 获取列车信息
    train_data = route_random_train(data_v3, data, route_name,
                                    database, departure_time)
    if not isinstance(train_data, tuple):
        return train_data

    ...


def main_random_train(LOCAL_FILE_PATH, DATABASE_PATH,
                      departure_time=None) -> tuple[str, tuple]:
    '''
    主函数：随机获取一辆列车的信息
    
    Args:
        LOCAL_FILE_PATH: 本地数据文件路径
        DATABASE_PATH: 数据库文件路径
        departure_time: 发车时间（秒），默认为当前时间
        
    Returns:
        包含HTML字符串和尺寸的元组
    '''
    # 加载列车时刻表数据
    with open(DATABASE_PATH + 'train_timetable_data.dat', 'rb') as f:
        database = pickle.load(f)

    # 加载车站和线路信息
    with open(LOCAL_FILE_PATH, encoding='utf-8') as f:
        data = json.load(f)

    try:
        # 获取随机列车信息
        train_data = random_train(data, database, departure_time)
    except IndexError:
        # 处理索引错误，重新尝试
        train_data = random_train(data, database, departure_time)

    ...


def main_train(LOCAL_FILE_PATH, DATABASE_PATH_1, DATABASE_PATH_2,
               station_name, train_id) -> tuple[str, tuple]:
    '''
    主函数：获取指定列车的详细信息
    
    Args:
        LOCAL_FILE_PATH: 本地数据文件路径
        DATABASE_PATH_1: 列车时刻表数据库路径
        DATABASE_PATH_2: 车站时刻表数据库路径
        station_name: 车站名称或短ID
        train_id: 列车ID
        
    Returns:
        包含HTML字符串和尺寸的元组，或None/False表示失败
    '''
    # 加载列车时刻表数据
    with open(DATABASE_PATH_1 + 'train_timetable_data.dat', 'rb') as f:
        train_timetable = pickle.load(f)

    # 加载车站时刻表数据
    with open(DATABASE_PATH_2 + 'station_timetable_data.dat', 'rb') as f:
        station_timetable = pickle.load(f)

    # 加载车站和线路信息
    with open(LOCAL_FILE_PATH, encoding='utf-8') as f:
        data = json.load(f)

    # 获取列车信息
    train_data = get_train(data, station_name, train_id,
                           station_timetable, train_timetable)
    if not isinstance(train_data, tuple):
        return train_data

    ...


def main_text_timetable(LOCAL_FILE_PATH, DATABASE_PATH,
                        departure_time, station_name) -> str:
    '''
    主函数：获取指定车站的文本格式时刻表
    
    Args:
        LOCAL_FILE_PATH: 本地数据文件路径
        DATABASE_PATH: 数据库文件路径
        departure_time: 发车时间（秒）
        station_name: 车站名称或短ID
        
    Returns:
        文本格式的时刻表字符串，或None表示失败
    '''
    # 加载车站时刻表数据
    with open(DATABASE_PATH + 'station_timetable_data.dat', 'rb') as f:
        station_timetable = pickle.load(f)

    # 加载车站和线路信息
    with open(LOCAL_FILE_PATH, encoding='utf-8') as f:
        data = json.load(f)

    # 获取文本格式时刻表
    return get_text_timetable(data, station_name,
                              departure_time, station_timetable)


def main_sta_timetable(LOCAL_FILE_PATH, LOCAL_FILE_PATH_2,
                       DATABASE_PATH, station_name, route_names) -> str:
    '''
    主函数：获取指定车站和线路的HTML格式时刻表
    
    Args:
        LOCAL_FILE_PATH: v3格式的本地数据文件路径
        LOCAL_FILE_PATH_2: 本地数据文件路径
        DATABASE_PATH: 数据库文件路径
        station_name: 车站名称或短ID
        route_names: 线路名称或线路名称列表
        
    Returns:
        HTML格式的时刻表字符串，或None/False表示失败
    '''
    # 加载车站时刻表数据
    with open(DATABASE_PATH + 'station_timetable_data.dat', 'rb') as f:
        station_timetable = pickle.load(f)

    # 加载v3格式的线路信息
    with open(LOCAL_FILE_PATH, encoding='utf-8') as f:
        data_v3 = json.load(f)

    # 加载车站和线路信息
    with open(LOCAL_FILE_PATH_2, encoding='utf-8') as f:
        data = json.load(f)

    # 获取HTML格式时刻表
    return get_sta_timetable(data_v3, data, station_name, route_names,
                             DATABASE_PATH + 'station_template.htm',
                             station_timetable)


def main_get_sta_directions(LOCAL_FILE_PATH_2, station, template_path):
    '''
    主函数：获取指定车站的线路方向信息
    
    Args:
        LOCAL_FILE_PATH_2: 本地数据文件路径
        station: 车站名称或短ID
        template_path: HTML模板文件路径
        
    Returns:
        包含HTML字符串、尺寸和方向表的元组，或None表示失败
    '''
    # 加载车站和线路信息
    with open(LOCAL_FILE_PATH_2, encoding='utf-8') as f:
        data = json.load(f)

    # 获取线路方向信息
    return get_sta_directions(data, station, template_path)


def gen_departure_data(data, filename1, filename2, DEP_PATH, IGNORED_LINES):
    '''
    生成发车数据
    
    Args:
        data: 包含车站和线路信息的数据字典
        filename1: 车站时刻表数据保存路径
        filename2: 列车时刻表数据保存路径
        DEP_PATH: 发车数据文件路径
        IGNORED_LINES: 忽略的线路列表
        
    Returns:
        包含车站线路发车数据、列车数据和所有线路发车数据的元组
    '''
    # 加载发车数据
    with open(DEP_PATH, 'r', encoding='utf-8') as f:
        dep_data: dict[str, list[int]] = json.load(f)

    station_route_dep: dict[str, dict[str, list[int]]] = {}  # 车站线路发车数据
    all_route_dep: dict[str, dict[str, list[int]]] = {}  # 所有线路发车数据
    trains: dict[str, list] = {}  # 列车数据
    station_train_id = {}  # 车站列车ID计数器
    
    # 遍历每条线路的发车数据
    for route_id, departures in dep_data.items():
        if route_id not in data['routes']:
            continue

        route = data['routes'][route_id]  # 线路信息
        n: str = route['name']  # 线路名称
        if n in IGNORED_LINES:
            continue

        # 提取英文名称
        try:
            eng_name = n.split('|')[1].split('|')[0]
            if eng_name == '':
                eng_name = n.split('|')[0]
        except IndexError:
            eng_name = n.split('|')[0]

        durations = route['durations']  # 运行时间
        if durations == []:
            continue

        if route_id not in trains:
            trains[route_id] = []

        # 获取车站短ID列表
        station_ids = [data['stations'][x['id']]['station']
                       for x in route['stations']]
        
        # 处理运行时间长度
        if len(station_ids) - 1 < len(durations):
            durations = durations[:len(station_ids) - 1]

        if len(station_ids) - 1 > len(durations):
            continue

        # 处理发车时间
        departures_new = []
        for x in departures:
            if x < 0:
                x += 86400
            elif x >= 86400:
                x -= 86400
            departures_new.append(x)

        real_ids = [x['id'] for x in route['stations']]  # 车站实际ID列表
        dwells = [x['dwellTime'] for x in route['stations']]  # 停站时间
        if len(dwells) > 0:
            dep = -round(dwells[-1] / 1000)
        else:
            dep = 0

        timetable = []  # 时刻表
        
        # 从后往前计算每个车站的到达和发车时间
        for i in range(len(station_ids) - 1, 0, -1):
            station1 = station_ids[i - 1]  # 前一站短ID
            station2 = station_ids[i]  # 后一站短ID
            _station1 = real_ids[i - 1]  # 前一站实际ID
            _station2 = real_ids[i]  # 后一站实际ID
            dur = round(durations[i - 1] / 1000)  # 运行时间（秒）
            arr_time = dep  # 到达时间
            dep_time = dep - dur  # 发车时间
            dwell = round(dwells[i - 1] / 1000)  # 停站时间（秒）
            dep -= dur  # 更新时间
            dep -= dwell
            if station1 == station2:
                continue

            # 添加到时刻表
            timetable.insert(0, arr_time)
            timetable.insert(0, dep_time)

            # 初始化车站列车ID计数器
            if _station1 not in station_train_id:
                station_train_id[_station1] = 1

            # 初始化车站线路发车数据
            if _station1 not in station_route_dep:
                station_route_dep[_station1] = {}

            if eng_name not in station_route_dep[_station1]:
                station_route_dep[_station1][eng_name] = []

            # 初始化所有线路发车数据
            if _station1 not in all_route_dep:
                all_route_dep[_station1] = {}

            # 处理每个发车时间
            for i, x in enumerate(departures_new):
                new_dep = (dep_time + x + 8 * 60 * 60) % 86400  # 计算新的发车时间
                train_id = station_train_id[_station1]  # 列车ID
                # 添加到车站线路发车数据
                station_route_dep[_station1][eng_name].append(
                    (route_id, new_dep, (i, train_id)))
                # 添加到所有线路发车数据
                all_route_dep[_station1][train_id] = \
                    (route_id, i, new_dep)
                station_train_id[_station1] += 1

            # 按时间排序
            station_route_dep[_station1][eng_name].sort()

        if timetable == []:
            continue

        # 生成列车时刻表
        for x in departures_new:
            new_timetable = [y + x + 8 * 60 * 60 for y in timetable]
            trains[route_id].append(new_timetable)

    # 保存数据
    if filename1 is not None:
        with open(filename1, 'wb') as f:
            pickle.dump(all_route_dep, f)

    if filename2 is not None:
        with open(filename2, 'wb') as f:
            pickle.dump(trains, f)

    return station_route_dep, trains, all_route_dep
