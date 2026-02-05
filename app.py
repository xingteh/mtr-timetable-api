from flask import Flask, render_template, request, jsonify
import mtr_timetable_github as mtr
import os
import json
import pickle
from datetime import datetime, timezone, timedelta

app = Flask(__name__)

# 数据文件路径设置
DATA_PATH = '.'
DATABASE_PATH = '.'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/station', methods=['POST'])
def station_query():
    station_name = request.form.get('station_name')
    if not station_name:
        return jsonify({'error': '请输入车站名称'})
    
    try:
        # 加载数据
        with open(os.path.join(DATA_PATH, 'data.json'), 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 加载车站时刻表数据
        with open(os.path.join(DATABASE_PATH, 'station_timetable_data.dat'), 'rb') as f:
            station_timetable = pickle.load(f)
        
        # 获取当前时间
        tz = 8
        dtz = timezone(timedelta(hours=tz))
        departure_time = round(datetime.now().astimezone(dtz).replace(tzinfo=timezone.utc).timestamp())
        
        # 获取车站文本时刻表
        timetable = mtr.main_text_timetable(os.path.join(DATA_PATH, 'data.json'), 
                                           DATABASE_PATH, 
                                           departure_time, 
                                           station_name)
        
        if timetable is None:
            return jsonify({'error': '未找到该车站信息'})
        
        return jsonify({
            'station': station_name,
            'timetable': timetable
        })
    except FileNotFoundError as e:
        return jsonify({'error': f'数据文件未找到: {str(e)}'})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/route', methods=['POST'])
def route_query():
    route_name = request.form.get('route_name')
    if not route_name:
        return jsonify({'error': '请输入线路名称'})
    
    try:
        # 加载数据
        with open(os.path.join(DATA_PATH, 'data_v3.json'), 'r', encoding='utf-8') as f:
            data_v3 = json.load(f)
        
        with open(os.path.join(DATA_PATH, 'data.json'), 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 加载车站时刻表数据
        with open(os.path.join(DATABASE_PATH, 'station_timetable_data.dat'), 'rb') as f:
            station_timetable = pickle.load(f)
        
        # 尝试获取线路的第一个车站作为默认车站
        default_station = None
        route_ids = mtr.route_name_to_id(data_v3, route_name)
        if route_ids:
            route_id = route_ids[0]
            if route_id in data['routes']:
                stations = data['routes'][route_id]['stations']
                if stations:
                    default_station = stations[0]['id']
        
        if not default_station:
            return jsonify({'error': '无法找到线路的车站信息'})
        
        # 获取线路时刻表
        timetable = mtr.main_sta_timetable(os.path.join(DATA_PATH, 'data_v3.json'), 
                                          os.path.join(DATA_PATH, 'data.json'), 
                                          DATABASE_PATH, 
                                          default_station, 
                                          route_name)
        
        if timetable is None:
            return jsonify({'error': '未找到该线路信息'})
        elif timetable is False:
            return jsonify({'error': '该线路无列车数据'})
        
        return jsonify({
            'route': route_name,
            'trains': '线路列车数据加载成功'
        })
    except FileNotFoundError as e:
        return jsonify({'error': f'数据文件未找到: {str(e)}'})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/train', methods=['POST'])
def train_query():
    station_name = request.form.get('station_name')
    train_id = request.form.get('train_id')
    if not station_name or not train_id:
        return jsonify({'error': '请输入车站名称和列车ID'})
    
    try:
        # 加载数据
        with open(os.path.join(DATA_PATH, 'data.json'), 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 加载列车时刻表数据
        with open(os.path.join(DATABASE_PATH, 'train_timetable_data.dat'), 'rb') as f:
            train_timetable = pickle.load(f)
        
        # 加载车站时刻表数据
        with open(os.path.join(DATABASE_PATH, 'station_timetable_data.dat'), 'rb') as f:
            station_timetable = pickle.load(f)
        
        # 获取列车信息
        train_info = mtr.get_train(data, station_name, int(train_id), 
                                   station_timetable, train_timetable)
        
        if train_info is None:
            return jsonify({'error': '未找到该车站信息'})
        elif train_info is False:
            return jsonify({'error': '未找到该列车信息'})
        
        route_name, stations, status = train_info
        
        # 格式化车站信息
        formatted_stations = []
        for station in stations:
            formatted_stations.append({
                'name': station[0],
                'arrival': station[1],
                'departure': station[2],
                'id': station[3]
            })
        
        return jsonify({
            'train_id': train_id,
            'station': station_name,
            'route': route_name,
            'status': status,
            'schedule': formatted_stations
        })
    except FileNotFoundError as e:
        return jsonify({'error': f'数据文件未找到: {str(e)}'})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/random_train')
def random_train():
    try:
        # 加载数据
        with open(os.path.join(DATA_PATH, 'data.json'), 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 加载列车时刻表数据
        with open(os.path.join(DATABASE_PATH, 'train_timetable_data.dat'), 'rb') as f:
            train_timetable = pickle.load(f)
        
        # 获取随机列车信息
        train_info = mtr.random_train(data, train_timetable)
        
        route_name, stations, status = train_info
        
        # 格式化车站信息
        formatted_stations = []
        for station in stations:
            formatted_stations.append({
                'name': station[0],
                'arrival': station[1],
                'departure': station[2],
                'id': station[3]
            })
        
        return jsonify({
            'route': route_name,
            'status': status,
            'schedule': formatted_stations
        })
    except FileNotFoundError as e:
        return jsonify({'error': f'数据文件未找到: {str(e)}'})
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)
