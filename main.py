import paho.mqtt.client as mqtt
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import json
import matplotlib
matplotlib.use('TkAgg')  # 강제로 TkAgg 백엔드 사용


# map 설정 (m 단위)
MAP_WIDTH = 11.55
MAP_HEIGHT = 5.85
MAP_IMAGE = "lab.jpg"

# 앵커(ANC)들의 고정 좌표 (사용자 맵에 맞게 조정)
anchor_positions = {
    "ANC3": (0.5, 1.40),
    "ANC4": (6.3, 1.7),
    "ANC5": (5.85, 4.05)
}

# MQTT 브로커 설정
MQTT_BROKER = "168.188.126.168"
MQTT_TOPIC = "/uwb/table"
MQTT_PORT = 1883

# Matplotlib 초기화 (인터랙티브 모드)
plt.ion()
fig, ax = plt.subplots(figsize=(8, 5))

# 배경 이미지 로드 및 초기 표시
img = mpimg.imread(MAP_IMAGE)
ax.imshow(img, extent=[0, MAP_WIDTH, 0, MAP_HEIGHT], aspect='auto')
ax.set_xlim(0, MAP_WIDTH)
ax.set_ylim(0, MAP_HEIGHT)
ax.set_xticks([])
ax.set_yticks([])
ax.grid(False)
ax.set_xlabel("11.55 (m)")
ax.set_ylabel("5.85 (m)")
ax.set_title("UWB Anchor & Tag Position")

# 앵커(ANC) 위치 플로팅
for anchor_id, (x, y) in anchor_positions.items():
    ax.scatter(x, y, c="red", s=100, label=f"{anchor_id}")
    ax.text(x, y + 0.15, anchor_id, fontsize=10, ha="center", color="black")

# 태그 위치 마커 (초기 위치는 None이 아닌 (0,0)으로 설정)
tag_marker, = ax.plot([0], [0], "bo", markersize=10, label="Tag")
tag_text = ax.text(0, 0, "", fontsize=10, ha="center", color="blue")

plt.draw()
plt.pause(0.01)  # 초기 화면을 위해 필요


def trilateration(anchor_positions, distances):
    """ 삼변 측량 알고리즘으로 태그 위치 계산 """
    try:
        A, B, C = anchor_positions["ANC3"], anchor_positions["ANC4"], anchor_positions["ANC5"]
        d1, d2, d3 = distances["ANC3"], distances["ANC4"], distances["ANC5"]

        x1, y1 = A
        x2, y2 = B
        x3, y3 = C

        # 삼변측량 수식 (행렬 연산을 활용)
        A_mat = 2 * (x2 - x1)
        B_mat = 2 * (y2 - y1)
        C_mat = d1**2 - d2**2 - x1**2 - y1**2 + x2**2 + y2**2
        D_mat = 2 * (x3 - x1)
        E_mat = 2 * (y3 - y1)
        F_mat = d1**2 - d3**2 - x1**2 - y1**2 + x3**2 + y3**2

        # (x, y) 좌표 계산
        x = (C_mat - F_mat * B_mat / E_mat) / (A_mat - D_mat * B_mat / E_mat)
        y = (C_mat - A_mat * x) / B_mat

        # 계산된 좌표가 맵 범위를 벗어나면 무효 처리
        if not (0 <= x <= MAP_WIDTH and 0 <= y <= MAP_HEIGHT):
            print(f"Invalid calculated position: ({x}, {y})")
            return None, None

        return x, y

    except Exception as e:
        print(f"Error in trilateration: {e}")
        return None, None


def update_tag_position(tag_position):
    """ 태그 위치만 업데이트 (기존 맵 유지) """
    if tag_position:
        tag_x, tag_y = tag_position

        # 태그 위치가 None이면 업데이트 안 함
        if tag_x is None or tag_y is None:
            return

        # 위치 업데이트 확인 로그
        print(f"Updating tag position: ({tag_x:.2f}, {tag_y:.2f})")

        # 태그 위치 업데이트
        tag_marker.set_data([tag_x], [tag_y])
        tag_text.set_position((tag_x, tag_y + 0.15))
        tag_text.set_text(f"TAG ({tag_x:.2f}, {tag_y:.2f})")

        fig.canvas.draw_idle()
        fig.canvas.flush_events()
        plt.pause(0.01)  # 업데이트 속도 조절


def on_message(client, userdata, message):
    """ MQTT 메시지를 수신하고 태그 위치 업데이트 """
    try:
        payload = message.payload.decode()  # MQTT 메시지 디코딩
        data = json.loads(payload)  # JSON 파싱

        distances = {}
        for anchor_id, anchor_data in data.items():
            if anchor_id in anchor_positions:  # 앵커 ID 확인
                distances[anchor_id] = anchor_data["distance"]

        if len(distances) == 3:  # 3개 앵커 거리값이 있을 때만 처리
            tag_x, tag_y = trilateration(anchor_positions, distances)
            if tag_x is not None and tag_y is not None:
                print(f"Tag Position: ({tag_x:.2f}, {tag_y:.2f})")
                update_tag_position((tag_x, tag_y))  # 태그 위치를 업데이트

    except Exception as e:
        print(f"Error parsing message: {e}")


# MQTT 클라이언트 설정
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT)
client.subscribe(MQTT_TOPIC)

print(f"Subscribed to topic '{MQTT_TOPIC}'")
client.loop_forever()
