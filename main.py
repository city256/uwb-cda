import paho.mqtt.client as mqtt
import json

# 앵커 테이블 (딕셔너리)
anchor_table = {}
anchor_list = set() # 중복되는 id 방지

# MQTT 브로커 설정
MQTT_BROKER = "168.188.126.168"
MQTT_TOPIC = "/uwb/table"
MQTT_PORT = 1883

def on_message(client, userdata, message):
    try:
        payload = message.payload.decode()  # MQTT 메시지 디코딩
        data = json.loads(payload)  # JSON 파싱

        for anchor_id, anchor_data in data.items():
            # JSON에서 각 앵커의 데이터가 {"distance": 1.14, "seq": 1001, "active": True} 형태라고 가정
            distance = anchor_data["distance"]
            seq_num = anchor_data["seq"]
            active = anchor_data["active"]
            anchor_list.add(anchor_id)

            if anchor_id not in anchor_table:
                anchor_table[anchor_id] = {"distance": distance, "seq_num": seq_num, "active": active}
            else:
                anchor_table[anchor_id]["distance"] = distance
                anchor_table[anchor_id]["seq_num"] = seq_num
                anchor_table[anchor_id]["active"] = active

        print(f"Updated Anchor Table: {anchor_table}")
        # print(anchor_table["ANC3"])
        # print(anchor_table["ANC3"]["distance"])
        print(anchor_list, len(anchor_list))

    except Exception as e:
        print(f"Error parsing message: {e}")

# MQTT 클라이언트 설정
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT)
client.subscribe(MQTT_TOPIC)

print(f"Subscribed to topic '{MQTT_TOPIC}'")
client.loop_forever()
