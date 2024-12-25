import tkinter as tk
from tkinter import ttk
import time
import threading
import random
import paho.mqtt.client as mqtt


class IoTDeviceSimulator:
    def __init__(self, root):
        self.root = root
        self.root.title("IoT Device Simulator")
        self.mode = "Manual"  # manual ручной automatic автоматический
        self.sensor_value = 50  # начальное показание датчика
        self.pump_status = False
        self.running = True
        self.update_period = 3

        self.critical_low = 30  # минимальное допустимое значение
        self.critical_high = 70  # максимальное допустимое значение

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect("test.mosquitto.org", 1883, 60)
        threading.Thread(target=self.mqtt_client.loop_forever, daemon=True).start()

        self.create_ui()
        threading.Thread(target=self.sensor_update_loop, daemon=True).start()

    def create_ui(self):
        self.validate_positive_input = self.root.register(self.validate_positive)

        self.mode_label = ttk.Label(self.root, text="Mode:")
        self.mode_label.grid(row=0, column=0, padx=5, pady=5)

        self.mode_selector = ttk.Combobox(self.root, values=["Manual", "Automatic"], state="readonly")
        self.mode_selector.set(self.mode)
        self.mode_selector.grid(row=0, column=1, padx=5, pady=5)
        self.mode_selector.bind("<<ComboboxSelected>>", self.change_mode)

        self.sensor_label = ttk.Label(self.root, text=f"Sensor Value: {self.sensor_value}")
        self.sensor_label.grid(row=1, column=0, columnspan=2, padx=5, pady=5)

        self.pump_button = ttk.Button(self.root, text="Start Pump", command=self.toggle_pump)
        self.pump_button.grid(row=2, column=0, padx=5, pady=5)

        self.pump_status_label = ttk.Label(self.root, text="Pump Status: Off")
        self.pump_status_label.grid(row=2, column=1, padx=5, pady=5)

        self.period_label = ttk.Label(self.root, text="Update Period (s):")
        self.period_label.grid(row=3, column=0, padx=5, pady=5)

        self.period_spinbox = ttk.Spinbox(
            self.root,
            from_=1,
            to=60,
            validate="key",
            validatecommand=(self.validate_positive_input, "%P"),
        )
        self.period_spinbox.set(self.update_period)
        self.period_spinbox.grid(row=3, column=1, padx=5, pady=5)

        self.low_threshold_label = ttk.Label(self.root, text="Low Threshold:")
        self.low_threshold_label.grid(row=4, column=0, padx=5, pady=5)

        self.low_threshold_spinbox = ttk.Spinbox(
            self.root,
            from_=0,
            to=100,
            validate="key",
            state="disabled",
            validatecommand=(self.validate_positive_input, "%P"),
        )
        self.low_threshold_spinbox.set(self.critical_low)
        self.low_threshold_spinbox.grid(row=4, column=1, padx=5, pady=5)

        self.high_threshold_label = ttk.Label(self.root, text="High Threshold:")
        self.high_threshold_label.grid(row=5, column=0, padx=5, pady=5)

        self.high_threshold_spinbox = ttk.Spinbox(
            self.root,
            from_=0,
            to=100,
            validate="key",
            state="disabled",
            validatecommand=(self.validate_positive_input, "%P"),
        )
        self.high_threshold_spinbox.set(self.critical_high)
        self.high_threshold_spinbox.grid(row=5, column=1, padx=5, pady=5)

    def validate_positive(self, value):
        if value.isdigit():
            return True
        return False

    def change_mode(self, event):
        self.mode = self.mode_selector.get()
        self.mqtt_client.publish("iot/device/mode", self.mode)
        if self.mode == "Automatic":
            self.low_threshold_spinbox.config(state="normal")
            self.high_threshold_spinbox.config(state="normal")
        else:
            self.low_threshold_spinbox.config(state="disabled")
            self.high_threshold_spinbox.config(state="disabled")

    def toggle_pump(self):
        self.pump_status = not self.pump_status
        self.update_pump_ui()
        self.mqtt_client.publish("iot/device/pump", "on" if self.pump_status else "off")

    def update_pump_ui(self):
        if self.pump_status:
            self.pump_button.config(text="Stop Pump")
            self.pump_status_label.config(text="Pump Status: On")
        else:
            self.pump_button.config(text="Start Pump")
            self.pump_status_label.config(text="Pump Status: Off")

    def update_sensor_value(self):
        if self.pump_status:
            self.sensor_value = min(100, self.sensor_value + random.randint(5, 25))  # пока помпа работает почва увлажняется
        else:
            self.sensor_value = max(0, self.sensor_value - random.randint(5, 10))  # пока помпа не работает почва высыхает

        self.sensor_label.config(text=f"Sensor Value: {self.sensor_value}")

        if self.mode == "Automatic":
            self.critical_low = int(self.low_threshold_spinbox.get())
            self.critical_high = int(self.high_threshold_spinbox.get())

            if self.sensor_value < self.critical_low:
                self.pump_status = True
            elif self.sensor_value > self.critical_high:
                self.pump_status = False
            self.update_pump_ui()

        self.mqtt_client.publish("iot/device/sensor", self.sensor_value)

    def sensor_update_loop(self):
        while self.running:
            time.sleep(int(self.period_spinbox.get()))
            self.update_sensor_value()

    def on_connect(self, client, userdata, flags, rc):
        print("Connected to MQTT broker with result code " + str(rc))
        client.subscribe("iot/device/response")
        client.subscribe("iot/device/mode")

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode()

        if topic == "iot/device/response" and self.mode == "Manual":
            if payload == "on":
                self.pump_status = True
            elif payload == "off":
                self.pump_status = False
            self.update_pump_ui()

        if topic == "iot/device/mode":
            if payload == "Manual":
                self.mode = "Manual"
                self.mode_selector.set(self.mode)
                self.low_threshold_spinbox.config(state="disabled")
                self.high_threshold_spinbox.config(state="disabled")
            elif payload == "Automatic":
                self.mode = "Automatic"
                self.mode_selector.set(self.mode)
                self.low_threshold_spinbox.config(state="normal")
                self.high_threshold_spinbox.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    app = IoTDeviceSimulator(root)
    root.mainloop()
