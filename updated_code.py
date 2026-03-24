import time
import board
import ssl
import displayio
import terminalio
import wifi
import socketpool
import adafruit_requests
import touchio
import analogio
import pwmio
from adafruit_display_text import label
import audiomp3
from audioio import AudioOut
import digitalio 
import adafruit_ntp
import rtc 

backend_url = "http://172.20.10.11:8000" # note to user: replace the middle part (after // and before :8000) with your current computer IP address
device_id = "cat_01"
poll_frequency = 10
touch_cooldown_period = 0.6
wave_cooldown_period = 1.0

# communicate with the backend 
wifi.radio.connect("halithea", "artemismoon") # note to user: replace this with your Wi-Fi or phone hotspot credentials!
pool = socketpool.SocketPool(wifi.radio)
ssl_context = ssl.create_default_context()
requests = adafruit_requests.Session(pool, ssl_context)
ntp = adafruit_ntp.NTP(pool, tz_offset=-4)
rtc.RTC().datetime = ntp.datetime

# setup 
# enable = digitalio.DigitalInOut(board.D10)
# enable.direction = digitalio.Direction.OUTPUT
# enable.value = True
# time.sleep(0.1)
# audio = AudioOut(board.A0)

display = board.DISPLAY
window = displayio.Group()
display.root_group = window
touch_a4 = touchio.TouchIn(board.A4)   # green = complete
touch_a5 = touchio.TouchIn(board.A5)   # red = skip 
sensor = analogio.AnalogIn(board.A1)   
red = pwmio.PWMOut(board.D11, duty_cycle=0)
green = pwmio.PWMOut(board.D12, duty_cycle=0)
blue = pwmio.PWMOut(board.D13, duty_cycle=0)
audio_folder = "/audio_files"

# states
current_quest = None
last_poll = 0
fetch_time = 0
last_touch_time = 0
last_wave_time = 0
wave_hold_start = None
wave_triggered = False
last_countdown_refresh = 0
countdown_refresh_period = 60

# led light control 
def led_off():
    red.duty_cycle = 0
    green.duty_cycle = 0
    blue.duty_cycle = 0

def led_green():
    red.duty_cycle = 0
    green.duty_cycle = 65535
    blue.duty_cycle = 0

def led_red():
    red.duty_cycle = 65535
    green.duty_cycle = 0
    blue.duty_cycle = 0

def flash_green(duration=0.6):
    led_green()
    time.sleep(duration)
    led_off()

def flash_red(duration=0.6):
    led_red()
    time.sleep(duration)
    led_off()

led_off()

# touch detection using capacitive touch sensors 
def left_touched():
    if touch_a4.raw_value > 30000:
        return touch_a4.value
    return False

def right_touched():
    if touch_a5.raw_value > 30000:
        return touch_a5.value
    return False

# a countdown is displayed on the screen when there is an active quest 
def compute_countdown_minutes(quest):
    if not quest:
        return None
    end_str = quest.get("response_window_end")
    print("response_window_end:", end_str)
    print("local time:", time.localtime())
    if not end_str:
        return None
    try:
        time_part = end_str.split("T")[1]
        pieces = time_part.split(":")
        hour = int(pieces[0])
        minute = int(pieces[1])
        now_struct = time.localtime()
        now_seconds = (
            now_struct.tm_hour * 3600 +
            now_struct.tm_min * 60 +
            now_struct.tm_sec
        )
        end_seconds = hour * 3600 + minute * 60
        remaining_seconds = max(0, end_seconds - now_seconds)
        if remaining_seconds == 0:
            return 0
        return (remaining_seconds + 59) // 60
    except Exception as e:
        print("Countdown parse error:", e)
        print("response_window_end was:", end_str)
        print("local time was:", time.localtime())
        return None

# UI display
def clear_window():
    while len(window) > 0:
        window.pop()

def format_countdown(minutes_left):
    if minutes_left is None:
        return "-- min"
    return "{} min".format(minutes_left)

def show_no_quest():
    clear_window()
    title = label.Label(
        terminalio.FONT,
        text="No active quest",
        color=0xAAAAAA,
        scale=2,
        x=5,
        y=30,
    )
    window.append(title)

def show_error(line1="Request failed", line2="Check backend"):
    clear_window()
    l1 = label.Label(
        terminalio.FONT,
        text=line1,
        color=0xE96B6B,
        scale=1,
        x=5,
        y=15,
    )
    l2 = label.Label(
        terminalio.FONT,
        text=line2,
        color=0xFFFFFF,
        scale=1,
        x=5,
        y=35,
    )
    window.append(l1)
    window.append(l2)

def show_status_message(line1, line2="", color1=0xFFFFFF, color2=0xFFFFFF):
    clear_window()
    line_1 = label.Label(
        terminalio.FONT,
        text=line1,
        color=color1,
        scale=2,
        x=5,
        y=24,
    )
    window.append(line_1)
    if line2:
        line_2 = label.Label(
            terminalio.FONT,
            text=line2,
            color=color2,
            scale=2,
            x=5,
            y=55,
        )
        window.append(line_2)

