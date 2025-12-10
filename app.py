import json
import os
import urllib.request
import urllib.error
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# --- 配置 ---
# 西雅图经纬度
LATITUDE = 47.6062
LONGITUDE = -122.3321
SCHEDULE_FILE = 'schedule.json'


# --- 核心：获取天气数据 ---
def get_weather_data():
    # 我们同时请求 current (当前) 和 hourly (每小时) 数据
    # timezone=auto 解决时差导致的 N/A 问题
    url = (
        "https://api.open-meteo.com/v1/forecast?"
        f"latitude={LATITUDE}&longitude={LONGITUDE}&timezone=auto"
        "&current=temperature_2m,apparent_temperature,precipitation,weather_code"
        "&hourly=temperature_2m,apparent_temperature,precipitation_probability,weather_code"
        "&forecast_days=1"
    )

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Weather API Error: {e}")
        return None


# --- 核心：日程读写 ---
def load_schedule():
    if not os.path.exists(SCHEDULE_FILE):
        return []
    try:
        with open(SCHEDULE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []


def save_schedule_data(data):
    with open(SCHEDULE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# --- 路由 ---
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/weather')
def api_weather():
    data = get_weather_data()
    if not data:
        return jsonify({"error": "Failed"}), 500

    current = data.get('current', {})
    hourly = data.get('hourly', {})

    # 1. 获取最高/最低温
    temps = hourly.get('apparent_temperature', [])
    probs = hourly.get('precipitation_probability', [])
    times = hourly.get('time', [])  # ISO 格式时间

    max_temp = max(temps) if temps else 0
    min_temp = min(temps) if temps else 0

    # 2. 降雨预测逻辑
    rain_forecast = "No Rain"
    # 如果当前正在下雨
    if current.get('precipitation', 0) > 0:
        rain_forecast = "Raining"
    else:
        # 检查未来几个数据点 (简单的预测)
        # API 返回的 hourly 通常是从 00:00 开始的 24 个数据
        # 我们简单检查一下列表中是否有高概率降雨
        high_rain_chance = [p for p in probs if p > 50]
        if high_rain_chance:
            rain_forecast = "Rain Soon"

    # 3. 整理图表数据 (只取时间的小时部分)
    short_times = [t.split('T')[1] for t in times]

    return jsonify({
        "current_temp": round(current.get('apparent_temperature', 0)),
        "max_temp": round(max_temp),
        "min_temp": round(min_temp),
        "rain_forecast": rain_forecast,
        "chart_data": {
            "time": short_times,
            "temp": temps,
            "rain": probs
        }
    })


# 日程 API
@app.route('/api/schedule', methods=['GET', 'POST'])
def handle_schedule():
    if request.method == 'POST':
        try:
            current_schedule = load_schedule()
            current_schedule.append(request.json)
            save_schedule_data(current_schedule)
            return jsonify({"status": "ok"})
        except:
            return jsonify({"error": "err"}), 400
    return jsonify(load_schedule())


@app.route('/api/schedule/delete', methods=['POST'])
def delete_schedule():
    idx = request.json.get('index')
    data = load_schedule()
    if 0 <= idx < len(data):
        data.pop(idx)
        save_schedule_data(data)
    return jsonify({"status": "ok"})


if __name__ == '__main__':
    # 端口设为 5002 防止冲突
    app.run(host='0.0.0.0', port=5002, debug=True)