import paho.mqtt.client as mqtt
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np
import json
import matplotlib

matplotlib.use('TkAgg')  # 강제로 TkAgg 백엔드 사용

# 📌 맵 설정 (단위: m)
MAP_WIDTH = 11.55
MAP_HEIGHT = 5.85
MAP_IMAGE = "lab.jpg"

# 📌 4개의 앵커 좌표 설정
anchor_positions = {
    "ANC3": (0.5, 1.40),
    "ANC4": (6.3, 1.7),
    "ANC5": (5.85, 4.05),
    "ANC6": (9.9, 3.62)
}

# 📌 MQTT 설정
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

# 📌 태그 위치 마커 (삼변측량 = 빨강, 사변측량 = 파랑)
tag_marker_tri, = ax.plot([0], [0], "ro", markersize=10, label="Tri")  # 삼변측량
tag_marker_quad, = ax.plot([0], [0], "bo", markersize=10, label="Quad")  # 사변측량
tag_text_tri = ax.text(0, 0, "", fontsize=10, ha="center", color="blue")
tag_text_quad = ax.text(0, 0, "", fontsize=10, ha="center", color="green")

plt.draw()
plt.pause(0.01)


# 📌 삼변측량법 (Trilateration)
def trilateration(anchor_positions, distances):
    try:
        A, B, C = anchor_positions["ANC1"], anchor_positions["ANC2"], anchor_positions["ANC3"]
        d1, d2, d3 = distances["ANC1"], distances["ANC2"], distances["ANC3"]

        x1, y1 = A
        x2, y2 = B
        x3, y3 = C

        A_mat = 2 * (x2 - x1)
        B_mat = 2 * (y2 - y1)
        C_mat = d1 ** 2 - d2 ** 2 - x1 ** 2 - y1 ** 2 + x2 ** 2 + y2 ** 2
        D_mat = 2 * (x3 - x1)
        E_mat = 2 * (y3 - y1)
        F_mat = d1 ** 2 - d3 ** 2 - x1 ** 2 - y1 ** 2 + x3 ** 2 + y3 ** 2

        x = (C_mat - F_mat * B_mat / E_mat) / (A_mat - D_mat * B_mat / E_mat)
        y = (C_mat - A_mat * x) / B_mat

        if not (0 <= x <= MAP_WIDTH and 0 <= y <= MAP_HEIGHT):
            return None, None
        return x, y

    except Exception as e:
        print(f"Error in trilateration: {e}")
        return None, None


# 📌 사변측량법 (Quadrilateral Lateration)
def quadrilateral_lateration(anchor_positions, distances):
    try:
        (x1, y1), d1 = anchor_positions["ANC1"], distances["ANC1"]
        (x2, y2), d2 = anchor_positions["ANC2"], distances["ANC2"]
        (x3, y3), d3 = anchor_positions["ANC3"], distances["ANC3"]
        (x4, y4), d4 = anchor_positions["ANC4"], distances["ANC4"]

        A = np.array([
            [2 * (x2 - x1), 2 * (y2 - y1)],
            [2 * (x3 - x1), 2 * (y3 - y1)],
            [2 * (x4 - x1), 2 * (y4 - y1)],
        ])

        B = np.array([
            [d1 ** 2 - d2 ** 2 - x1 ** 2 - y1 ** 2 + x2 ** 2 + y2 ** 2],
            [d1 ** 2 - d3 ** 2 - x1 ** 2 - y1 ** 2 + x3 ** 2 + y3 ** 2],
            [d1 ** 2 - d4 ** 2 - x1 ** 2 - y1 ** 2 + x4 ** 2 + y4 ** 2]
        ])

        pos, _, _, _ = np.linalg.lstsq(A, B, rcond=None)
        x, y = pos.flatten()

        if not (0 <= x <= MAP_WIDTH and 0 <= y <= MAP_HEIGHT):
            return None, None
        return x, y

    except Exception as e:
        print(f"Error in quadrilateral lateration: {e}")
        return None, None


# 📌 태그 위치 업데이트 함수
def update_tag_position(tag_pos_tri, tag_pos_quad):
    if tag_pos_tri:
        x_tri, y_tri = tag_pos_tri
        if x_tri is not None and y_tri is not None:
            tag_marker_tri.set_data([x_tri], [y_tri])
            tag_text_tri.set_position((x_tri, y_tri + 0.15))
            tag_text_tri.set_text(f"Tri ({x_tri:.2f}, {y_tri:.2f})")

    if tag_pos_quad:
        x_quad, y_quad = tag_pos_quad
        if x_quad is not None and y_quad is not None:
            tag_marker_quad.set_data([x_quad], [y_quad])
            tag_text_quad.set_position((x_quad, y_quad + 0.15))
            tag_text_quad.set_text(f"Quad ({x_quad:.2f}, {y_quad:.2f})")

    fig.canvas.draw_idle()
    fig.canvas.flush_events()
    plt.pause(0.01)


# 📌 MQTT 메시지 처리 함수
def on_message(client, userdata, message):
    try:
        payload = message.payload.decode()
        data = json.loads(payload)

        distances = {}
        for anchor_id, anchor_data in data.items():
            if anchor_id in anchor_positions:
                distances[anchor_id] = anchor_data["distance"]

        if len(distances) >= 3:  # 삼변측량
            tag_x_tri, tag_y_tri = trilateration(anchor_positions, distances)
        else:
            tag_x_tri, tag_y_tri = None, None

        if len(distances) >= 4:  # 사변측량
            tag_x_quad, tag_y_quad = quadrilateral_lateration(anchor_positions, distances)
        else:
            tag_x_quad, tag_y_quad = None, None

        update_tag_position((tag_x_tri, tag_y_tri), (tag_x_quad, tag_y_quad))

    except Exception as e:
        print(f"Error parsing message: {e}")



# 📌 MQTT 클라이언트 설정
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT)
client.subscribe(MQTT_TOPIC)

print(f"Subscribed to topic '{MQTT_TOPIC}'")
client.loop_forever()