def show_quest_ui(quest, minutes_left=None):
    clear_window()
    status = quest.get("status", "")
    title_text = quest.get("title", "Quest")
    start_time = quest.get("scheduled_time", "--:--")
    duration_val = quest.get("duration_minutes", 0)
    y = 10
    header = label.Label(
        terminalio.FONT,
        text="Upcoming Quest" if status == "pending" else "Quest Alert",
        color=0xE96B6B,
        scale=2,
        x=5,
        y=y,
    )
    window.append(header)
    y += 20
    task = label.Label(
        terminalio.FONT,
        text=title_text[:12],
        color=0xFFFFFF,
        scale=2,
        x=5,
        y=y,
    )
    window.append(task)
    y += 22
    start = label.Label(
        terminalio.FONT,
        text="Start: " + str(start_time),
        color=0xFFFFFF,
        scale=2,
        x=5,
        y=y,
    )
    window.append(start)
    y += 20
    duration_label = label.Label(
        terminalio.FONT,
        text="Duration: {} min".format(duration_val),
        color=0xFFFFFF,
        scale=2,
        x=5,
        y=y,
    )
    window.append(duration_label)
    y += 20
    countdown = label.Label(
        terminalio.FONT,
        text=format_countdown(minutes_left),
        color=0x8BE98B,
        scale=2,
        x=5,
        y=y,
    )
    window.append(countdown)

# fetch data from backend
def fetch_device_state():
    global current_quest, fetch_time
    url = backend_url + "/device-state?device_id=" + device_id
    print("GET", url)
    response = None
    try:
        response = requests.get(url)
        print("status:", response.status_code)
        if response.status_code != 200:
            show_error("HTTP error", str(response.status_code))
            return
        data = response.json()
        print("json:", data)
        current_quest = data.get("active_quest")
        fetch_time = time.monotonic()
        if current_quest is None:
            show_no_quest()
        else:
            minutes_left = compute_countdown_minutes(current_quest)
            show_quest_ui(current_quest, minutes_left)
    except Exception as e:
        print("Request Exception:", repr(e))
        show_error("Request failed, see serial")
    finally:
        try:
            if response is not None:
                response.close()
        except Exception as e:
            print("Close Error:", repr(e))

# send data to backend when wave or touch events are detected
def post_device_state(event_type, quest_id=None):
    payload = {
        "device_id": device_id,
        "event_type": event_type,
    }
    if quest_id is not None:
        payload["quest_id"] = quest_id
    print("POST /device-events", payload)
    response = None
    try:
        response = requests.post(
            backend_url + "/device-events",
            json=payload,
        )
        print("event status:", response.status_code)
        if response.status_code != 200:
            try:
                print("event error:", response.text)
            except Exception:
                pass
            show_error("Event failed", str(response.status_code))
            return False
        return True
    except Exception as e:
        print("Post Exception:", repr(e))
        show_error("Post failed", "See serial")
        return False
    finally:
        try:
            if response is not None:
                response.close()
        except Exception as e:
            print("Post close error:", repr(e))

# play meow sound and change LED light color to green; send data to backend 
def post_wave_event():
    ok = post_device_state("pet")
    if ok:
        show_status_message("Wave detected","Hi :)", 0x8BE98B, 0xFFFFFF)
        flash_green(0.4)
      #  filepath = audio_folder + "/cat1.mp3"
      #  with open(filepath, "rb") as f:
         #   mp3 = audiomp3.MP3Decoder(f)
          #  audio.play(mp3)
          #  while audio.playing:
          #      time.sleep(0.01)
        if current_quest is None:
            show_no_quest()
        else:
            minutes_left = compute_countdown_minutes(current_quest)
            show_quest_ui(current_quest, minutes_left)      

# change LED light color based on user response; send data to backend   
def post_quest_event(event_type):
    global current_quest
    if current_quest is None:
        print("No current quest; ignoring touch.")
        return
    quest_id = current_quest.get("id")
    if quest_id is None:
        print("Current quest missing id; ignoring touch.")
        return
    ok = post_device_state(event_type, quest_id=quest_id)
    if not ok:
        return
    if event_type == "quest_completed":
        show_status_message("Completed!", "+2 bond", 0x8BE98B, 0xFFFFFF)
        flash_green(0.6)
    elif event_type == "quest_skipped":
        show_status_message("Skipped", "-0.5 bond", 0xE96B6B, 0xFFFFFF)
        flash_red(0.6)
    time.sleep(0.8)
    fetch_device_state()

# wave detection and reaction using light sensor 
def check_wave_sensor(now):
    global wave_hold_start, wave_triggered, last_wave_time
    sensor_val = sensor.value
    if sensor_val > 52000:
        if wave_hold_start is None:
            wave_hold_start = now
        if (now - wave_hold_start) >= 0.01 and not wave_triggered:
            if (now - last_wave_time) >= wave_cooldown_period:
                wave_triggered = True
                last_wave_time = now
                post_wave_event()
    else:
        wave_hold_start = None
        wave_triggered = False

show_status_message("Connecting...", "", 0xFFFFFF, 0xFFFFFF)
fetch_device_state()

# main loop
while True:
    now = time.monotonic()
    # communicate with the backend to get quest updates 
    if now - last_poll >= poll_frequency:
        fetch_device_state()
        last_poll = now
    if current_quest is not None and now - last_countdown_refresh >= countdown_refresh_period:
        remaining_time = compute_countdown_minutes(current_quest)
        show_quest_ui(current_quest, remaining_time)
        last_countdown_refresh = now
    # wave detection
    check_wave_sensor(now)
    # touch input detection
    if now - last_touch_time >= touch_cooldown_period:
        if current_quest is not None and left_touched():
            print("A4 touched; quest_completed")
            last_touch_time = now
            post_quest_event("quest_completed")
        elif current_quest is not None and right_touched():
            print("A5 touched; quest_skipped")
            last_touch_time = now
            post_quest_event("quest_skipped")
    time.sleep(0.1)